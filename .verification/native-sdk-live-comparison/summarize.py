"""Assemble the native-service replacement evidence; no tests or Docker changes."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;APP=ROOT/'experiments/live-docker/native-sdk'
run=json.loads((OUT/'native-1.json').read_text());reference=json.loads((OUT/'reference.json').read_text())
line=run['load_log'].strip().splitlines()[0];ids=sorted(line.split(' ids=',1)[1].split(','))
source=[APP/'src/core.ts',APP/'src/app.native',APP/'src/shared.ts',APP/'src/services/docker.ts',APP/'docker-client/main.go']
text=[line for p in source for line in p.read_text().splitlines()]
service=APP/'build/native-live-containers_services';worker=APP/'zig-out/bin/native-docker-client'
extra=(APP/'run.sh').stat().st_size+sum(p.stat().st_size for p in (APP/'assets').rglob('*') if p.is_file())
observation=json.loads((OUT/'native-service-observation.json').read_text())
build=json.loads((OUT/'native-service-build.json').read_text());moby_build=json.loads((OUT/'moby-build.json').read_text())
build['elapsed_s']+=moby_build['elapsed_s'];build['cache']+='; plus '+moby_build['cache']
data={'framework':'Native SDK 0.11.0','sdk_revision':'16f29572307c2cc133907537c4dfd98046d4e0f4','docker_sdk':'Official Moby Go SDK v0.6.2','architecture':'Compiled TypeScript UI -> SDK-managed native TypeScript child service -> transient native Go/Moby worker; no Node at runtime.',
'lines':{'code':sum(bool(l.strip()) and not l.lstrip().startswith('//') for l in text),'physical':len(text),'scope':'Authored TypeScript core/shared/service, native markup and full Go worker; excludes manifests, shell launcher, build tools, lockfiles, generated service host and dependencies'},
'native_elf_bytes':run['binary_bytes'],'service_host_bytes':service.stat().st_size,'docker_worker_bytes':worker.stat().st_size,'helper_assets_bytes':extra,'deployment_bytes':run['binary_bytes']+service.stat().st_size+worker.stat().st_size+extra,
'binary_sha256':{'ui':run['binary_sha256'],'service':hashlib.sha256(service.read_bytes()).hexdigest(),'moby_worker':hashlib.sha256(worker.read_bytes()).hexdigest()},
'deployment_scope':'Uncompressed native UI ELF + native TypeScript service-host ELF + native Go/Moby worker ELF + assets and shell launcher. No Node/npm runtime files. Shared system libraries excluded; no installer produced.',
'run':run,'reference':reference,'same_ids_as_reference':ids==reference['ids'],'initial_load_ms':float(re.search(r'elapsed_ms=([0-9.]+)',line).group(1)),
'build_observation':build,'native_observation':observation,'node_helper_baseline':json.loads((OUT/'node-helper-baseline/summary.json').read_text()),
'limitations':['One 2s warmup/5s idle sample; not contemporaneous with older runs.','Persistent native service host included in idle totals; transient native Moby worker has exited. No request-time peak claim.','Service dispatch, worker startup and UI delivery are outside API-load interval.','Pinned compiler HTTP source omits socketPath; in-process library rejected child_process (SC4005); native child service plus Go/Moby worker used explicitly.','Software canvas/Cairo in GTK4; default GTK presentation retained.','512 KiB display/proof response limit, 512 Unicode-code-point fields, 20k rows; SDK response buffers first.','Only Linux X11/XWayland executed; Windows/macOS remain unverified.','No automated tests. Earlier Node-helper results preserved as superseded historical evidence.']}
(OUT/'summary.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({k:data[k] for k in ('lines','native_elf_bytes','service_host_bytes','docker_worker_bytes','deployment_bytes','same_ids_as_reference')},indent=2))
