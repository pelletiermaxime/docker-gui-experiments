"""Render the live Docker SDK comparison; no tests or Docker operations."""
import base64,hashlib,html,json,re,statistics
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
BASE=ROOT/'.verification/gui-comparison'
apps={
 'nanoui':{'label':'Zig + NanoUI','client':'Zig Docker SDK 1.0.0','pin':'zig-0.17 / d65b714977eeadb5b38c1b577f4ef53e3f88083a','url':'https://github.com/GuangYiL/container-zig/tree/d65b714977eeadb5b38c1b577f4ef53e3f88083a','color':'#eec26d','binary':'experiments/live-docker/nanoui-containers/zig-out/bin/nanoui-live-containers','source':['experiments/live-docker/nanoui-containers/src/main.zig'],'build':['experiments/live-docker/nanoui-containers/build.zig','experiments/live-docker/nanoui-containers/build.zig.zon'],'profile':'Zig 0.17.0; ReleaseFast, strip=true, libc for NanoUI'},
 'mygo':{'label':'Go + MyGo','client':'Official Moby client v0.6.2','pin':'github.com/moby/moby/client v0.6.2; API types v1.56.1','url':'https://pkg.go.dev/github.com/moby/moby/client@v0.6.2','color':'#77d7e6','binary':'experiments/live-docker/mygo-containers/build/mygo-containers','source':['experiments/live-docker/mygo-containers/main.go'],'build':['experiments/live-docker/mygo-containers/go.mod'],'profile':'Go 1.27.1; CGO_ENABLED=0, -trimpath, mygo_noinspector, -s -w, production=1'},
 'gpui':{'label':'Rust + gpui-pre','client':'Bollard 0.21.1','pin':'gpui-pre / gpui-pre-platform 0.3.9; Bollard 0.21.1','url':'https://docs.rs/bollard/0.21.1/bollard/','color':'#85e2bf','binary':'experiments/live-docker/gpui-containers/build/gpui-live-containers','source':['experiments/live-docker/gpui-containers/src/main.rs','experiments/live-docker/gpui-containers/src/search.rs'],'build':['experiments/live-docker/gpui-containers/Cargo.toml'],'profile':'Rust 1.99.0; z, fat LTO, codegen-units=1, panic=abort, strip=true, force-unwind-tables=no; X11'}
}
apps['slint']={'label':'Rust + Slint software','client':'Bollard 0.21.1','pin':'Slint 1.18.1; Bollard 0.21.1','url':'https://docs.rs/slint/1.18.1/slint/','color':'#f79f91','binary':'experiments/live-docker/slint-containers/build/slint-live-containers','source':['experiments/live-docker/slint-containers/src/main.rs'],'build':['experiments/live-docker/slint-containers/Cargo.toml'],'profile':'Rust 1.99.0; z, fat LTO, codegen-units=1, panic=abort, strip=true, force-unwind-tables=no; Winit X11 + software renderer; Fluent dark widgets','baseline_key':None}
apps={key:apps[key] for key in ('nanoui','mygo','gpui','slint')}
def lines(paths):
 text=[line for path in paths for line in (ROOT/path).read_text().splitlines()]
 return {'code':sum(bool(l.strip()) and not l.lstrip().startswith('//') for l in text),'physical':len(text)}
def mib(n):return f'{n/1048576:,.2f}'
def n(value,digits=2):return f'{value:,.{digits}f}'
def picture(path):return 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
def med(runs,field):return statistics.median(r[field] for r in runs)
old=json.loads((BASE/'summary.json').read_text())
daemon=json.loads((OUT/'daemon.json').read_text())
proof={k:v for k,v in json.loads((OUT/'transport-proof.json').read_text()).items() if k in apps}
refresh_path=OUT/'refresh-observation.json'
refresh={k:v for k,v in json.loads(refresh_path.read_text()).items() if k in apps} if refresh_path.exists() else {}
css=re.search(r'<style>(.*?)</style>',(BASE/'rapport.html').read_text(),re.S)[1]
css+='\n.grid>*{min-width:0}a{overflow-wrap:anywhere}'
recorded_apps=json.loads((OUT/'summary.json').read_text())['apps']
for key,app in apps.items():
 runs=[json.loads((OUT/f'{key}-{i}.json').read_text()) for i in (1,2,3)]
 app.update(runs=runs,lines=recorded_apps[key]['lines'],build_lines=recorded_apps[key].get('build_lines',lines(app['build'])),binary_bytes=recorded_apps[key]['binary_bytes'],binary_sha256=recorded_apps[key]['binary_sha256'],build_observation=json.loads((OUT/f'{key}-build.json').read_text()))
 for field in ('idle_rss_median_bytes','idle_pss_median_bytes','idle_cpu_percent_one_core','initial_load_ms'):
  values=[r[field] for r in runs];app[field]={'median':statistics.median(values),'min':min(values),'max':max(values)}
 if any(r['binary_sha256']!=app['binary_sha256'] for r in runs):raise RuntimeError(f'Binary changed: {key}')
 app['all_runs_match_reference_ids']=all(r['matches_initial_inventory'] for r in runs)
 app['historical_snapshot_baseline']=({k:old['apps'][app.get('baseline_key',key)][k] for k in ['binary_bytes','lines','idle_rss_median_bytes','idle_pss_median_bytes','idle_cpu_percent_one_core']} if app.get('baseline_key',key) is not None else None)
