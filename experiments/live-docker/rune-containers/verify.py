#!/usr/bin/env python3
"""Drive Rune through AT-SPI and measure Wayland or XWayland; Docker is read-only.

Requires PyGObject with Atspi 2.0. Artifacts go to the ignored verification tree.
"""
import argparse
import hashlib
import http.client
import http.server
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import statistics
import subprocess
import tempfile
import threading
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, Gio, GLib

ROOT = Path(__file__).resolve().parents[3]
APP = Path(__file__).resolve().parent
OUT = ROOT / ".verification/rune"
BINARY = APP / "build/rune-live-containers"


def wait_for(fn, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {fn}")


def application(pid):
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        child = desktop.get_child_at_index(i)
        if child.get_process_id() == pid:
            return child


def nodes(app):
    if app is None:
        return
    yield app
    for i in range(app.get_child_count()):
        yield from nodes(app.get_child_at_index(i))


def strings(app):
    while GLib.MainContext.default().pending():
        GLib.MainContext.default().iteration(False)
    result = []
    for node in nodes(app):
        node.clear_cache()
        name = node.get_name()
        if name:
            result.append(name)
        text = node.get_text_iface()
        if text:
            try:
                result.append(Atspi.Text.get_text(text, 0, -1))
            except GLib.Error:
                # Clearing the field removes this interface between the two calls.
                pass
    return result


def has(app, value):
    return any(value in text for text in strings(app))


def edit(app, value):
    field = next(n for n in nodes(app) if n.get_name() == "Search containers")
    field.clear_cache()
    assert field.get_component_iface().grab_focus()
    wait_for(lambda: field.get_state_set().contains(Atspi.StateType.FOCUSED))
    editable = field.get_editable_text_iface()
    if editable:
        assert editable.set_text_contents(value)
        return
    wtype = os.environ.get("WTYPE", str(OUT / "wtype/build/wtype"))
    if value:
        subprocess.run([wtype, value], check=True, timeout=5)


def refresh(app):
    button = next(n for n in nodes(app) if n.get_name() == "Refresh")
    assert button.get_action_iface().do_action(0)


def launch(stem, endpoint=None, backend="wayland"):
    env = dict(os.environ, WINIT_UNIX_BACKEND="wayland" if backend == "wayland" else "x11")
    env.pop("DISPLAY" if backend == "wayland" else "WAYLAND_DISPLAY", None)
    if backend == "xwayland":
        env["WINIT_X11_SCALE_FACTOR"] = "1"
    env.pop("CONTAINER_SNAPSHOT", None)
    if endpoint:
        env["DOCKER_HOST"] = endpoint
    log = (OUT / f"{stem}.log").open("w")
    proc = subprocess.Popen([str(BINARY)], env=env, stdout=log, stderr=log, start_new_session=True)
    return proc, log


def stop(proc, log):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except ProcessLookupError:
        pass
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    log.close()


class Proxy(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    mode = "live"
    listings = 0
    real_socket = "/var/run/docker.sock"


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        listing = self.path.split("?", 1)[0].endswith("/containers/json")
        if not (listing or self.path in ("/version", "/_ping")):
            self.send_error(403)
            return
        if listing:
            self.server.listings += 1
            mode = self.server.mode
            if mode == "error":
                body = b'{"message":"Controlled read-only proxy failure"}'
                self.send_response(500)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if mode == "timeout":
                time.sleep(11)
                return
        conn = http.client.HTTPConnection("localhost", timeout=5)
        conn.sock = socket.socket(socket.AF_UNIX)
        conn.sock.settimeout(5)
        conn.sock.connect(self.server.real_socket)
        try:
            conn.request("GET", self.path)
            reply = conn.getresponse()
            body = reply.read()
            self.send_response(reply.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        finally:
            conn.close()


def functional():
    reference = json.loads(subprocess.check_output(["curl", "--silent", "--show-error", "--unix-socket", "/var/run/docker.sock", "http://localhost/containers/json?all=true"]))
    total = len(reference)
    assert total, "Need existing containers to exercise filtering and retained data"
    expected_ids = sorted(row["Id"] for row in reference)
    name = reference[0]["Names"][0].lstrip("/")
    expected_matches = sum(any(name.lower() in value.lower() for value in (", ".join(n.lstrip("/") for n in row["Names"]), row["Image"], row["State"])) for row in reference)
    with tempfile.TemporaryDirectory(prefix="rune-docker-") as temporary:
        endpoint = Path(temporary) / "docker.sock"
        with Proxy(str(endpoint), Handler) as proxy:
            threading.Thread(target=proxy.serve_forever, daemon=True).start()
            proc, log = launch("functional", f"unix://{endpoint}")
            try:
                app = wait_for(lambda: application(proc.pid))
                wait_for(lambda: has(app, f"{total} / {total} containers"))
                assert "Window backend: Wayland" in (OUT / "functional.log").read_text()
                loaded = (OUT / "functional.log").read_text().split(" ids=")[-1].strip().splitlines()[0].split(",")
                assert loaded == expected_ids
                table = next(n for n in nodes(app) if n.get_role_name() == "table")
                assert table.get_component_iface().grab_focus()
                wtype = os.environ.get("WTYPE", str(OUT / "wtype/build/wtype"))
                subprocess.run([wtype, "-P", "End", "-p", "End"], check=True, timeout=5)
                wait_for(lambda: has(app, reference[-1]["Names"][0].lstrip("/")))
                subprocess.run([wtype, "-P", "Home", "-p", "Home"], check=True, timeout=5)
                wait_for(lambda: has(app, name))
                edit(app, name.upper())
                wait_for(lambda: has(app, f"{expected_matches} / {total} containers"))
                edit(app, "__rune_no_container_matches__")
                wait_for(lambda: has(app, f"0 / {total} containers"))
                edit(app, "")
                wait_for(lambda: has(app, f"{total} / {total} containers"))
                before = proxy.listings
                refresh(app)
                wait_for(lambda: proxy.listings == before + 1)
                wait_for(lambda: has(app, f"{total} / {total} containers"))
                proxy.mode = "error"
                refresh(app)
                wait_for(lambda: has(app, "Controlled read-only proxy failure"))
                assert has(app, f"{total} / {total} containers")
                assert has(app, name)
                proxy.mode = "timeout"
                before = proxy.listings
                started = time.monotonic()
                refresh(app)
                wait_for(lambda: proxy.listings == before + 1)
                wait_for(lambda: has(app, "Loading…"))
                edit(app, "__rune_no_container_matches__")
                wait_for(lambda: not has(app, name))
                refresh_button = next(n for n in nodes(app) if n.get_name() == "Refresh")
                assert not refresh_button.get_state_set().contains(Atspi.StateType.ENABLED)
                wait_for(lambda: has(app, "Docker request exceeded 10 seconds"), timeout=13)
                timeout_elapsed = time.monotonic() - started
                assert 9.5 <= timeout_elapsed <= 13
                assert has(app, f"0 / {total} containers")
                proxy.mode = "live"
                edit(app, "")
                refresh(app)
                wait_for(lambda: has(app, f"{total} / {total} containers") and not has(app, "Cannot load containers"))
                assert proc.poll() is None
                result = {"backend": "native Wayland", "containers": total, "ids_match_daemon": True, "keyboard_table_navigation": True, "search_case_insensitive": True, "empty_search_results": True, "manual_refresh": True, "failed_refresh_retains_rows": True, "responsive_during_timeout": True, "refresh_disabled_while_busy": True, "timeout_seconds": timeout_elapsed, "recovery": True, "listing_requests": proxy.listings}
                (OUT / "functional.json").write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result), flush=True)
            finally:
                stop(proc, log)
                proxy.shutdown()


def measure(run, backend):
    spec = importlib.util.spec_from_file_location("live_measure", ROOT / "experiments/live-docker/measure.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    started = time.monotonic()
    stem = f"{backend}-{run}"
    proc, log = launch(stem, backend=backend)
    try:
        app = wait_for(lambda: application(proc.pid))
        wait_for(lambda: has(app, "containers · all states"))
        ready_after = time.monotonic() - started
        load_log = (OUT / f"{stem}.log").read_text()
        native_handle = "Wayland" if backend == "wayland" else "Xlib"
        assert f"Window backend: {native_handle}" in load_log
        loaded_ids = load_log.split(" ids=")[-1].strip().splitlines()[0]
        client_size = None
        if backend == "xwayland":
            window = subprocess.check_output(["xdotool", "search", "--all", "--onlyvisible", "--pid", str(proc.pid)], text=True).splitlines()[0]
            geometry = dict(line.split("=", 1) for line in subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", window], text=True).splitlines())
            client_size = [int(geometry["WIDTH"]), int(geometry["HEIGHT"])]
            assert client_size == [1000, 680], client_size
        time.sleep(4)
        before = helper.process_sample(proc.pid)
        samples = []
        idle_start = time.monotonic()
        while time.monotonic() - idle_start < 20:
            assert proc.poll() is None
            samples.append(helper.process_sample(proc.pid))
            time.sleep(0.5)
        after = helper.process_sample(proc.pid)
        elapsed = time.monotonic() - idle_start
        result = {"name": "rune", "run": run, "backend": f"Rune / wgpu / {backend} / COSMIC", "ready_with_data_seconds": ready_after, "warmup_seconds": 4, "idle_seconds": elapsed, "idle_cpu_percent_one_core": 100 * (after["cpu_seconds"] - before["cpu_seconds"]) / elapsed, "idle_rss_median_bytes": statistics.median(s["rss_bytes"] for s in samples), "idle_pss_median_bytes": statistics.median(s["pss_bytes"] for s in samples), "binary_bytes": BINARY.stat().st_size, "binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest(), "container_count": len(loaded_ids.split(",")), "dataset_sha256": hashlib.sha256(loaded_ids.encode()).hexdigest(), "client_size": client_size, "graphics_libraries": sorted({line.split()[-1] for line in Path(f"/proc/{proc.pid}/maps").read_text().splitlines() if any(p in line for p in ("/dri/", "libGL", "libEGL", "libvulkan"))}), "samples": samples}
        if backend == "xwayland":
            subprocess.run(["magick", "import", "-window", window, str(OUT / f"{stem}.png")], check=True, timeout=10)
        elif (OUT / "capture").exists():
            subprocess.run([str(OUT / "capture"), str(OUT / f"{stem}.png")], check=True, timeout=10)
            import struct
            result["client_size"] = list(struct.unpack(">II", (OUT / f"{stem}.png").read_bytes()[16:24]))
            assert result["client_size"] == [1000, 680], result["client_size"]
        result["x11_scale_factor"] = "1" if backend == "xwayland" else None
        (OUT / f"{stem}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "samples"}), flush=True)
    finally:
        stop(proc, log)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("functional", "measure"))
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument("--backend", choices=("wayland", "xwayland"), default="wayland")
    args = parser.parse_args()
    if args.mode == "functional" and args.backend != "wayland":
        parser.error("The functional driver currently targets native Wayland only")
    OUT.mkdir(parents=True, exist_ok=True)
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def accessibility(method, parameters):
        return bus.call_sync("org.a11y.Bus", "/org/a11y/bus", "org.freedesktop.DBus.Properties", method, parameters, None, Gio.DBusCallFlags.NONE, 5000, None)
    enabled = accessibility("Get", GLib.Variant("(ss)", ("org.a11y.Status", "IsEnabled"))).unpack()[0]
    try:
        if not enabled:
            accessibility("Set", GLib.Variant("(ssv)", ("org.a11y.Status", "IsEnabled", GLib.Variant("b", True))))
        functional() if args.mode == "functional" else measure(args.run, args.backend)
    finally:
        if not enabled:
            accessibility("Set", GLib.Variant("(ssv)", ("org.a11y.Status", "IsEnabled", GLib.Variant("b", False))))
