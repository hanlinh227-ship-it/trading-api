#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== V327 LIVE/PAPER SEPARATION AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ

echo '=== RUN PAPER ==='
nl -ba run-paper.sh | sed -n '1,220p'

echo '=== PACKAGE SCRIPTS ==='
node - <<'NODE'
const p=require('/opt/meme-alpha/app/package.json');console.log(JSON.stringify(p.scripts||{},null,2));
NODE

echo '=== SOURCE EXECUTION REFERENCES ==='
for f in src/*.js; do
  [ -f "$f" ] || continue
  if grep -Eqi 'paper|position|cycle5|signal-snapshot|scanner|buy|sell|trade' "$f"; then
    echo "--- $f ---"
    grep -nEi 'paper|position|cycle5|signal-snapshot|scanner|buy|sell|trade' "$f" | head -180 || true
  fi
done

echo '=== RUNTIME CADENCE SAMPLE ==='
for i in 1 2 3 4; do
  node - <<'NODE'
const fs=require('fs');
for(const [k,p] of Object.entries({signal:'/opt/meme-alpha/app/runtime-status/signal-snapshot.json',radar:'/opt/meme-alpha/app/runtime-status/new-listing-radar.json',gate:'/opt/meme-alpha/app/runtime-status/micro-live-gate.json',trend:'/opt/meme-alpha/app/runtime-status/trend-pulse.json'})){
 try{const x=JSON.parse(fs.readFileSync(p,'utf8'));const t=x.timestamp||x.updatedAt||x.generatedAt||'';const age=(Date.now()-Date.parse(t))/1000;console.log(`${k} stamp=${t} ageSec=${Number.isFinite(age)?age.toFixed(2):'na'}`)}catch(e){console.log(`${k}=unreadable`)}
}
NODE
  sleep 8
done

echo '=== LIVE STATE PUBLIC CHAIN SNAPSHOT ==='
PUB='DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk'
node - "$PUB" <<'NODE'
const fs=require('fs');const pub=process.argv[2];const cfg=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));async function rpc(method,params){const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params})});const j=await r.json();if(j.error)throw new Error(JSON.stringify(j.error));return j.result};(async()=>{const b=await rpc('getBalance',[pub,{commitment:'confirmed'}]);console.log('SOL='+(b.value/1e9));const t=await rpc('getTokenAccountsByOwner',[pub,{programId:'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'},{encoding:'jsonParsed',commitment:'confirmed'}]);for(const x of t.value||[]){const i=x.account?.data?.parsed?.info||{},a=i.tokenAmount||{};if(BigInt(a.amount||'0')>0n)console.log(`TOKEN mint=${i.mint} amount=${a.uiAmountString}`)}})().catch(e=>{console.log('CHAIN_ERROR='+e.message);process.exit(1)});
NODE

echo V327_LIVE_PAPER_SEPARATION_AUDIT_PASS
