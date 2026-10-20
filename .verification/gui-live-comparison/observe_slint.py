"""Owned native observations, separate from resource measurement; read-only Docker."""
from pathlib import Path
import csv,fcntl,io,json,os,signal,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
binary=ROOT/'experiments/live-docker/slint-containers/build/slint-live-containers'
daemon=json.loads((OUT/'daemon.json').read_text())
env=dict(os.environ,DOCKER_HOST=daemon['docker_host'],WINIT_UNIX_BACKEND='x11',SLINT_SCALE_FACTOR='1',SLINT_BACKEND='winit-software')
env.pop('WAYLAND_DISPLAY',None);env.pop('CONTAINER_SNAPSHOT',None)
lock=open(f'/tmp/ferrydock-native-verification-{os.getuid()}.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
record={}
def command(*args):return subprocess.check_output(list(args),env=env,text=True,stderr=subprocess.STDOUT,timeout=10).strip()
with (OUT/'slint-live.log').open('w') as log:
 p=subprocess.Popen(['strace','-f','-e','trace=execve,connect','-o',str(OUT/'slint-transport.trace'),str(binary)],env=env,stdout=log,stderr=log,start_new_session=True)
 try:
  time.sleep(4)
  children=Path(f'/proc/{p.pid}/task/{p.pid}/children').read_text().split()
  app_pid=next(int(pid) for pid in children if Path(f'/proc/{pid}/exe').resolve()==binary.resolve())
  window=command('xdotool','search','--all','--onlyvisible','--pid',str(app_pid)).splitlines()[0]
  command('xdotool','windowactivate','--sync',window)
  command('xdotool','windowsize','--sync',window,'1000','680')
  def capture(name):
   time.sleep(.5)
   dest=OUT/f'slint-{name}.png'
   command('magick','import','-window',window,str(dest))
   text=command('tesseract',str(dest),'stdout','--psm','6')
   (OUT/f'slint-{name}.txt').write_text(text+'\n')
   return text
  def owned_click(x,y):
   if Path(f'/proc/{app_pid}/exe').resolve()!=binary.resolve():raise RuntimeError('Executable ownership changed')
   if command('xdotool','getwindowpid',window)!=str(app_pid):raise RuntimeError('Window ownership changed')
   command('xdotool','windowactivate','--sync',window)
   if command('xdotool','getactivewindow')!=window:raise RuntimeError('Owned window is not active')
   command('xdotool','mousemove','--window',window,str(x),str(y));command('xdotool','click','1')
  startup=capture('live')
  tsv=command('tesseract',str(OUT/'slint-live.png'),'stdout','--psm','6','tsv')
  words=list(csv.DictReader(io.StringIO(tsv),delimiter='\t'))
  def location(word):
   row=next(r for r in words if r['text'].strip().lower()==word.lower())
   return int(row['left'])+int(row['width'])//2,int(row['top'])+int(row['height'])//2
  record={'app':'slint','pid':app_pid,'window':window,'startup_ocr':startup}
  try:
   owned_click(*location('Search'))
   command('xdotool','type','--clearmodifiers','--delay','15','__slint_no_match__')
   record['search_ocr']=capture('search')
   command('xdotool','key','--clearmodifiers','ctrl+a','BackSpace')
   record['cleared_ocr']=capture('cleared')
   owned_click(*location('Refresh'))
   time.sleep(1)
   record['refresh_ocr']=capture('refreshed')
  except Exception as error:record['input_observation_error']=str(error)
  record['successful_load_count']=(OUT/'slint-live.log').read_text().count('Docker load: count=')
  record['refresh_confirmed']=record['successful_load_count']>=2
 finally:
  try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=5)
  except ProcessLookupError:pass
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  record['owned_process_exited']=p.poll() is not None
  (OUT/'slint-native-observation.json').write_text(json.dumps(record,indent=2)+'\n')
  fcntl.flock(lock,fcntl.LOCK_UN)
print(json.dumps(record,indent=2))
