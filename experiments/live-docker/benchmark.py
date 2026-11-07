#!/usr/bin/env python3
"""Time isolated optimized builds without downloading dependencies or clearing shared caches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".verification/wayland-refresh-20261107"
APPS = {
    "nanoui": ("nanoui-containers", "nanoui-live-containers"),
    "mygo": ("mygo-containers", "mygo-containers"),
    "gpui": ("gpui-containers", "gpui-live-containers"),
    "rune": ("rune-containers", "rune-live-containers"),
}
PINS = {
    "nanoui": "e26765e8422f0a719e3bb90d9d97067d92d495b7",
    "mygo": "1dfa5a1f912b75de41f8732ce1d38e1cd9a18421",
    "gpui": "0.3.11",
    "rune": "f73f72cdc563534e4f7de9f5a79bed007ac42384",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(name, number):
    folder, executable = APPS[name]
    source = ROOT / "experiments/live-docker" / folder
    directory = OUT / "builds" / f"{name}-{number}"
    directory.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env.pop("RUSTC_WRAPPER", None)
    env.pop("RUSTC_WORKSPACE_WRAPPER", None)
    env.pop("GOFLAGS", None)
    cwd = ROOT
    if name in ("gpui", "rune"):
        env.update(CARGO_TARGET_DIR=str(directory / "target"), CARGO_BUILD_JOBS="4", CARGO_INCREMENTAL="0", CARGO_NET_OFFLINE="true", RUSTFLAGS="-C force-unwind-tables=no")
        command = ["cargo", "build", "--release", "--locked", "--offline", "--manifest-path", str(source / "Cargo.toml")]
        binary = directory / "target/release" / executable
        cache = "Empty Cargo target; registry sources pre-downloaded; incremental and compiler wrappers disabled"
        compiler = subprocess.check_output(["rustc", "--version"], text=True).strip()
        profile = "opt-level=3, fat LTO, codegen-units=1, panic=abort, strip=true, force-unwind-tables=no"
    elif name == "mygo":
        env.update(CGO_ENABLED="0", GOCACHE=str(directory / "go-cache"), GOMAXPROCS="4", GOPROXY="off", GOSUMDB="off", GOTOOLCHAIN="local")
        cwd = source
        binary = directory / executable
        command = ["go", "build", "-buildvcs=false", "-p", "4", "-trimpath", "-tags", "mygo_noinspector", "-ldflags", "-s -w -X github.com/egoist/mygo.production=1", "-o", str(binary), "."]
        cache = "Empty Go build cache including standard library; module sources pre-downloaded"
        compiler = subprocess.check_output(["go", "version"], text=True).strip()
        profile = "Default optimized Go compiler, CGO_ENABLED=0, trimpath, inspector disabled, production=1, stripped, VCS stamping disabled"
    else:
        env.update(ZIG_GLOBAL_CACHE_DIR=str(directory / "zig-global"), ZIG_LOCAL_CACHE_DIR=str(directory / "zig-local"))
        env.pop("ZIG_LOCAL_PKG_DIR", None)
        command = ["zig", "build", "--build-file", str(source / "build.zig"), "--system", str(OUT / "packages"), "-Doptimize=ReleaseFast", "-j4", "--prefix", str(directory / "install")]
        binary = directory / "install/bin" / executable
        cache = "Empty Zig local and global build caches; pre-fetched source packages read-only through --system"
        compiler = "zig " + subprocess.check_output(["zig", "version"], text=True).strip()
        profile = "ReleaseFast, strip=true, LLVM backend"
    timed = ["/usr/bin/time", "-f", '{"wall_seconds":%e,"user_seconds":%U,"system_seconds":%S,"max_process_rss_kib":%M,"exit_code":%x}', "-o", str(directory / "time.json"), *command]
    started = time.monotonic()
    with (directory / "build.log").open("w") as log:
        result = subprocess.run(timed, cwd=cwd, env=env, stdout=log, stderr=log)
    elapsed = time.monotonic() - started
    timing_lines = (directory / "time.json").read_text().splitlines()
    timing = json.loads(next(line for line in reversed(timing_lines) if line.startswith("{")))
    record = {
        "name": name, "run": number, "revision": PINS[name], "compiler": compiler,
        "profile": profile, "cache": cache, "jobs": 4, "downloads_in_timing": False,
        "filesystem_cache": "Not flushed; no OS-wide cache or service changes",
        "kernel": platform.release(), "command": command, "elapsed_seconds": elapsed,
        **timing,
    }
    if result.returncode == 0:
        record.update(binary_bytes=binary.stat().st_size, binary_sha256=sha(binary))
        (OUT / "bin").mkdir(exist_ok=True)
        shutil.copy2(binary, OUT / "bin" / name)
    (directory / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)
    if result.returncode:
        raise SystemExit(f"Build failed; see {directory / 'build.log'}")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=APPS)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--start", type=int, default=1)
    args = parser.parse_args()
    records = [build(args.name, number) for number in range(args.start, args.start + args.runs)]
    summary = {"name": args.name, "runs": records, "median_seconds": statistics.median(r["elapsed_seconds"] for r in records), "min_seconds": min(r["elapsed_seconds"] for r in records), "max_seconds": max(r["elapsed_seconds"] for r in records)}
    (OUT / f"{args.name}-builds.json").write_text(json.dumps(summary, indent=2) + "\n")
