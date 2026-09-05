#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
WALLET=DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk
STATE=/var/lib/meme-alpha/data/micro-live/state.json

echo '=== V358 LATEST SELL FORENSIC AUDIT ==='
echo NOW_UTC=$(date -u +%FT%TZ)
echo '--- executor service/process ---'
systemctl is-active meme-alpha-micro-live.service || true
pgrep -af '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true

echo '--- recent executor journal ---'
journalctl -u meme-alpha-micro-live.service --since '3 hours ago' --no-pager -o short-iso 2>/dev/null | tail -n 500 || true

echo '--- runtime status files likely containing trade history ---'
find "$APP/runtime-status" -maxdepth 1 -type f -printf '%f %s %TY-%Tm-%TdT%TH:%TM:%TS\n' 2>/dev/null | sort | grep -Ei 'micro|trade|event|exec|position|portfolio|audit|log' | tail -n 80 || true

echo '--- grep sell/exit/rotation/tp from runtime status text ---'
for f in "$APP"/runtime-status/*; do
  [ -f "$f" ] || continue
  case "$f" in *.json|*.jsonl|*.log|*.txt) grep -Ehi 'MICRO_SELL|SELL|EXIT|TAKE|TP[123]|PROFIT|ROTATION|ROTATE|TRAIL|WEAK|STOP' "$f" 2>/dev/null | tail -n 120 || true;; esac
done

echo '--- state as meme-alpha user ---'
if runuser -u meme-alpha -- test -r "$STATE"; then
  runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs');const s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
console.log('STATE_VERSION='+(s.version||''));
console.log('OPEN_POSITIONS='+((s.positions||[]).length));
for(const p of (s.positions||[])) console.log('POS '+JSON.stringify({mint:p.mint,symbol:p.symbol,costBasisLamports:p.costBasisLamports,lifetimeCostLamports:p.lifetimeCostLamports,realizedPnlLamports:p.realizedPnlLamports,lastReturnPct:p.lastReturnPct,peakReturnPct:p.peakReturnPct,tp1Done:p.tp1Done,tp2Done:p.tp2Done,tp3Done:p.tp3Done,profitProtectDone:p.profitProtectDone,lastMarkAt:p.lastMarkAt,lastQuoteAt:p.lastQuoteAt}));
console.log('CLOSED='+(s.closed||0));
console.log('LEARNING='+JSON.stringify(s.learning||{}));
NODE
else
  echo STATE_READ_VIA_RUNUSER=FALSE
fi

echo '--- latest wallet signatures + parsed tx deltas ---'
/usr/bin/node - "$APP/config/runtime.json" "$WALLET" <<'NODE'
const fs=require('fs');
const cfg=JSON.parse(fs.readFileSync(process.argv[2],'utf8')); const wallet=process.argv[3];
async function rpc(method,params){const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(12000)});const j=await r.json();if(j.error)throw new Error(JSON.stringify(j.error));return j.result}
(async()=>{
  const sigs=await rpc('getSignaturesForAddress',[wallet,{limit:20,commitment:'confirmed'}]);
  for(const s of sigs){
    let tx; try{tx=await rpc('getTransaction',[s.signature,{encoding:'jsonParsed',maxSupportedTransactionVersion:0,commitment:'confirmed'}])}catch(e){console.log('TXERR '+s.signature+' '+e.message);continue}
    if(!tx)continue; const m=tx.meta||{}; const keys=(tx.transaction?.message?.accountKeys||[]).map(k=>typeof k==='string'?k:k.pubkey); const wi=keys.indexOf(wallet);
    const preSol=wi>=0?Number(m.preBalances?.[wi]||0):0,postSol=wi>=0?Number(m.postBalances?.[wi]||0):0,solDelta=(postSol-preSol)/1e9;
    const pre=new Map(),post=new Map();
    for(const b of m.preTokenBalances||[])if(b.owner===wallet)pre.set(b.mint,Number(b.uiTokenAmount?.amount||0)/10**Number(b.uiTokenAmount?.decimals||0));
    for(const b of m.postTokenBalances||[])if(b.owner===wallet)post.set(b.mint,Number(b.uiTokenAmount?.amount||0)/10**Number(b.uiTokenAmount?.decimals||0));
    const deltas=[];for(const mint of new Set([...pre.keys(),...post.keys()])){const d=(post.get(mint)||0)-(pre.get(mint)||0);if(Math.abs(d)>0)deltas.push({mint,delta:d,pre:pre.get(mint)||0,post:post.get(mint)||0})}
    const likelySell=solDelta>0.0005&&deltas.some(x=>x.delta<0);
    console.log('TX '+JSON.stringify({signature:s.signature,blockTime:s.blockTime?new Date(s.blockTime*1000).toISOString():null,err:s.err,solDelta:Number(solDelta.toFixed(9)),feeSOL:Number((Number(m.fee||0)/1e9).toFixed(9)),likelySell,deltas}));
  }
})().catch(e=>{console.error('CHAIN_AUDIT_ERROR',e);process.exitCode=1});
NODE

echo V358_LATEST_SELL_FORENSIC_AUDIT=COMPLETE
