#!/usr/bin/env python3
"""Assemble measured build/runtime results for the report without altering historical rows."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".verification/wayland-refresh-20261107"
MEASUREMENT_DATE = "2026-11-07"
CONFIG = {
    "nanoui": {"label": "Zig + NanoUI · updated", "client": "NanoUI 0.12.0 · Zig Docker SDK 1.0.0", "pin": "NanoUI e26765e8422f0a719e3bb90d9d97067d92d495b7", "url": "https://github.com/justrach/nanoui/tree/e26765e8422f0a719e3bb90d9d97067d92d495b7", "color": "#eec26d", "source": ["nanoui-containers/src/main.zig"], "manifest": "nanoui-containers/build.zig"},
    "mygo": {"label": "Go + MyGo · updated", "client": "MyGo 0.8.1 · Moby client v0.6.2", "pin": "MyGo 1dfa5a1f912b75de41f8732ce1d38e1cd9a18421", "url": "https://github.com/egoist/mygo/tree/1dfa5a1f912b75de41f8732ce1d38e1cd9a18421", "color": "#77d7e6", "source": ["mygo-containers/main.go"], "manifest": "mygo-containers/go.mod"},
    "gpui": {"label": "Rust + gpui-pre · updated", "client": "gpui-pre 0.3.11 · Bollard 0.21.1", "pin": "gpui-pre / gpui-pre-platform 0.3.11", "url": "https://docs.rs/gpui-pre/0.3.11/gpui/", "color": "#85e2bf", "source": ["gpui-containers/src/main.rs", "gpui-containers/src/search.rs"], "manifest": "gpui-containers/Cargo.toml"},
    "rune": {"label": "Rust + Rune · production", "client": "Rune f73f72c · Bollard 0.21.1", "pin": "Rune / rune-kit f73f72cdc563534e4f7de9f5a79bed007ac42384", "url": "https://github.com/anomalyco/rune/tree/f73f72cdc563534e4f7de9f5a79bed007ac42384", "color": "#d7a2da", "source": ["rune-containers/src/main.rs"], "manifest": "rune-containers/Cargo.toml"},
}


def count_lines(paths):
    lines = [line for path in paths for line in (ROOT / "experiments/live-docker" / path).read_text().splitlines()]
    return {"code": sum(bool(line.strip()) and not line.lstrip().startswith("//") for line in lines), "physical": len(lines)}


def source_hash(paths):
    return {path: hashlib.sha256((ROOT / "experiments/live-docker" / path).read_bytes()).hexdigest() for path in paths}


apps = {}
for name, config in CONFIG.items():
    builds = json.loads((OUT / f"{name}-builds.json").read_text())
    checks = json.loads((OUT / f"{name}-functional.json").read_text())
    runs = [json.loads((OUT / f"{name}-{run}.json").read_text()) for run in (1, 2, 3)]
    binary = OUT / "bin" / name
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    assert len(builds["runs"]) == 3
    assert all(build["binary_sha256"] == digest for build in builds["runs"])
    assert checks["refresh_observed"] and checks["recovery"]
    assert checks["binary_sha256"] == digest
    for run in runs:
        assert run["binary_sha256"] == digest
        assert run["backend"] == "native Wayland / COSMIC"
        log = (OUT / f"{name}-{run['run']}.log").read_text()
        if name in ("nanoui", "mygo"):
            ids_hash = re.search(r"ids_sha256=([0-9a-f]{64})", log)[1]
        else:
            ids = re.search(r" ids=([^\n]+)", log)[1].split(",")
            ids_hash = hashlib.sha256("\n".join(ids).encode()).hexdigest()
        assert ids_hash == checks["ids_sha256"]
        run.update(matches_initial_inventory=True, ids_sha256=ids_hash)
    app = dict(config)
    app["label"] = f"{config['label'].rsplit(' · ', 1)[0]} · {MEASUREMENT_DATE}"
    app["measurement_date"] = MEASUREMENT_DATE
    if name == "nanoui":
        renderer = json.loads((OUT / "nanoui-renderer.json").read_text())
        assert renderer["binary_sha256"] == digest
        app["renderer_observation"] = renderer
    app.update(
        runs=runs, lines=count_lines(config["source"]), build_lines=count_lines([config["manifest"]]),
        binary_bytes=binary.stat().st_size, binary_sha256=digest,
        size_label="ELF executable", historical_snapshot_baseline=None,
        all_runs_match_reference_ids=True, screenshot=str(OUT / f"{name}-1-window.png"),
        measurement_label=f"{MEASUREMENT_DATE} · Wayland · 3 × 20 s", native_input_observation=checks,
        clean_build=builds, profile=builds["runs"][0]["profile"],
        build_observation={"elapsed_s": builds["median_seconds"], "cache": "Median of 3 clean production builds; sources pre-fetched; 4 jobs"},
        source_sha256=source_hash(config["source"] + [config["manifest"]]),
    )
    for field in ("idle_rss_median_bytes", "idle_pss_median_bytes", "idle_cpu_percent_one_core", "initial_load_ms"):
        values = [run[field] for run in runs]
        app[field] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
    apps[name] = app

summary = {"apps": apps, "protocol": "Native Wayland, DISPLAY removed; 1000×680 requested window, captured surface dimensions recorded; owned window activated; 4s warmup, 20s idle, 500ms samples; 3 runtime runs and 3 isolated optimized builds per app; dependency downloads excluded from build timing; no OS-wide cache flushing; native Refresh, search, failure and recovery checks on the measured production binaries", "build_time_scope": "Empty language build caches. Go recompiles its packages; Cargo uses the installed Rust standard library; Zig rebuilds with empty local/global caches. Dependency sources and OS filesystem caches remain available."}
summary["host"] = {"cpu": next(line.partition(":")[2].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), "logical_cpus": os.cpu_count(), "kernel": platform.release(), "desktop": "COSMIC", "window_system": "Wayland"}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({name: {"build_seconds": app["clean_build"]["median_seconds"], "rss_mib": app["idle_rss_median_bytes"]["median"] / 1048576, "pss_mib": app["idle_pss_median_bytes"]["median"] / 1048576, "refresh": app["native_input_observation"]["refresh_observed"]} for name, app in apps.items()}, indent=2))
