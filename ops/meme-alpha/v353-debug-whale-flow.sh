#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
echo '=== V353 WHALE FLOW DEBUG ==='
if [ -f "$APP/runtime-status/signal-snapshot.json" ]; then
  /usr/bin/node - "$APP/config/runtime.json" "$APP/runtime-status/signal-snapshot.json" <<'NODE'
const fs=require('fs');
(async()=>{
  const cfg=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const s=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
  const c=(s.candidates||[]).find(x=>x?.mint&&x?.securityDecision==='PASS'&&x?.holderClusterDecision==='PASS');
  console.log('CANDIDATE_MINT='+(c?.mint||'NONE'));
  if(!c)return;
  async function rpc(method,params){const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(8000)});const txt=await r.text();let j;try{j=JSON.parse(txt)}catch{j={raw:txt}};console.log(method+'_HTTP='+r.status);console.log(method+'_BODY='+JSON.stringify(j).slice(0,1200));}
  await rpc('getTokenSupply',[c.mint,{commitment:'confirmed'}]);
  await rpc('getTokenLargestAccounts',[c.mint,{commitment:'confirmed'}]);
})().catch(e=>{console.log('DEBUG_ERROR='+String(e.message||e));process.exit(0)})
NODE
else echo SIGNAL_MISSING=TRUE; fi
journalctl -u meme-alpha-whale-flow.service -n 80 --no-pager 2>/dev/null | tail -80 || true
if [ -f "$APP/runtime-status/whale-flow-intel.json" ]; then cat "$APP/runtime-status/whale-flow-intel.json" | head -100; fi
echo V353_WHALE_FLOW_DEBUG=COMPLETE
