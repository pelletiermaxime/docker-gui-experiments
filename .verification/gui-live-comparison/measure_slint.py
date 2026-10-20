from pathlib import Path
import fcntl,hashlib,json,os,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
reference=json.loads((OUT/'daemon.json').read_text())
env=dict(os.environ,DOCKER_HOST=reference['docker_host'])
lock=open(f'/tmp/ferrydock-native-verification-{os.getuid()}.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
ids=sorted(subprocess.check_output(['docker','--host',reference['docker_host'],'ps','-aq','--no-trunc'],text=True).split())
digest=hashlib.sha256('\n'.join(ids).encode()).hexdigest()
(OUT/'slint-reference.json').write_text(json.dumps({'ids':ids,'container_count':len(ids),'ids_sha256':digest,'matches_original_reference':digest==reference['ids_sha256']},indent=2)+'\n')
for run in (1,2,3):
 with (OUT/f'slint-{run}-measurement-launch.log').open('w') as log:
  subprocess.run(['python',str(ROOT/'experiments/live-docker/measure.py'),'slint',str(ROOT/'experiments/live-docker/slint-containers/build/slint-live-containers'),'--output',str(OUT),'--run',str(run)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 path=OUT/f'slint-{run}.json';data=json.loads(path.read_text())
 match=re.search(r'Docker load: count=(\d+) elapsed_ms=(\d+) ids=([^\n]+)',data['load_log'])
 if not match:raise RuntimeError('Missing successful Docker load proof')
 app_ids=sorted(match[3].split(','));app_digest=hashlib.sha256('\n'.join(app_ids).encode()).hexdigest()
 data.update(container_count=int(match[1]),initial_load_ms=int(match[2]),container_ids_sha256=app_digest,matches_initial_inventory=app_digest==reference['ids_sha256'],matches_current_reference=app_digest==digest)
 path.write_text(json.dumps(data,indent=2)+'\n')
 print(json.dumps({'run':run,'rss_mib':data['idle_rss_median_bytes']/1048576,'cpu_percent':data['idle_cpu_percent_one_core'],'containers':data['container_count'],'same_ids':data['matches_initial_inventory'],'graphics_libraries':data['graphics_libraries']}),flush=True)
fcntl.flock(lock,fcntl.LOCK_UN)
