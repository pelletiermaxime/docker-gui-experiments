# Live containers · Rust + gpui-pre + Bollard

Minimal independent variant of `../../gpui-containers`: same native list,
search field and manual Refresh, with the Docker Engine API as its only data
source. It does not read snapshots or invoke the Docker CLI.

- UI: `gpui-pre` and `gpui-pre-platform` **0.3.9**, without GPUI Kit.
- Docker client: **Bollard 0.21.1**, default HTTP/Unix-socket/Windows-named-pipe
  features; no TLS or SSH features.
- `Docker::connect_with_defaults()` honors `DOCKER_HOST`, otherwise uses
  Bollard's platform default. Docker CLI contexts are not resolved. For Docker
  Desktop on macOS, set `DOCKER_HOST` to its available Unix socket when needed.
- A GPUI background worker creates a small Tokio runtime per refresh. A single
  10-second deadline covers connect, API-version negotiation and listing all
  containers, including stopped ones. The UI remains responsive. Failed refreshes
  retain the previous list; more than 20,000 returned containers produces an
  error. This is a retained-row limit, not a streaming HTTP-response-size limit.
- A successful request writes the count, elapsed milliseconds and sorted container
  IDs to stderr so the measurement can confirm the real dataset. No endpoint or
  credentials are logged. No polling and no Docker mutations.

From the FerryDock repository root:

```sh
CARGO_TARGET_DIR="$PWD/experiments/gpui-containers/target" \
CARGO_BUILD_JOBS=4 RUSTFLAGS='-C force-unwind-tables=no' \
cargo build --release --locked \
  --manifest-path experiments/live-docker/gpui-containers/Cargo.toml

mkdir -p experiments/live-docker/gpui-containers/build
cp experiments/gpui-containers/target/release/gpui-live-containers experiments/live-docker/gpui-containers/build/
./experiments/live-docker/gpui-containers/build/gpui-live-containers
```

The distinct executable name preserves the original snapshot prototype. Release
settings match it: size optimization, fat LTO, one codegen unit, panic abort and
stripping. The shared target directory reuses dependencies; this is not a clean
build. Linux is configured for X11/XWayland. Windows/macOS need their GPUI platform
features selected before building; no cross-platform execution is claimed.

The local input is copied from the original GPUI prototype, with its existing
Apache-2.0 attribution in `src/search.rs` and `LICENSE-APACHE`. No automated tests
were added or run.
