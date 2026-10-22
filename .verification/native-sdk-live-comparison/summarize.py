"""Assemble recorded build, native observations and the single short run."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;APP=ROOT/'experiments/live-docker/native-sdk'
run=json.loads((OUT/'native-1.json').read_text());reference=json.loads((OUT/'reference.json').read_text())
line=run['load_log'].strip().splitlines()[0];ids=sorted(line.split(' ids=',1)[1].split(','))
source=[APP/'src/core.ts',APP/'src/app.native',APP/'docker.mjs']
text=[line for p in source for line in p.read_text().splitlines()]
modules=APP/'node_modules'
deps=sum(p.stat().st_size for p in modules.rglob('*') if p.is_file() and p.relative_to(modules).parts[0]!='@native-sdk')
node=Path(shutil.which('node')).resolve()
extra=(APP/'docker.mjs').stat().st_size+sum(p.stat().st_size for p in (APP/'assets').rglob('*') if p.is_file())
observation={'summary':'SDK native snapshot: 1000 × 680, scale 1, software pixel presentation, no dispatch errors. Search pgsql showed 2 rows; clearing restored 14. Refresh logged a new Docker request. Captured with SDK runtime canvas screenshot in a separate automation-enabled build; resource binary had automation disabled.',
'window_size':[1000,680],'backend':'software','present_path':'pixels','search_query':'pgsql','search_rows':2,'clear_rows':14,'request_records':len((OUT/'observation-load.log').read_text().splitlines()),'capture':'Native SDK deterministic runtime canvas, not OS window capture','observation_binary_sha256':hashlib.sha256((APP/'zig-out/bin/native-live-containers').read_bytes()).hexdigest(),'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source}}
data={'framework':'Native SDK 0.11.0','sdk_revision':'16f29572307c2cc133907537c4dfd98046d4e0f4','docker_sdk':'Dockerode 5.0.1','node_version':subprocess.check_output([str(node),'--version'],text=True).strip(),
'lines':{'code':sum(bool(l.strip()) and not l.lstrip().startswith('//') for l in text),'physical':len(text),'scope':'Authored TypeScript core + native markup + Node Docker helper; excludes manifest, build tooling, lockfiles, generated code, dependencies and SDK text reducer'},
'native_elf_bytes':run['binary_bytes'],'production_dependencies_bytes':deps,'node_executable_bytes':node.stat().st_size,'helper_assets_bytes':extra,'deployment_bytes':run['binary_bytes']+deps+node.stat().st_size+extra,
'deployment_scope':'Uncompressed native ELF + production npm tree (SDK editor copy excluded) + Node executable + Docker helper + app assets. Shared system libraries excluded; no installer produced.',
'run':run,'reference':reference,'same_ids_as_reference':ids==reference['ids'],'initial_load_ms':float(re.search(r'elapsed_ms=([0-9.]+)',line).group(1)),
'build_observation':json.loads((OUT/'build.json').read_text()),'native_observation':observation,
'limitations':['One 2s warmup/5s idle sample; not contemporaneous with older runs.','Transient Node worker had exited; idle figures do not capture its request-time memory or peak.','Node startup and UI delivery are outside the SDK request interval.','Native SDK uses software canvas/Cairo; GTK4 default presentation retained, graphics libraries mapped.','512 KiB display-pipe limit, 512 UTF-16-code-unit display fields, 20,000 retained rows; Engine response buffers first.','Only Linux X11/XWayland executed; Windows/macOS remain unverified.','No automated tests. One provisional sample overlapped a compiler and is retained but excluded.']}
(OUT/'summary.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({k:data[k] for k in ('lines','native_elf_bytes','production_dependencies_bytes','node_executable_bytes','helper_assets_bytes','deployment_bytes','same_ids_as_reference','initial_load_ms')},indent=2))
