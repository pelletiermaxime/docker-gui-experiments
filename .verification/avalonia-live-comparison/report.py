"""Render the short Avalonia observation and append it to the live report."""
from pathlib import Path
import base64
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
project = ROOT / 'experiments/live-docker/avalonia-containers'
run = json.loads((OUT / 'avalonia-1.json').read_text())
builds = json.loads((OUT / 'builds.json').read_text())
build = {b['kind']: b for b in builds if b['exit_code'] == 0}
native = json.loads((OUT / 'native-observation.json').read_text())
reference = json.loads((OUT / 'reference.json').read_text())
sources = sorted(project.glob('*.cs'))
physical = sum(len(p.read_text().splitlines()) for p in sources)
code = sum(bool(line.strip()) and not line.lstrip().startswith('//')
           for p in sources for line in p.read_text().splitlines())
summary = {'framework': 'Avalonia 12.1.2 / desktop Skia / X11',
           'sdk': '.NET SDK 10.0.402', 'docker_sdk': 'Docker.DotNet.Enhanced 4.3.3',
           'code_lines': code, 'physical_lines': physical,
           'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
           'builds': builds, 'reference': reference, 'native_observation': native,
           'runs': [run], 'protocol': 'One short sample, 2 seconds warmup and 5 seconds idle, 1000x680 X11/XWayland. Requested to reduce measurement time; not equivalent precision to older three-run results.'}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
mib = lambda value: f'{value / 1048576:.2f}'
fd, sc = build['framework-dependent'], build['self-contained']
table = f'''<div class="table-wrap"><table><thead><tr><th>Integration</th><th>Code lines</th><th>Publish, runtime separate</th><th>Publish, runtime included</th><th>Idle RSS</th><th>Idle PSS</th><th>Idle CPU</th></tr></thead><tbody><tr><th>Avalonia 12.1.2 / C#</th><td>{code}</td><td>{mib(fd['directory_bytes'])} MiB</td><td>{mib(sc['directory_bytes'])} MiB</td><td>{mib(run['idle_rss_median_bytes'])} MiB</td><td>{mib(run['idle_pss_median_bytes'])} MiB</td><td>{run['idle_cpu_percent_one_core']:.2f}%</td></tr></tbody></table></div>'''
section = '<section id="dotnet-avalonia-comparison"><h2>Additional experiment: C# + Avalonia</h2><p>The same live Docker list, using Avalonia 12.1.2 with its built-in DataGrid and Docker.DotNet.Enhanced 4.3.3.</p>' + table + '<p><strong>Short protocol: one run, two seconds warmup and five seconds idle.</strong> This was requested to shorten experimentation; it is more approximate than the older three-run results. Publish-directory sizes include managed dependencies and, for the runtime-included variant, .NET. Both exclude system libraries. Resource results use the self-contained, untrimmed JIT build.</p><p><a href="../avalonia-live-comparison/rapport.html">Open Avalonia details, native screenshots and measurement limitations.</a></p></section>'
images = ''
for name, caption in [('avalonia-1', 'Short measured run'), ('native-search', 'Native search at ordinary desktop scale'), ('native-refreshed', 'After native Refresh at ordinary desktop scale')]:
    p = OUT / f'{name}.png'
    if p.exists():
        encoded = base64.b64encode(p.read_bytes()).decode()
        images += f'<figure><img alt="{caption}" src="data:image/png;base64,{encoded}"><figcaption>{caption}</figcaption></figure>'
