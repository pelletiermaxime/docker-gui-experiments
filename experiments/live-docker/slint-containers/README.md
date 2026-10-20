# Live containers · Rust + Slint software renderer + Bollard

Independent minimal live Docker comparison. Slint 1.18.1 supplies the search
field, button, layout and table; Bollard 0.21.1 supplies the same Docker operations
as the gpui-pre variant. UI definitions are inline in `src/main.rs`, and count as
application code alongside Rust. There is no local text-input implementation.

Only Slint's Winit backend and built-in software renderer are enabled. Skia,
FemtoVG and WGPU renderers are disabled. The application explicitly selects
Winit/software. Both X11 and Wayland are compiled on Linux; measurements force
X11/XWayland at 1,000 × 680 pixels and scale 1 to match the existing experiment.
The UI uses Slint's Fluent widget style with a dark palette.

Startup and manual Refresh load all container states on a worker thread. A small
Tokio runtime and one 10-second timeout enclose connection, version negotiation
and listing. Completed results return through Slint's event loop. There is no
polling. Refresh requests cannot overlap, failed loads preserve the last good
list, and more than 20,000 returned rows is an error. The row check happens after
response decoding; it is not a response byte cap. The table uses Slint's built-in
virtualized row implementation. Search matches name/image/state.

No JSON fixture and no Docker subprocess. `DOCKER_HOST` or Bollard's platform
default selects the endpoint; Docker CLI contexts are not resolved by the app.
Linux is the observed platform. Winit and Bollard provide Windows/macOS paths,
but those builds and native interactions have not been exercised here.

From the FerryDock repository root:

```sh
SLINT_STYLE=fluent \
CARGO_TARGET_DIR="$PWD/experiments/gpui-containers/target" \
CARGO_BUILD_JOBS=4 RUSTFLAGS='-C force-unwind-tables=no' \
cargo build --release --locked \
  --manifest-path experiments/live-docker/slint-containers/Cargo.toml

mkdir -p experiments/live-docker/slint-containers/build
cp experiments/gpui-containers/target/release/slint-live-containers \
  experiments/live-docker/slint-containers/build/
./experiments/live-docker/slint-containers/build/slint-live-containers
```

The distinct executable preserves every earlier experiment. Release settings
match gpui-pre: size optimization, fat LTO, one codegen unit, panic abort,
stripping and disabled unwind tables. The shared target reuses existing Rust
dependencies; the first recorded Slint build includes new dependency downloads
and compilation, so it is not a comparable clean-build timing.

Measurements, native captures, transport observations and the English HTML report
are under `.verification/gui-live-comparison/`. No automated tests added or run,
no Docker resources modified, no commit or push.
