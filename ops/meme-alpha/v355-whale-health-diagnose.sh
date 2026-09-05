#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SIG="$APP/runtime-status/signal-snapshot.json"
WHALE="$APP/runtime-status/whale-flow-intel.json"
CFG="$APP/config/runtime.json"
echo '=== V355 WHALE HEALTH DIAGNOSE ==='
for i in 1 2 3 4 5; do
  node - "$SIG" "$WHALE" <<'NODE'
const fs=require('fs');
const sig=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const wh=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const pass=(sig.candidates||[]).filter(x=>x?.mint&&x?.securityDecision==='PASS'&&x?.holderClusterDecision==='PASS');
const age=(Date.now()-Date.parse(wh.updatedAt||0))/1000;
console.log(`SAMPLE pass=${pass.length} whaleStatus=${wh.status} whaleRows=${(wh.rows||[]).length} whaleAge=${age.toFixed(2)}`);
if(pass[0])console.log('TEST_MINT='+pass[0].mint);
NODE
  sleep 12
done
node - "$SIG" "$CFG" <<'NODE'
const fs=require('fs');
const sig=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const cfg=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const c=(sig.candidates||[]).find(x=>x?.mint&&x?.securityDecision==='PASS'&&x?.holderClusterDecision==='PASS');
if(!c){console.log('RPC_TEST=NO_ELIGIBLE_CANDIDATE');process.exit(0)}
async function rpc(method,params){const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(8000)});const j=await r.json();if(j.error)throw new Error(`${method}:${j.error.code}:${j.error.message}`);return j.result}
(async()=>{try{const a=await rpc('getTokenLargestAccounts',[c.mint,{commitment:'confirmed'}]);const b=await rpc('getTokenSupply',[c.mint,{commitment:'confirmed'}]);console.log('RPC_TEST=PASS');console.log('RPC_LARGEST_ROWS='+(a?.value||[]).length);console.log('RPC_SUPPLY='+(b?.value?.amount||''));}catch(e){console.log('RPC_TEST=FAIL');console.log('RPC_ERROR='+String(e.message||e).slice(0,300));}})();
NODE
echo V355_WHALE_HEALTH_DIAGNOSE=COMPLETE