for app in apps.values():
 app['measurement_label']='3 × 20 s'
 app['size_label']='ELF executable'
 app['screenshot']=str(OUT/f"{next(key for key,value in apps.items() if value is app)}-1.png")
for key,label,color in [('maui','C# + .NET MAUI','#bca6ff'),('avalonia','C# + Avalonia','#94bfff')]:
 folder=ROOT/f'.verification/{key}-live-comparison'
 data=json.loads((folder/'summary.json').read_text())
 runs=[]
 for original in data['runs']:
  run=dict(original)
  run['container_count']=data['reference']['container_count']
  run['matches_initial_inventory']=run['same_ids_as_reference']
  run['initial_load_ms']=int(re.search(r'Docker load: count=\d+ elapsed_ms=(\d+)',run['load_log']).group(1))
  runs.append(run)
 builds={b['kind']:b for b in data['builds'] if b['exit_code']==0}
 publish=builds['self-contained'];dependent=builds['framework-dependent']
 app={'label':label,'client':data['docker_sdk'],'pin':data['framework']+'; '+data['docker_sdk'],
  'url':f'../{key}-live-comparison/rapport.html','color':color,'runs':runs,
  'lines':{'code':data['code_lines'],'physical':data['physical_lines']},
  'binary_bytes':publish['directory_bytes'],'size_label':'Self-contained publish directory',
  'framework_dependent_bytes':dependent['directory_bytes'],
  'profile':'.NET SDK 10.0.402; net10.0; Release JIT; untrimmed; runtime included; no NativeAOT',
  'build_observation':{'elapsed_s':dependent['elapsed_seconds'],'cache':dependent['scope']},
  'all_runs_match_reference_ids':all(r['matches_initial_inventory'] for r in runs),
  'historical_snapshot_baseline':None,'screenshot':str(folder/f'{key}-1.png'),
  'measurement_label':'1 × 5 s · quick' if key=='avalonia' else '3 × 20 s',
  'native_input_observation':data['native_observation']}
 for field in ('idle_rss_median_bytes','idle_pss_median_bytes','idle_cpu_percent_one_core','initial_load_ms'):
  values=[r[field] for r in runs];app[field]={'median':statistics.median(values),'min':min(values),'max':max(values)}
 apps[key]=app
native_folder=ROOT/'.verification/native-sdk-live-comparison'
native=json.loads((native_folder/'summary.json').read_text())
native_run=dict(native['run'])
native_run.update(container_count=native['reference']['container_count'],matches_initial_inventory=native['same_ids_as_reference'],initial_load_ms=native['initial_load_ms'])
app={'label':'TypeScript + Native SDK','client':'Moby Go SDK v0.6.2 / compiled native service','pin':'Native SDK 0.11.0 (16f2957); native Moby worker v0.6.2','url':'https://github.com/vercel-labs/native/tree/v0.11.0','color':'#f2d4a1','runs':[native_run],
 'lines':native['lines'],'binary_bytes':native['deployment_bytes'],'size_label':'UI ELF + native service host + Moby worker + assets',
 'native_elf_bytes':native['native_elf_bytes'],'service_host_bytes':native['service_host_bytes'],'docker_worker_bytes':native['docker_worker_bytes'],
 'profile':'TypeScript UI + native TypeScript child service / scriptc 0.3.0; Zig 0.16.0 ReleaseFast + strip; Go 1.27.1 native Moby worker, CGO=0, -s -w; automation off; no Node at runtime; Linux GTK/Cairo software view; shared OS libraries excluded',
 'build_observation':native['build_observation'],'all_runs_match_reference_ids':native['same_ids_as_reference'],'historical_snapshot_baseline':None,'screenshot':str(native_folder/'native-1.png'),'measurement_label':'1 × 5 s · quick',
 'native_input_observation':native['native_observation']}
