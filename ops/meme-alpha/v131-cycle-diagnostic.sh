#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
LOG=/var/log/meme-alpha/paper.log
cd "$APP"
echo '=== V1.3.1 CYCLE DIAGNOSTIC ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs'; const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8')); if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER'); console.log('MODE=PAPER');
NODE
echo '=== SERVICE ==='
systemctl --no-pager status meme-alpha-paper.service | tail -40 || true
echo '=== PACKAGE SCRIPTS ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs'; const j=JSON.parse(fs.readFileSync('package.json','utf8')); console.log(JSON.stringify(j.scripts,null,2));
NODE
echo '=== SOURCE SYNTAX ==='
for f in src/scanner.js src/universe.js src/security.js src/token2022-audit.js src/holder-cluster.js src/persistence.js src/reaction-telemetry.js src/risk.js src/position.js src/validation.js src/entry-exit-intelligence.js src/stress-validation.js; do
  if [ -f "$f" ]; then node --check "$f" >/dev/null && echo "SYNTAX_PASS $f" || echo "SYNTAX_FAIL $f"; else echo "MISSING $f"; fi
done
echo '=== RECENT FAILURE CONTEXT ==='
tail -500 "$LOG" | grep -nE -C 5 'CYCLE_FAILED|FULL_CYCLE_FAILED|FAST_POSITION_TICK_FAILED|ReferenceError|TypeError|SyntaxError|MODULE_NOT_FOUND|ENOENT|HTTP [45][0-9][0-9]|JUPITER_.*FAIL|Error:' || true
echo '=== RECENT TAIL ==='
tail -180 "$LOG"
echo '=== HEALTH/RISK ==='
cat /var/lib/meme-alpha/data/paper/scanner-source-health.json || true
cat /var/lib/meme-alpha/data/paper/risk-state.json || true
echo 'V131_DIAGNOSTIC_COMPLETE'
