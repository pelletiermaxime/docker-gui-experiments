"""Build the MAUI GTK4 experiment using the isolated local SDK; no tests."""
from pathlib import Path
import json
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TOOLS = OUT / 'toolchains'
environment = dict(os.environ, DOTNET_ROOT=str(TOOLS / 'dotnet'),
                   DOTNET_CLI_HOME=str(TOOLS / 'cli-home'),
                   NUGET_PACKAGES=str(TOOLS / 'nuget-packages'),
                   DOTNET_CLI_TELEMETRY_OPTOUT='1', DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',
                   DOTNET_GENERATE_ASPNET_CERTIFICATE='false')
project = ROOT / 'experiments/live-docker/maui-containers/MauiContainers.csproj'
results = json.loads((OUT / 'builds.json').read_text()) if (OUT / 'builds.json').exists() else []
for name, contained in [('framework-dependent', 'false'), ('self-contained', 'true')]:
    destination = project.parent / 'build' / name
    command = [str(TOOLS / 'dotnet/dotnet'), 'publish', str(project), '-c', 'Release',
               '-r', 'linux-x64', '--self-contained', contained, '-o', str(destination),
               '-p:DebugType=None', '-p:DebugSymbols=false', '--verbosity', 'minimal']
    started = time.monotonic()
    log = OUT / f'build-{name}-{len(results) + 1}.log'
    with log.open('w') as stream:
        process = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream,
                                 stderr=subprocess.STDOUT)
    result = {'kind': name, 'command': command, 'elapsed_seconds': time.monotonic() - started,
              'exit_code': process.returncode, 'log': log.name,
              'scope': 'Publish after initial package restore; includes incremental compilation and any newly needed package downloads; not a clean-build timing.'}
    if process.returncode == 0:
        files = [p for p in destination.rglob('*') if p.is_file()]
        result.update(directory_bytes=sum(p.stat().st_size for p in files),
                      file_count=len(files), apphost_bytes=(destination / 'MauiContainers').stat().st_size)
    results.append(result)
    (OUT / 'builds.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    if process.returncode:
        print(log.read_text()[-4500:], flush=True)
        raise SystemExit(process.returncode)
