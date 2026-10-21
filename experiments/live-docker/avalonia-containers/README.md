# Live Docker containers · Avalonia

Minimal C# desktop app with the same scope as the other live experiments:
name/image/state/status columns, all containers, search and manual Refresh.
Avalonia's built-in TextBox, Button and virtualized DataGrid supply the UI. No
WebView, JSON input, Docker subprocess, polling or container actions.

Pinned packages: Avalonia Desktop, Fluent theme and DataGrid **12.1.2**;
Docker.DotNet.Enhanced **4.3.3**. Target: `net10.0`, built with SDK **10.0.402**.
All Avalonia packages use the same version. The project includes its NuGet lockfile.
No MVVM framework, ReactiveUI, custom text editor or bundled font package.

```sh
dotnet publish experiments/live-docker/avalonia-containers/AvaloniaContainers.csproj \
  -c Release -r linux-x64 --self-contained true \
  -p:DebugType=None -p:DebugSymbols=false \
  -o experiments/live-docker/avalonia-containers/build/self-contained
DOCKER_HOST=unix:///var/run/docker.sock \
  experiments/live-docker/avalonia-containers/build/self-contained/AvaloniaContainers
```

Use `--self-contained false` for output requiring an installed .NET runtime.
Compare complete publish-directory sizes: the apphost is only a small launcher.
The self-contained output includes .NET; the framework-dependent output excludes
it. Both exclude system graphics/windowing libraries. These are untrimmed JIT
Release builds, without NativeAOT or single-file packaging, matching the MAUI port.

Docker reads run off the UI thread, with a ten-second cancellation deadline and
SDK request timeout. Refreshes cannot overlap, failed loads retain previous rows,
and closing the window cancels the request. The 20,000-row limit is checked after
SDK buffering/decoding, not as a wire-response byte cap. The SDK/data transformation
logic matches the MAUI experiment.

The app explicitly uses `DOCKER_HOST`, or the local platform default, without
invoking Docker CLI or choosing a Docker CLI context. Windows defaults to a named
pipe; Unix platforms default to `/var/run/docker.sock`. For Docker Desktop on
macOS, set its actual Unix endpoint explicitly. Only Linux execution is observed.

Avalonia's `UsePlatformDetect` selects its normal desktop integration. The recorded
run uses X11/XWayland and the default Skia rendering configuration; no renderer or
GPU adapter is forced. The measurement launcher sets the documented per-monitor `AVALONIA_SCREEN_SCALE_FACTORS`
to 1 (using X11 monitor names) to match the other apps' scale and 1,000 × 680 physical client size; ordinary launches
follow desktop scaling. Avalonia supports Windows/macOS/Linux upstream; this is not
evidence of this app running on the other platforms.

The report and native observations live in `.verification/avalonia-live-comparison/`.
At the user's request, measurement is **one quick run: 2 seconds warmup + 5 seconds
idle**, at a 1,000 × 680 client size. It is less stable than the original three-run
protocol and is not a throughput benchmark. Native input observations run outside
the resource interval. No automated test suite was added or run.
