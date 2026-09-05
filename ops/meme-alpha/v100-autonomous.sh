#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA AUTONOMOUS v1.0 INSPECTION ==='
node - <<'NODE'
const fs=require('fs');
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
NODE

echo '=== CURRENT EXECUTION REFERENCES ==='
grep -RniE 'dexscreener|jupiter|quote|priceImpact|PAPER_(BUY|SELL|PROBE)' src/position.js src/risk.js src/persistence.js package.json || true

echo '=== POSITION SOURCE ==='
sed -n '1,520p' src/position.js

echo '=== PACKAGE ==='
cat package.json

echo '=== SERVICE ==='
systemctl --no-pager is-active meme-alpha-paper.service || true
systemctl --no-pager is-enabled meme-alpha-paper.service || true

echo '=== RESOURCES ==='
free -h
uptime

echo 'V100_AUTONOMOUS_INSPECTION_COMPLETE'
