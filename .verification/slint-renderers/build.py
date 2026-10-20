from pathlib import Path
import json,os,subprocess,time,shutil,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
project=ROOT/'experiments/live-docker/slint-renderers';dest=project/'build';dest.mkdir(exist_ok=True)
env=dict(os.environ,CARGO_TARGET_DIR=str(ROOT/'experiments/gpui-containers/target'),CARGO_BUILD_JOBS='4',RUSTFLAGS='-C force-unwind-tables=no',SLINT_STYLE='fluent')
results={}
for family in ['software','femtovg','femtovg-wgpu','skia','skia-opengl','vello','qt']:
 started=time.monotonic();command=['cargo','build','--release','--no-default-features','--features',family,'--manifest-path',str(project/'Cargo.toml')]
 with (OUT/f'build-{family}.log').open('w') as log:
  process=subprocess.Popen(command,env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
  (OUT/'building.json').write_text(json.dumps({'family':family,'pid':process.pid,'started_monotonic':started})+'\n')
  code=process.wait()
 result={'family':family,'command':command,'elapsed_s':time.monotonic()-started,'exit_code':code,'cache':'Sequential release builds with shared warm target; newly required renderer dependencies may download/compile. Not comparable clean build timings.'}
 if code==0:
  binary=dest/f'slint-{family}';shutil.copy2(Path(env['CARGO_TARGET_DIR'])/'release/slint-renderer-containers',binary)
  result.update(binary=str(binary.relative_to(ROOT)),binary_bytes=binary.stat().st_size,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
 else:result['error_tail']=(OUT/f'build-{family}.log').read_text()[-3500:]
 results[family]=result;(OUT/'builds.json').write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in result if k not in ['command','cache']}),flush=True)
(OUT/'building.json').unlink(missing_ok=True)
