#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out="$root/.verification/wayland-refresh-20261107/tools"
cosmic_revision=c0cff4db14c37ed954983158e4055aa94c7741d9
mkdir -p "$out"
pkg-config --exists wayland-client libpng gbm libdrm xkbcommon
for protocol in ext-foreign-toplevel-list ext-image-capture-source ext-image-copy-capture; do
    source="/usr/share/wayland-protocols/staging/$protocol/$protocol-v1.xml"
    wayland-scanner client-header "$source" "$out/$protocol.h"
    wayland-scanner private-code "$source" "$out/$protocol.c"
done
wayland-scanner client-header /usr/share/wayland-protocols/stable/linux-dmabuf/linux-dmabuf-v1.xml "$out/linux-dmabuf.h"
wayland-scanner private-code /usr/share/wayland-protocols/stable/linux-dmabuf/linux-dmabuf-v1.xml "$out/linux-dmabuf.c"
for protocol in cosmic-toplevel-info cosmic-toplevel-management; do
    if [[ ! -s "$out/$protocol.xml" ]]; then
        curl --fail --silent --show-error \
            "https://api.github.com/repos/pop-os/cosmic-protocols/contents/unstable/$protocol-unstable-v1.xml?ref=$cosmic_revision" \
            | jq -er .content | base64 -d > "$out/$protocol.xml"
    fi
    wayland-scanner client-header "$out/$protocol.xml" "$out/$protocol.h"
    wayland-scanner private-code "$out/$protocol.xml" "$out/$protocol.c"
done
cc -I "$out" -o "$out/capture" "$root/experiments/live-docker/wayland_capture.c" \
    "$out/ext-foreign-toplevel-list.c" "$out/ext-image-capture-source.c" \
    "$out/ext-image-copy-capture.c" "$out/linux-dmabuf.c" \
    $(pkg-config --cflags --libs wayland-client libpng gbm libdrm)
cc -I "$out" -o "$out/focus" "$root/experiments/live-docker/wayland_focus.c" \
    "$out/cosmic-toplevel-info.c" "$out/cosmic-toplevel-management.c" \
    "$out/ext-foreign-toplevel-list.c" $(pkg-config --cflags --libs wayland-client)
if [[ -n ${WTYPE:-} ]]; then
    [[ -x "$WTYPE" ]] || { echo 'WTYPE must name an executable.' >&2; exit 1; }
    ln -sfn "$(realpath "$WTYPE")" "$out/wtype"
    exit 0
fi
wtype_revision=4b9cc29664f178cf380ccfe7f98405d38dffda3c
wtype_digest=ff3035f8032782172246a850254f46069e3a1670c0a445426d448ee82138dfa6
wtype_source="$out/wtype-source"
if [[ ! -e "$wtype_source" ]]; then
    curl --fail --location --silent --show-error \
        "https://api.github.com/repos/atx/wtype/tarball/$wtype_revision" --output "$out/wtype.tar.gz"
    printf '%s  %s\n' "$wtype_digest" "$out/wtype.tar.gz" | sha256sum --check --status
    mkdir -p "$wtype_source"
    tar -xzf "$out/wtype.tar.gz" -C "$wtype_source" --strip-components=1
    printf '%s\n' "$wtype_revision" > "$wtype_source/.revision"
elif [[ ! -f "$wtype_source/.revision" ]] || [[ $(cat "$wtype_source/.revision") != "$wtype_revision" ]]; then
    echo 'Existing wtype source does not match the verification pin.' >&2
    exit 1
fi
if [[ ! -f "$wtype_source/build/build.ninja" ]]; then
    meson setup "$wtype_source/build" "$wtype_source" --buildtype=release
fi
meson compile -C "$wtype_source/build"
ln -sfn "$wtype_source/build/wtype" "$out/wtype"
