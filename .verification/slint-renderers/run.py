from pathlib import Path
import csv,fcntl,hashlib,json,os,re,signal,subprocess,time,sys
def interrupted(signum, frame): raise KeyboardInterrupt
signal.signal(signal.SIGTERM, interrupted)
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
builds=json.loads((OUT/'builds.json').read_text());matrix=json.loads((OUT/'matrix.json').read_text())
reference=json.loads((ROOT/'.verification/gui-live-comparison/daemon.json').read_text())
environment=dict(os.environ,DOCKER_HOST=reference['docker_host'],SLINT_SCALE_FACTOR='1',WINIT_UNIX_BACKEND='x11',QT_QPA_PLATFORM='xcb',QT_SCALE_FACTOR='1',QT_AUTO_SCREEN_SCALE_FACTOR='0',QT_ENABLE_HIGHDPI_SCALING='0',WGPU_BACKEND='vulkan',WGPU_ADAPTER_NAME='Intel')
for key in ['WAYLAND_DISPLAY','CONTAINER_SNAPSHOT','SLINT_BACKEND']:environment.pop(key,None)
lock=open(f'/tmp/ferrydock-native-verification-{os.getuid()}.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
ids=sorted(subprocess.check_output(['docker','--host',reference['docker_host'],'ps','-aq','--no-trunc'],env=environment,text=True).split())
reference.update(ids=ids,container_count=len(ids),ids_sha256=hashlib.sha256('\n'.join(ids).encode()).hexdigest())
(OUT/'reference.json').write_text(json.dumps(reference,indent=2)+'\n')
subset=set(sys.argv[1:])
observed=json.loads((OUT/'observations.json').read_text()) if subset else {}
results=json.loads((OUT/'results.json').read_text()) if subset else {}
if subset:matrix=[entry for entry in matrix if entry['id'] in subset]
def save():
 (OUT/'observations.json').write_text(json.dumps(observed,indent=2)+'\n')
 (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
def stop(p):
 try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=5)
 except ProcessLookupError:pass
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
def command(env,*args,check=True):return subprocess.run(args,env=env,capture_output=True,text=True,check=check,timeout=10)
for entry in matrix:
 name=entry['id'];build=builds[entry['family']]
 results[name]={'config':entry,'build':build,'runs':[],'status':'pending'}
 if build['exit_code']:
  results[name].update(status='build_failed',error=build.get('error_tail','build failed'));save();continue
 binary=ROOT/build['binary'];env=dict(environment,FERRYDOCK_SLINT_BACKEND=entry['backend'],FERRYDOCK_SLINT_RENDERER=entry['renderer'])
 record={'config':entry}
 with (OUT/f'{name}-native.log').open('w') as log:
  p=subprocess.Popen(['strace','-f','-e','trace=execve,connect','-o',str(OUT/f'{name}-transport.trace'),str(binary)],env=env,stdout=log,stderr=log,start_new_session=True)
  try:
   deadline=time.monotonic()+30;window=None;app_pid=None
   while time.monotonic()<deadline:
    if p.poll() is not None:raise RuntimeError(f'Exited {p.returncode}: '+(OUT/f'{name}-native.log').read_text()[-1800:])
    children=Path(f'/proc/{p.pid}/task/{p.pid}/children').read_text().split()
    app_pid=next((int(pid) for pid in children if Path(f'/proc/{pid}/exe').resolve()==binary.resolve()),None)
    if app_pid:
     query=command(env,'xdotool','search','--all','--onlyvisible','--pid',str(app_pid),check=False)
     if query.returncode==0:window=query.stdout.splitlines()[0];break
    time.sleep(.2)
   if window is None:raise RuntimeError('No owned visible window within 30 seconds')
   command(env,'xdotool','windowactivate','--sync',window);command(env,'xdotool','windowsize','--sync',window,'1000','680')
   time.sleep(4)
   if p.poll() is not None:raise RuntimeError('Exited before native capture')
   capture=OUT/f'{name}-native.png';command(env,'magick','import','-window',window,str(capture))
   ocr=command(env,'tesseract',str(capture),'stdout','--psm','6').stdout
   (OUT/f'{name}-native.txt').write_text(ocr)
   record.update(pid=app_pid,window=window,capture=capture.name,ocr=ocr,log=(OUT/f'{name}-native.log').read_text())
   if not re.search(r'Docker load: count=\d+',record['log']):raise RuntimeError('No successful live load log')
   if 'unrecognized renderer' in record['log'].lower() or 'falling back' in record['log'].lower():raise RuntimeError('Renderer fallback detected; request not verified')
   results[name]['status']='observed'
  except Exception as e:record['error']=str(e);results[name].update(status='runtime_failed',error=str(e))
  finally:stop(p);record['owned_process_exited']=p.poll() is not None
 trace=(OUT/f'{name}-transport.trace').read_text().splitlines()
 record.update(executables=[l for l in trace if 'execve(' in l],docker_socket_connections=[l for l in trace if 'connect(' in l and '/var/run/docker.sock' in l])
 observed[name]=record;save();print(json.dumps({'phase':'native','renderer':name,'status':results[name]['status'],'error':record.get('error')}),flush=True)
for run in (1,2,3):
 for entry in matrix:
  name=entry['id'];result=results[name]
  if result['status'] not in ['observed','measured']:continue
  env=dict(environment,FERRYDOCK_SLINT_BACKEND=entry['backend'],FERRYDOCK_SLINT_RENDERER=entry['renderer'])
  try:
   with (OUT/f'{name}-{run}-launch.log').open('w') as log:
    child=subprocess.Popen(['python',str(OUT/'measure_base.py'),name,str(ROOT/result['build']['binary']),'--output',str(OUT),'--run',str(run)],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
     code=child.wait()
     if code:raise RuntimeError(f'Measurement helper exited {code}')
    except BaseException:
     if child.poll() is None:child.send_signal(signal.SIGINT);child.wait(timeout=15)
     raise
   path=OUT/f'{name}-{run}.json';data=json.loads(path.read_text())
   proof=re.search(r'Docker load: count=(\d+) elapsed_ms=(\d+) ids=([^\n]+)',data['load_log'])
   if not proof:raise RuntimeError('No successful live Docker load proof')
   digest=hashlib.sha256('\n'.join(sorted(proof[3].split(','))).encode()).hexdigest()
   data.update(container_count=int(proof[1]),initial_load_ms=int(proof[2]),container_ids_sha256=digest,matches_reference=digest==reference['ids_sha256'])
   path.write_text(json.dumps(data,indent=2)+'\n');result['runs'].append(data);result['status']='measured';save()
   print(json.dumps({'phase':'measure','renderer':name,'run':run,'rss_mib':data['idle_rss_median_bytes']/1048576,'cpu_percent':data['idle_cpu_percent_one_core'],'same_ids':data['matches_reference']}),flush=True)
  except Exception as e:
   result.update(status='measurement_failed',error=str(e));save();print(json.dumps({'phase':'measure','renderer':name,'error':str(e)}),flush=True)
fcntl.flock(lock,fcntl.LOCK_UN)
