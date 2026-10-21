# Live Docker containers · .NET MAUI

Minimal C# port: all containers, name/image/state/status columns, search, manual
Refresh, background loading, a 10-second deadline and last-good results retained
after an error. A MAUI `CollectionView` supplies virtualized rows; `Entry` supplies
native text editing. No JSON input, Docker subprocess, polling or container actions.

## Pinned stack

- .NET SDK 10.0.402 / `net10.0`; Release, JIT, no trimming or NativeAOT.
- MAUI Controls 10.0.110.
- `Microsoft.Maui.Platforms.Linux.Gtk4` 0.1.0-preview.13.26512.5
  (upstream commit `bf5365abb26e85c3076e4a9c1395e55d9cad765a`).
- `Docker.DotNet.Enhanced` 4.3.3, the maintained Docker.DotNet fork used by
  Testcontainers. The application uses its `DockerClientBuilder` and typed list API.

**The Linux host is experimental**, not an officially supported MAUI platform.
The app uses MAUI controls mapped to GTK4 by Microsoft's MAUI Labs backend, not
Blazor or a WebView. GTK/system graphics libraries remain external dependencies.
The upstream backend package references GirCore WebKit bindings even though this
app does not create a WebView. This project is the Linux head only; it does not
claim Windows/Mac Catalyst builds. The MAUI UI could be reused by those heads.

## Build and run

Install .NET 10 and GTK4, then run from this repository's root:

```sh
dotnet publish experiments/live-docker/maui-containers/MauiContainers.csproj \
  -c Release -r linux-x64 --self-contained true \
  -p:DebugType=None -p:DebugSymbols=false \
  -o experiments/live-docker/maui-containers/build/self-contained
DOCKER_HOST=unix:///var/run/docker.sock \
  experiments/live-docker/maui-containers/build/self-contained/MauiContainers
```

Use `--self-contained false` for a smaller publish directory that requires the
.NET runtime on the destination machine. The apphost executable is just a launcher;
compare complete publish-directory sizes, not its size alone. Framework-dependent
output excludes the runtime; self-contained output includes it. Both exclude GTK
and graphics drivers. The included `packages.lock.json` records dependency versions.

The app explicitly uses `DOCKER_HOST`, or the local platform default. It does not
invoke Docker CLI or select a CLI context. Unix sockets were observed; this Linux
host does not establish named-pipe, remote/TLS or macOS behavior. The SDK buffers
the response before the 20,000-row retention check, as in the other experiments.

## Observations

The HTML report and scripts are in `.verification/maui-live-comparison/`.
Measurements use the self-contained build, Linux X11/XWayland, a 1,000 × 680
client, four seconds warmup and twenty seconds at idle. Build timings follow an
initial package restore and include warm caches; they are not clean-build times.

The GTK4 backend emits layout/theme warnings and wraps some long image names
despite the MAUI truncation settings. These are recorded, not hidden or patched
in the framework. Desktop observations and resource sampling do not establish
production readiness. No automated test suite was added or run.
