#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA AUTONOMOUS v1.0 ENTRY INSPECTION ==='
node - <<'NODE'
const fs=require('fs');
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
NODE

echo '=== POSITION ENTRY SECTION ==='
sed -n '500,940p' src/position.js

echo '=== STATE SUMMARY ==='
node src/paper.js || true

echo '=== SERVICE ==='
systemctl --no-pager is-active meme-alpha-paper.service || true
systemctl --no-pager is-enabled meme-alpha-paper.service || true

echo 'V100_ENTRY_INSPECTION_COMPLETE'
