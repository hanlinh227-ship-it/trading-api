#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== V150 PRELIVE DIAG ==='
for f in src/universe.js src/validation.js src/security.js src/token2022-audit.js src/holder-cluster.js src/micro-live-gate.js config/runtime.json package.json; do
  echo "===== $f ====="
  sed -n '1,260p' "$f" 2>/dev/null || true
done
echo '===== PAPER FILES ====='
find /var/lib/meme-alpha/data/paper -maxdepth 1 -type f -printf '%f %s bytes\n' | sort || true
echo '===== VALIDATION OUTPUT ====='
cat /var/lib/meme-alpha/data/paper/validation.json 2>/dev/null || true
echo '===== RISK OUTPUT ====='
cat /var/lib/meme-alpha/data/paper/risk-state.json 2>/dev/null || true
echo '===== GATE OUTPUT ====='
cat /opt/meme-alpha/app/runtime-status/micro-live-gate.json 2>/dev/null || true
echo 'V150_DIAG_PASS'
