#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v1.1.1 REACTION/ORCHESTRATION INSPECTION ==='
node - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('SCANNER_INTERVAL_MS='+c.scannerIntervalMs);
NODE

echo '=== POSITION ARG/MANAGE/ENTRY MARKERS ==='
grep -nE 'process\.argv|openPositions|for \(const pos|PAPER_BUY_PROBE|PAPER_SELL|ENTRY_ALLOWED|RISK_STATE_FRESH|SOURCE_HEALTH_ENTRY_GATE|POSITION_ENGINE_STATUS|closeFraction|emergency|thesis|tp1|tp2' src/position.js || true

echo '=== POSITION CORE 260-1040 ==='
sed -n '260,1040p' src/position.js

echo '=== RISK CURRENT ==='
sed -n '1,420p' src/risk.js

echo '=== RUN LOOP ==='
cat run-paper.sh

echo '=== PACKAGE ==='
cat package.json

echo '=== LATEST LOG TAIL ==='
tail -120 /var/log/meme-alpha/paper.log || true

echo '=== SERVICE ==='
systemctl --no-pager is-active meme-alpha-paper.service || true
systemctl --no-pager is-enabled meme-alpha-paper.service || true

echo 'V111_INSPECTION_COMPLETE'
