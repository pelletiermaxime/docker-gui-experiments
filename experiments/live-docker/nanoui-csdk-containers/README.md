# NanoUI + C libdocker from Zig

Fourth live comparison variant. The existing NanoUI UI is copied into a separate
folder. Docker requests go through the published C SDK `danielsuo/libdocker`,
pinned at `4e6c007615fe151ea59609d5081175ea1fe8e65b` (its CMake declares 1.1.0).

This is a C interoperability experiment, not a claim of a mature official SDK.
Docker lists this library as unofficial. GitHub metadata checked 2026-10-19 showed
68 stars, repository creation in 2017 and last push in January 2023. The SDK is a
small GET/POST wrapper over libcurl; it does not supply typed models or automatic
API negotiation. Zig queries `/version`, selects API <=1.55 supported by the
server, requests `/containers/json?all=true`, and decodes the five useful fields.

`build.zig` compiles the upstream C source and local C bridge into the executable.
It generates Zig declarations from `src/docker_bridge.h` with `addTranslateC`, then
calls the C functions normally. System libcurl is linked dynamically. The app
executable alone therefore excludes libcurl and its transitive shared libraries.
The report records libcurl version/linkage and memory with those libraries loaded.
Both local C bridge/header and Zig UI/loader count as application code; upstream
SDK and generated bindings do not.

The SDK normally hardcodes `/var/run/docker.sock`. A small recorded SDK patch reads
an explicit `unix://` DOCKER_HOST instead. Only Unix sockets are supported in this
variant. It is not a Windows named-pipe implementation and has not been run on
macOS. No Docker CLI or input snapshot is used. Existing sibling apps are untouched.

The worker uses a libcurl deadline budget across version/list requests (10 seconds
for network calls), with NOSIGNAL enabled. Each C request owns a fresh SDK object
and releases it, avoiding the SDK's buffer reset issue on reused clients. The C
response copy is freed after Zig owns decoded fields. The C SDK buffers its entire
response; the 20,000-row check is after JSON decoding, not a wire-size cap. Failed
refresh preserves the last good list. Startup and Refresh are the only loads.

Dependencies: existing pinned NanoUI, Zig 0.17.0, libcurl headers/shared library,
plus the pinned ignored C SDK checkout. No system installation was changed.

```sh
git clone https://github.com/danielsuo/libdocker .verification/gui-live-comparison/deps/libdocker
git -C .verification/gui-live-comparison/deps/libdocker checkout 4e6c007615fe151ea59609d5081175ea1fe8e65b
git -C .verification/gui-live-comparison/deps/libdocker apply ../../libdocker-unix-host.patch

ZIG_GLOBAL_CACHE_DIR=/tmp/ferrydock-nanoui-zig-global-cache \
ZIG_LOCAL_CACHE_DIR=/tmp/ferrydock-nanoui-csdk-zig-cache \
ZIG_LOCAL_PKG_DIR=/tmp/ferrydock-nanoui-zig-pkgs \
.verification/gui-comparison/toolchains/zig-x86_64-linux-0.17.0/zig build \
  --build-file experiments/live-docker/nanoui-csdk-containers/build.zig \
  -Doptimize=ReleaseFast -j4
./experiments/live-docker/nanoui-csdk-containers/zig-out/bin/nanoui-csdk-containers
```

C SDK request/status handling stays in libdocker. The local bridge configures curl
lifecycle/timeouts and copies the SDK response; it is not a new HTTP implementation.
No unit/integration test suite added or run, no container mutations, no commit/push.
