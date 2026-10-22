#!/bin/sh
set -eu
app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
NATIVE_DOCKER_CONFIGURATION=$("$app_dir/zig-out/bin/native-docker-client" --configuration)
export NATIVE_DOCKER_CONFIGURATION
exec "$app_dir/zig-out/bin/native-live-containers"
