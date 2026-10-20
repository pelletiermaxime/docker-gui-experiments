"""Render the local measurements as one portable, dependency-free HTML file."""
import base64
from datetime import datetime
import gzip
import html
import json
from pathlib import Path
import statistics
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
KIT_ARCHIVE = OUT / "gpui-kit-baseline"
KIT_BASELINE = json.loads((KIT_ARCHIVE / "summary.json").read_text())["apps"]["gpui"]
APPS = {
    "nanoui": {
        "label": "Zig + NanoUI", "color": "#eec26d", "language": "Zig 0.17.0",
        "repo": "justrach/nanoui", "commit": "d61e253205472cef0854367125295d87c810c5b3",
        "binary": "experiments/nanoui-containers/zig-out/bin/nanoui-containers",
        "source": ["experiments/nanoui-containers/src/main.zig"],
        "build": ["experiments/nanoui-containers/build.zig", "experiments/nanoui-containers/build.zig.zon"],
        "flags": "ReleaseFast, strip=true; Zig standard-library file/process I/O; libc linked for NanoUI",
    },
    "mygo": {
        "label": "Go + MyGo", "color": "#77d7e6", "language": "Go 1.27.1",
        "repo": "egoist/mygo", "commit": "5fb60098a44a4c629cbdeac5f0ff80ce2f843c2f",
        "binary": "experiments/mygo-containers/build/mygo-containers",
        "source": ["experiments/mygo-containers/main.go"],
        "build": ["experiments/mygo-containers/go.mod"],
        "flags": "CGO_ENABLED=0, -trimpath, -tags mygo_noinspector, -ldflags '-s -w -X github.com/egoist/mygo.production=1'",
    },
    "gpui_kit": {
        **{k: KIT_BASELINE[k] for k in ("label", "language", "version", "url", "flags")},
        "color": "#beacf5",
        "flags": "cargo build --release --locked, lto=thin, strip=true; gpui-fast feature, no test-support or tree-sitter",
        "binary": ".verification/gui-comparison/gpui-kit-baseline/gpui-kit-containers",
        "source": [".verification/gui-comparison/gpui-kit-baseline/src/main.rs"],
        "build": [".verification/gui-comparison/gpui-kit-baseline/Cargo.toml"],
        "runs_dir": "gpui-kit-baseline", "runs_prefix": "gpui",
    },
    "gpui": {
        "label": "Rust + gpui-pre", "color": "#85e2bf", "language": "Rust 1.99.0",
        "version": "gpui-pre 0.3.9 (snapshot Zed 93d7456), without Kit or GPUI Fast, X11 backend in this Linux build",
        "url": "https://docs.rs/gpui-pre/0.3.9/gpui/",
        "binary": "experiments/gpui-containers/target/release/gpui-containers",
        "source": ["experiments/gpui-containers/src/main.rs", "experiments/gpui-containers/src/search.rs"],
        "build": ["experiments/gpui-containers/Cargo.toml"],
        "flags": "opt-level=z, lto=fat, codegen-units=1, panic=abort, strip=true, force-unwind-tables=no ; default-features=false, x11 ; no executable compression",
    },
}


def lines(paths):
    total = blank = comments = 0
    for path in paths:
        for line in (ROOT / path).read_text().splitlines():
            total += 1
            blank += not line.strip()
            comments += line.lstrip().startswith("//")
    return {"physical": total, "code": total - blank - comments, "blank": blank, "comments": comments}


def number(n, digits=2):
    return f"{n:,.{digits}f}"


def mib(n):
    return number(n / 1048576)


