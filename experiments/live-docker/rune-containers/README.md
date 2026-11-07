# Live containers · Rust + Rune + Bollard

Independent native Rune variant of the live Docker comparison. The app lists all
container states, with Name / Image / State / Status columns, a search field,
manual Refresh, and virtualized rows. Startup and Refresh read Docker directly
through Bollard 0.21.1. The app never invokes Docker CLI commands, reads fixture
data, polls Docker periodically, or changes Docker resources.

Rune and rune-kit are pinned to upstream revision
`f73f72cdc563534e4f7de9f5a79bed007ac42384`. `prepare.sh` downloads and verifies the
source archive into the ignored `.verification/rune/source` tree. Path
dependencies keep that exact source available without a full Git history fetch.
The preparation script preserves existing source unless its revision marker
matches; it does not overwrite an unrelated source tree.

Docker loading runs on a background thread with a small Tokio runtime. A single
ten-second deadline covers connection, API negotiation, and listing. Refresh is
disabled while loading, and errors retain the last successful result. The
20,000-row cap is checked after the SDK has buffered and decoded the response;
it is not a wire-response byte limit. Search matches name, image, or state without
case sensitivity. The app logs successful counts, request duration, sorted IDs,
and the observed native window backend, without logging endpoints or credentials.

`DOCKER_HOST` selects Bollard's endpoint; Docker CLI contexts are not resolved.
The Rune dependency enables accessibility but omits optional D-Bus desktop
services, SVG image loading, and audio support. The application uses Rune's dark
neutral theme and built-in fonts. On Linux Rune renders through wgpu/Vulkan.

From this repository root:

```sh
bash experiments/live-docker/rune-containers/prepare.sh
CARGO_BUILD_JOBS=4 RUSTFLAGS='-C force-unwind-tables=no' \
  cargo build --release --locked \
  --manifest-path experiments/live-docker/rune-containers/Cargo.toml
env -u DISPLAY WINIT_UNIX_BACKEND=wayland \
  DOCKER_HOST=unix:///var/run/docker.sock \
  experiments/live-docker/rune-containers/target/release/rune-live-containers
```

The production release profile uses opt-level=3, fat LTO, one codegen unit,
panic abort, and stripping. The historical report binary used opt-level="z".
The shared [production refresh workflow](../README.md#november-7-production-refresh)
builds three clean runs into a separate directory, preserving that binary, and
validates the exact new executable alongside the updated GPUI app.
Native Wayland is deliberately
selected by removing `DISPLAY`; the app logs `Window backend: Wayland`. Existing
comparison measurements used XWayland and a different desktop session, so these
new measurements require that context when compared. Windows and macOS execution
has not been verified.

## Historical paired-backend verification

The current production comparison uses `../verify_wayland.py` through the shared
workflow linked above. The older driver below targets the retained historical
binary in `build/` and its paired Wayland/XWayland observations.

`verify.py` requires Python/PyGObject, AT-SPI 2.0, and `wtype` for Wayland typing
into Rune's initially empty search field. Set `WTYPE` to its executable path; by
default it uses `.verification/rune/wtype/build/wtype`. COSMIC must expose the
virtual-keyboard protocol. The driver temporarily enables the accessibility bus
if necessary and restores its prior state in `finally`.

```sh
WTYPE=/path/to/wtype python experiments/live-docker/rune-containers/verify.py functional
DOCKER_HOST=unix:///var/run/docker.sock \
  python experiments/live-docker/rune-containers/verify.py measure --run 1
DOCKER_HOST=unix:///var/run/docker.sock \
  python experiments/live-docker/rune-containers/verify.py measure --backend xwayland --run 1
```

The functional run compares startup IDs with the real local daemon, checks
keyboard navigation to the first and last virtualized rows, case-insensitive
search, no matches, clearing search, manual Refresh, retained
data after an HTTP error, responsiveness while waiting, the ten-second deadline,
and recovery. A private temporary Unix-socket proxy forwards only GET requests
for version, ping, and container listing; injected failures never alter Docker.
The harness, unlike the app, uses curl for its independent daemon reference.

The driver processes accessibility events and refreshes cached interface data:
Rune exposes an editable-text interface only once this field contains text.
Initial typing uses the native Wayland virtual keyboard; subsequent field edits
and button actions use accessibility. This is an automation limitation of the
current toolkit, not a failure to type or clear text in the visible app.

The measurement run uses the real Docker socket directly, waits for data through
accessibility, warms up for four seconds, then samples RSS/PSS and CPU for twenty
seconds at 500 ms intervals using the existing measurement helper. It does not
use X11 tools for native Wayland. `--backend xwayland` removes `WAYLAND_DISPLAY`,
sets the X11 scale factor to 1, verifies an Xlib handle and a 1000×680 client
surface, and captures the window after sampling. If the local native capture
helper exists, Wayland runs also capture and verify their surface after sampling.
Binary and dataset hashes are recorded so alternating runs can be compared.
Accessibility remains enabled during this run. Results and logs
are under `.verification/rune`; they are not automatically added to the shared
report. Application-reported readiness is different from measured presentation
latency, and RSS/PSS do not include every compositor or GPU allocation, or the
shared XWayland server process.
