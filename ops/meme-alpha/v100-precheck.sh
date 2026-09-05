#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo "=== MEME ALPHA v1.0 PRECHECK TAIL ==="
node - <<'NODE'
const fs=require('fs');
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('JUPITER='+c.jupiter);
NODE

echo "=== POSITION.JS 220-620 ==="
sed -n '220,620p' src/position.js

echo "=== ENTRY MARKERS ==="
grep -nE 'PAPER_BUY|PAPER_PROBE|openPositions.push|remainingCostSol|entryPrice|qty' src/position.js || true

echo "=== RISK TAIL ==="
sed -n '220,520p' src/risk.js

echo "=== PAPER STATE ==="
node src/paper.js || true

echo "=== RESOURCE CHECK ==="
uptime
free -h

echo "V100_PRECHECK_TAIL_COMPLETE"
