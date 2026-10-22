# Native SDK live Docker list — native service

Native SDK **0.11.0**, compiled TypeScript core/native markup and a compiled
TypeScript service, using the official **Moby Go SDK v0.6.2** in a small native
worker. **No Node, npm packages, Docker CLI or WebView at runtime.**

The UI calls the SDK-generated `dockerList` command. Native SDK manages its
compiled native child-service host; that service synchronously calls the native
Moby worker. The worker performs a fresh all-states Engine request with API
negotiation at startup and on Refresh, then exits. The service host stays alive;
resource sampling includes it and all live descendants. Search and the windowed
list remain in the TypeScript UI; failed loads retain the previous rows.

This is explicitly a **TypeScript UI/service + Go Docker-worker integration**.
It is not an all-TypeScript Docker SDK. The pinned compiler's HTTP lowering does
not implement `socketPath`, and its in-process library mode rejects
`child_process` (SC4005). The supported native child carrier plus Moby keeps real
Docker SDK behavior and portable SDK transports without a Node runtime or a
handwritten socket/HTTP implementation. No compiler/framework patch is applied.

The old Node/Dockerode implementation and its measurements are retained only as
historical evidence in `.verification/native-sdk-live-comparison/node-helper-baseline/`.
The shared live report replaces that implementation's main row with this one.

## Build

Build tools: Node 24+, npm, Go 1.27.1 and Zig 0.16.0. Native SDK's CLI can obtain
its pinned Zig compiler. Node is a **build tool only**. Linux needs GTK4 development
libraries. This SDK release's npm archive omits a file embedded by build.zig, so
use the complete unchanged upstream release:

```sh
git clone --depth 1 --branch v0.11.0 https://github.com/vercel-labs/native.git \
  .verification/native-sdk-live-comparison/toolchains/sdk
cd .verification/native-sdk-live-comparison/toolchains/sdk/packages/core
npm ci --include=dev
cd ../../../../../..
npm ci --prefix experiments/live-docker/native-sdk --ignore-scripts
cd experiments/live-docker/native-sdk/docker-client
CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o ../zig-out/bin/native-docker-client .
cd ../../../..
NATIVE_SDK_PATH="$PWD/.verification/native-sdk-live-comparison/toolchains/sdk" \
  experiments/live-docker/native-sdk/node_modules/.bin/native build \
  experiments/live-docker/native-sdk --yes
strip --strip-all experiments/live-docker/native-sdk/zig-out/bin/native-live-containers \
  experiments/live-docker/native-sdk/zig-out/bin/native-live-containers_services
```

SDK pin: `16f29572307c2cc133907537c4dfd98046d4e0f4` (`v0.11.0`). The runtime
payload is **three native executables plus app assets**; system shared libraries
are excluded from the recorded file-size sum. There is no npm runtime payload.

## Launch

```sh
DOCKER_HOST=unix:///var/run/docker.sock experiments/live-docker/native-sdk/run.sh
```

The launcher uses the native worker to encode its absolute path and Docker
configuration into an environment-delivered typed-service request, then replaces
itself with the UI. This avoids depending on the service host's app-data cwd or
its restricted environment. The compiled service receives no executable source.
On Windows, set `$env:NATIVE_DOCKER_CONFIGURATION` to the output of
`native-docker-client.exe --configuration`, then run the UI executable beside
`native-live-containers_services.exe`. Only Linux was executed; macOS/Windows
remain unverified. Moby owns Unix socket / Windows named-pipe transport and
`DOCKER_HOST`, `DOCKER_CERT_PATH`, `DOCKER_TLS_VERIFY` configuration. Docker CLI
context discovery is not added.

The request deadline is ten seconds. The Engine response buffers before a
20,000-row retention check; the display response is limited to 512 KiB and each
field to 512 Unicode code points, with embedded tabs/newlines replaced by spaces.
The API timer excludes native worker startup, service dispatch and UI delivery.

Linux rendering remains SDK software rasterization → Cairo → GTK4 drawing area,
with GTK4's default presentation settings. Resource measurements use one short
run, **2s warmup + 5s idle**, automation disabled. Capture/input observations use
a separate automation-enabled build. No automated tests were added or run.
