#!/usr/bin/env bash
set -euo pipefail

echo "This script installs the Python-side Android build tool."
echo "You still need a working JDK and Android SDK/NDK as required by Buildozer."
echo

if python3 - <<'PY'
import sys
raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)
PY
then
  python3 -m pip install --upgrade buildozer cython
else
  python3 -m pip install --user --upgrade buildozer cython
fi

echo
echo "Next:"
echo "  cd /home/tom/github/if-uri/urirun-android-node-app"
echo "  make apk"
