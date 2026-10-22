"""Owned native UI observation with exec/connect trace, outside resource sampling."""
from pathlib import Path
import json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;APP=ROOT/'experiments/live-docker/native-sdk'
env=dict(os.environ,GDK_BACKEND='x11',GDK_SCALE='1',GDK_DPI_SCALE='1')
for key in ('WAYLAND_DISPLAY','CONTAINER_SNAPSHOT','GSK_RENDERER'):env.pop(key,None)
configuration={'worker':str(APP/'zig-out/bin/native-docker-client'),'host':'unix:///var/run/docker.sock','proof':str(OUT/'native-service-observation-load.log'),'certPath':'','tlsVerify':''}
configuration_path=OUT/'native-service-observation-load.log';configuration_path.write_text('')
env['NATIVE_DOCKER_CONFIGURATION']=json.dumps(configuration)
env['PATH']=str(OUT/'toolchains/runtime-empty')
command=[shutil.which('strace'),'-f','-e','trace=execve,connect','-o',str(OUT/'native-service-transport.trace'),str(APP/'zig-out/bin/native-live-containers')]
with (OUT/'native-service-observation.log').open('w') as log:
 process=subprocess.Popen(command,cwd=APP,env=env,stdout=log,stderr=log,start_new_session=True)
 (OUT/'observation.pid').write_text(str(process.pid));print('Owned traced observation process:',process.pid,flush=True)
 raise SystemExit(process.wait())
