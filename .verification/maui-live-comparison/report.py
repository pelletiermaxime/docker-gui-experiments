"""Generate the MAUI report and append it to the live Docker comparison."""
from pathlib import Path
import base64
import hashlib
import html
import json
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
project = ROOT / 'experiments/live-docker/maui-containers'
runs = [json.loads((OUT / f'maui-{i}.json').read_text()) for i in (1, 2, 3)]
builds = json.loads((OUT / 'builds.json').read_text())
successful = {b['kind']: b for b in builds if b['exit_code'] == 0}
observation = json.loads((OUT / 'native-observation.json').read_text())
reference = json.loads((OUT / 'reference.json').read_text())
files = sorted(project.glob('*.cs'))
physical = sum(len(p.read_text().splitlines()) for p in files)
code = sum(bool(line.strip()) and not line.lstrip().startswith('//')
           for p in files for line in p.read_text().splitlines())
metrics = {key: statistics.median(r[key] for r in runs) for key in
           ['idle_rss_median_bytes', 'idle_pss_median_bytes',
            'idle_cpu_percent_one_core', 'visible_after_seconds']}
summary = {'framework': 'MAUI Controls 10.0.110 / experimental Linux GTK4 backend',
           'backend_package': '0.1.0-preview.13.26512.5',
           'sdk': '.NET SDK 10.0.402', 'docker_sdk': 'Docker.DotNet.Enhanced 4.3.3',
           'code_lines': code, 'physical_lines': physical,
           'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
           'medians': metrics, 'builds': builds, 'reference': reference,
           'native_observation': observation, 'runs': runs,
           'scope': 'Self-contained untrimmed Release build; Linux X11/XWayland, 1000x680, 4s warmup, 20s idle, three sequential runs. Not contemporaneous with older frameworks.'}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
mib = lambda value: f'{value / 1048576:.2f}'
fd, sc = successful['framework-dependent'], successful['self-contained']
row = f'<tr><th>.NET MAUI / experimental GTK4</th><td>{code}</td><td>{mib(fd["directory_bytes"])} MiB</td><td>{mib(sc["directory_bytes"])} MiB</td><td>{mib(metrics["idle_rss_median_bytes"])} MiB</td><td>{mib(metrics["idle_pss_median_bytes"])} MiB</td><td>{metrics["idle_cpu_percent_one_core"]:.2f}%</td></tr>'
table = '<div class="table-wrap"><table><thead><tr><th>Integration</th><th>App code lines</th><th>Publish, runtime separate</th><th>Publish, runtime included</th><th>Idle RSS</th><th>Idle PSS</th><th>Idle CPU</th></tr></thead><tbody>' + row + '</tbody></table></div>'
section = '<section id="dotnet-maui-comparison"><h2>Additional experiment: C# + .NET MAUI</h2><p>The same live Docker list was recreated with MAUI Controls 10.0.110, the experimental Microsoft MAUI Labs GTK4 Linux backend, and Docker.DotNet.Enhanced 4.3.3. These are later measurements, separate from the original five integrations.</p>' + table + '<p>Directory sizes include the managed application and dependencies. The runtime-included publish also includes .NET; both exclude system GTK and graphics drivers. The tiny apphost is only a launcher and is not a comparable standalone executable. Results use the self-contained, untrimmed JIT build; no NativeAOT claim. Linux backend behavior does not predict Windows/WinUI or Mac Catalyst results.</p><p><a href="../maui-live-comparison/rapport.html">Open the MAUI report, screenshots, build observations and backend limitations.</a></p></section>'
images = ''
for name, label in [('maui-1', 'Measured native window'), ('native-search', 'Search observation'), ('native-refreshed', 'After Refresh')]:
    p = OUT / f'{name}.png'
    if p.exists():
        image = base64.b64encode(p.read_bytes()).decode()
        images += f'<figure><img src="data:image/png;base64,{image}" alt="{label}"><figcaption>{label}</figcaption></figure>'
