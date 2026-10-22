"""One short native resource observation, with all compilers finished."""
from pathlib import Path
import hashlib,json,os,signal,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
APP=ROOT/'experiments/live-docker/native-sdk';binary=APP/'build/measured-native-live-containers'
proof=OUT/'docker-load.log';proof.write_text('')
env=dict(os.environ,DOCKER_HOST='unix:///var/run/docker.sock',GDK_BACKEND='x11',GDK_SCALE='1',GDK_DPI_SCALE='1',NATIVE_DOCKER_PROOF=str(proof))
for key in ('WAYLAND_DISPLAY','CONTAINER_SNAPSHOT','GSK_RENDERER'):env.pop(key,None)
ids=sorted(subprocess.check_output(['docker','--host',env['DOCKER_HOST'],'ps','-aq','--no-trunc'],env=env,text=True).split())
reference={'docker_host':env['DOCKER_HOST'],'container_count':len(ids),'ids':ids,'ids_sha256':hashlib.sha256('\n'.join(ids).encode()).hexdigest()}
(OUT/'reference.json').write_text(json.dumps(reference,indent=2)+'\n')
with (OUT/'native-1.log').open('w') as log:
 proc=subprocess.Popen([str(binary)],cwd=APP,env=env,stdout=log,stderr=log,start_new_session=True)
 try:
  deadline=time.monotonic()+15
  while not proof.stat().st_size:
   if proc.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Native app did not load Docker')
   time.sleep(.05)
  subprocess.run([sys.executable,str(OUT/'sample.py'),str(proc.pid)],check=True)
  result=json.loads((OUT/'native-1.json').read_text());result.update(binary_bytes=binary.stat().st_size,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),load_log=proof.read_text(),sampling_note='One release window after successful startup load, 2s warmup then 5s idle. Automation disabled. Node worker exited; no startup peak measured. All compiler processes finished before launch.')
  (OUT/'native-1.json').write_text(json.dumps(result,indent=2)+'\n')
 finally:
  if proc.poll() is None:os.killpg(proc.pid,signal.SIGTERM)
  proc.wait(timeout=5)
