# Live Docker SDK comparison

Independent variants of the original minimal native container list. Each reads
Docker Engine directly through a Docker client library at startup and on Refresh:

| App | UI | Docker client |
| --- | --- | --- |
| [Zig](nanoui-containers/README.md) | NanoUI 0.12.0 | Zig Docker SDK 1.0.0, zig-0.17 revision d65b714977eeadb5b38c1b577f4ef53e3f88083a |
| [Go](mygo-containers/README.md) | MyGo 0.8.1 (1dfa5a1f912b) | official Moby client v0.6.2 |
| [Rust](gpui-containers/README.md) | gpui-pre 0.3.11, no Kit | Bollard 0.21.1 |
| [Rust + software renderer](slint-containers/README.md) | Slint 1.18.1, Winit + software | Bollard 0.21.1 |
| [Rust + Rune](rune-containers/README.md) | Rune / rune-kit f73f72c, wgpu + Vulkan | Bollard 0.21.1 |

A separate [Slint renderer comparison](slint-renderers/README.md) keeps the same
Slint UI and Docker code while comparing CPU/GPU renderer families and Qt. Its
HTML report is under `.verification/slint-renderers/`.

All states; name/image/state/status columns; search; manual Refresh; virtualized
rows; background I/O; 10-second load deadline; last good data retained after an
error. These apps do not read the JSON fixture or invoke a local Docker CLI.
No periodic polling, event subscription, metrics stream, or container controls.
"Live" means a fresh daemon request at startup and on Refresh.

Each client buffers/decodes its response before the 20,000-row retention limit is checked.
The row limit does not impose a common wire-response byte limit. Desktop behavior
was originally observed on Linux XWayland. The production refresh below uses
native Wayland under COSMIC for all new runs. Windows and macOS were not executed. SDK transports and
endpoint discovery differ; DOCKER_HOST is explicitly pinned for measurement.
The apps do not implement Docker CLI context discovery. The Zig-native variant uses the SDK's endpoint
resolver example with a one-line adaptation for the installed Zig release, recorded
in the report. The GPUI variant keeps its existing local search widget.

The existing JSON/CLI comparison and its binaries remain unchanged. The separate
English report, raw measurements, captures, SDK source pin/patch, and transport
traces are under `.verification/gui-live-comparison/` (ignored).

Launch from the FerryDock root after building (commands in each README):

```sh
./experiments/live-docker/nanoui-containers/zig-out/bin/nanoui-live-containers
./experiments/live-docker/mygo-containers/build/mygo-containers
./experiments/live-docker/gpui-containers/build/gpui-live-containers
./experiments/live-docker/slint-containers/build/slint-live-containers
./experiments/live-docker/rune-containers/build/rune-live-containers
```

The Rust binary has a distinct name and reuses the existing warm GPUI target;
source/manifests/lockfile are in this new folder. None of the original binaries is
overwritten. Docker must be running and accessible to your user. For non-default
local endpoints, set DOCKER_HOST explicitly, for example Docker Desktop's Unix
socket on macOS or, for clients supporting it, its named pipe on Windows. Only the local Linux socket was
measured; each client supports different remote/TLS features.

`measure.py` is a separate live variant of the existing measurement helper. It
removes CONTAINER_SNAPSHOT from the child environment. After compilation:

```sh
DOCKER_HOST=unix:///var/run/docker.sock python experiments/live-docker/measure.py \
  mygo experiments/live-docker/mygo-containers/build/mygo-containers \
  --output .verification/gui-live-comparison --run 1
```

Measurement uses a 1,000 × 680 X11 client surface, 4-second warmup, then 20 seconds
at idle; one app at a time, no strace during sampling. Native captures/transport
traces are separate observations. The launcher/harness may use read-only Docker
CLI commands to identify the active endpoint and reference IDs; the apps do not.
The original variants had no automated tests added or run. Rune has a separate
native interaction and measurement driver documented in its README. The shared
report includes Rune alongside the seven retained integrations.

## November 7 production refresh

Updated NanoUI, MyGo, gpui-pre and the Rune production control use native Wayland
under COSMIC. Historical binaries and measurements remain separate. New results
appear immediately below their historical rows in the shared report.

```sh
bash experiments/live-docker/prepare-latest.sh
bash experiments/live-docker/prepare-wayland-tools.sh
python experiments/live-docker/benchmark.py mygo
python experiments/live-docker/benchmark.py nanoui
python experiments/live-docker/benchmark.py gpui
python experiments/live-docker/benchmark.py rune
python experiments/live-docker/verify_wayland.py functional mygo
python experiments/live-docker/verify_wayland.py measure mygo --run 1
python experiments/live-docker/verify_wayland.py renderer nanoui
```

Repeat functional validation for each app and measurement for runs 1–3 of each
app, sequentially, after builds finish. Then run `summarize_wayland.py` and the
existing report generator. Outputs live in
`.verification/wayland-refresh-20261107/`; clean production executables are in
its `bin/` directory. To launch one directly:

```sh
env -u DISPLAY GDK_BACKEND=wayland WINIT_UNIX_BACKEND=wayland \
  .verification/wayland-refresh-20261107/bin/mygo
```

Each build gets an empty language build cache, four build jobs, pre-fetched
dependencies and an isolated output directory. Rust uses opt-level=3, fat LTO,
one codegen unit, panic abort and stripping; NanoUI uses ReleaseFast; MyGo uses
its production configuration. Timings exclude downloads. Filesystem caches are
not flushed. The harness refuses to reuse an existing build-run directory.

Functional validation uses the measured binary, native controls or Wayland
keyboard input, and a temporary read-only proxy to check Refresh, search,
retained rows on HTTP failure, a responsive ten-second timeout and recovery.
Resource sampling runs separately, with DISPLAY removed, four seconds of warmup
and twenty seconds of idle samples every 500 ms. Captures follow sampling.
The renderer diagnostic runs separately from resource sampling. Native helpers
require COSMIC's toplevel/capture protocols, Wayland development headers,
libdrm/GBM, libpng, xkbcommon, `wayland-scanner`, Meson and Ninja. Preparation
downloads and builds wtype at `4b9cc29664f178cf380ccfe7f98405d38dffda3c`;
`WTYPE=/absolute/path` overrides it. The Python driver needs PyGObject,
AT-SPI and Tesseract. It enables accessibility only during functional
checks and restores the previous desktop setting afterward.
