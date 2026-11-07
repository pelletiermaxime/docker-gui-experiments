# Live containers · Rust + gpui-pre + Bollard

Minimal independent variant of `../../gpui-containers`: same native list,
search field and manual Refresh, with the Docker Engine API as its only data
source. It does not read snapshots or invoke the Docker CLI.

- UI: `gpui-pre` and `gpui-pre-platform` **0.3.11**, without GPUI Kit.
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
bash experiments/live-docker/prepare-latest.sh
python experiments/live-docker/benchmark.py gpui
env -u DISPLAY WINIT_UNIX_BACKEND=wayland .verification/wayland-refresh-20261107/bin/gpui
```

This runs three clean production builds with isolated Cargo targets and four jobs.
Release settings use opt-level=3, fat LTO, one codegen unit, panic abort and
stripping. Linux enables Wayland only. F5 or Ctrl+R activates Refresh, including
while the search field has focus. Native input validation and idle sampling use
the [production refresh workflow](../README.md#november-7-production-refresh).

The local input is copied from the original GPUI prototype, with its existing
Apache-2.0 attribution in `src/search.rs` and `LICENSE-APACHE`. Native verification is performed on the exact production binary.
