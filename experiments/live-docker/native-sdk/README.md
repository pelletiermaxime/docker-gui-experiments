# Native SDK live Docker list

Native SDK **0.11.0**, TypeScript core and native markup, with **Dockerode 5.0.1**
in a short-lived Node helper. No WebView, snapshot input, Docker CLI or polling.
The Linux native view uses the SDK's software rasterizer, a Cairo image and a
GTK4 drawing area. GTK4 presentation retains its defaults; the entire presentation
path is not claimed to be GPU-free.

Search uses the SDK text-edit reducer. A windowed list retains visible rows.
Refresh launches one background Docker request; previous rows survive errors.
A request has a ten-second deadline, a 20,000-container retention limit and a
512 KiB display-pipe bound. Each display field is limited to 512 UTF-16 code units and
embedded tab/newline characters are replaced with spaces. Dockerode handles the
Engine protocol and response decoding. The helper probes the Engine API version
and then lists all states. The reported API interval excludes Node startup and
UI delivery. Dockerode's buffered Engine response precedes the display limits.

## Architecture caveat

The SDK's deterministic compiled TypeScript core cannot import arbitrary npm
libraries. This experiment uses its documented `Cmd.spawn` sidecar pattern;
Dockerode runs in **Node**, not inside the compiled UI. Node starts at launch
and on Refresh, then exits. Idle UI memory therefore excludes an already exited
Docker worker. This is a native UI with a Node-backed Docker integration, not a
runtime-free TypeScript Docker client. The report lists the native executable,
production npm dependencies and Node executable separately, and charts their
combined runtime-included deployment payload. Shared system libraries remain
outside that byte count. The helper's startup peak may precede sampling.

## Build

Requirements: Node 24+, npm, Zig 0.16.0 (the SDK CLI can obtain its pinned
compiler), GTK development libraries, and a running Docker Engine. The SDK is
experimental. Its npm 0.11.0 SDK archive omits a file embedded by build.zig, so
this reproduction uses the complete matching upstream release without a patch.
From the repository root:

```sh
git clone --depth 1 --branch v0.11.0 https://github.com/vercel-labs/native.git \
  .verification/native-sdk-live-comparison/toolchains/sdk
cd .verification/native-sdk-live-comparison/toolchains/sdk/packages/core
npm ci --include=dev
cd ../../../../../..
npm ci --prefix experiments/live-docker/native-sdk --ignore-scripts
NATIVE_SDK_PATH="$PWD/.verification/native-sdk-live-comparison/toolchains/sdk" \
  experiments/live-docker/native-sdk/node_modules/.bin/native build \
  experiments/live-docker/native-sdk --yes
```

Release pin: `16f29572307c2cc133907537c4dfd98046d4e0f4` (`v0.11.0`).
The measured Linux release was post-processed with
`strip --strip-all experiments/live-docker/native-sdk/zig-out/bin/native-live-containers`.
Resource sampling uses automation disabled (the default); screenshots/input
observations use a separate `-Dautomation=true` build with the same app sources.

Launch **from the app directory** so the relative helper path resolves:

```sh
cd experiments/live-docker/native-sdk
DOCKER_HOST=unix:///var/run/docker.sock ./zig-out/bin/native-live-containers
```

Node must be on PATH. `DOCKER_HOST` accepts Unix sockets, Windows named pipes
and HTTP(S)/TCP URLs; optional `DOCKER_CERT_PATH` loads CA/client certificates.
No SSH or Docker CLI context discovery. Linux only was executed. macOS/Windows
UI and Docker transports are upstream capabilities, not execution evidence.
Node, Dockerode and Native SDK retain their upstream licenses.

No automated tests. The resource observation deliberately uses one short run:
two seconds warmup, five seconds idle. See the common live report and the raw
`.verification/native-sdk-live-comparison/` evidence.
