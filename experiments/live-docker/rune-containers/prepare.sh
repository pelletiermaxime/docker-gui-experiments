#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/../../.." && pwd)
revision=f73f72cdc563534e4f7de9f5a79bed007ac42384
digest=18cfdd42af06909ba090cab5168cc53eba9a3788b8bca6df8682991078640d2f
destination="$root/.verification/rune/source"
archive="$root/.verification/rune/source.tar.gz"

if [[ -f "$destination/.revision" ]] && [[ $(cat "$destination/.revision") == "$revision" ]]; then
    exit 0
fi
if [[ -d "$destination" ]]; then
    echo "Existing Rune source has no matching revision marker: $destination" >&2
    echo 'Preserve or move that directory before preparing a new source tree.' >&2
    exit 1
fi
mkdir -p "$(dirname "$destination")"
curl --fail --location --retry 2 --connect-timeout 15 --max-time 600 \
    "https://api.github.com/repos/anomalyco/rune/tarball/$revision" --output "$archive"
printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status
temporary=$(mktemp -d "${destination}.XXXXXX")
trap 'rm -rf "$temporary"' EXIT
tar -xzf "$archive" -C "$temporary" --strip-components=1
printf '%s\n' "$revision" > "$temporary/.revision"
mv "$temporary" "$destination"
