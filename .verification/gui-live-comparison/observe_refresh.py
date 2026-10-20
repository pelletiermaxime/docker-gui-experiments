"""Read-only native Refresh observation, outside resource measurements."""
from pathlib import Path
import csv,io,json,os,re,signal,subprocess,time
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
daemon=json.loads((OUT/'daemon.json').read_text());results={}
apps={'nanoui':ROOT/'experiments/live-docker/nanoui-containers/zig-out/bin/nanoui-live-containers','mygo':ROOT/'experiments/live-docker/mygo-containers/build/mygo-containers','gpui':ROOT/'experiments/gpui-containers/target/release/gpui-live-containers'}
results['nanoui']={'refresh_observed':False,'reason':'Owned-window OCR/click attempts did not produce a second load; startup loaded all 14 IDs. Click delivery versus widget behavior is unresolved.'}
for name,binary in apps.items():
 if name=='nanoui':continue
 env=dict(os.environ,GDK_BACKEND='x11',DOCKER_HOST=daemon['docker_host']);env.pop('WAYLAND_DISPLAY',None);env.pop('CONTAINER_SNAPSHOT',None)
 if name=='gpui':env['GPUI_X11_SCALE_FACTOR']='1'
 logpath=OUT/f'{name}-refresh.log'
 with logpath.open('w') as log:
  p=subprocess.Popen([str(binary)],env=env,stdout=log,stderr=log,start_new_session=True)
  try:
   time.sleep(3)
   if p.poll() is not None:raise RuntimeError(f'{name} exited')
   win=subprocess.check_output(['xdotool','search','--all','--onlyvisible','--pid',str(p.pid)],env=env,text=True).splitlines()[0]
   subprocess.run(['xdotool','windowactivate','--sync',win],env=env,check=True,timeout=3)
   before=OUT/f'{name}-refresh-before.png'
   subprocess.run(['magick','import','-window',win,str(before)],env=env,check=True,timeout=10)
   tsv=subprocess.check_output(['tesseract',str(before),'stdout','--psm','11','tsv'],env=env,text=True,stderr=subprocess.DEVNULL)
   rows=[r for r in csv.DictReader(io.StringIO(tsv),delimiter='\t') if r.get('text','').strip()=='Refresh']
   if len(rows)!=1:
    processed=OUT/f'{name}-refresh-ocr.png'
    subprocess.run(['magick',str(before),'-colorspace','Gray','-negate','-threshold','30%',str(processed)],env=env,check=True)
    tsv=subprocess.check_output(['tesseract',str(processed),'stdout','--psm','11','tsv'],env=env,text=True,stderr=subprocess.DEVNULL)
    rows=[r for r in csv.DictReader(io.StringIO(tsv),delimiter='\t') if r.get('text','').strip()=='Refresh']
   if len(rows)!=1:raise RuntimeError(f'Cannot locate owned Refresh button for {name}')
   hit=rows[0];x=int(hit['left'])+int(hit['width'])//2;y=int(hit['top'])+int(hit['height'])//2
   active=subprocess.check_output(['xdotool','getactivewindow'],env=env,text=True).strip()
   if active!=win:raise RuntimeError('Owned window lost focus')
   subprocess.run(['xdotool','mousemove','--window',win,str(x),str(y)],env=env,check=True,timeout=3)
   time.sleep(0.5)
   subprocess.run(['xdotool','click','1'],env=env,check=True,timeout=3)
   time.sleep(2)
   data=logpath.read_text();loads=len(re.findall('ids_sha256=|Docker load: count=',data))
   if loads<2:
    subprocess.run(['magick','import','-window',win,str(OUT/f'{name}-refresh-unconfirmed.png')],env=env,check=True,timeout=10)
    raise RuntimeError(f'Refresh did not produce second SDK load: {name}')
   subprocess.run(['magick','import','-window',win,str(OUT/f'{name}-refresh-after.png')],env=env,check=True,timeout=10)
   results[name]={'refresh_observed':True,'successful_sdk_loads':loads,'refresh_clicked_via':'OCR Refresh label on owned active window','pid':p.pid}
   print(json.dumps({name:results[name]}),flush=True)
  except Exception as error:
   results[name]={'refresh_observed':False,'reason':str(error)}
   print(json.dumps({name:results[name]}),flush=True)
  finally:
   try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=5)
   except ProcessLookupError:pass
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
(OUT/'refresh-observation.json').write_text(json.dumps(results,indent=2)+'\n')
