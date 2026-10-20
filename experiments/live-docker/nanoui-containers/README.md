# NanoUI + container-zig: live Docker list

Independent live version of the original minimal UI. Read-only all-container list,
search and manual Refresh; no snapshot file, Docker CLI, application polling or
container mutation. NanoUI remains pinned to `d61e253205472cef0854367125295d87c810c5b3`.

**Experimental dependency:** GitHub metadata checked on 2026-10-19 returned one
star, creation on 2026-07-06 and last push on 2026-07-14. This client was chosen
for its Zig 0.17 branch, not demonstrated production maturity. The live report
includes the selection history and alternatives; successful listing is not proof
of full API or cross-platform reliability.

Uses container-zig 1.0.0, `zig-0.17` revision
`d65b714977eeadb5b38c1b577f4ef53e3f88083a`, and Zig 0.17.0.
The SDK negotiates the daemon API and calls `container.list(all=true)` on a worker.
A standard-library Select races the complete load against a 10-second timer.
The latest successful list survives failed refreshes. More than 20,000 containers
is an error after SDK decoding; this is a retained-row cap, not a wire-size cap.
SDK results are released after copying the five displayed/proof fields.

The SDK's endpoint-discovery example supplies DOCKER_HOST/default socket selection.
It supports Unix sockets, TCP/TLS, named pipes, and SSH. Only local Unix-socket
execution has been observed here. SSH transport upstream uses a remote Docker CLI;
this experiment uses the local socket directly. No Docker CLI context fallback.
An explicit DOCKER_HOST is useful for Docker Desktop's per-user socket on Mac.

One upstream helper line needed adapting for the installed Zig 0.17 release:
`Uri.getHostAlloc` was removed; URI host decoding now uses the component API.
The patch is preserved in `.verification/gui-live-comparison/container-zig-zig017.patch`.
No HTTP or socket implementation is written in this application.

Fetch the pinned SDK into the ignored dependency area if recreating the experiment:

```sh
git clone --branch zig-0.17 https://github.com/GuangYiL/container-zig .verification/gui-live-comparison/deps/container-zig
git -C .verification/gui-live-comparison/deps/container-zig checkout d65b714977eeadb5b38c1b577f4ef53e3f88083a
git -C .verification/gui-live-comparison/deps/container-zig apply ../../container-zig-zig017.patch
```

From the FerryDock root, with the ignored dependency checkouts available:

```sh
ZIG_GLOBAL_CACHE_DIR=/tmp/ferrydock-nanoui-zig-global-cache \
ZIG_LOCAL_CACHE_DIR=/tmp/ferrydock-live-nanoui-zig-cache \
ZIG_LOCAL_PKG_DIR=/tmp/ferrydock-nanoui-zig-pkgs \
.verification/gui-comparison/toolchains/zig-x86_64-linux-0.17.0/zig build \
  --build-file experiments/live-docker/nanoui-containers/build.zig \
  -Doptimize=ReleaseFast -j4
./experiments/live-docker/nanoui-containers/zig-out/bin/nanoui-live-containers
```

Build uses libc for NanoUI's system integration, rather than application-declared
OS functions. Native UI still uses the toolkit's CPU/Cairo/GTK backend on Linux.
No automated tests added or executed. Reports/captures live in
`.verification/gui-live-comparison/`; original experiments are preserved.