for field in ('idle_rss_median_bytes','idle_pss_median_bytes','idle_cpu_percent_one_core','initial_load_ms'):
 value=native_run[field];app[field]={'median':value,'min':value,'max':value}
apps['native']=app
RUNE=ROOT/'.verification/rune'
rune_comparison=json.loads((RUNE/'wayland-xwayland-comparison.json').read_text())
rune_checks=json.loads((RUNE/'functional.json').read_text())
refresh_folder=ROOT/'.verification/wayland-refresh-20261107'
updated_path=refresh_folder/'summary.json'
updated=json.loads(updated_path.read_text()) if updated_path.exists() else None
if updated:
 paired={}
 for key,original in apps.items():
  original['historical']=True
  paired[key]=original
  if key in updated['apps']:
   paired[f'{key}_updated']=updated['apps'][key]
 for key,app in updated['apps'].items():
  if key not in apps:
   paired[f'{key}_updated']=app
  paired[f'{key}_updated']['screenshot']=str(refresh_folder/f'{key}-1-window.png')
 apps=paired
renderers={
 'nanoui':{'mode':'CPU','backend':'NanoUI raster · Cairo','evidence':'Historical NanoUI Linux implementation used its CPU rasterizer and Cairo pixel presentation.'},
 'nanoui_updated':{'mode':'GPU','backend':'NanoUI · OpenGL 3.3','evidence':'Measured production binary separately logged OpenGL on Mesa Intel Arc (MTL).'},
 'mygo':{'mode':'GPU (inferred)','backend':'MyGo · OpenGL / GLX','evidence':'Historical MyGo renderer configuration and recorded GL/GLX mappings; no per-frame renderer diagnostic was captured.'},
 'mygo_updated':{'mode':'GPU','backend':'MyGo · OpenGL / EGL','evidence':'Measured production binary separately reported frames drawn on the GPU; MyGo Linux renderer uses OpenGL.'},
 'gpui':{'mode':'GPU','backend':'wgpu · Vulkan','evidence':'gpui-pre-wgpu renderer in the pinned dependency graph; Vulkan and Intel Vulkan driver recorded in process mappings.'},
 'gpui_updated':{'mode':'GPU','backend':'wgpu · Vulkan','evidence':'gpui-pre-wgpu renderer in the pinned dependency graph; Vulkan and Intel Vulkan driver recorded in process mappings.'},
 'slint':{'mode':'CPU','backend':'Slint software','evidence':'Software renderer explicitly selected; GPU renderer features excluded from this build.'},
 'maui':{'mode':'Unverified','backend':'GTK4 · GSK auto','evidence':'Native GTK4 controls. Exact CPU/GPU renderer was not recorded; loaded EGL/GLES/Vulkan libraries alone do not prove the selected backend.'},
 'avalonia':{'mode':'GPU (inferred)','backend':'Skia · OpenGL / GLX','evidence':'Avalonia desktop Skia configuration and recorded GL/GLX mappings; the selected renderer was not instrumented.'},
 'native':{'mode':'CPU','backend':'Native raster · Cairo','evidence':'Native SDK reported software pixel drawing. GTK4 presentation retains its default configuration and may use GPU compositing.'},
 'rune_updated':{'mode':'GPU','backend':'wgpu · Vulkan','evidence':'Rune wgpu renderer and Vulkan/Intel Vulkan driver recorded in the native Wayland production runs.'},
}
for key,app in apps.items():
 app['rendering']=renderers[key]
 app['screenshot']=str(Path(app['screenshot']).relative_to(ROOT))
mygo_renderer_path=refresh_folder/'mygo-renderer.json'
if mygo_renderer_path.exists() and 'mygo_updated' in apps:
 observation=json.loads(mygo_renderer_path.read_text())
 if observation['binary_sha256']!=apps['mygo_updated']['binary_sha256']:raise RuntimeError('MyGo renderer observation binary mismatch')
 apps['mygo_updated']['renderer_observation']=observation