build_rows = ''.join(f'<tr><td>{b["kind"]}</td><td>{b["exit_code"]}</td><td>{b["elapsed_seconds"]:.2f}s</td><td>{html.escape(b["log"])}</td></tr>' for b in builds)
run_rows = ''.join(f'<tr><td>{r["run"]}</td><td>{mib(r["idle_rss_median_bytes"])}</td><td>{mib(r["idle_pss_median_bytes"])}</td><td>{r["idle_cpu_percent_one_core"]:.2f}%</td><td>{r["same_ids_as_reference"]}</td></tr>' for r in runs)
raw = base64.b64encode(json.dumps(summary, indent=2).encode()).decode()
page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Live Docker · .NET MAUI experiment</title>
<style>:root{{color-scheme:dark;font:16px/1.65 system-ui;background:#111821;color:#dce5ee}}body{{max-width:1160px;margin:56px auto;padding:0 24px}}h1{{font-size:46px;line-height:1.12;color:white}}h2{{margin-top:42px}}a{{color:#85e2bf}}.callout{{background:#243132;border-left:4px solid #85e2bf;padding:20px}}.table-wrap{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;border-bottom:1px solid #354253;padding:12px}}img{{width:100%;border-radius:10px}}figure{{margin:24px 0}}figcaption,.muted{{color:#9eafc2}}code{{font-size:.9em}}footer{{margin:48px 0;color:#9eafc2}}</style>
<main><p class="muted">Docker GUI experiments / C# / Linux GTK4</p><h1>A live Docker list<br>in .NET MAUI.</h1><p>Built-in Entry, Button and virtualized CollectionView controls, background Docker SDK requests, search and manual Refresh. Same four display fields, all container states, no polling or Docker mutations.</p>
<p class="callout"><strong>This uses MAUI's experimental Linux GTK4 backend.</strong> It is developed in Microsoft MAUI Labs and is not an officially supported MAUI platform. These measurements describe this backend, not standard Windows/WinUI or Mac Catalyst. The native window loaded the same {reference['container_count']} full container IDs as the current read-only reference.</p>
<h2>Measured results</h2>{table}<p>{physical} physical C# lines; {code} nonblank/non-comment C# lines across Program, App and MainPage, including the UI. Project/lockfiles and observation scripts are separate. Memory/CPU are medians of three runs of the self-contained build.</p>
<p>The apphost launcher is {fd['apphost_bytes']:,} bytes. It loads managed assemblies and .NET, so reporting that number as the app size would be misleading. Framework-dependent publish output requires a separate .NET runtime. Self-contained output includes the runtime. Both exclude shared GTK and graphics libraries; neither is a fully static executable. Release uses the JIT, without trimming, single-file bundling or NativeAOT.</p>
<h2>Native windows and input</h2>{images}<p>The inspected search capture records the typed query and filtered rows. Refresh is observed through native keyboard activation of its button and an additional successful SDK-load log: {observation.get('loads_before_refresh', 'unconfirmed')} before, {observation.get('loads_after_refresh', 'unconfirmed')} after. The observation process exited: {observation['owned_process_exited']}.</p>
<h2>Scope and limitations</h2><ul><li>MAUI Controls 10.0.110; GTK4 backend 0.1.0-preview.13.26512.5; .NET SDK 10.0.402; Docker.DotNet.Enhanced 4.3.3. Packages are locked.</li><li>Four-second warmup, twenty seconds at idle, 500 ms process samples, one owned X11/XWayland window at a time, 1,000 × 680 client surface. No strace during these measurements.</li><li>RSS includes resident shared pages; PSS apportions them. Neither includes the compositor's memory or all GPU allocations. GTK's default graphics path is retained; mapped library presence does not prove a particular adapter.</li><li>These runs happened after the original framework comparison. The inventory ID digest is {reference['ids_sha256']}; current inventory equivalence does not make timing or environmental conditions contemporaneous.</li><li>SDK responses are fully buffered before the 20,000-row limit. Requests have a ten-second deadline; failed loads preserve the last successful rows. No Docker CLI or snapshot is used inside the app.</li><li>The experimental backend emits GTK layout/theme warnings. Some long image names wrap despite MAUI truncation settings, and the native layout differs from the other prototypes. Screenshots retain these issues; no backend patches were applied.</li><li>No Windows, macOS, busy-output, large-inventory, energy or interactive-throughput measurements. No automated test suite was added or run.</li></ul>
<h2>Individual idle runs</h2><div class="table-wrap"><table><tr><th>Run</th><th>RSS MiB</th><th>PSS MiB</th><th>CPU, one core = 100%</th><th>Same IDs</th></tr>{run_rows}</table></div>
<h2>Observed compilation</h2><div class="table-wrap"><table><tr><th>Publish mode</th><th>Exit</th><th>Wall time</th><th>Log</th></tr>{build_rows}</table></div><p>Initial package restore precedes these timings. They include cached compilation and any new package downloads. The first compilation failed on two API assumptions; the source was corrected and rebuilt. They are development observations, not comparable clean-build timings. SDK installation/download time is excluded.</p>
<h2>Code-quality assessment</h2><p>The app uses native MAUI controls, one focused page and a small platform bootstrap. Async Docker work runs off the UI thread, refreshes cannot overlap, and cancellation follows window closure. This is a small demonstration, not a complete Docker endpoint manager. It deliberately omits a view-model framework and additional abstraction layers; the remaining Linux risk is chiefly the experimental handler/backend behavior.</p>
<h2>Sources and evidence</h2><p><a href="https://github.com/pelletiermaxime/docker-gui-experiments/tree/main/experiments/live-docker/maui-containers">Application source and launch instructions</a> · <a href="https://learn.microsoft.com/en-us/dotnet/maui/developer-tools/platform-backends/linux-gtk4">Microsoft's GTK4 backend documentation</a> · <a href="https://www.nuget.org/packages/Docker.DotNet.Enhanced/4.3.3">Docker SDK package</a></p><p><a download="maui-live-comparison.json" href="data:application/json;base64,{raw}">Download measurements and provenance JSON</a></p><p><a href="../gui-live-comparison/rapport.html">Return to the live Docker comparison</a> · <a href="../../index.html">All reports</a></p><footer>Minimal exploratory application. Read-only Docker access; native observations and measurements only.</footer></main></html>'''
(OUT / 'rapport.html').write_text(page)
for path in [ROOT / '.verification/gui-live-comparison/rapport.html', ROOT / '.verification/gui-live-comparison/build_report.py']:
    text = path.read_text()
    marker = '<section id="dotnet-maui-comparison">'
    if marker in text:
        text = re.sub(r'<section id="dotnet-maui-comparison">.*?</section>', lambda _: section, text, flags=re.S)
    else:
        text = text.replace('<section><h2>Actual windows</h2>', section + '\n<section><h2>Actual windows</h2>', 1)
    text = text.replace('Five native variants.<br>Live Docker clients.', 'Five original variants.<br>Plus .NET MAUI.')
    path.write_text(text)
print(json.dumps({'code_lines': code, 'physical_lines': physical, 'medians': metrics,
                  'framework_dependent_mib': fd['directory_bytes'] / 1048576,
                  'self_contained_mib': sc['directory_bytes'] / 1048576}, indent=2))
