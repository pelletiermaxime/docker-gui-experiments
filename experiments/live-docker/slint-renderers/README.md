# Slint renderer comparison

The same minimal live Docker list as `../slint-containers`, with a neutral header
and an environment-selected backend/renderer. Slint 1.18.1, Bollard 0.21.1 and the
same locked dependencies, worker/timeout/filter/table behavior are retained.
The UI still uses Slint's built-in input, table, Fluent style and dark palette.
No automated tests, container mutations or Docker subprocesses in the app.

Seven independently preserved renderer-family builds cover eight configurations:

| Build feature | Backend | Renderer selector | Scope |
| --- | --- | --- | --- |
| `software` | `winit` | `software` | Slint's CPU renderer |
| `femtovg` | `winit` | `femtovg` | OpenGL |
| `femtovg-wgpu` | `winit` | `femtovg-wgpu` | WGPU |
| `skia` | `winit` | `skia-software` | Skia CPU |
| `skia-opengl` | `winit` | `skia-opengl` | Skia OpenGL |
| `skia` | `winit` | `skia-wgpu` | Skia WGPU |
| `vello` | `winit` | `vello` | Experimental WGPU renderer |
| `qt` | `qt` | ignored by Qt | Qt windowing/rendering backend |

Slint's Skia software/WGPU modes share one executable. OpenGL requires the
explicit renderer-skia-opengl feature and has its own independently sized build.
The initial OpenGL request fell back when that feature was absent; its data was
archived and excluded, then this configuration was rebuilt and measured again. Other renderer families are
built separately. All variants include the same Rust and inline Slint UI code.
The original software experiment and its binary remain unchanged.

Build a family from the FerryDock repository root (replace `femtovg` as needed):

```sh
SLINT_STYLE=fluent \
CARGO_TARGET_DIR="$PWD/experiments/gpui-containers/target" \
CARGO_BUILD_JOBS=4 RUSTFLAGS='-C force-unwind-tables=no' \
cargo build --release --locked --no-default-features --features femtovg \
  --manifest-path experiments/live-docker/slint-renderers/Cargo.toml
mkdir -p experiments/live-docker/slint-renderers/build
cp experiments/gpui-containers/target/release/slint-renderer-containers \
  experiments/live-docker/slint-renderers/build/slint-femtovg
```

Launch an independently saved build, for example:

```sh
FERRYDOCK_SLINT_BACKEND=winit FERRYDOCK_SLINT_RENDERER=femtovg \
  ./experiments/live-docker/slint-renderers/build/slint-femtovg

FERRYDOCK_SLINT_BACKEND=winit FERRYDOCK_SLINT_RENDERER=skia-software \
  ./experiments/live-docker/slint-renderers/build/slint-skia

FERRYDOCK_SLINT_BACKEND=winit FERRYDOCK_SLINT_RENDERER=femtovg-wgpu \
WGPU_BACKEND=vulkan WGPU_ADAPTER_NAME=Intel \
  ./experiments/live-docker/slint-renderers/build/slint-femtovg-wgpu

FERRYDOCK_SLINT_BACKEND=qt \
  ./experiments/live-docker/slint-renderers/build/slint-qt
```

Set DOCKER_HOST if Bollard's default endpoint is not the intended local daemon.
The app does not resolve Docker CLI contexts. The backend/renderer names are
explicitly selected and logged. Only Linux is observed; upstream cross-platform
support is not a claim that these builds ran on Windows/macOS.

The experiment's ignored artifacts, family build logs, native captures,
read-only transport observations, three-round resource measurements and English
HTML report live under `.verification/slint-renderers/`. The existing live report
links to this separate renderer-only comparison. The measurement environment
uses X11/XWayland and scale 1; Qt uses xcb. WGPU_BACKEND=vulkan requests Vulkan for
WGPU modes, and WGPU_ADAPTER_NAME=Intel requests the same Intel family reported
by the external GLX default-device summary. Actual per-process adapter selection
is not independently instrumented. System Qt libraries, other platform libraries and graphics
drivers are excluded from executable sizes. No system package installation is
part of this experiment.

Build times include varying cache reuse and potentially dependency downloads;
they are observations, not comparable clean builds. Resource measurements are
idle-only, with a 4-second warmup and 20-second sampling interval. They do not
establish active rendering throughput or latency. Native captures establish the
startup view, not search/Refresh interactions. No commit or push.
