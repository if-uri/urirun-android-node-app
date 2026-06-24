#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-http://127.0.0.1:8765}"

echo "== health =="
curl -fsS "$BASE/health"
echo
echo "== routes =="
curl -fsS "$BASE/routes"
echo
echo "== ping =="
curl -fsS -X POST "$BASE/run" \
  -H 'Content-Type: application/json' \
  -d '{"uri":"android://device/app/command/ping","payload":{"from":"test-uri-api"}}'
echo

