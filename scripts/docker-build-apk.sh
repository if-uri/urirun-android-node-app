#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${URIRUN_ANDROID_BUILD_IMAGE:-urirun-android-node-app:dev}"
SERVICE_APK_DIR="${SERVICE_APK_DIR:-/home/tom/github/if-uri/urirun-service-android-node/apk}"
DOCKERFILE="$ROOT/docker/Dockerfile.android-dev"
BUILDOZER_CACHE="${URIRUN_BUILDOZER_CACHE:-$HOME/.buildozer-cache}"

cd "$ROOT"

command -v docker >/dev/null || {
  echo "docker not found" >&2
  exit 1
}

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not reachable by this user." >&2
  echo "Run from a host terminal with Docker access, or add the user to the docker group." >&2
  exit 1
fi

if [[ "${URIRUN_ANDROID_BUILD_SKIP_IMAGE:-0}" != "1" ]]; then
  docker build -f "$DOCKERFILE" -t "$IMAGE" "$ROOT"
fi

mkdir -p "$BUILDOZER_CACHE"
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -e HOME=/tmp/build-home \
  -e BUILDOZER_WARN_ON_ROOT=0 \
  -v "$ROOT:/work" \
  -v "$BUILDOZER_CACHE:/tmp/build-home/.buildozer" \
  -w /work \
  "$IMAGE" \
  buildozer android debug

mkdir -p "$SERVICE_APK_DIR"
ls bin/*.apk >/dev/null 2>&1 || {
  echo "Build finished but no APK was found in $ROOT/bin" >&2
  exit 1
}
cp bin/*.apk "$SERVICE_APK_DIR"/
echo "Published APK files:"
ls -lh "$SERVICE_APK_DIR"/*.apk

