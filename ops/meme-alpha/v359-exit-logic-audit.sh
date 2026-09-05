#!/usr/bin/env bash
set -euo pipefail
SRC=/opt/meme-alpha/app/src/micro-live-executor.js
echo '=== V359 EXIT LOGIC AUDIT ==='
node - "$SRC" <<'NODE'
const fs=require('fs'),s=fs.readFileSync(process.argv[2],'utf8');
for(const needle of ['function event','async function placeSell','function profitPlan','async function managePosition','async function maybeRotate','ROTATION_TO_STRONGER_OPPORTUNITY','PROFIT_PROTECT','TP1','TRAIL','WEAK']){
 const i=s.indexOf(needle); if(i>=0){console.log('\n--- '+needle+' ---');console.log(s.slice(Math.max(0,i-500),Math.min(s.length,i+5000)));}
}
NODE
echo V359_EXIT_LOGIC_AUDIT=COMPLETE
