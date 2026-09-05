#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== V306 SCANNER HOTPATH AUDIT ==='
stat -c 'SRC_DIR owner=%U group=%G mode=%a' src 2>/dev/null || true
for f in src/scanner.js src/universe.js src/security.js src/token2022-audit.js src/holder-cluster.js src/persistence.js src/reaction-telemetry.js src/risk.js src/safe-signal-export.js src/position.js src/validation.js src/stress-test.js src/micro-live-gate.js; do
 [ -e "$f" ] || continue
 stat -c '%n owner=%U group=%G mode=%a size=%s' "$f" || true
 [ -w "$f" ] && echo "$f WRITABLE=TRUE" || echo "$f WRITABLE=FALSE"
done

echo '=== SCANNER DEEP / SELL-ROUTE HOT PATH ==='
if [ -r src/scanner.js ]; then
  nl -ba src/scanner.js | sed -n '690,1060p'
fi

echo '=== MICRO LIVE GATE LOGIC ==='
if [ -r src/micro-live-gate.js ]; then
  nl -ba src/micro-live-gate.js | sed -n '1,280p'
fi

echo '=== VALIDATION / STRESS COST SHAPE ==='
for f in src/validation.js src/stress-test.js; do
 [ -r "$f" ] || continue
 echo "--- $f"
 grep -nEi 'fetch|sleep|setTimeout|for *\(|for .* of|Promise\.all|writeFile|readFile' "$f" | head -160 || true
done

echo 'V306_SCANNER_HOTPATH_AUDIT_PASS'
