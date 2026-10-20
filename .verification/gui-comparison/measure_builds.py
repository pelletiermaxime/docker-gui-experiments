"""Measure release builds using existing dependency caches, without editing app sources."""
from pathlib import Path
import hashlib,json,os,shutil,statistics,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
RUN=OUT/'build-timing-work'
RUN.mkdir(exist_ok=False)
base_env=dict(os.environ)
results={}
restores=[]

def copy_app(name,source):
 dest=RUN/name
 dest.mkdir()
 for filename in ('build.zig','build.zig.zon','go.mod','go.sum','Cargo.toml','Cargo.lock'):
  src=source/filename
  if src.exists():shutil.copy2(src,dest/filename)
 if (source/'src').exists():shutil.copytree(source/'src',dest/'src')
 if (source/'main.go').exists():shutil.copy2(source/'main.go',dest/'main.go')
 for main in (dest/'src/main.zig',dest/'src/main.rs',dest/'main.go'):
  if main.exists():
   with main.open('a') as changed:changed.write(f"\n// Application edit for compile timing: {time.time_ns()}\n")
 return dest

def measure(key,folder,command,extra_env):
 env=dict(base_env,**extra_env)
 log=RUN/f'{key}-rebuild.log'
 started=time.perf_counter()
 with log.open('w') as output:
  subprocess.run(command,cwd=folder,env=env,stdout=output,stderr=subprocess.STDOUT,check=True)
 elapsed=time.perf_counter()-started
 noop=[]
 for index in range(3):
  started=time.perf_counter()
  with (RUN/f'{key}-noop-{index+1}.log').open('w') as output:
   subprocess.run(command,cwd=folder,env=env,stdout=output,stderr=subprocess.STDOUT,check=True)
  noop.append(time.perf_counter()-started)
 # Preserve command, complete build log, and raw samples alongside the report.
 results[key]={'warm_dependency_rebuild_seconds':elapsed,'unchanged_build_seconds':noop,
  'unchanged_build_median_seconds':statistics.median(noop),'application_rebuild_samples':1,
  'command':command,'working_directory':str(folder.relative_to(ROOT)),
  'environment_overrides':extra_env,'log':str(log.relative_to(OUT))}
 (OUT/'build-times.json').write_text(json.dumps({'scope':'Release builds on Linux; dependency caches reused; one app rebuild after an added comment in an isolated source copy per integration and three unchanged builds; not clean builds; no tests; sequential execution','parallelism':'4 build jobs; Go GOMAXPROCS=4; no CPU affinity or machine isolation','integrations':results},indent=2)+'\n')
 print(json.dumps({'integration':key,'warm_dependency_rebuild_seconds':round(elapsed,3),'unchanged_build_median_seconds':round(statistics.median(noop),3)}),flush=True)

try:
 nano=copy_app('nanoui',ROOT/'experiments/nanoui-containers')
 p=nano/'build.zig.zon';p.write_text(p.read_text().replace('../../.verification/gui-comparison/deps/nanoui','../../deps/nanoui'))
 measure('nanoui',nano,[str(OUT/'toolchains/zig-x86_64-linux-0.17.0/zig'),'build','-Doptimize=ReleaseFast','-j4'],{
  'ZIG_GLOBAL_CACHE_DIR':'/tmp/ferrydock-nanoui-zig-global-cache','ZIG_LOCAL_CACHE_DIR':'/tmp/ferrydock-nanoui-zig-cache','ZIG_LOCAL_PKG_DIR':'/tmp/ferrydock-nanoui-zig-pkgs'})
 go=copy_app('mygo',ROOT/'experiments/mygo-containers')
 p=go/'go.mod';p.write_text(p.read_text().replace('../../.verification/gui-comparison/deps/mygo',str(OUT/'deps/mygo')))
 measure('mygo',go,['go','build','-p','4','-trimpath','-tags','mygo_noinspector','-ldflags','-s -w -X github.com/egoist/mygo.production=1','-o','mygo-containers','.'],{
  'CGO_ENABLED':'0','GOMAXPROCS':'4','GOCACHE':'/tmp/ferrydock-mygo-build-cache','GOMODCACHE':'/tmp/ferrydock-mygo-module-cache','GOPROXY':'off','GOSUMDB':'off'})
 for key,src,target,flags in [
  ('gpui_kit',OUT/'gpui-kit-baseline',ROOT/'target',''),
  ('gpui',ROOT/'experiments/gpui-containers',ROOT/'experiments/gpui-containers/target','-C force-unwind-tables=no')]:
  folder=copy_app(key,src)
  binary=target/'release/gpui-containers'
  if binary.exists():
   backup=RUN/f'{key}-original-binary';shutil.copy2(binary,backup);restores.append((binary,backup))
  measure(key,folder,['cargo','build','--release','--locked','--offline'],{
   'CARGO_TARGET_DIR':str(target),'CARGO_BUILD_JOBS':'4','RUSTFLAGS':flags})
finally:
 for binary,backup in restores:
  temp=binary.with_name('.build-timing-restore')
  shutil.copy2(backup,temp);os.replace(temp,binary)
 print('Original application executables restored.',flush=True)
