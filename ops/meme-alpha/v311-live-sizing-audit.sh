#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== V311 LIVE SIZING AUDIT ==='
stat -c 'executor owner=%U group=%G mode=%a size=%s' src/micro-live-executor.js 2>/dev/null || true
echo '=== EXECUTOR SIZING / ENTRY / LIMIT EXCERPTS ==='
grep -nEi 'size|allocation|exposure|equity|balance|max|limit|risk|buy|entry|scale|notional|sol|policy' src/micro-live-executor.js | head -320 || true
echo '=== EXECUTOR CORE 1-520 ==='
nl -ba src/micro-live-executor.js | sed -n '1,520p'
echo '=== LIVE STATE SAFE ==='
node - <<'NODE'
const fs=require('fs'); for(const p of ['/var/lib/meme-alpha/data/micro-live/state.json','/opt/meme-alpha/app/runtime-status/micro-live-gate.json']){try{const x=JSON.parse(fs.readFileSync(p,'utf8')); const deny=/key|secret|private|seed|mnemonic|raw|signed|transaction|wallet/i; const o={}; for(const [k,v] of Object.entries(x)) if(!deny.test(k)) o[k]=v; console.log(p,JSON.stringify(o,null,2));}catch{}}
NODE
echo V311_LIVE_SIZING_AUDIT_PASS
