#!/usr/bin/env python3
"""Validate real native Wayland Docker clients and measure their production processes."""
import argparse
import contextlib
import hashlib
import http.client
import http.server
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import socketserver
import statistics
import struct
import subprocess
import tempfile
import threading
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, Gio, GLib

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".verification/wayland-refresh-20261107"
TITLES = {
    "mygo": "FerryDock · MyGo · live Docker",
    "nanoui": "FerryDock · NanoUI Live",
    "gpui": "FerryDock · Live GPUI",
    "rune": "FerryDock · Live Rune",
}
CAPTURE = OUT / "tools/capture"
FOCUS = OUT / "tools/focus"
WTYPE = OUT / "tools/wtype"
LOAD = re.compile(r"(?:containers=|Docker load: count=)(\d+).*?elapsed_ms=(\d+)")


def wait(fn, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        try:
            result = fn()
            if result:
                return result
        except GLib.Error:
            pass
        time.sleep(0.1)
    raise AssertionError(f"Condition was not observed: {fn}")


def tree(node):
    if node is None:
        return
    yield node
    for i in range(node.get_child_count()):
        yield from tree(node.get_child_at_index(i))


def app_for(pid):
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app.get_process_id() == pid:
            return app


@contextlib.contextmanager
def accessibility():
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def call(method, parameters):
        return bus.call_sync("org.a11y.Bus", "/org/a11y/bus", "org.freedesktop.DBus.Properties", method, parameters, None, Gio.DBusCallFlags.NONE, 5000, None)
    previous = call("Get", GLib.Variant("(ss)", ("org.a11y.Status", "IsEnabled"))).unpack()[0]
    if not previous:
        call("Set", GLib.Variant("(ssv)", ("org.a11y.Status", "IsEnabled", GLib.Variant("b", True))))
    try:
        yield
    finally:
        if not previous:
            call("Set", GLib.Variant("(ssv)", ("org.a11y.Status", "IsEnabled", GLib.Variant("b", False))))


class Proxy(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    mode = "live"
    listings = 0


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_HEAD(self):
        self.forward(True)

    def do_GET(self):
        self.forward(False)

    def forward(self, head):
        listing = self.path.split("?", 1)[0].endswith("/containers/json")
        if not (listing or self.path in ("/version", "/_ping")):
            self.send_error(403)
            return
        if listing:
            self.server.listings += 1
            if self.server.mode == "error":
                body = b'{"message":"Controlled read-only validation failure"}'
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    self.wfile.write(body)
                return
            if self.server.mode == "timeout":
                time.sleep(11)
                return
        conn = http.client.HTTPConnection("localhost", timeout=5)
        conn.sock = socket.socket(socket.AF_UNIX)
        conn.sock.settimeout(5)
        conn.sock.connect("/var/run/docker.sock")
        try:
            conn.request("HEAD" if head else "GET", self.path)
            response = conn.getresponse()
            body = response.read()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() in ("api-version", "content-type", "docker-experimental", "ostype"):
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head:
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    self.wfile.write(body)
        finally:
            conn.close()


class Client:
    def __init__(self, name, stem, endpoint=None, accessible=False, debug=False):
        self.name, self.stem = name, stem
        self.log_path = OUT / f"{stem}.log"
        self.log = self.log_path.open("w")
        env = dict(os.environ, GDK_BACKEND="wayland", GDK_SCALE="1", WINIT_UNIX_BACKEND="wayland", DOCKER_HOST=endpoint or "unix:///var/run/docker.sock")
        env.pop("DISPLAY", None)
        env.pop("CONTAINER_SNAPSHOT", None)
        if debug:
            env["NANOUI_DEBUG"] = "1"
        if accessible:
            env.pop("NO_AT_BRIDGE", None)
            env["GTK_MODULES"] = "atk-bridge"
        else:
            env["NO_AT_BRIDGE"] = "1"
        self.proc = subprocess.Popen([str(OUT / "bin" / name)], env=env, stdout=self.log, stderr=self.log, start_new_session=True)
        self.app = None
        self.search_text = ""

    def close(self):
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=5)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait()
        self.log.close()

    def ready(self):
        if self.proc.poll() is not None:
            raise AssertionError(f"App exited; see {self.log_path}")
        return LOAD.search(self.log_path.read_text())

    def elements(self):
        self.app = self.app or app_for(self.proc.pid)
        return list(tree(self.app)) if self.app else []

    def text(self):
        if self.name in ("mygo", "rune"):
            result = []
            for node in self.elements():
                node.clear_cache()
                result.append(node.get_name())
                text = node.get_text_iface()
                if text:
                    try:
                        result.append(Atspi.Text.get_text(text, 0, -1))
                    except GLib.Error:
                        pass
            return "\n".join(result)
        path = self.capture("state")
        return "\n".join(subprocess.check_output(["tesseract", str(path), "stdout", "--psm", mode], stderr=subprocess.DEVNULL, text=True, timeout=10) for mode in ("6", "11"))

    def capture(self, suffix):
        path = OUT / f"{self.stem}-{suffix}.png"
        subprocess.run([str(CAPTURE), str(path), TITLES[self.name]], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return path

    def activate(self):
        subprocess.run([str(FOCUS), TITLES[self.name]], check=True, stdout=subprocess.DEVNULL, timeout=10)

    def key(self, *args):
        self.activate()
        subprocess.run([str(WTYPE), *args], check=True, timeout=8)

    def edit(self, value):
        if self.name in ("mygo", "rune"):
            fields = [n for n in self.elements() if n.get_editable_text_iface()]
            if fields:
                fields[0].clear_cache()
                assert fields[0].get_editable_text_iface().set_text_contents(value)
                return
            field = next(n for n in self.elements() if n.get_role_name() == "entry")
            assert field.get_component_iface().grab_focus()
            self.key(value)
            return
        # Keep literal typing separate from special keys: the local Wayland
        # virtual keyboard uses a bounded printable-key map for pure text.
        self.key("-P", "End", "-p", "End", *[key for _ in self.search_text for key in ("-P", "BackSpace", "-p", "BackSpace")])
        if value:
            self.key("-s", "20", value)
        self.search_text = value

    def refresh(self):
        if self.name in ("mygo", "rune"):
            button = next(n for n in self.elements() if n.get_name() == "Refresh" and n.get_action_iface())
            assert button.get_action_iface().do_action(0)
        elif self.name in ("gpui", "nanoui"):
            self.key("-P", "F5", "-p", "F5")


def has_count(client, shown, total):
    return re.search(rf"\b{shown}\s*[/|]\s*{total}\s+containers", client.text(), re.I) is not None


def functional(name):
    reference = json.loads(subprocess.check_output(["curl", "-fsS", "--unix-socket", "/var/run/docker.sock", "http://localhost/containers/json?all=true"]))
    ids = sorted(row["Id"] for row in reference)
    digest = hashlib.sha256("\n".join(ids).encode()).hexdigest()
    total = len(reference)
    assert total
    query = reference[0]["Names"][0].lstrip("/")
    expected = sum(any(query.lower() in value.lower() for value in (", ".join(n.lstrip("/") for n in row["Names"]), row["Image"], row["State"])) for row in reference)
    with tempfile.TemporaryDirectory(prefix="ferrydock-wayland-") as temporary, accessibility():
        endpoint = Path(temporary) / "docker.sock"
        with Proxy(str(endpoint), Handler) as proxy:
            threading.Thread(target=proxy.serve_forever, daemon=True).start()
            client = Client(name, f"{name}-functional", f"unix://{endpoint}", accessible=True)
            try:
                wait(client.ready)
                wait(lambda: has_count(client, total, total))
                log = client.log_path.read_text()
                if name in ("mygo", "nanoui"):
                    assert f"ids_sha256={digest}" in log
                else:
                    logged_ids = log.split(" ids=")[-1].strip().splitlines()[0].split(",")
                    assert logged_ids == ids
                client.edit(query.upper())
                wait(lambda: has_count(client, expected, total))
                client.capture("search")
                client.edit("__no_container_matches__")
                wait(lambda: has_count(client, 0, total))
                client.edit("")
                wait(lambda: has_count(client, total, total))
                before = proxy.listings
                client.refresh()
                wait(lambda: proxy.listings == before + 1)
                wait(lambda: len(LOAD.findall(client.log_path.read_text())) == 2)
                proxy.mode = "error"
                client.refresh()
                wait(lambda: proxy.listings == before + 2)
                wait(lambda: re.search(r"failed|Docker API|Cannot load|error", client.text(), re.I))
                assert has_count(client, total, total)
                client.capture("error")
                proxy.mode = "timeout"
                started = time.monotonic()
                client.refresh()
                wait(lambda: proxy.listings == before + 3)
                client.edit("__no_container_matches__")
                wait(lambda: "Loading" in client.text())
                wait(lambda: re.search(r"timeout|timed?\s*out|exceeded|deadline", client.text(), re.I), seconds=14)
                timeout = time.monotonic() - started
                assert 9 <= timeout <= 15, timeout
                assert has_count(client, 0, total)
                proxy.mode = "live"
                client.edit("")
                client.refresh()
                wait(lambda: len(LOAD.findall(client.log_path.read_text())) == 3)
                wait(lambda: has_count(client, total, total))
                client.capture("recovered")
                result = {"name": name, "backend": "native Wayland", "container_count": total, "ids_sha256": digest, "binary_sha256": hashlib.sha256((OUT / "bin" / name).read_bytes()).hexdigest(), "search_case_insensitive": True, "search_clear": True, "no_matches": True, "refresh_observed": True, "successful_loads": 3, "failed_refresh_retains_data": True, "responsive_during_timeout": True, "timeout_seconds": timeout, "recovery": True, "input": "AT-SPI native controls" if name in ("mygo", "rune") else "Wayland virtual keyboard; owned window activation confirmed; F5"}
                (OUT / f"{name}-functional.json").write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result), flush=True)
            finally:
                client.close()
                proxy.shutdown()


