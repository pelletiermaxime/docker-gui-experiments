# NanoUI + container-zig: live Docker list

Independent live version of the original minimal UI. Read-only all-container list,
search and manual Refresh; no snapshot file, Docker CLI, application polling or
container mutation. NanoUI 0.12.0 is pinned to `e26765e8422f0a719e3bb90d9d97067d92d495b7`.

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

From the FerryDock root, with the Docker SDK checkout and patch available:

```sh
bash experiments/live-docker/prepare-latest.sh
python experiments/live-docker/benchmark.py nanoui
env -u DISPLAY GDK_BACKEND=wayland .verification/wayland-refresh-20261107/bin/nanoui
```

This runs three clean ReleaseFast builds with isolated Zig caches and four jobs.
The updated NanoUI Linux backend selects OpenGL when available, with a CPU fallback.
F5 activates Refresh; the search field receives initial keyboard focus.
Native Wayland validation and idle sampling use the shared
[production refresh workflow](../README.md#november-7-production-refresh).
