#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo "=== MEME ALPHA v1.0 PRECHECK ==="
node - <<'NODE'
const fs=require('fs');
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('JUPITER='+c.jupiter);
NODE

echo "=== PACKAGE ==="
cat package.json

echo "=== POSITION.JS ==="
sed -n '1,420p' src/position.js

echo "=== RISK.JS ==="
sed -n '1,320p' src/risk.js

echo "=== PERSISTENCE.JS HEAD ==="
sed -n '1,260p' src/persistence.js

echo "=== PAPER STATE ==="
node src/paper.js || true

echo "=== RESOURCE CHECK ==="
uptime
free -h

echo "V100_PRECHECK_COMPLETE"
