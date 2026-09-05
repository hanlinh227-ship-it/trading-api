#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
LOG=/var/log/meme-alpha/paper.log
cd "$APP"
echo '=== V1.3.1 PERSISTENCE EXIT-CODE PROBE ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs'; const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8')); if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER'); console.log('MODE=PAPER');
NODE
echo '=== PERSISTENCE RUNTIME PROBE ==='
set +e
node src/persistence.js
PRC=$?
set -e
echo "PERSISTENCE_RC=$PRC"
echo '=== PERSISTENCE SOURCE TAIL ==='
tail -180 src/persistence.js || true
echo '=== REACTION/RISK PROBE ==='
set +e
node src/reaction-telemetry.js; RRC=$?
node src/risk.js; KRC=$?
set -e
echo "REACTION_RC=$RRC"
echo "RISK_RC=$KRC"
echo '=== RECENT FULL-CYCLE MARKERS ==='
tail -500 "$LOG" | grep -nE -C 3 'PERSISTENCE_STATUS|PERSISTENCE_INVARIANT|UNSAFE|FULL_CYCLE_FAILED|FULL_CYCLE_COMPLETE' || true
echo 'V131_PERSISTENCE_PROBE_COMPLETE'
