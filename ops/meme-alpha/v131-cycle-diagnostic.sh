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
systemctl --no-pager status meme-alpha-paper.service | tail -35 || true
echo '=== REACTION RUNTIME PROBE ==='
set +e
node src/reaction-telemetry.js
RC=$?
set -e
echo "REACTION_RC=$RC"
echo '=== REACTION SOURCE TAIL ==='
tail -120 src/reaction-telemetry.js || true
echo '=== RISK RUNTIME PROBE ==='
set +e
node src/risk.js
RRC=$?
set -e
echo "RISK_RC=$RRC"
echo '=== RECENT FAILURE CONTEXT ==='
tail -650 "$LOG" | grep -nE -C 8 'CYCLE_FAILED|FULL_CYCLE_FAILED|FAST_POSITION_TICK_FAILED|ReferenceError|TypeError|SyntaxError|MODULE_NOT_FOUND|ENOENT|HTTP [45][0-9][0-9]|JUPITER_.*FAIL|Error:' || true
echo '=== HEALTH/RISK ==='
cat /var/lib/meme-alpha/data/paper/scanner-source-health.json || true
cat /var/lib/meme-alpha/data/paper/risk-state.json || true
echo 'V131_RUNTIME_PROBE_COMPLETE'
