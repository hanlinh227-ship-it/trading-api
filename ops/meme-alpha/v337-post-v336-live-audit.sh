#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
EXE="$APP/src/micro-live-executor.js"
EXPECTED=608785762d5387b58a2bfb4adead1bf29e7cfe9c489472bf7013442a35ab21d2

echo '=== V337 POST V336 LIVE AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ
ACTUAL=$(sha256sum "$EXE"|awk '{print $1}')
echo EXECUTOR_SHA256=$ACTUAL
[ "$ACTUAL" = "$EXPECTED" ] || { echo EXECUTOR_HASH_MISMATCH; exit 2; }
node --check "$EXE"
echo EXECUTOR_V336_MARKER=$(grep -q 'MICRO_LIVE_EXECUTOR_V336_AUTONOMOUS' "$EXE" && echo true || echo false)
echo CONTINUOUS_ALLOCATION_MARKER=$(grep -q 'CONTINUOUS_ALLOCATION' "$EXE" && echo true || echo false)
echo ROTATION_MARKER=$(grep -q 'ROTATION_TO_STRONGER_OPPORTUNITY' "$EXE" && echo true || echo false)
echo DYNAMIC_EXIT_HEADROOM_MARKER=$(grep -q 'DYNAMIC_NETWORK_EXIT_HEADROOM' "$EXE" && echo true || echo false)
echo EXECUTOR_PROCESSES=$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)
echo SIGNER_PROCESSES=$(pgrep -fc '/usr/bin/python3 /opt/meme-alpha-signer/ready_signer.py' || true)
echo PAPER_RUNNER_PROCESSES=$(pgrep -fc '/bin/bash /opt/meme-alpha/app/run-paper.sh' || true)
node - <<'NODE'
const fs=require('fs');
function r(p,d={}){try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}}
const now=Date.now();
const g=r('/opt/meme-alpha/app/runtime-status/micro-live-gate.json');
const s=r('/opt/meme-alpha/app/runtime-status/signal-snapshot.json');
const n=r('/opt/meme-alpha/app/runtime-status/new-listing-radar.json');
const t=r('/opt/meme-alpha/app/runtime-status/trend-pulse.json');
const age=x=>{const z=Date.parse(x||0);return Number.isFinite(z)?((now-z)/1000).toFixed(2):'NA'};
console.log('GATE_ALLOWED='+g.allowed);
console.log('GATE_REASONS='+JSON.stringify(g.reasons||[]));
console.log('SIGNAL_SOURCE='+(s.sourceHealth||s.source||'NA'));
console.log('SIGNAL_CACHE='+(s.cache===true));
console.log('SIGNAL_CANDIDATES='+((s.candidates||[]).length));
console.log('SIGNAL_AGE_SEC='+age(s.timestamp||s.generatedAt));
console.log('RADAR_STATUS='+(n.status||'NA'));
console.log('RADAR_CANDIDATES='+((n.candidates||[]).length));
console.log('RADAR_AGE_SEC='+age(n.updatedAt||n.timestamp));
console.log('TREND_AGE_SEC='+age(t.timestamp));
NODE
# Public-chain wallet check using runtime RPC and known signer public key. Read-only.
node - <<'NODE'
const fs=require('fs');const pub='DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk';const cfg=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));
async function rpc(method,params){const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(12000)});const j=await r.json();if(j.error)throw new Error(JSON.stringify(j.error));return j.result}
(async()=>{const b=await rpc('getBalance',[pub,{commitment:'confirmed'}]);console.log('LIVE_SOL='+(Number(b.value)/1e9).toFixed(9));let out=[];for(const programId of ['TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA','TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb']){const x=await rpc('getTokenAccountsByOwner',[pub,{programId},{encoding:'jsonParsed',commitment:'confirmed'}]);for(const a of x.value||[]){const i=a.account?.data?.parsed?.info||{},u=i.tokenAmount||{};if(BigInt(u.amount||'0')>0n)out.push({mint:i.mint,amount:u.uiAmountString||String(u.uiAmount||0)});}}console.log('LIVE_NONZERO_TOKENS='+out.length);for(const x of out)console.log('LIVE_HOLDING mint='+x.mint+' amount='+x.amount);})().catch(e=>{console.error('CHAIN_AUDIT_ERROR='+e.message);process.exit(3)});
NODE

echo V337_POST_V336_LIVE_AUDIT_PASS
