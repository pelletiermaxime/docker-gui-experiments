from pathlib import Path
import os,subprocess,time,signal,json
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
APPS={'nanoui':ROOT/'experiments/live-docker/nanoui-containers/zig-out/bin/nanoui-live-containers','mygo':ROOT/'experiments/live-docker/mygo-containers/build/mygo-containers','gpui':ROOT/'experiments/gpui-containers/target/release/gpui-live-containers'}
daemon=json.loads((OUT/'daemon.json').read_text())
for name,binary in APPS.items():
 env=dict(os.environ,GDK_BACKEND='x11',DOCKER_HOST=daemon['docker_host'])
 env.pop('WAYLAND_DISPLAY',None);env.pop('CONTAINER_SNAPSHOT',None)
 if name=='gpui':env['GPUI_X11_SCALE_FACTOR']='1'
 with (OUT/f'{name}-live.log').open('w') as log:
  p=subprocess.Popen(['strace','-f','-e','trace=execve,connect','-o',str(OUT/f'{name}-transport.trace'),str(binary)],env=env,stdout=log,stderr=log,start_new_session=True)
  try:
   time.sleep(5)
   if p.poll() is not None:raise RuntimeError(f'{name} exited; see log')
   children=Path(f'/proc/{p.pid}/task/{p.pid}/children').read_text().split()
   app_pid=next(int(pid) for pid in children if Path(f'/proc/{pid}/exe').resolve()==binary.resolve())
   win=subprocess.check_output(['xdotool','search','--all','--onlyvisible','--pid',str(app_pid)],env=env,text=True).splitlines()[0]
   subprocess.run(['magick','import','-window',win,str(OUT/f'{name}-live.png')],env=env,check=True,timeout=10)
   print(json.dumps({'app':name,'pid':app_pid,'capture':f'{name}-live.png'}),flush=True)
  finally:
   try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=5)
   except ProcessLookupError:pass
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
