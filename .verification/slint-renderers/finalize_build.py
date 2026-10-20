from pathlib import Path
import json,os,subprocess,time,shutil,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
project=ROOT/'experiments/live-docker/slint-renderers'
env=dict(os.environ,CARGO_TARGET_DIR=str(ROOT/'experiments/gpui-containers/target'),CARGO_BUILD_JOBS='4',RUSTFLAGS='-C force-unwind-tables=no',SLINT_STYLE='fluent')
cmd=['cargo','build','--release','--locked','--no-default-features','--features','software','--manifest-path',str(project/'Cargo.toml')];started=time.monotonic()
with (OUT/'build-software-final.log').open('w') as log:p=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
results=json.loads((OUT/'builds.json').read_text());old=results['software'];result={'family':'software','command':cmd,'elapsed_s':time.monotonic()-started,'exit_code':p.returncode,'cache':'Warm dependency build after neutralizing the UI renderer label. Sequential shared cache; not a clean build.','initial_build':old}
if p.returncode==0:
 binary=project/'build/slint-software';shutil.copy2(Path(env['CARGO_TARGET_DIR'])/'release/slint-renderer-containers',binary)
 result.update(binary=str(binary.relative_to(ROOT)),binary_bytes=binary.stat().st_size,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
else:result['error_tail']=(OUT/'build-software-final.log').read_text()[-3000:]
results['software']=result
(OUT/'builds.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(result))
