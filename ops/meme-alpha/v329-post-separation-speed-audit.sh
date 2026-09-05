#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
PUB='DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk'

echo '=== V329 POST-SEPARATION SPEED AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ
for i in 1 2 3 4 5 6; do
  /usr/bin/node - <<'NODE'
const fs=require('fs');
for(const [k,p] of Object.entries({signal:'/opt/meme-alpha/app/runtime-status/signal-snapshot.json',radar:'/opt/meme-alpha/app/runtime-status/new-listing-radar.json',gate:'/opt/meme-alpha/app/runtime-status/micro-live-gate.json',trend:'/opt/meme-alpha/app/runtime-status/trend-pulse.json',sep:'/opt/meme-alpha/app/runtime-status/execution-separation.json'})){
 try{const x=JSON.parse(fs.readFileSync(p,'utf8'));const t=x.timestamp||x.updatedAt||x.generatedAt||'';const age=(Date.now()-Date.parse(t))/1000;console.log(`${k} stamp=${t} ageSec=${Number.isFinite(age)?age.toFixed(2):'na'} status=${x.status||x.sourceHealth?.status||''} allowed=${x.allowed??''} candidates=${Array.isArray(x.candidates)?x.candidates.length:''}`)}catch(e){console.log(`${k}=unreadable`)}
}
NODE
  sleep 6
done

echo '=== LIVE CHAIN ==='
/usr/bin/node - "$PUB" <<'NODE'
const fs=require('fs'),pub=process.argv[2],cfg=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));async function rpc(method,params){const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params})});const j=await r.json();if(j.error)throw new Error(JSON.stringify(j.error));return j.result};(async()=>{const b=await rpc('getBalance',[pub,{commitment:'confirmed'}]);console.log('LIVE_SOL='+(b.value/1e9).toFixed(9));const t=await rpc('getTokenAccountsByOwner',[pub,{programId:'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'},{encoding:'jsonParsed',commitment:'confirmed'}]);let n=0;for(const x of t.value||[]){const i=x.account?.data?.parsed?.info||{},a=i.tokenAmount||{};if(BigInt(a.amount||'0')>0n){n++;console.log(`LIVE_TOKEN mint=${i.mint} amount=${a.uiAmountString}`)}}console.log('LIVE_TOKEN_COUNT='+n);const s=await rpc('getSignaturesForAddress',[pub,{limit:5,commitment:'confirmed'}]);for(const x of s)console.log(`SIG time=${x.blockTime?new Date(x.blockTime*1000).toISOString():'unknown'} sig=${x.signature} err=${x.err?JSON.stringify(x.err):'null'}`)})().catch(e=>{console.log('CHAIN_ERROR='+e.message);process.exit(1)});
NODE

echo V329_POST_SEPARATION_SPEED_AUDIT_PASS
