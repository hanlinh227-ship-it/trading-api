#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
STATE=/var/lib/meme-alpha/data/micro-live/state.json
WALLET=DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk
EXPECTED=68230517180a7867ec0b4b8a0068d9ab7e07ed1bc62324c498902969b638e2ab
echo '=== V352 POST V351 AUDIT ==='
ACTUAL=$(sha256sum "$APP/src/micro-live-executor.js" | awk '{print $1}')
echo EXECUTOR_SHA="$ACTUAL"
[ "$ACTUAL" = "$EXPECTED" ] && echo EXECUTOR_SHA_MATCH=TRUE || echo EXECUTOR_SHA_MATCH=FALSE
grep -q 'MICRO_LIVE_EXECUTOR_V351_ADAPTIVE_ALPHA=STARTED' "$APP/src/micro-live-executor.js" && echo V351_EXECUTOR_MARKER=TRUE || echo V351_EXECUTOR_MARKER=FALSE
grep -q 'ONLINE_EXPECTANCY_LEARNING=TRUE' "$APP/src/micro-live-executor.js" && echo ONLINE_LEARNING_MARKER=TRUE || echo ONLINE_LEARNING_MARKER=FALSE
grep -q 'JITO_REGION_RACE_WITH_SAFE_FALLBACK=TRUE' "$APP/src/micro-live-executor.js" && echo JITO_ROUTER_MARKER=TRUE || echo JITO_ROUTER_MARKER=FALSE
grep -q '^LIVE_SIGNAL_MAX_AGE_SEC=60$' "$APP/run-paper.sh" && echo SIGNAL_TTL_60=TRUE || echo SIGNAL_TTL_60=FALSE
grep -q 'paperExecutionEnabled:false' "$APP/run-paper.sh" && echo PAPER_EXECUTION_DISABLED=TRUE || echo PAPER_EXECUTION_DISABLED=FALSE
for s in meme-alpha-micro-live.service meme-alpha-paper.service meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service meme-alpha-signer.service; do echo "$s=$(systemctl is-active "$s" 2>/dev/null || true)"; done
if [ -f "$STATE" ]; then /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));console.log('STATE_VERSION='+(s.version||''));console.log('OPEN_POSITIONS='+((s.positions||[]).length));console.log('POSITION_MINTS='+JSON.stringify((s.positions||[]).map(x=>x.mint).sort()));console.log('LEARNING_CLOSED='+(s.learning?.totalClosed||0));console.log('LEARNING_WIN_RATE='+(s.learning?.totalClosed?((s.learning.totalWins||0)/s.learning.totalClosed):0));
NODE
else echo STATE_MISSING=TRUE; fi
for f in realtime-pool-pulse.json whale-flow-intel.json signal-snapshot.json micro-live-gate.json; do if [ -f "$APP/runtime-status/$f" ]; then /usr/bin/node - "$APP/runtime-status/$f" "$f" <<'NODE'
const fs=require('fs'),j=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),name=process.argv[3];const age=(Date.now()-Date.parse(j.updatedAt||j.timestamp||0))/1000;console.log(name+'_STATUS='+(j.status??j.allowed??''));console.log(name+'_AGE_SEC='+(Number.isFinite(age)?age.toFixed(2):'NA'));console.log(name+'_ROWS='+((j.rows||j.candidates||[]).length));
NODE
fi; done
/usr/bin/node - "$APP/config/runtime.json" "$WALLET" <<'NODE'
const fs=require('fs');const cfg=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),w=process.argv[3];async function rpc(m,p){const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:m,params:p}),signal:AbortSignal.timeout(8000)});const j=await r.json();if(j.error)throw new Error(j.error.message);return j.result}const b=await rpc('getBalance',[w,{commitment:'confirmed'}]);const t=await rpc('getTokenAccountsByOwner',[w,{programId:'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'},{encoding:'jsonParsed',commitment:'confirmed'}]);const nz=(t.value||[]).filter(x=>Number(x.account?.data?.parsed?.info?.tokenAmount?.amount||0)>0);console.log('LIVE_SOL='+(Number(b.value)/1e9).toFixed(9));console.log('NONZERO_TOKEN_ACCOUNTS='+nz.length)}
NODE
echo V352_POST_V351_AUDIT=COMPLETE
