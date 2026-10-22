# Live Docker SDK comparison

Eight independent variants of the original minimal native container list. Each reads
Docker Engine directly through a Docker client library at startup and on Refresh:

| App | UI | Docker client |
| --- | --- | --- |
| [Zig](nanoui-containers/README.md) | NanoUI, original pinned revision | container-zig 1.0.0, zig-0.17 revision d65b714977eeadb5b38c1b577f4ef53e3f88083a |
| [Zig + C SDK](nanoui-csdk-containers/README.md) | NanoUI, same pinned revision | unofficial C libdocker, pinned 4e6c007; system shared libcurl |
| [Go](mygo-containers/README.md) | MyGo, original pinned revision | official Moby client v0.6.2 |
| [Rust](gpui-containers/README.md) | gpui-pre 0.3.9, no Kit | Bollard 0.21.1 |
| [Rust + software renderer](slint-containers/README.md) | Slint 1.18.1, Winit + software | Bollard 0.21.1 |
| [C# + MAUI](maui-containers/README.md) | MAUI 10.0.110 / experimental GTK4 Linux backend | Docker.DotNet.Enhanced 4.3.3 |
| [C# + Avalonia](avalonia-containers/README.md) | Avalonia 12.1.2 / desktop Skia | Docker.DotNet.Enhanced 4.3.3 |
| [TypeScript + Native SDK](native-sdk/README.md) | Native SDK 0.11.0 / compiled native UI | Compiled TypeScript service + native Moby SDK worker v0.6.2 |

The [C# + .NET MAUI variant](maui-containers/README.md) uses MAUI Controls
10.0.110, Microsoft's experimental GTK4 Linux backend and Docker.DotNet.Enhanced
4.3.3. Its later measurements and screenshot appear with the other apps in the live report;
the original five rows retain their original measurement provenance. It reports
complete publish-directory sizes rather than treating the apphost as a standalone
executable. The app uses an observable collection for its virtualized MAUI list.

The subsequent [Avalonia C# port](avalonia-containers/README.md) uses Avalonia
12.1.2 and the same Docker SDK and request logic. Its single short resource sample
(2 seconds warmup, 5 seconds idle) follows the user's request to shorten
measurement. Both .NET ports share the main charts, table and screenshot gallery,
with their full publish-directory sizes and per-row sampling labels.

The [Native SDK port](native-sdk/README.md) compiles its TypeScript UI and service to native
code and invokes a native Go/Moby worker on startup and Refresh. Node is a build
tool only. Its one short run uses 2s warmup + 5s idle, including the persistent
service host. Its size row includes all three native executables and assets.
It adds a 512 KiB display-pipe bound; the SDK response itself is buffered.

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
has only been observed on Linux XWayland, not Windows or macOS. SDK transports and
endpoint discovery differ; DOCKER_HOST is explicitly pinned for measurement.
The apps do not implement Docker CLI context discovery. The Zig-native variant uses the SDK's endpoint
resolver example with a one-line adaptation for the installed Zig release, recorded
in the report. The C SDK variant accepts Unix sockets only, with no Windows named-pipe transport; Rust keeps its existing local search widget.

The existing JSON/CLI comparison and its binaries remain unchanged. The separate
English report, raw measurements, captures, SDK source pin/patch, and transport
traces are under `.verification/gui-live-comparison/` (ignored).

Launch from the FerryDock root after building (commands in each README):

```sh
./experiments/live-docker/nanoui-containers/zig-out/bin/nanoui-live-containers
./experiments/live-docker/nanoui-csdk-containers/zig-out/bin/nanoui-csdk-containers
./experiments/live-docker/mygo-containers/build/mygo-containers
./experiments/live-docker/gpui-containers/build/gpui-live-containers
./experiments/live-docker/slint-containers/build/slint-live-containers
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
No automated tests added or run, no Docker resources created, no commit or push.