raw = base64.b64encode(json.dumps(summary, indent=2).encode()).decode()
build_rows = ''.join(f'<tr><td>{b["kind"]}</td><td>{b["elapsed_seconds"]:.2f}s</td><td>{b["exit_code"]}</td></tr>' for b in builds)
page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Live Docker · Avalonia experiment</title>
<style>:root{{color-scheme:dark;font:16px/1.65 system-ui;background:#111821;color:#dce5ee}}body{{max-width:1160px;margin:56px auto;padding:0 24px}}h1{{font-size:46px;line-height:1.12;color:white}}h2{{margin-top:42px}}a{{color:#85e2bf}}.callout{{background:#243132;border-left:4px solid #85e2bf;padding:20px}}.table-wrap{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;border-bottom:1px solid #354253;padding:12px}}img{{width:100%;border-radius:10px}}figure{{margin:24px 0}}figcaption,.muted{{color:#9eafc2}}footer{{margin:48px 0;color:#9eafc2}}</style>
<main><p class="muted">Docker GUI experiments / C# / Avalonia desktop</p><h1>The same Docker list.<br>Now in Avalonia.</h1><p>Built-in TextBox, Button and virtualized DataGrid, Fluent dark styling, background Docker SDK loading, search and manual Refresh. No WebView, Docker subprocess, snapshot input, polling or container mutations.</p>
<p class="callout"><strong>A deliberately short measurement.</strong> One fresh process, two seconds warmup, five seconds idle, 500 ms process samples, scale 1 via named-monitor AVALONIA_SCREEN_SCALE_FACTORS. The user requested a shorter protocol. Treat these numbers as a quick baseline with more uncertainty than the older three-run measurements.</p>
<h2>Observed results</h2>{table}<p>{physical} physical C# lines, {code} nonblank/non-comment lines, including the UI, app and platform bootstrap. Project files, lockfiles and observation scripts are separate. Idle RSS/PSS are medians of samples within this one run; CPU is the measured interval average, with 100% representing one logical core.</p>
<p>Framework-dependent output excludes the installed .NET runtime. Self-contained output includes it. Both exclude external system graphics/windowing libraries. The {fd['apphost_bytes']:,}-byte apphost is a launcher and is not a comparable standalone executable size. Release is untrimmed JIT, without NativeAOT or single-file packaging, matching the MAUI experiment.</p>
<h2>Native window and input</h2>{images}<p>All {reference['container_count']} current full container IDs matched the read-only reference: {run['same_ids_as_reference']}. Inventory SHA-256: {reference['ids_sha256']}. Native keyboard input records search, clearing and Refresh. Successful SDK load logs before/after Refresh: {native.get('loads_before_refresh', 'unconfirmed')} / {native.get('loads_after_refresh', 'unconfirmed')}. The owned observation process exited: {native['owned_process_exited']}.</p>
<h2>What differs from MAUI?</h2><p>Both C# ports use the same .NET SDK and Docker.DotNet.Enhanced 4.3.3 client, equivalent background request/timeout logic, the same four fields, last-good-state behavior and post-decode 20,000-row cap. Avalonia uses its normal desktop integration and Skia rendering; MAUI's observed Linux host is an experimental GTK4 backend. Avalonia's default renderer/adapter is not forced. Loaded graphics libraries are recorded, but library presence does not independently identify the active GPU.</p><p>Runtime and toolkit differences, JIT behavior, caches, selected features and unequal sample durations prevent assigning every difference to a single cause. MAUI has three longer final runs; Avalonia has one short run. The shorter warmup may retain startup JIT/GC activity in the CPU interval. The initial desktop-scaled sample did not match the requested physical window size and is archived/excluded. This is an exploratory comparison, not a controlled language or renderer ranking.</p>
<h2>Observed build times</h2><table><tr><th>Publish mode</th><th>Wall time</th><th>Exit</th></tr>{build_rows}</table><p>The first publish includes dependency restore/download and compilation. The second shares caches and compiled code. SDK installation is excluded. These are development observations, not equivalent clean-build timings. No automated test suite was added or run.</p>
<h2>Code and portability</h2><p>A small code-only UI uses Avalonia's DataGrid and text input rather than custom controls. No MVVM framework or bundled font set is added. Requests cannot overlap and window closure cancels the active load. The SDK buffers its full response before the retention limit, so this is not a common wire-byte cap.</p><p>Avalonia supports Windows, macOS and Linux upstream. Only this Linux X11/XWayland run is observed; Windows/macOS builds and named-pipe/TLS transports are not proven here. DOCKER_HOST explicitly selects the endpoint, or the app uses its local platform default.</p>
<h2>Evidence</h2><p><a href="https://github.com/pelletiermaxime/docker-gui-experiments/tree/main/experiments/live-docker/avalonia-containers">Source and build instructions</a> · <a href="https://github.com/AvaloniaUI/Avalonia">Avalonia upstream</a> · <a href="https://www.nuget.org/packages/Docker.DotNet.Enhanced/4.3.3">Docker SDK</a></p><p><a download="avalonia-live-comparison.json" href="data:application/json;base64,{raw}">Download full measurements and provenance</a></p><p><a href="../gui-live-comparison/rapport.html">Live Docker comparison</a> · <a href="../maui-live-comparison/rapport.html">MAUI report</a> · <a href="../../index.html">All reports</a></p><footer>Read-only exploratory app. Single short resource observation; native input outside the measured interval.</footer></main></html>'''
(OUT / 'rapport.html').write_text(page)
for p in [ROOT / '.verification/gui-live-comparison/rapport.html', ROOT / '.verification/gui-live-comparison/build_report.py']:
    text = p.read_text()
    if '<section id="dotnet-avalonia-comparison">' in text:
        text = re.sub(r'<section id="dotnet-avalonia-comparison">.*?</section>', lambda _: section, text, flags=re.S)
    else:
        text = text.replace('<section><h2>Actual windows</h2>', section + '\n<section><h2>Actual windows</h2>', 1)
    text = text.replace('Plus .NET MAUI.', 'Plus .NET ports.')
    text = text.replace('All five loaded the same live inventory.', 'The original five loaded the same live inventory.')
    p.write_text(text)
print(json.dumps({'code_lines': code, 'rss_mib': run['idle_rss_median_bytes'] / 1048576,
                  'pss_mib': run['idle_pss_median_bytes'] / 1048576,
                  'idle_cpu_percent': run['idle_cpu_percent_one_core'],
                  'publish_without_runtime_mib': fd['directory_bytes'] / 1048576,
                  'publish_with_runtime_mib': sc['directory_bytes'] / 1048576}, indent=2))
