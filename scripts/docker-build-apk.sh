#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${URIRUN_ANDROID_BUILD_IMAGE:-urirun-android-node-app:dev}"
SERVICE_APK_DIR="${SERVICE_APK_DIR:-/home/tom/github/if-uri/urirun-service-android-node/apk}"
DOCKERFILE="$ROOT/docker/Dockerfile.android-dev"
BUILDOZER_CACHE="${URIRUN_BUILDOZER_CACHE:-$HOME/.buildozer-cache}"
# Writable HOME for the in-container build user. The container runs as the host UID, so
# $HOME (/tmp/build-home) and its .local/.cache/.buildozer must be host-owned dirs — otherwise
# p4a's `pip install --user` hits "Permission denied: /tmp/build-home/.local".
BUILD_HOME="${URIRUN_ANDROID_BUILD_HOME:-$HOME/.urirun-android-build-home}"

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

# Pre-create the build user's HOME subdirs on the host (owned by this user) so the mapped
# UID can write .local/.cache inside the container. .buildozer is provided by the nested
# bind mount below (persistent SDK/NDK/dist cache across runs).
mkdir -p "$BUILD_HOME/.local" "$BUILD_HOME/.cache" "$BUILDOZER_CACHE"

# Pre-accept Android SDK licenses so sdkmanager runs non-interactively.
# These are the standard SHA1 hashes published by Google for automated CI builds.
SDK_LICENSES="$BUILDOZER_CACHE/android/platform/android-sdk/licenses"
mkdir -p "$SDK_LICENSES"
printf '8933bad161af4408b1c790f1ed2ff5e7de9e7e3c\nd56f5187479451eabf01fb78af6dfcb131a6481e\n24333f8a63b6825ea9c5514f83c2829b004d1fee\n' \
  > "$SDK_LICENSES/android-sdk-license"
printf '84831b9409646a918e30573bab4c9c91346d8abd\n' \
  > "$SDK_LICENSES/android-sdk-arm-dbt-license"
printf 'd975f751698a77b662f1254ddbeed3901e976f5a\n' \
  > "$SDK_LICENSES/intel-android-extra-license"
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -e HOME=/tmp/build-home \
  -e PYTHONUSERBASE=/tmp/build-home/.local \
  -e BUILDOZER_WARN_ON_ROOT=0 \
  -v "$ROOT:/work" \
  -v "$BUILD_HOME:/tmp/build-home" \
  -v "$BUILDOZER_CACHE:/tmp/build-home/.buildozer" \
  -w /work \
  "$IMAGE" \
  bash -c '
    set -e
    accept_licenses() {
      local sdkm
      sdkm=$(find /tmp/build-home/.buildozer -name sdkmanager -path "*/bin/*" 2>/dev/null | head -1)
      [ -n "$sdkm" ] || return 0
      local root
      root=$(dirname "$(dirname "$(dirname "$sdkm")")")
      # Accept EVERY SDK license (incl. brand-new build-tools that buildozer always grabs as
      # the latest) so sdkmanager installs them non-interactively.
      yes | "$sdkm" --sdk_root="$root" --licenses >/dev/null 2>&1 || true
    }
    accept_licenses
    # Run buildozer ONCE. A retry here is harmful: p4a recipe prebuilds (e.g. SDL2_image
    # git-cloning external/jpeg) are not idempotent, so a second run on partial state fails
    # with "destination path already exists". Re-run the whole script after a clean instead.
    buildozer android debug
  '

mkdir -p "$SERVICE_APK_DIR"
ls bin/*.apk >/dev/null 2>&1 || {
  echo "Build finished but no APK was found in $ROOT/bin" >&2
  exit 1
}
cp bin/*.apk "$SERVICE_APK_DIR"/
echo "Published APK files:"
ls -lh "$SERVICE_APK_DIR"/*.apk

