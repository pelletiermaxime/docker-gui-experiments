"""Sample an already-open owned Native SDK app; no input injection or tests."""
from pathlib import Path
import importlib.util,json,os,statistics,sys,time
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('existing_measurement',ROOT/'experiments/live-docker/measure.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
pid=int(sys.argv[1]);samples=[]
for _ in range(8):
 samples.append({'phase':'warmup',**helper.process_sample(pid)});time.sleep(.25)
before=helper.process_sample(pid);start=time.monotonic()
while time.monotonic()-start<5:
 samples.append({'phase':'idle',**helper.process_sample(pid)});time.sleep(.5)
after=helper.process_sample(pid);elapsed=time.monotonic()-start
idle=[s for s in samples if s['phase']=='idle']
result={'name':'native','run':1,'warmup_seconds':2,'idle_seconds':elapsed,
'idle_cpu_percent_one_core':100*(after['cpu_seconds']-before['cpu_seconds'])/elapsed,
'idle_rss_median_bytes':statistics.median(s['rss_bytes'] for s in idle),
'idle_pss_median_bytes':statistics.median(s['pss_bytes'] for s in idle),
'sampled_peak_rss_bytes':max(s['rss_bytes'] for s in samples),'max_processes':max(s['processes'] for s in samples),
'backend':'Native SDK 0.11.0; GTK4 X11 / software renderer; GTK4 default presentation; GDK_SCALE=1',
'client_size':[1000,680],'sampling_note':'One loaded release window, 2s warmup then 5s idle. Input observations run separately. Native Moby worker had exited; the SDK service host is included. No startup peak measured.',
'shared_libraries':sorted({l.split()[-1] for l in Path(f'/proc/{pid}/maps').read_text().splitlines() if '.so' in l and l.split()[-1].startswith('/')}),
'samples':samples}
(OUT/'native-1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('samples','shared_libraries')}))