def image(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


rows = {}
for key, app in APPS.items():
    run_dir = OUT / app.get("runs_dir", "")
    run_prefix = app.get("runs_prefix", key)
    runs = [json.loads((run_dir / f"{run_prefix}-{i}.json").read_text()) for i in (1, 2, 3)]
    row = dict(app, runs=runs, lines=lines(app["source"]), build_lines=lines(app["build"]))
    for metric in ("idle_rss_median_bytes", "idle_pss_median_bytes", "idle_cpu_percent_one_core", "visible_after_seconds", "sampled_peak_rss_bytes"):
        values = [r[metric] for r in runs]
        row[metric] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
    row["binary_bytes"] = (ROOT / app["binary"]).stat().st_size
    row["gzip_bytes"] = len(gzip.compress((ROOT / app["binary"]).read_bytes(), mtime=0))
    rows[key] = row

host = json.loads((OUT / "host.json").read_text())
build_times_path = OUT / "build-times.json"
build_times = json.loads(build_times_path.read_text()) if build_times_path.exists() else None
data = {"build_times": build_times, "host": host, "apps": rows, "report_language": "en", "measurement_scope": "Linux only; Windows/macOS discussion is based on upstream platform documentation and source inspection, not measurements", "protocol": "4 integrations, 3 runs each (12 total); 3 new portable-Zig runs, 3 retained MyGo runs, 3 archived GPUI Kit runs, 3 retained gpui-pre runs; same snapshot, 4 s warmup, 20 s idle, 500 ms sampling; original libc/timeout Zig series archived and excluded"}
(OUT / "summary.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
nano, go, kit, gpui = (rows[key] for key in ("nanoui", "mygo", "gpui_kit", "gpui"))
ratio = go["binary_bytes"] / nano["binary_bytes"]
stamp = datetime.now(ZoneInfo("America/Toronto")).strftime("%Y-%m-%d %H:%M %Z")


def comparison(label, metric, formatter, unit=""):
    values = [r[metric]["median"] if isinstance(r[metric], dict) else r[metric] for r in rows.values()]
    maximum = max(values) or 1
    bars = ""
    for (key, app), value in zip(rows.items(), values):
        bars += f'<div class="bar-row"><span>{app["label"]}</span><div class="track"><i style="width:{value / maximum * 100:.3f}%;background:{app["color"]}"></i></div><strong>{formatter(value)} {unit}</strong></div>'
    return f'<article class="metric"><h3>{label}</h3>{bars}</article>'


charts = comparison("ELF executable · smaller is better", "binary_bytes", mib, "MiB")
charts += comparison("RSS memory · median at idle", "idle_rss_median_bytes", mib, "MiB")
charts += comparison("PSS memory · shared pages apportioned", "idle_pss_median_bytes", mib, "MiB")
charts += comparison("Idle CPU · 100% = one logical core", "idle_cpu_percent_one_core", number, "%")

table = ""
for key, row in rows.items():
    l = row["lines"]
    table += f'''<tr><th><span class="dot" style="background:{row['color']}"></span>{row['label']}</th>
    <td>{mib(row['binary_bytes'])} MiB<br><small>{row['binary_bytes']:,} bytes</small></td>
    <td>{mib(row['gzip_bytes'])} MiB</td>
    <td>{l['code']}<br><small>{l['physical']} physical</small></td>
    <td>{row['build_lines']['physical']}</td>
    <td>{mib(row['idle_rss_median_bytes']['median'])} MiB</td>
    <td>{mib(row['idle_pss_median_bytes']['median'])} MiB</td>
    <td>{number(row['idle_cpu_percent_one_core']['median'])} %</td></tr>'''

details = ""
for key, row in rows.items():
    for r in row["runs"]:
        details += f'<tr><th>{row["label"]} · {r["run"]}</th><td>{mib(r["idle_rss_median_bytes"])} MiB</td><td>{mib(r["idle_pss_median_bytes"])} MiB</td><td>{number(r["idle_cpu_percent_one_core"])} %</td><td>{number(r["idle_seconds"])} s</td><td>{mib(r["sampled_peak_rss_bytes"])} MiB</td></tr>'

versions = ""
for key, row in rows.items():
    url = row.get("url") or f'https://github.com/{row["repo"]}/tree/{row["commit"]}'
    version = row.get("version") or f'{row["repo"]}@{row["commit"][:12]}'
    versions += f'<p><strong>{row["label"]}</strong> · {row["language"]}<br><a href="{url}">{version}</a><br><code>{html.escape(row["flags"])}</code></p>'

raw = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
screenshots = ""
for key, row in rows.items():
    capture = OUT / row.get("runs_dir", "") / f'{row.get("runs_prefix", key)}-1.png'
    screenshots += f'<figure><figcaption><span class="dot" style="background:{row["color"]}"></span>{row["label"]} · actual Linux window</figcaption><a href="{image(capture)}" target="_blank"><img alt="Container list in {row["label"]}" src="{image(capture)}"></a></figure>'

build_section = ""
if build_times:
    build_rows = ""
    for key, result in build_times["integrations"].items():
        app = rows[key]
        build_rows += f'<tr><th>{app["label"]}</th><td>{number(result["warm_dependency_rebuild_seconds"])} s</td><td>{number(result["unchanged_build_median_seconds"], 3)} s</td></tr>'
    build_section = f'''<section id="build-times"><h2>Release build times</h2><p>Measured on this Linux machine, with the existing dependency caches retained. The first column rebuilds the application after a harmless comment is added to an isolated copy of its main source file. The second column is the median of three subsequent builds with no source changes. All four integrations run sequentially.</p><div class="table-wrap"><table><thead><tr><th>Integration</th><th>App rebuild · dependencies cached</th><th>Unchanged build · median of 3</th></tr></thead><tbody>{build_rows}</tbody></table></div><p class="muted" style="font-size:13px;margin-top:14px">One edited-source rebuild sample per integration; these are observed durations, not a statistical ranking. Build parallelism is capped at four jobs; Go also uses GOMAXPROCS=4. There is no CPU affinity, cache flush, or isolation from other desktop applications. Logs, exact commands, environment overrides, and individual unchanged-build samples are embedded in the downloadable JSON and stored in <code>build-times.json</code>.</p><div class="grid" style="margin-top:24px"><article class="card"><h3>The profiles affect the result</h3><p>These are the release profiles used for the measured executables: Zig ReleaseFast, the stripped Go build, Kit with thin LTO, and gpui-pre with size optimization, fat LTO, and one codegen unit. The direct GPUI profile prioritizes executable size and can make linking much more expensive. This comparison measures these app/toolkit/profile combinations, not an inherent language-only compilation cost.</p></article><article class="card"><h3>What is not measured</h3><p>A full clean build, including recompiling every dependency, is <strong>not measured</strong>. Downloads and toolchain installation are excluded. Earlier logs recorded a 4m08s Kit build and a 1m17s direct-GPUI rebuild, but their cache states differ, so they are not used as comparable clean-build results.</p><p>Implementation time was not instrumented either. Go/MyGo required less iteration than the Rust implementations in this session; that observation includes the chosen APIs and the author's implementation/debugging decisions. No numeric development-speed ratio is justified.</p></article></div></section>'''

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FerryDock · NanoUI / MyGo / GPUI Kit / gpui-pre</title>
<style>
:root{{--bg:#101619;--panel:#192226;--line:#304045;--text:#e4eeed;--muted:#a5b8b9;--mint:#85e2bf}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,sans-serif}}main{{max-width:1240px;margin:auto;padding:56px 32px 64px}}a{{color:var(--mint)}}h1{{font-size:clamp(36px,5vw,62px);line-height:1.12;letter-spacing:-2px;margin:20px 0}}h2{{font-size:26px;margin:0 0 20px}}h3{{font-size:16px;margin:0 0 24px}}p{{margin:0 0 16px}}.eyebrow{{color:var(--mint);text-transform:uppercase;letter-spacing:2px;font-size:12px;font-weight:750}}.lede{{color:var(--muted);max-width:850px;font-size:19px}}.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0 32px}}.chip{{background:#233337;border:1px solid var(--line);padding:5px 12px;border-radius:40px;font-size:12px}}section{{margin-top:48px}}.callout{{border-left:3px solid var(--mint);background:#192a29;padding:22px 26px;border-radius:0 12px 12px 0}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.metric,.card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:24px}}.bar-row{{display:grid;grid-template-columns:145px 1fr 90px;align-items:center;gap:12px;margin:15px 0;font-size:12px}}.bar-row strong{{text-align:right;font-variant-numeric:tabular-nums}}.track{{height:12px;background:#29363a;border-radius:20px;overflow:hidden}}.track i{{height:100%;display:block;border-radius:20px}}.muted,small{{color:var(--muted)}}small{{font-size:12px}}.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}}.table-wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:12px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:16px 14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}thead{{background:#223035}}tbody tr:last-child>*{{border-bottom:0}}th{{font-weight:600}}code{{font:12px/1.6 ui-monospace,monospace;overflow-wrap:anywhere;color:#d9e9dd}}figure{{margin:0;min-width:0}}figcaption{{margin-bottom:12px;font-size:14px;font-weight:650}}img{{width:100%;border:1px solid var(--line);border-radius:10px}}ul{{padding-left:20px}}li{{margin-bottom:9px}}details{{border:1px solid var(--line);border-radius:12px;padding:18px 22px;background:var(--panel)}}summary{{cursor:pointer;font-weight:650}}.download{{display:inline-block;margin-top:18px;padding:9px 16px;border:1px solid var(--line);border-radius:8px;text-decoration:none}}footer{{border-top:1px solid var(--line);margin-top:48px;padding-top:20px;color:var(--muted);font-size:12px}}@media(max-width:800px){{main{{padding:30px 18px}}.grid{{grid-template-columns:1fr}}.bar-row{{grid-template-columns:130px 1fr 80px}}}}@media print{{body{{--bg:#fff;--panel:#f4f6f6;--line:#ccd4d4;--text:#182728;--muted:#53686a;--mint:#226853}}main{{padding:0}}section,.metric{{break-inside:avoid}}.callout{{background:#e8f5ef}}.download{{display:none}}}}
</style></head><body><main>
<div class="eyebrow">FerryDock / native UI comparison</div>
<p id="live-sdk-report-link" style="margin-top:16px"><a href="../gui-live-comparison/rapport.html">Open the live Docker SDK comparison →</a> <span class="muted">Zig/container-zig, Go/Moby, Rust/Bollard</span></p>
<h1>Four integrations.<br>The same container list.</h1>
<p class="lede">Zig + NanoUI, Go + MyGo, Rust + GPUI Kit, and Rust + gpui-pre: four small native prototypes displaying the same Docker inventory, measured on one Linux desktop.</p>
<div class="chips"><span class="chip">14 real containers, frozen snapshot</span><span class="chip">1,000 × 680 client pixels</span><span class="chip">3 runs per integration</span><span class="chip">Linux measurements</span><span class="chip">Windows / macOS outlook below</span><span class="chip">No automated tests added or run</span></div>
<div class="callout"><strong>Four prototypes, one shared scope.</strong> Median idle RSS is {mib(nano["idle_rss_median_bytes"]["median"])} MiB for NanoUI, {mib(go["idle_rss_median_bytes"]["median"])} MiB for MyGo, {mib(kit["idle_rss_median_bytes"]["median"])} MiB for GPUI Kit, and {mib(gpui["idle_rss_median_bytes"]["median"])} MiB for gpui-pre. The charts compare executable size, memory, and CPU. Code quality is a source-based assessment of these prototypes. <a href="#other-platforms">Windows and macOS expectations</a> are discussed separately from the measurements.</div>
<section><h2>Two separate GPUI integrations</h2><div class="table-wrap"><table><thead><tr><th>Integration</th><th>Executable</th><th>Idle RSS</th><th>Idle CPU</th></tr></thead><tbody><tr><th>GPUI Kit 0.8.0 + GPUI Fast 0.1.10</th><td>{mib(kit["binary_bytes"])} MiB</td><td>{mib(kit["idle_rss_median_bytes"]["median"])} MiB</td><td>{number(kit["idle_cpu_percent_one_core"]["median"])}%</td></tr><tr><th>gpui-pre 0.3.9, used directly</th><td>{mib(gpui["binary_bytes"])} MiB</td><td>{mib(gpui["idle_rss_median_bytes"]["median"])} MiB</td><td>{number(gpui["idle_cpu_percent_one_core"]["median"])}%</td></tr></tbody></table></div><p class="muted" style="font-size:13px;margin-top:14px">The direct integration removes Kit, GPUI Fast, Kit assets, and the application-level Tokio runtime. Its Linux build selects X11 and a size-oriented profile: z, fat LTO, one codegen unit, panic=abort, stripped symbols, and unwind tables disabled for compiled crates. The backend and build profile also change, so the difference does not isolate Kit's cost. No executable is compressed. Both integrations appear independently throughout this report; Kit sources, executable, and measurements are preserved in <code>gpui-kit-baseline/</code>.</p></section>
<section><h2>The measurements</h2><div class="grid">{charts}</div><p class="muted" style="margin-top:16px;font-size:13px">Median of three runs. Within each run, memory is the median of samples; CPU is consumed CPU time divided by elapsed time. MiB = 1,048,576 bytes. Lower values mean fewer resources consumed in this workload.</p></section>
<section><div class="table-wrap"><table><thead><tr><th>Prototype</th><th>ELF executable</th><th>Gzipped executable</th><th>App code lines</th><th>Build lines</th><th>RSS</th><th>PSS</th><th>Idle CPU</th></tr></thead><tbody>{table}</tbody></table></div>
<p class="muted" style="font-size:13px;margin-top:14px">App lines: <code>main.zig</code> for NanoUI, <code>main.go</code> for MyGo, archived <code>main.rs</code> for GPUI Kit, and <code>main.rs</code> + <code>search.rs</code> for gpui-pre. Blank lines and whole-line comments are excluded from code lines; physical lines include them. Build lines cover <code>build.zig + build.zig.zon</code>, <code>go.mod</code>, or <code>Cargo.toml</code>, including blanks. Dependencies, lockfiles, READMEs, and measurement scripts are excluded. Language formatters differ: a Rust builder chain often occupies several lines. Line count measures text volume, not code quality.</p></section>
{build_section}
<section><h2>The four apps</h2><p class="muted">Actual Linux windows captured after the first run, outside the measurement interval. All four integrations also displayed the 14 containers read directly from Docker outside the measurements. Click an image to enlarge it. Screenshots preserve the prototypes' original French labels; the report itself is in English.</p><div class="grid">{screenshots}</div><p class="muted" style="font-size:13px;margin-top:16px">Shared scope: all containers; name, image, state, and status columns; search; manual Refresh; a dark theme; and virtualized rows. Logs, terminals, Docker controls, and container resource monitoring are outside this prototype. Typography and row density follow each toolkit, so the interfaces are not pixel-identical.</p></section>
<section><h2>Code quality: a source review</h2><div class="grid">
<article class="card"><h3 style="color:#eec26d">Zig + NanoUI</h3><p>State and ownership are explicit: a snapshot owns its arena, and the worker returns its result to the UI thread. The virtual list builds only visible rows. Toolkit components supply the text field, button, and row layout.</p><p>The implementation manually manages allocations, arena cleanup, a thread, a toolkit callback, and filtered indices. File loading uses <code>std.Io.Dir.readFileAlloc</code>; Docker runs through <code>std.process.run</code> with an argument array, bounded stdout/stderr, and a standard-library timeout. The runtime I/O service comes from <code>std.process.Init.io</code>. There are no application-declared libc file/process functions, shell command, or external timeout utility.</p><p class="muted">Assessment: compact native Zig code using the same level of portable I/O abstraction as the other prototypes. Arena ownership and the worker-to-UI handoff remain explicit maintenance costs.</p></article>
<article class="card"><h3 style="color:#77d7e6">Go + MyGo</h3><p>The standard library covers JSON, files, and subprocess timeouts directly. A goroutine loads rows; <code>RunOnMain</code> publishes the result. <code>ui.Table</code> provides headers and virtualization. Loading, filtering, and rendering fit in one file.</p><p>Garbage collection removes manual string-lifetime management. The executable includes the Go runtime. A bounded writer caps Docker output, and a failed refresh preserves the previous inventory.</p><p class="muted">Assessment: the most direct maintenance path in these prototypes, particularly for a PHP/Node developer. This is a limited judgment about this implementation, not a conclusion about full applications.</p></article>
<article class="card"><h3 style="color:#beacf5">Rust + GPUI Kit</h3><p>GPUI Kit 0.8.0 with GPUI Fast 0.1.10 supplies <code>Input</code>, <code>Button</code>, and the virtualized <code>DataTable</code>. Application logic occupies 301 code lines in one file; text editing belongs to the library.</p><p>A GPUI worker loads data and uses a temporary Tokio runtime for the Docker subprocess, timeout, and bounded output. Sources and measurements are preserved from the archived integration.</p><p class="muted">Tradeoff: less local widget code to maintain, with a measured {mib(kit["binary_bytes"])} MiB executable. The different backend and build profile prevent attributing the entire size gap to Kit.</p></article>
<article class="card"><h3 style="color:#85e2bf">Rust + gpui-pre</h3><p>An independent implementation using gpui-pre 0.3.9 directly, based on Zed snapshot 93d7456. The view uses <code>div</code>, <code>uniform_list</code>, and a local search field connected to GPUI's native text input. The button is a clickable element.</p><p>GPUI's executor loads data; <code>async-process</code> runs Docker with bounded output and cancellation on drop. A GPUI timer enforces the timeout. There is no application polling loop.</p><p class="muted">Tradeoff: more local text editing, selection, and clipboard code. Line counts include <code>search.rs</code>; NanoUI, MyGo, and Kit provide their text fields through libraries. The local field has a non-blinking caret and lacks drag selection and horizontal text scrolling.</p></article>
</div><p class="muted" style="margin-top:16px">Common source-level properties: I/O runs off the UI thread, refreshes cannot overlap, output is capped at 4 MiB, the Docker command has a 10-second limit, errors remain visible, and the apps do not poll. Loading and filtering still scale with row count; virtualization limits rendering work. No automated correctness tests, audit, load profile, or accessibility verification was performed.</p></section>
<section><h2>Equivalent portable loading APIs</h2><p>All four apps use their language or runtime's portable file/process abstractions. Each can read the same JSON snapshot, or invoke the Docker CLI directly with separate arguments. No app-specific Linux syscall wrapper or external timeout command is used in the current Zig implementation.</p><div class="table-wrap"><table><thead><tr><th>Integration</th><th>Snapshot loading</th><th>Docker subprocess and deadline</th></tr></thead><tbody><tr><th>Zig + NanoUI</th><td><code>std.Io.Dir.readFileAlloc</code></td><td><code>std.process.run</code>, argv array, stdout/stderr limits, <code>std.Io.Timeout</code>.</td></tr><tr><th>Go + MyGo</th><td>Go standard-library file I/O.</td><td><code>os/exec</code> with context deadline and bounded output.</td></tr><tr><th>Rust + GPUI Kit</th><td>Rust standard-library file I/O.</td><td>Tokio process, timeout, and bounded output.</td></tr><tr><th>Rust + gpui-pre</th><td>Rust standard-library file I/O.</td><td><code>async-process</code>, GPUI timer, and bounded output.</td></tr></tbody></table></div><p class="muted" style="font-size:13px;margin-top:14px">Equivalent abstraction level does not mean identical implementation: each runtime still maps these APIs to the host OS. The former Zig version explicitly declared libc <code>fopen/fread/popen</code> wrappers and used GNU <code>timeout</code>. Those were not raw Linux syscalls, but the resulting portability mismatch was real. That implementation is superseded. The toolkit's GTK/Cairo and libc linkage on Linux remains a platform backend detail, just as the other toolkits have platform backends.</p></section>
<section><h2>What this comparison measures</h2><div class="grid"><article class="card"><h3>A short, reproducible protocol</h3><ol><li>Capture <code>docker ps --all --no-trunc --format '{{{{json .}}}}'</code> locally, retaining the five fields used by the prototypes.</li><li>All four integrations read the same 14-row NDJSON snapshot, with the same SHA-256 digest.</li><li>Three new runs of the portable Zig implementation replace its original libc-based series. The three MyGo, three Kit, and three gpui-pre runs are retained, giving twelve current runs. The superseded Zig implementation and measurements are archived in <code>nanoui-libc-baseline/</code> and excluded from the charts. All builds were finished before the new measurements; these series were not collected simultaneously.</li><li>Normalize the client surface to 1,000 × 680 pixels; use <code>GPUI_X11_SCALE_FACTOR=1</code> for gpui-pre to match the observed toolkit scale. Keep the window active and pointer outside it, then allow four seconds to settle and measure twenty seconds at idle.</li><li>Sample <code>/proc</code> every 500 ms for RSS, PSS, and CPU time of the process and its descendants.</li><li>Capture the window after measurement, then close only the process group started for that run.</li></ol></article><article class="card"><h3>Limits that affect interpretation</h3><ul><li>CPU covers a static window at idle, not scrolling, searching, repeated refreshes, or Docker's cost.</li><li>RSS counts shared pages in full; PSS apportions them across processes. Neither alone covers all GPU allocations.</li><li>100% CPU means one logical core. A displayed 0.00% means below the resolution of this measurement window, not proven zero work.</li><li>Executable size excludes dynamically loaded system libraries and the Docker CLI; it is not a self-contained package size.</li><li>These are warm-cache runs on a shared desktop with other applications. They do not establish a universal ranking.</li><li>The full FerryDock application is not measured; its scope is much broader than these minimal lists.</li></ul></article></div></section>
<section><h2>The backend matters as much as the language</h2><div class="callout"><p>On Linux, NanoUI renders on the <strong>CPU</strong> and presents through Cairo/GTK 3. MyGo offers GPU OpenGL rendering and a CPU fallback; an earlier diagnostic launch on this machine reported GPU rendering with <code>MYGO_FRAME_STATS=all</code>, outside the measured runs. Both use GTK 3 through X11/XWayland here. gpui-pre 0.3.9 uses its own X11 window and wgpu rendering; GPUI Kit uses GPUI Fast. Observed graphics libraries are retained in the raw data. MyGo loaded GLX/Mesa libraries, while NanoUI did not load OpenGL.</p><p>NanoUI describes itself as originating from a port of MyGo's core to Zig, retaining its architecture. The frameworks are related, with different feature coverage. At the pinned revision, NanoUI documents missing accessibility and several desktop APIs.</p><small>Primary sources: <a href="https://github.com/justrach/nanoui/blob/d61e253205472cef0854367125295d87c810c5b3/README.md#platforms">NanoUI platforms</a>, <a href="https://github.com/justrach/nanoui/blob/d61e253205472cef0854367125295d87c810c5b3/README.md#credits">NanoUI origins</a>, <a href="https://github.com/egoist/mygo/blob/5fb60098a44a4c629cbdeac5f0ff80ce2f843c2f/docs/ui/README.md">MyGo native UI</a>, <a href="https://docs.rs/gpui-pre/0.3.9/gpui/">gpui-pre 0.3.9</a>.</small></div></section>
<section id="other-platforms"><h2>What to expect on Windows and macOS</h2>
<p class="lede">A portability and rendering outlook, not a benchmark. None of these four prototypes has been built, launched, or measured on Windows or macOS in this comparison. The platform entries below describe the pinned toolkits' documented backends or published source, followed by implications inferred for these apps.</p>
<div class="table-wrap"><table><thead><tr><th>Integration</th><th>Windows backend</th><th>macOS backend</th><th>Work specific to this prototype</th></tr></thead><tbody>
<tr><th>Zig + NanoUI</th><td>Win32 window/input; CPU rasterizer presented with GDI.</td><td>AppKit window/input; Metal rendering and CoreText.</td><td>File loading, process launch, timeout, and allocation now use Zig standard-library abstractions. Docker is launched directly with arguments, with no Linux shell or GNU timeout dependency. Target builds and native behavior remain unverified outside Linux.</td></tr>
<tr><th>Go + MyGo</th><td>GPU rendering through Direct3D 11.</td><td>GPU rendering through Metal.</td><td>JSON and subprocess code use Go's standard library; the prototype does not depend on the external Linux timeout command. Target builds, Docker discovery, and desktop interaction still need verification.</td></tr>
<tr><th>Rust + GPUI Kit / Fast</th><td>GPUI Fast's published target dependencies include Win32, Direct3D 11, and DirectWrite.</td><td>Published Apple target dependencies include Metal bindings; this target build's selected renderer has not been verified.</td><td>Build the pinned Kit/Fast stack for the target. Its availability in upstream source does not establish that this archived app builds or behaves correctly on that target.</td></tr>
<tr><th>Rust + gpui-pre</th><td>The 0.3.9 platform crate selects its Windows implementation; published dependencies include Direct3D 11 and DirectWrite.</td><td>The 0.3.9 platform crate selects its macOS implementation, with the Apple Metal renderer.</td><td>The measured Linux build selects X11. Other targets select their own platform implementations, rather than running this ELF file. Review target build settings and the local search field's platform shortcuts, IME, and clipboard behavior.</td></tr>
</tbody></table></div>
<p class="muted" style="font-size:13px;margin-top:14px">Sources for the platform matrix: <a href="https://github.com/justrach/nanoui/blob/d61e253205472cef0854367125295d87c810c5b3/README.md#platforms">NanoUI platform matrix at the pinned commit</a>; <a href="https://github.com/egoist/mygo/blob/5fb60098a44a4c629cbdeac5f0ff80ce2f843c2f/docs/ui/README.md">MyGo native backends at the pinned commit</a>; <a href="https://docs.rs/crate/gpui-fast/0.1.10/source/Cargo.toml">GPUI Fast 0.1.10 target dependencies</a>; <a href="https://docs.rs/crate/gpui-pre-platform/0.3.9/source/Cargo.toml">gpui-pre platform selection</a>, <a href="https://docs.rs/crate/gpui-pre-windows/0.3.9/source/Cargo.toml">Windows dependencies</a>, and <a href="https://docs.rs/crate/gpui-pre-apple/0.3.9/source/Cargo.toml">Apple renderer dependencies</a>. These establish available platform paths, not execution proof for our prototypes.</p>
<div class="grid" style="margin-top:24px"><article class="card"><h3>How the windows would look</h3><p><strong>Expected, not captured:</strong> the same container rows, dark palette, columns, search, and Refresh layout should remain recognizable after a port. All four use toolkit-drawn content; switching OS does not automatically replace those controls with standard Windows or AppKit widgets.</p><p>Window decorations, fonts, text rasterization, DPI scaling, and keyboard conventions can differ. On Mac, the local gpui-pre input deserves particular attention because it currently binds Ctrl-based editing shortcuts. Keeping the current dark theme would also require retaining the explicit theme choices.</p><p class="muted">No Windows/Mac screenshots or mockups are presented as real output.</p></article>
<article class="card"><h3>How size, memory, and CPU might change</h3><p><strong>Inference:</strong> NanoUI's largest architectural change is on Mac, where its Linux CPU renderer is replaced by Metal. MyGo also switches from OpenGL to platform-specific GPU rendering. Both GPUI variants use target-specific graphics and text dependencies. Idle fixed costs, active rendering costs, and executable contents can therefore change.</p><p>The 14-row workload is small, so framework, font, window, and driver overhead can outweigh the data itself. No justified Windows/Mac MiB estimate or ordering follows from the Linux results. Apple Silicon and x86-64 builds also differ; a universal Mac executable includes more than one architecture.</p><p class="muted">GPU rendering alone does not guarantee lower idle RAM or CPU. The measured Linux ranking must be remeasured on each target.</p></article></div>
<div class="callout" style="margin-top:24px"><strong>What a fair follow-up would measure.</strong> Build release executables for each target, run the same JSON snapshot and display size, and report executable size separately from installers, app bundles, and debug symbols. Keep Docker engine/VM consumption outside UI memory figures; the snapshot already avoids that dependency during sampling. Windows working-set measures and macOS memory/footprint measures do not map exactly to Linux RSS/PSS, so record each metric explicitly. Then observe live Docker loading and the native text field separately. No cross-platform run or port is included in the current work.</div>
</section>
<section><h2>Environment and pinned versions</h2><div class="grid"><article class="card"><p><strong>{html.escape(host['cpu'])}</strong><br>{host['logical_cpus']} logical CPUs · {number(int(host['memory_total_kib'].split()[1]) / 1048576,1)} GiB RAM<br>{html.escape(host['system'])}<br>Plasma Wayland, XWayland display <code>:0</code></p><p class="muted">Containers, Docker context, FerryDock sources, and FerryDock dependencies were left unchanged. Experiment repositories and toolchains are local to this comparison.</p></article><article class="card">{versions}</article></div></section>
<section><details><summary>View all twelve runs and raw data</summary><div class="table-wrap" style="margin-top:20px"><table><thead><tr><th>Run</th><th>Median RSS</th><th>Median PSS</th><th>CPU</th><th>Idle interval</th><th>Sampled peak RSS</th></tr></thead><tbody>{details}</tbody></table></div><p class="muted" style="font-size:13px;margin-top:12px">Sampled peak RSS is the largest sample after the window becomes visible, including warmup; it is not an absolute startup peak. The duration column is the measured idle interval.</p><a class="download" href="data:application/json;base64,{raw}" download="ferrydock-gui-comparison.json">Download measurement JSON</a></details></section>
<footer>Generated {stamp} · Self-contained HTML report with embedded captures and measurements. Sources: <code>experiments/nanoui-containers</code>, <code>experiments/mygo-containers</code>, and <code>experiments/gpui-containers</code>; archived Kit sources: <code>gpui-kit-baseline/src</code> beside this report. Protocol: <code>experiments/measure.py</code>. No commit or push.</footer>
</main></body></html>'''
(OUT / "rapport.html").write_text(page)
print(json.dumps({key: {"binary_bytes": row["binary_bytes"], "lines": row["lines"], "rss_mib": row["idle_rss_median_bytes"]["median"] / 1048576, "pss_mib": row["idle_pss_median_bytes"]["median"] / 1048576, "cpu_percent": row["idle_cpu_percent_one_core"]["median"]} for key, row in rows.items()}, indent=2))
