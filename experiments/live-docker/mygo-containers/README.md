# Live containers · Go + MyGo

Minimal native, read-only Docker list with a library-provided search field,
virtualized table, and manual Refresh. No snapshot file, Docker CLI, shell, or
hand-written HTTP implementation. UI updates run on the main thread; the Docker
request runs in a goroutine. Loading or request errors preserve the last list.

- Go 1.27.1.
- MyGo commit `5fb60098a44a4c629cbdeac5f0ff80ce2f843c2f` (same local replacement as the original experiment).
- Official Moby Go client `github.com/moby/moby/client v0.6.2`, with API types `v1.56.1`, pinned in `go.mod` and `go.sum`.
- `client.New(client.FromEnv)` negotiates the daemon API version and calls `ContainerList` with `All: true`. Each Refresh creates and closes its client, including negotiation in the logged loading time.
- A 10-second context limits connection/negotiation/list loading. At most 20,000 rows are retained; a larger result is rejected after the library decodes it. This is a retained-data bound, not a response-memory cap.

From the repository root, with the original experiment's pinned MyGo checkout
already available at `.verification/gui-comparison/deps/mygo`:

```sh
cd experiments/live-docker/mygo-containers
CGO_ENABLED=0 go build -p 4 -trimpath -tags mygo_noinspector -ldflags '-s -w -X github.com/egoist/mygo.production=1' -o build/mygo-containers .
./build/mygo-containers
```

The SDK reads `DOCKER_HOST`, `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH`, and
`DOCKER_API_VERSION`, or uses its platform's default endpoint. It does not read
Docker CLI contexts. On Docker Desktop, explicitly set `DOCKER_HOST` if the
active daemon is not at the SDK default socket/pipe. No endpoint or credentials
are printed. The library owns Unix-socket/TCP/TLS/Windows named-pipe transport;
the application contains no OS-specific process or socket calls. Only Linux
execution is being checked in this experiment. MyGo's native platform runtime
libraries are still required; this executable is not a full cross-platform
installation package.

A successful load prints the container count, elapsed milliseconds, and the
SHA-256 of all sorted full IDs joined by `\n` with no trailing newline. This
allows the three implementations to compare daemon results without dumping
container metadata. Names are displayed without Docker's leading `/`.
No automatic polling, actions, or automated tests.
