# Container list · Zig + NanoUI

Minimal native desktop prototype (measured on Linux): all Docker containers, name/image/state search, manual Refresh,
visible read errors, no container actions and no Docker polling. Native NanoUI widgets
and virtualized rows; GTK 3 and Cairo provide the Linux window and CPU rendering.
This prototype is for comparison, not a replacement for FerryDock.

Pinned dependency: [`justrach/nanoui`](https://github.com/justrach/nanoui), commit
`d61e253205472cef0854367125295d87c810c5b3` (declares version 0.3.0).
Zig **0.17.0** is required; no global compiler installation is changed.

From the repository root, restore the local ignored dependency/toolchain if needed:

```sh
mkdir -p .verification/gui-comparison/deps .verification/gui-comparison/toolchains
git clone https://github.com/justrach/nanoui .verification/gui-comparison/deps/nanoui
git -C .verification/gui-comparison/deps/nanoui checkout d61e253205472cef0854367125295d87c810c5b3
curl -fL https://ziglang.org/download/0.17.0/zig-x86_64-linux-0.17.0.tar.xz -o .verification/gui-comparison/toolchains/zig-0.17.0.tar.xz
echo '1cbe9df9f27e6b78d14ccbca43b6703a404ef79ef1c463de901d7f088d4e2026  .verification/gui-comparison/toolchains/zig-0.17.0.tar.xz' | sha256sum -c -
tar -xJf .verification/gui-comparison/toolchains/zig-0.17.0.tar.xz -C .verification/gui-comparison/toolchains
cd experiments/nanoui-containers
ZIG_GLOBAL_CACHE_DIR=/tmp/ferrydock-nanoui-zig-global-cache \
ZIG_LOCAL_CACHE_DIR=/tmp/ferrydock-nanoui-zig-cache \
ZIG_LOCAL_PKG_DIR=/tmp/ferrydock-nanoui-zig-pkgs \
../../.verification/gui-comparison/toolchains/zig-x86_64-linux-0.17.0/zig build -Doptimize=ReleaseFast
./zig-out/bin/nanoui-containers
```

Use `CONTAINER_SNAPSHOT=/absolute/path/containers.ndjson` for reproducible data instead
of Docker. Each line is an object with Docker CLI `ID`, `Names`, `Image`, `State`,
`Status` fields. Refresh rereads the same source. A Docker read runs on a worker,
uses Zig 0.17 standard-library `std.process.run` with separate arguments,
a 10-second I/O deadline, stdout limited to 4 MiB and stderr limited to 4 KiB.
Snapshot files use `std.Io.Dir.readFileAlloc` with the same 4 MiB limit.
The I/O service comes from `std.process.Init.io`; allocations use
`std.heap.smp_allocator`. There are no app-declared libc file/process functions,
shell invocations or external timeout commands. These standard-library APIs select
the host implementation for Linux, Windows or macOS; this prototype has only been
built and exercised on Linux. Search is ASCII case insensitive.
The app joins a running read when closing (up to its timeout).

Builds are stripped; executable: `zig-out/bin/nanoui-containers`.
No automated tests are included, as requested. No upstream code changes are needed.

The former libc/GNU-timeout version and its measurements are archived under
`.verification/gui-comparison/nanoui-libc-baseline/`. The report uses fresh
measurements of this portable-API version; it still compares four integrations.
