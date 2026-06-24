#!/usr/bin/env bash
set -u

BASE="${1:-http://192.168.188.212:8195}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== urirun Android APK service diagnosis =="
echo "service: $BASE"
echo

echo "== service /api/status =="
if curl -fsS --max-time 5 "$BASE/api/status"; then
  echo
else
  echo "NOT REACHABLE: $BASE/api/status"
fi
echo

echo "== service /apk/ =="
if curl -fsS --max-time 5 "$BASE/apk/"; then
  echo
else
  echo "NOT REACHABLE: $BASE/apk/"
fi
echo

echo "== local APK files =="
found=0
for dir in \
  /home/tom/github/if-uri/urirun-service-android-node/apk \
  "$ROOT/bin" \
  /home/tom/github/if-uri/android-node-app/bin \
  "$HOME/.urirun/android-node/apk"
do
  echo "-- $dir"
  if find "$dir" -maxdepth 1 -type f -name '*.apk' -printf '%p %s bytes\n' 2>/dev/null | grep -q .; then
    find "$dir" -maxdepth 1 -type f -name '*.apk' -printf '%p %s bytes\n' 2>/dev/null
    found=1
  else
    echo "no apk"
  fi
done
echo

echo "== docker =="
if command -v docker >/dev/null 2>&1; then
  docker --version
  if docker info >/dev/null 2>&1; then
    echo "docker daemon: reachable"
  else
    echo "docker daemon: NOT reachable by this user"
  fi
else
  echo "docker: not installed"
fi
echo

if [ "$found" -eq 0 ]; then
  echo "RESULT: no APK exists. Build it with:"
  echo "  cd $ROOT"
  echo "  make docker-apk"
else
  echo "RESULT: APK exists. If /apk/ is empty, restart:"
  echo "  /home/tom/github/if-uri/urirun/venv/bin/urirun-android-node restart --host 0.0.0.0 --port 8195 --force-replace"
fi