app_code_breakdown=lines(['experiments/live-docker/gpui-containers/src/main.rs'])
input_lines=lines(['experiments/live-docker/gpui-containers/src/search.rs'])
source={'slint_native_observation':json.loads((OUT/'slint-native-observation.json').read_text()),'daemon':daemon,'apps':apps,'transport_observations':proof,'refresh_observations':refresh,'host':old['host'],'protocol':'Original three rounds, each Zig/Go/Rust in order, preserved; Slint software added later in three separate runs with the same sampling settings; live SDK load on launch, no snapshot, no application polling; 4s warmup +20s idle, 500ms samples; X11/XWayland 1000x680, GPUI scale1; strace observations separate from measurements.','dotnet_protocol':'MAUI: three later 4s warmup/20s idle runs. Avalonia and Native SDK: one short 2s warmup/5s idle run each. Native SDK uses a persistent compiled service host, included in idle figures; its native Go worker exits after loading. Node is absent at runtime. Native rows show ELF size; .NET rows show the complete runtime-included publish directory. Measurements are not contemporaneous.','native_sdk':native,'rune_wayland_xwayland':rune_comparison,'rune_functional_checks':rune_checks,'updated_wayland':updated,'limits':'Linux only; clean production builds for four updated rows; no interactive throughput benchmark; native interaction coverage differs by integration, with automated Rune smoke checks; all clients buffer/decode their finite response before checking the 20k retained-row limit.'}
(OUT/'summary.json').write_text(json.dumps(source,indent=2)+'\n')
raw=base64.b64encode(json.dumps(source,indent=2).encode()).decode()
table='';screens='';versions='';runs_table=''
for key,app in apps.items():
 size_detail=app['size_label']
 if 'framework_dependent_bytes' in app:size_detail+=f"; {mib(app['framework_dependent_bytes'])} MiB with runtime separate"
 build=app['build_observation']
 rendering=app['rendering']
 renderer_cell=f'<td title="{html.escape(rendering["evidence"],quote=True)}"><strong>{html.escape(rendering["mode"])}</strong><br><small>{html.escape(rendering["backend"])}</small></td>'
 build_detail=(f"3 clean builds · {min(r['elapsed_seconds'] for r in app['clean_build']['runs']):.1f}–{max(r['elapsed_seconds'] for r in app['clean_build']['runs']):.1f} s" if 'clean_build' in app else 'Historical · mixed cache')
 table+=f'<tr><th>{app["label"]}<br><small>{app["client"]}</small></th>{renderer_cell}<td>{mib(app["binary_bytes"])} MiB<br><small>{size_detail}</small></td><td>{app["lines"]["code"]}<br><small>{app["lines"]["physical"]} physical</small></td><td>{mib(app["idle_rss_median_bytes"]["median"])} MiB</td><td>{mib(app["idle_pss_median_bytes"]["median"])} MiB</td><td>{n(app["idle_cpu_percent_one_core"]["median"])}%</td><td>{n(app["initial_load_ms"]["median"],1)} ms</td><td>{app["measurement_label"]}</td><td>{n(build["elapsed_s"],1)} s<br><small>{build_detail}</small></td></tr>'
 img=picture(ROOT/app['screenshot'])
 screenshot_note=' · runtime canvas capture; separate observation build' if key=='native' else ''
 screens+=f'<figure><figcaption>{app["label"]} · {app["client"]}{screenshot_note}</figcaption><a href="{img}" target="_blank"><img alt="Live Docker list in {app["label"]}" src="{img}"></a></figure>'
 versions+=f'<p><strong>{app["label"]}</strong><br><a href="{app["url"]}">{app["pin"]}</a><br><code>{html.escape(app["profile"])}</code></p>'
 for r in app['runs']:
  runs_table+=f'<tr><th>{app["label"]} · {r["run"]}</th><td>{r["container_count"]}</td><td>{r["matches_initial_inventory"]}</td><td>{mib(r["idle_rss_median_bytes"])} MiB</td><td>{mib(r["idle_pss_median_bytes"])} MiB</td><td>{n(r["idle_cpu_percent_one_core"])}%</td><td>{r["initial_load_ms"]} ms</td></tr>'
