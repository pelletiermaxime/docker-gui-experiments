#!/usr/bin/env python3
"""Measure an owned native app on X11; no tests or Docker mutations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import time


def interrupted(signum, frame):
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, interrupted)

def process_sample(pid):
    """Sum the process and live descendants, including reaped-child CPU."""
    pending, seen = [pid], set()
    rss = pss = ticks = 0
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        base = Path(f"/proc/{current}")
        try:
            fields = (base / "stat").read_text().rsplit(")", 1)[1].split()
            ticks += sum(int(fields[i]) for i in (11, 12, 13, 14))
            memory = dict(line.split(":", 1) for line in (base / "smaps_rollup").read_text().splitlines() if ":" in line)
            rss += int(memory["Rss"].split()[0]) * 1024
            pss += int(memory["Pss"].split()[0]) * 1024
            for task in (base / "task").iterdir():
                pending.extend(map(int, (task / "children").read_text().split()))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return {"rss_bytes": rss, "pss_bytes": pss, "cpu_seconds": ticks / os.sysconf("SC_CLK_TCK"), "processes": len(seen)}


def measure(args, run):
    env = dict(os.environ, GDK_BACKEND="x11")
    env.update(SLINT_SCALE_FACTOR="1", QT_SCALE_FACTOR="1", QT_AUTO_SCREEN_SCALE_FACTOR="0", QT_ENABLE_HIGHDPI_SCALING="0", QT_QPA_PLATFORM="xcb", WINIT_UNIX_BACKEND="x11")
    env.pop("CONTAINER_SNAPSHOT", None)
    env.pop("WAYLAND_DISPLAY", None)
    if args.name == "gpui":
        # Match the observed 1x toolkit rendering of the other two prototypes.
        env["GPUI_X11_SCALE_FACTOR"] = "1"
    if args.name == "slint":
        env.update(WINIT_UNIX_BACKEND="x11", SLINT_SCALE_FACTOR="1", SLINT_BACKEND="winit-software")
    stem = args.output / f"{args.name}-{run}"
    samples = []
    with stem.with_suffix(".log").open("w") as log:
        started = time.monotonic()
        proc = subprocess.Popen([str(args.binary.resolve())], env=env, stdout=log, stderr=log, start_new_session=True)
        try:
            window = None
            while time.monotonic() - started < 15:
                if proc.poll() is not None:
                    raise RuntimeError(f"{args.name} exited {proc.returncode}; see {stem}.log")
                result = subprocess.run(["xdotool", "search", "--all", "--onlyvisible", "--pid", str(proc.pid)], env=env, capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    window = result.stdout.splitlines()[0]
                    break
                time.sleep(0.05)
            if window is None:
                raise RuntimeError("No visible window within 15 seconds")
            visible_after = time.monotonic() - started
            subprocess.run(["xdotool", "windowactivate", "--sync", window], env=env, capture_output=True, timeout=3, check=True)
            # The toolkits interpret WindowOptions.Height differently (frame vs
            # client). Normalize the captured client surface before sampling.
            subprocess.run(["xdotool", "windowsize", "--sync", window, "1000", "680"], env=env, capture_output=True, timeout=3, check=True)
            # Keep the pointer out of app windows to avoid hover animation.
            subprocess.run(["xdotool", "mousemove", "0", "0"], env=env, capture_output=True, timeout=3, check=True)
            while time.monotonic() - started < visible_after + args.warmup:
                if proc.poll() is not None:
                    raise RuntimeError("App exited during warmup")
                samples.append({"phase": "warmup", **process_sample(proc.pid)})
                time.sleep(0.25)
            before = process_sample(proc.pid)
            idle_start = time.monotonic()
            while time.monotonic() - idle_start < args.seconds:
                if proc.poll() is not None:
                    raise RuntimeError("App exited during measurement")
                samples.append({"phase": "idle", **process_sample(proc.pid)})
                time.sleep(0.5)
            after = process_sample(proc.pid)
            elapsed = time.monotonic() - idle_start
            # Screenshot capture runs after the measured interval.
            subprocess.run(["magick", "import", "-window", window, str(stem.with_suffix(".png"))], env=env, capture_output=True, timeout=10, check=True)
            idle = [s for s in samples if s["phase"] == "idle"]
            result = {
                "name": args.name, "run": run,
                "visible_after_seconds": visible_after,
                "warmup_seconds": args.warmup,
                "idle_seconds": elapsed,
                "idle_cpu_percent_one_core": 100 * (after["cpu_seconds"] - before["cpu_seconds"]) / elapsed,
                "idle_rss_median_bytes": statistics.median(s["rss_bytes"] for s in idle),
                "idle_pss_median_bytes": statistics.median(s["pss_bytes"] for s in idle),
                "sampled_peak_rss_bytes": max(s["rss_bytes"] for s in samples),
                "max_processes": max(s["processes"] for s in samples),
                "binary_bytes": args.binary.stat().st_size,
                "binary_sha256": hashlib.sha256(args.binary.read_bytes()).hexdigest(),
                "data_source": "live Docker Engine API via SDK",
                "docker_host": env.get("DOCKER_HOST", "library default"),
                "load_log": stem.with_suffix(".log").read_text(),
                "backend": env.get("FERRYDOCK_SLINT_BACKEND", "winit"),
                "renderer_requested": env.get("FERRYDOCK_SLINT_RENDERER"),
                "wgpu_backend_requested": env.get("WGPU_BACKEND"),
                "wgpu_adapter_requested": env.get("WGPU_ADAPTER_NAME"),
                "client_size": [1000, 680],
                "gpui_x11_scale_factor": env.get("GPUI_X11_SCALE_FACTOR") if args.name == "gpui" else None,
                "shared_libraries": sorted({line.split()[-1] for line in Path(f"/proc/{proc.pid}/maps").read_text().splitlines() if ".so" in line and line.split()[-1].startswith("/")}),
                "graphics_libraries": sorted({line.split()[-1] for line in Path(f"/proc/{proc.pid}/maps").read_text().splitlines() if any(part in line for part in ("/dri/", "libGL", "libEGL", "libvulkan"))}),
                "samples": samples,
            }
            stem.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps({k: v for k, v in result.items() if k != "samples"}), flush=True)
        finally:
            # Only the process group created above belongs to this run.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", type=int, required=True)
    parser.add_argument("--warmup", type=float, default=4)
    parser.add_argument("--seconds", type=float, default=20)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    measure(args, args.run)
