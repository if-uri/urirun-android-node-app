#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_APK_DIR="${SERVICE_APK_DIR:-/home/tom/github/if-uri/urirun-service-android-node/apk}"

cd "$ROOT"

command -v buildozer >/dev/null || {
  echo "buildozer not found. Run: $ROOT/scripts/setup-build-toolchain.sh" >&2
  exit 1
}
command -v java >/dev/null || {
  echo "java/JDK not found. Install a JDK required by Buildozer." >&2
  exit 1
}

buildozer android debug
mkdir -p "$SERVICE_APK_DIR"
cp bin/*.apk "$SERVICE_APK_DIR"/
echo "Published APK files:"
ls -lh "$SERVICE_APK_DIR"/*.apk

