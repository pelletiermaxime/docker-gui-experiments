"""Observe one owned Avalonia window with a short protocol with the existing read-only idle protocol."""
from pathlib import Path
import fcntl
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
binary = ROOT / 'experiments/live-docker/avalonia-containers/build/self-contained/AvaloniaContainers'
environment = dict(os.environ, DOCKER_HOST='unix:///var/run/docker.sock', AVALONIA_GLOBAL_SCALE_FACTOR='1')
monitors = subprocess.check_output(['xrandr', '--listactivemonitors'], env=environment, text=True, stderr=subprocess.DEVNULL).splitlines()[1:]
environment['AVALONIA_SCREEN_SCALE_FACTORS'] = ';'.join(line.split()[-1] + '=1' for line in monitors if line.split())
lock = open(f'/tmp/ferrydock-native-verification-{os.getuid()}.lock', 'a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
ids = sorted(subprocess.check_output(['docker', '--host', environment['DOCKER_HOST'],
                                     'ps', '-aq', '--no-trunc'], env=environment, text=True).split())
reference = {'docker_host': environment['DOCKER_HOST'], 'ids': ids, 'container_count': len(ids),
             'ids_sha256': hashlib.sha256('\n'.join(ids).encode()).hexdigest()}
(OUT / 'reference.json').write_text(json.dumps(reference, indent=2) + '\n')
for run in map(int, sys.argv[1:] or ['1']):
    with (OUT / f'avalonia-{run}-launch.log').open('w') as stream:
        process = subprocess.run([sys.executable, str(OUT / 'measure.py'), 'avalonia', str(binary),
                                  '--output', str(OUT), '--run', str(run), '--warmup', '2', '--seconds', '5'],
                                 cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT)
    if process.returncode:
        print((OUT / f'avalonia-{run}-launch.log').read_text()[-1800:])
        log = OUT / f'avalonia-{run}.log'
        if log.exists(): print(log.read_text()[-3500:])
        raise SystemExit(process.returncode)
    result = json.loads((OUT / f'avalonia-{run}.json').read_text())
    lines = [line for line in result['load_log'].splitlines() if line.startswith('Docker load:')]
    loaded = sorted(lines[-1].split(' ids=', 1)[1].split(',')) if lines else []
    result['same_ids_as_reference'] = loaded == ids
    (OUT / f'avalonia-{run}.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'run': run, 'same_ids': loaded == ids,
                      'rss_mib': result['idle_rss_median_bytes'] / 1048576,
                      'pss_mib': result['idle_pss_median_bytes'] / 1048576,
                      'idle_cpu_percent': result['idle_cpu_percent_one_core']}), flush=True)