def renderer(name):
    assert name == "nanoui", "The renderer diagnostic is specific to NanoUI"
    client = Client(name, "nanoui-renderer-observation", debug=True)
    try:
        wait(client.ready)
        match = wait(lambda: re.search(r"nanoui: window [0-9a-f]+ draws with (.+)", client.log_path.read_text()))
        result = {"renderer": match[1], "binary_sha256": hashlib.sha256((OUT / "bin" / name).read_bytes()).hexdigest(), "scope": "Separate renderer observation; NANOUI_DEBUG=1; no resource sampling"}
        (OUT / "nanoui-renderer.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        client.close()


def measure(name, run):
    spec = importlib.util.spec_from_file_location("old_measure", ROOT / "experiments/live-docker/measure.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    started = time.monotonic()
    client = Client(name, f"{name}-{run}")
    try:
        match = wait(client.ready)
        ready = time.monotonic() - started
        client.activate()
        time.sleep(4)
        before = helper.process_sample(client.proc.pid)
        samples = []
        start = time.monotonic()
        while time.monotonic() - start < 20:
            assert client.proc.poll() is None
            samples.append(helper.process_sample(client.proc.pid))
            time.sleep(0.5)
        after = helper.process_sample(client.proc.pid)
        elapsed = time.monotonic() - start
        maps = Path(f"/proc/{client.proc.pid}/maps").read_text().splitlines()
        graphics = sorted({line.split()[-1] for line in maps if any(p in line for p in ("libvulkan", "libGL", "libEGL", "/dri/", "libgtk-"))})
        screenshot = client.capture("window")
        pixels = list(struct.unpack(">II", screenshot.read_bytes()[16:24]))
        result = {"name": name, "run": run, "backend": "native Wayland / COSMIC", "container_count": int(match[1]), "initial_load_ms": int(match[2]), "ready_with_data_seconds": ready, "warmup_seconds": 4, "idle_seconds": elapsed, "idle_cpu_percent_one_core": 100*(after["cpu_seconds"]-before["cpu_seconds"])/elapsed, "idle_rss_median_bytes": statistics.median(s["rss_bytes"] for s in samples), "idle_pss_median_bytes": statistics.median(s["pss_bytes"] for s in samples), "binary_bytes": (OUT / "bin" / name).stat().st_size, "binary_sha256": hashlib.sha256((OUT / "bin" / name).read_bytes()).hexdigest(), "capture_pixels": pixels, "graphics_libraries": graphics, "samples": samples}
        (OUT / f"{name}-{run}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k:v for k,v in result.items() if k!="samples"}), flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("functional", "measure", "renderer"))
    parser.add_argument("name", choices=TITLES)
    parser.add_argument("--run", type=int, default=1)
    args = parser.parse_args()
    if args.mode == "functional":
        functional(args.name)
    elif args.mode == "renderer":
        renderer(args.name)
    else:
        measure(args.name, args.run)
