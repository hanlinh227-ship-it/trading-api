#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== V310 EXPANSION PATCH AUDIT ==='
echo '=== RUN PAPER ==='
nl -ba run-paper.sh | sed -n '1,360p'
echo '=== SCANNER DISCOVERY / ANALYZE ==='
nl -ba src/scanner.js | sed -n '1,690p'
echo '=== POSITION ALLOCATION ==='
nl -ba src/position.js | sed -n '220,340p'
echo '=== POSITION ENTRY ==='
nl -ba src/position.js | sed -n '800,990p'
echo '=== LIVE POLICY SAFE FIELDS ==='
node - <<'NODE'
const fs=require('fs'); const p='/etc/meme-alpha/micro-live-policy.json';
try{const x=JSON.parse(fs.readFileSync(p,'utf8')); const deny=/key|secret|token|private|seed|mnemonic|url|endpoint|wallet/i; const o={}; for(const [k,v] of Object.entries(x)) if(!deny.test(k)) o[k]=v; console.log(JSON.stringify(o,null,2));}catch(e){console.log('MICRO_LIVE_POLICY_UNREADABLE')}
NODE
echo 'V310_EXPANSION_PATCH_AUDIT_PASS'