def chart(title,field,formatter,unit):
 values=[a[field]['median'] if isinstance(a[field],dict) else a[field] for a in apps.values()];maximum=max(values) or 1
 bars=''.join(f'<div class="bar-row"><span>{a["label"]}</span><div class="track"><i style="width:{v/maximum*100:.3f}%;background:{a["color"]}"></i></div><strong>{formatter(v)} {unit}</strong></div>' for a,v in zip(apps.values(),values))
 return f'<article class="metric"><h3>{title}</h3>{bars}</article>'
charts=chart('Executable / self-contained publish size','binary_bytes',mib,'MiB')+chart('Idle RSS memory','idle_rss_median_bytes',mib,'MiB')+chart('Idle PSS memory','idle_pss_median_bytes',mib,'MiB')+chart('Idle CPU · 100% = one core','idle_cpu_percent_one_core',n,'%')
stamp=datetime.now(ZoneInfo('America/Toronto')).strftime('%Y-%m-%d %H:%M %Z')
page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FerryDock · live Docker SDK comparison</title><style>{css}</style></head><body><main>
<div class="eyebrow">FerryDock / separate live SDK experiment</div><h1>Eight native variants.<br>Live Docker clients.</h1>
<p class="lede">Eight implementations of the same live Docker container list, with search and manual Refresh.</p>
<section><h2>Measurements</h2><div class="grid">{charts}</div><div class="table-wrap" style="margin-top:24px"><table><thead><tr><th>Integration / Docker SDK</th><th>Rendering</th><th>Executable / publish output</th><th>App code lines</th><th>Idle RSS</th><th>Idle PSS</th><th>Idle CPU</th><th>Initial API load</th><th>Sampling</th><th>Production build</th></tr></thead><tbody>{table}</tbody></table></div><p class="muted" style="font-size:13px;margin-top:14px">Rendering identifies app drawing; GTK presentation can additionally use the GPU. Inferred backends are marked; MAUI’s exact GTK4 backend was not recorded. Dated NanoUI, MyGo and GPUI results sit immediately below their historical results. NanoUI 0.12.0, MyGo 0.8.1, gpui-pre 0.3.11 and Rune use native Wayland on COSMIC, three runtime runs (4s warmup + 20s idle) and three clean production builds with four build jobs. Dependencies were downloaded before timing; each build uses a fresh language build cache. Filesystem caches were not flushed. Rust uses opt-level=3, fat LTO and stripping; Zig uses ReleaseFast; Go uses its production build. Historical build times used different cache states. Avalonia and Native SDK retain one short runtime sample each. Native sizes are ELF executables; .NET sizes include the runtime; Native SDK includes its UI, service host, worker and assets. MiB = 1,048,576 bytes. CPU 100% means one core; 0.00% is below sampling resolution. API-load times have different logging boundaries. Process memory excludes Docker, the compositor and some GPU allocations.</p></section>
<section><h2>Rendering backend matters for this workload</h2><p>The historical NanoUI Linux build used GTK 3, CPU rasterization and Cairo presentation. NanoUI 0.12.0 enables OpenGL when available, with a CPU fallback. Its updated production binary was separately confirmed drawing with OpenGL on Mesa Intel Arc (MTL). Slint also uses CPU rendering here, through its software renderer and Winit window backend. The earlier MyGo runs recorded OpenGL/GLX libraries; GPUI recorded Vulkan/EGL/driver libraries. Loaded libraries identify rendering infrastructure, but do not allocate the measured memory gap to specific components.</p><p>The workload is a small list at idle after one API load. It does not demonstrate a GPU advantage for scrolling, live charts, a terminal, high-DPI rendering or animation. GPU rendering can help frequent redraws; CPU rendering can avoid graphics initialization overhead. The figures compare these implementations and configurations, rather than inherent language memory costs. RSS includes resident shared-library pages; PSS apportions shared pages. Compositor/display-server memory and full GPU allocations are outside these process measurements.</p></section>
<section id="rune"><h2>Rune</h2><p>Rune uses wgpu/Vulkan on Intel i915. Its dated result uses native Wayland and the same speed-optimized Rust settings as the dated GPUI build.</p><p>Search, clearing, no results, Refresh, retained rows after a failed request, a responsive ten-second timeout and recovery are validated separately from resource sampling. <a href="../../experiments/live-docker/rune-containers/README.md">Build and verification instructions</a>.</p></section>
<section id="slint-renderer-comparison"><h2>Slint renderer-only comparison</h2><p>The same Slint UI and Docker code were separately compared across eight rendering configurations, including Qt. These are newer runs, separate from the earlier framework measurements above. Skia/OpenGL was corrected and repeated separately after detecting a renderer fallback.</p><div class="table-wrap"><table><thead><tr><th>Configuration</th><th>ELF executable</th><th>Idle RSS</th><th>Idle PSS</th><th>Idle CPU</th><th>Window visible</th><th>Same IDs</th></tr></thead><tbody><tr><th>Slint software<br><small>CPU</small></th><td>11.45 MiB</td><td>21.22 MiB</td><td>15.18 MiB</td><td>0.00%</td><td>0.058s</td><td>True</td></tr><tr><th>FemtoVG / OpenGL<br><small>GPU / OpenGL</small></th><td>11.33 MiB</td><td>77.82 MiB</td><td>63.91 MiB</td><td>0.00%</td><td>0.168s</td><td>True</td></tr><tr><th>FemtoVG / WGPU<br><small>GPU / WGPU (Vulkan requested)</small></th><td>13.81 MiB</td><td>99.48 MiB</td><td>90.54 MiB</td><td>0.00%</td><td>0.330s</td><td>True</td></tr><tr><th>Skia software<br><small>CPU</small></th><td>17.21 MiB</td><td>29.27 MiB</td><td>20.83 MiB</td><td>0.00%</td><td>0.060s</td><td>True</td></tr><tr><th>Skia / OpenGL<br><small>GPU / OpenGL</small></th><td>17.21 MiB</td><td>83.16 MiB</td><td>71.76 MiB</td><td>0.00%</td><td>0.112s</td><td>True</td></tr><tr><th>Skia / WGPU<br><small>GPU / WGPU (Vulkan requested)</small></th><td>17.21 MiB</td><td>102.48 MiB</td><td>92.68 MiB</td><td>0.00%</td><td>0.168s</td><td>True</td></tr><tr><th>Vello (experimental)<br><small>GPU / WGPU (Vulkan requested)</small></th><td>14.12 MiB</td><td>108.55 MiB</td><td>99.88 MiB</td><td>0.05%</td><td>0.328s</td><td>True</td></tr><tr><th>Qt backend<br><small>Qt windowing / rendering</small></th><td>8.14 MiB</td><td>68.43 MiB</td><td>46.68 MiB</td><td>0.00%</td><td>0.168s</td><td>True</td></tr></tbody></table></div><p style="margin-top:16px"><a href="../slint-renderers/rapport.html">Open the detailed Slint renderer report, captures, build timings and limitations.</a></p></section>
<section><h2>Actual windows</h2><div class="grid">{screens}</div><p class="muted" style="margin-top:16px">Captures were made separately from resource sampling. Native SDK uses its own runtime canvas screenshot from an automation-enabled observation build; its measured release binary has automation disabled. All eight variants keep name, image, state and status columns, search, manual Refresh, dark styling and virtualization. Live data is fetched at startup and on Refresh; there is no periodic polling, event subscription, or container resource stream.</p></section>
<section><h2>Implementation and code ownership</h2><div class="grid">
<article class="card"><h3>Go / official Moby client</h3><p><code>client.New(client.FromEnv)</code> handles environment/default configuration and automatic API negotiation. A goroutine calls <code>ContainerList(All:true)</code> under a 10-second context and sends the typed results to the UI thread. The per-refresh client is closed after use.</p><p>MyGo still supplies the search field and virtualized table. The SDK replaces the previous file/scanner/subprocess plumbing; the interface is otherwise the same.</p></article>
<article class="card"><h3>Rust / Bollard + gpui-pre</h3><p><code>Docker::connect_with_defaults</code>, <code>negotiate_version</code>, and <code>list_containers(all=true)</code> run on a GPUI background worker with a temporary current-thread Tokio runtime. A 10-second Tokio timeout encloses connection, negotiation and listing. The UI receives mapped rows after completion.</p><p>The direct GPUI app still owns its text-input widget: {input_lines['code']} code lines in <code>search.rs</code>, plus {app_code_breakdown['code']} in <code>main.rs</code>. The GPUI comparison uses gpui-pre; GPUI Kit remains in the original report. Slint is the additional Rust software-rendering variant below.</p></article>
<article class="card"><h3>Rust / Slint software + Bollard</h3><p>Slint 1.18.1 supplies <code>LineEdit</code>, <code>Button</code> and <code>StandardTableView</code>. Inline Slint UI definitions count alongside Rust in <code>main.rs</code>. There is no local text-editing widget. Docker I/O runs on a worker thread with the same Bollard connect/negotiate/list operations and 10-second Tokio timeout; completion returns through Slint’s event loop. Filtering retains models for matching rows, and the built-in table virtualizes rows.</p><p>Only Winit and Slint’s built-in software renderer are enabled. Skia, FemtoVG and WGPU renderers are excluded; the app explicitly selects software rendering. Both Linux window-system features are compiled; the observed window uses X11/XWayland at scale 1. Windows/macOS are supported upstream but unexecuted here. Bollard is pinned identically; the lockfiles resolve Tokio 1.54.0 here versus 1.53.3 in the earlier GPUI variant, so this is not an identical full dependency graph.</p></article>
<article class="card"><h3>Rust / Rune + Bollard</h3><p>Rune supplies the search input, button and virtualized four-column table. Docker loading runs on a background thread with a current-thread Tokio runtime; completion updates application state through <code>AppHandle</code>. Filtering keeps indices into the loaded rows. The application owns loading/error state and retains its data after failure.</p><p>The rendering path is GPU-backed wgpu/Vulkan. Its release settings match the other Rust variants. The pinned pre-release toolkit and its component README/examples provided the implementation APIs. See the <a href="#rune">Rune observations and native checks</a>.</p></article>
<article class="card"><h3>Native SDK / compiled native service + Moby</h3><p>The TypeScript UI calls <code>dockerList</code> from <code>@native-sdk/services</code>. The SDK compiles <code>src/services/docker.ts</code> to a native child-service executable and owns request dispatch/deadlines. The service calls a small native Go worker using the official Moby SDK v0.6.2, with automatic API negotiation, a 10-second context and all-states listing. The worker exits after each load; the native service host remains alive and is included in idle resource totals. <strong>No Node, npm runtime dependencies, Docker CLI or WebView is required.</strong></p><p>This is a <strong>TypeScript UI/service + Go Docker worker</strong>, not an all-TypeScript Docker SDK. The pinned compiler's HTTP lowering omits Unix <code>socketPath</code>; a direct compile probe failed with SC3004. Its in-process library carrier rejected <code>child_process</code> with SC4005, so the implementation uses the supported native child carrier. Explicit endpoint/worker configuration crosses the typed request boundary because the child host filters its environment and uses its app-data cwd. Moby supplies the portable Docker transport; no app-specific Unix syscalls or HTTP implementation was added.</p><p>UI ELF: <strong>{mib(native['native_elf_bytes'])} MiB</strong>; native service host: <strong>{mib(native['service_host_bytes'])} MiB</strong>; native Moby worker: <strong>{mib(native['docker_worker_bytes'])} MiB</strong>; assets: <strong>{mib(native['helper_assets_bytes'])} MiB</strong>. Total uncompressed deployment files: <strong>{mib(native['deployment_bytes'])} MiB</strong>, excluding shared system libraries. Node remains a build tool only. The resource run used an empty PATH, with Node and Docker CLI unavailable; separate exec/connect tracing records the native executables and Docker socket.</p><p>The UI still uses SDK text editing and a windowed list, with a software canvas/Cairo image in GTK4. GTK4 presentation retains its defaults; loaded graphics libraries do not prove a fully GPU-free presentation path. Display delivery is bounded to 512 KiB, fields to 512 Unicode code points and retention to 20,000 rows; the SDK response buffers first. Errors keep the previous list. Source counts include all authored TypeScript, markup and Go worker code, excluding generated host code and dependencies.</p><p><strong>Correction:</strong> The earlier Node-helper row was an implementation choice, not an intrinsic Native SDK requirement. Its {mib(native['node_helper_baseline']['deployment_bytes'])} MiB deployment and {mib(native['node_helper_baseline']['run']['idle_rss_median_bytes'])} MiB RSS are retained in <code>node-helper-baseline/</code> and the raw data. That worker had already exited during idle sampling, so removing Node does not imply a matching RAM reduction. The new measurements replace its row in the main comparison.</p><p>SDK pin: <code>16f29572307c2cc133907537c4dfd98046d4e0f4</code>, unchanged source rather than the incomplete npm archive. No framework/compiler patch. Only Linux was executed. See the <a href="https://github.com/pelletiermaxime/docker-gui-experiments/blob/c35c821391b85c326d8dae437ebff5f1eefc5553/experiments/live-docker/native-sdk/README.md">reproduction notes</a> and <a href="https://native-sdk.dev/docs/typescript/services">Native SDK service documentation</a>.</p><p><strong>Native observations:</strong> {html.escape(native['native_observation']['summary'])}</p></article>
<article class="card"><h3>Common behavior and limits</h3><p>All read all container states, disable overlapping Refresh requests, show errors, and retain the last good rows after a failed refresh. More than 20,000 returned rows is an error. Each client buffers/decodes its finite response before that retention check; this is not a common wire-response byte cap. Native SDK additionally bounds its display pipe to 512 KiB and sanitizes/truncates display fields, so its retention and delivery limits are not identical to the other apps.</p><p>App line counts include mapping, timeout wiring, proof logging and local input code, excluding blank lines and whole-line comments. Libraries, generated C bindings, upstream endpoint helper, lockfiles, build files and scripts are excluded. These are implementation counts, not a controlled measure of language verbosity.</p></article></div></section>
<section><h2>Refresh validation</h2><p>The updated NanoUI, MyGo, gpui-pre and Rune production binaries are checked on native Wayland against the live daemon: complete inventory, case-insensitive search, no results, clearing, a second successful load through Refresh, retained data after an injected HTTP 500, responsive input during a stalled request, the ten-second deadline and successful recovery. These checks use a temporary read-only proxy and run outside performance sampling. Historical interaction evidence is retained in the raw data; the older Slint interaction gap remains unverified.</p></section>
<section><h2>Protocol and portability</h2><p>Updated runs remove DISPLAY and select Wayland explicitly. Each app requests a 1,000 × 680 window; toolkit handling of decorations differs, and actual capture sizes are recorded. After a four-second warmup, process/descendant RSS, PSS and CPU are sampled every 500 ms for twenty seconds. One app runs at a time. Captures and functional checks are separate from sampling. Every new run must match its independent live inventory reference and the measured executable hash.</p><p>Clean builds use isolated output/cache directories, pre-fetched dependencies, four build jobs and no compiler wrappers. Cargo uses the installed standard library; Go rebuilds its packages in a fresh GOCACHE; Zig uses empty local/global caches. Sources and filesystem caches remain available. The build table reports medians of three runs with their ranges.</p><p>Historical measurements remain unchanged and mostly used XWayland. Only Linux local Docker sockets were exercised; Windows/macOS and remote/TLS behavior are untested. Package sizes exclude shared OS libraries and drivers. These idle runs do not measure active scrolling, large-inventory throughput or continuous updates.</p></section>
<section><h2>Pinned clients and build profiles</h2><div class="grid">{versions}</div><p class="muted">Historical pins remain recorded above. Updated pins: NanoUI e26765e8422f (0.12.0), MyGo 1dfa5a1f912b (0.8.1), gpui-pre 0.3.11; Rune f73f72c is rebuilt unchanged. Source projects are under <code>experiments/live-docker/</code>; launch and build commands are in each README.</p></section>
<section><details><summary>All {sum(len(a["runs"]) for a in apps.values())} runs and raw data</summary><div class="table-wrap" style="margin-top:20px"><table><thead><tr><th>Run</th><th>Containers</th><th>Reference IDs match</th><th>RSS</th><th>PSS</th><th>Idle CPU</th><th>API load</th></tr></thead><tbody>{runs_table}</tbody></table></div><a class="download" download="live-docker-sdk-comparison.json" href="data:application/json;base64,{raw}">Download measurement JSON</a></details></section>
<footer>Generated {stamp}. Self-contained HTML with embedded screenshots/data. Updated production binaries passed native Wayland Refresh validation; historical evidence is retained. No Docker resources created or changed. Original measurement evidence preserved. Reproduction commands are in the project READMEs.</footer></main></body></html>'''
(OUT/'rapport.html').write_text(page)
print(json.dumps({key:{'binary_mib':app['binary_bytes']/1048576,'code_lines':app['lines']['code'],'rss_mib':app['idle_rss_median_bytes']['median']/1048576,'pss_mib':app['idle_pss_median_bytes']['median']/1048576,'cpu_percent':app['idle_cpu_percent_one_core']['median'],'all_ids_match':app['all_runs_match_reference_ids']} for key,app in apps.items()},indent=2))
