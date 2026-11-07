#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out="$root/.verification/wayland-refresh-20261107"
mkdir -p "$out/deps" "$out/packages"
fetch_source() {
    local name=$1 repository=$2 revision=$3 digest=$4 destination=$5
    if [[ -f "$destination/.revision" ]] && [[ $(cat "$destination/.revision") == "$revision" ]]; then
        return
    fi
    if [[ -e "$destination" ]]; then
        echo "Existing source is not marked with the required revision: $destination" >&2
        exit 1
    fi
    local archive="$out/deps/$name.tar.gz"
    if [[ ! -f "$archive" ]]; then
        curl --fail --location --retry 2 --connect-timeout 15 --max-time 600 \
            "https://api.github.com/repos/$repository/tarball/$revision" --output "$archive"
    fi
    printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status
    mkdir -p "$destination"
    tar -xzf "$archive" -C "$destination" --strip-components=1
    printf '%s\n' "$revision" > "$destination/.revision"
}
fetch_source nanoui justrach/nanoui e26765e8422f0a719e3bb90d9d97067d92d495b7 \
    a60b30e07460da652789c584e5f2964716541bca0f9c167e6d31b8afafae05c0 "$out/deps/nanoui"
fetch_source mygo egoist/mygo 1dfa5a1f912b75de41f8732ce1d38e1cd9a18421 \
    96a95e0b7be0c6ad04d7185960e7c9faaf48992a9bcae97ba68bfd3533b8db99 "$out/deps/mygo"
fetch_source http-zig justrach/http-zig 1f798e762f52ff81cc6c370b4f322c9e65064462 \
    246d1948baa1df5d549c56eedc9a3de4c954c3e086a5d3370da2f59bf3e2e279 \
    "$out/packages/http_zig-0.1.0-2CB7E00SAwAnwnBkJDgCDm3zLwrCmZZkHNSw5t7X9Vbf"
bash "$root/experiments/live-docker/rune-containers/prepare.sh"
cargo fetch --locked --manifest-path "$root/experiments/live-docker/gpui-containers/Cargo.toml"
cargo fetch --locked --manifest-path "$root/experiments/live-docker/rune-containers/Cargo.toml"
(cd "$root/experiments/live-docker/mygo-containers" && CGO_ENABLED=0 go mod download)
