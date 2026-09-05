#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-micro-live.service
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi

echo '=== MEME ALPHA v2.10 SMART PROFIT / ANTI-WHIPSAW EXIT STAGE ==='
SRC="$APP/src/micro-live-executor.js"
DST="$APP/ops/meme-alpha/micro-live/micro-live-executor-v210.js"
[ -f "$SRC" ] || { echo ABORT_LIVE_EXECUTOR_MISSING; exit 1; }
grep -q 'MICRO_LIVE_EXECUTOR_V290_FAST_TREND=STARTED\|MICRO_LIVE_EXECUTOR_V210_SMART_EXIT=STARTED' "$SRC" || { echo ABORT_UNEXPECTED_EXECUTOR_BASE; exit 1; }
mkdir -p "$APP/ops/meme-alpha/micro-live"
cp "$SRC" "$DST"

python3 - "$DST" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
if 'MICRO_LIVE_EXECUTOR_V210_SMART_EXIT=STARTED' in s:
 print('ALREADY_PATCHED_V210=TRUE');sys.exit(0)

# Add non-signing Jupiter order preview helper. It never executes or signs.
s=s.replace("async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'content-type':'application/json','accept':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});const txt=await r.text();let j;try{j=JSON.parse(txt)}catch{j={raw:txt}};if(!r.ok)throw new Error(`HTTP_${r.status}`);return j}\n",
"async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'content-type':'application/json','accept':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});const txt=await r.text();let j;try{j=JSON.parse(txt)}catch{j={raw:txt}};if(!r.ok)throw new Error(`HTTP_${r.status}`);return j}\nasync function getJson(url){const r=await fetch(url,{headers:{'accept':'application/json','user-agent':'meme-alpha-v210-smart-exit'},signal:AbortSignal.timeout(12000)});const txt=await r.text();let j;try{j=JSON.parse(txt)}catch{j={raw:txt}};if(!r.ok)throw new Error(`HTTP_${r.status}`);return j}\n",1)

old="""function holdSafe(c){
  if(!coreSafe(c))return false;
  if(n(c.score)<55)return false;
  if(n(c.priceChange5m,-999)<=-5.5)return false;
  if(n(c.netBuyers5m,0)<=-10)return false;
  return true;
}
"""
new="""function hardSafetyBroken(c){
  if(!c)return false; // missing/stale analysis is not itself a reason to dump a live token
  if((Array.isArray(c.hardReject)&&c.hardReject.length>0)||c.sellRoute===false||c.token2022===true)return true;
  if(c.securityDecision==='BLOCK'||c.holderClusterDecision==='BLOCK')return true;
  if(n(c.liquidityUsd,999999)<20_000)return true;
  return false;
}
function severeTrendBreak(c){
  if(!c)return false;
  const p=pulseFor(c),chg=p?n(p.price5m,n(c.priceChange5m)):n(c.priceChange5m),net=n(c.netBuyers5m),bs=p?n(p.buySellRatio,1):n(c.buySellRatio5m,1);
  return chg<=-13||net<=-30||(chg<=-9&&bs<0.55);
}
function softTrendWeak(c){
  if(!c)return false;
  const p=pulseFor(c),chg=p?n(p.price5m,n(c.priceChange5m)):n(c.priceChange5m),net=n(c.netBuyers5m),bs=p?n(p.buySellRatio,1):n(c.buySellRatio5m,1),pulse=n(p?.pulseScore,50);
  return n(c.score)<52||chg<=-7||net<=-12||(p?.status==='EXHAUSTED'&&pulse<50&&bs<0.85);
}
function holdSafe(c){return !hardSafetyBroken(c)&&!severeTrendBreak(c)&&!softTrendWeak(c)}
function profitThresholds(c){
  const p=pulseFor(c),strong=!!p&&p.status==='BREAKOUT'&&n(p.pulseScore)>=75&&n(p.buySellRatio)>=1.10;
  return strong?{tp1:30,tp2:70,tp3:130}:{tp1:22,tp2:50,tp3:100};
}
"""
if old not in s:raise SystemExit('HOLD_SAFE_PATTERN_NOT_FOUND')
s=s.replace(old,new,1)

# State migration/defaults for live smart exit.
needle="""    if(!st.position.lastAddAt)st.position.lastAddAt=st.position.openedAt||null;
"""
insert="""    if(!st.position.lastAddAt)st.position.lastAddAt=st.position.openedAt||null;
    if(!Number.isFinite(Number(st.position.weakExitCount)))st.position.weakExitCount=0;
    if(!Number.isFinite(Number(st.position.gateClosedCount)))st.position.gateClosedCount=0;
    if(!Number.isFinite(Number(st.position.peakReturnPct)))st.position.peakReturnPct=null;
    if(!Number.isFinite(Number(st.position.lastReturnPct)))st.position.lastReturnPct=null;
    st.position.tp1Done=st.position.tp1Done===true;st.position.tp2Done=st.position.tp2Done===true;st.position.tp3Done=st.position.tp3Done===true;st.position.profitProtectDone=st.position.profitProtectDone===true;st.position.scaleInLockedAfterProfit=st.position.scaleInLockedAfterProfit===true;
"""
if needle not in s:raise SystemExit('NORMALIZE_PATTERN_NOT_FOUND')
s=s.replace(needle,insert,1)
s=s.replace("st.version='2.9.0'","st.version='2.10.0'",1)

# Ensure newly opened positions carry smart-exit state immediately.
s=s.replace("walletBeforeSolLamports:beforeSol,walletAfterSolLamports:afterSol};event({type:'MICRO_BUY'",
"walletBeforeSolLamports:beforeSol,walletAfterSolLamports:afterSol,weakExitCount:0,gateClosedCount:0,peakReturnPct:null,lastReturnPct:null,tp1Done:false,tp2Done:false,tp3Done:false,profitProtectDone:false,scaleInLockedAfterProfit:false};event({type:'MICRO_BUY'",1)

# Replace full-only sell with mark preview + partial sell accounting + full wrapper.
pat=r"async function sell\(st,reason\)\{.*?\n\}\n\nasync function observeCapital"
replacement="""async function previewExitReturn(st,pub){
  const pos=st.position;if(!pos)return null;const now=Date.now(),last=Date.parse(pos.lastMarkAt||0);
  if(Number.isFinite(last)&&now-last<10_000&&Number.isFinite(Number(pos.lastReturnPct)))return Number(pos.lastReturnPct);
  const amount=await tokenBalance(pub,pos.mint);if(amount<=0n)return null;
  const cfg=read(`${APP}/config/runtime.json`),u=new URL(`${String(cfg.jupiter).replace(/\\/$/,'')}/swap/v2/order`);u.searchParams.set('inputMint',pos.mint);u.searchParams.set('outputMint',WSOL);u.searchParams.set('amount',amount.toString());u.searchParams.set('taker',pub);
  const q=await getJson(u.toString()),out=n(q.outAmount??q.outputAmount??q.otherAmountThreshold,-1),cost=n(pos.costBasisLamports||pos.entrySolLamports);
  if(out<=0||cost<=0)throw new Error('EXIT_PREVIEW_INVALID');const ret=(out-cost)/cost*100;pos.lastReturnPct=ret;pos.peakReturnPct=Number.isFinite(Number(pos.peakReturnPct))?Math.max(Number(pos.peakReturnPct),ret):ret;pos.lastMarkAt=new Date().toISOString();pos.lastPreviewOutLamports=out;pos.lastPreviewImpactPct=n(q.priceImpactPct,0);return ret;
}
async function sellFraction(st,fraction,reason){
  const p=rootPolicy(),h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)throw new Error('SIGNER_WALLET_UNAVAILABLE');const pos=st.position,m=pos.mint,beforeTok=await tokenBalance(h.publicKey,m),beforeSol=await solBalance(h.publicKey);if(beforeTok<=0n){event({type:'MICRO_POSITION_CLEARED_NO_TOKEN',reason,mint:m});st.position=null;atomic(statePath,st);return{closed:true}}
  const f=Math.max(0.01,Math.min(1,n(fraction,1)));let amount=f>=0.999?beforeTok:(beforeTok*BigInt(Math.max(1,Math.floor(f*1_000_000))))/1_000_000n;if(amount<=0n)amount=beforeTok;
  const o=await signer({op:'order',inputMint:m,outputMint:WSOL,amount:amount.toString(),maxPriceImpactPct:p.maxSellPriceImpactPct});if(!o.ok)throw new Error(`SIGNER_${o.error}`);
  const sig=await executeOrder(o),afterTok=await tokenBalance(h.publicKey,m),afterSol=await solBalance(h.publicKey);if(afterTok>=beforeTok)throw new Error('SELL_TOKEN_DELTA_ZERO');
  const sold=beforeTok-afterTok,received=Math.max(0,afterSol-beforeSol),oldCost=n(pos.costBasisLamports||pos.entrySolLamports),allocatedCost=Math.min(oldCost,Math.round(oldCost*Number(sold)/Number(beforeTok))),pnl=received-allocatedCost,cap=ensureCapital(st);cap.realizedTradingPnlLamports=n(cap.realizedTradingPnlLamports)+pnl;observeBalance(st,afterSol,p.externalFlowThresholdLamports,{suppress:true});
  const fullyClosed=afterTok<=0n||f>=0.999;if(fullyClosed){st.closed=n(st.closed)+1;st.position=null}else{pos.tokenRaw=afterTok.toString();pos.costBasisLamports=Math.max(0,oldCost-allocatedCost);pos.entrySolLamports=pos.costBasisLamports;pos.scaleInLockedAfterProfit=true;pos.lastProfitActionAt=new Date().toISOString()}
  event({type:fullyClosed?'MICRO_SELL':'MICRO_PARTIAL_SELL',mint:m,symbol:pos.symbol,reason,fractionRequested:f,signature:sig,tokenRawSold:sold.toString(),solLamportsReceived:received,allocatedCostBasisLamports:allocatedCost,pnlLamports:pnl,pnlSol:pnl/1e9,remainingTokenRaw:afterTok.toString(),remainingCostBasisLamports:fullyClosed?0:pos.costBasisLamports,realizedTradingPnlLamports:cap.realizedTradingPnlLamports});atomic(statePath,st);return{closed:fullyClosed,pnl,signature:sig};
}
async function sell(st,reason){return await sellFraction(st,1,reason)}

async function observeCapital"""
s2,nsub=re.subn(pat,replacement,s,count=1,flags=re.S)
if nsub!=1:raise SystemExit('SELL_PATTERN_NOT_FOUND')
s=s2

# Replace live-position branch: gate closure blocks new risk but does not force a blind dump;
# hard safety exits immediately; trend weakness is debounced; profits are harvested partially.
pat=r"  if\(st\.position\)\{\n.*?    await observeCapital\(st\);return\{action:'HOLD',reason:t\.name\|\|'SAFE'\};\n  \}"
replacement="""  if(st.position){
    const c=candidate(st.position.mint),pos=st.position,age=(Date.now()-Date.parse(pos.openedAt||0))/1000;
    if(!gate.allowed)pos.gateClosedCount=n(pos.gateClosedCount)+1;else pos.gateClosedCount=0;
    if(hardSafetyBroken(c)){await sell(st,'HARD_SAFETY_BREAK');return{action:'SELL',reason:'HARD_SAFETY_BREAK'}}
    if(severeTrendBreak(c)){await sell(st,'SEVERE_TREND_BREAK');return{action:'SELL',reason:'SEVERE_TREND_BREAK'}}
    const weak=softTrendWeak(c);pos.weakExitCount=weak?Math.min(12,n(pos.weakExitCount)+1):Math.max(0,n(pos.weakExitCount)-1);
    let ret=null;try{const h=await signer({op:'health'});if(h.ok&&h.publicKey&&h.walletLoaded)ret=await previewExitReturn(st,h.publicKey)}catch(e){event({type:'EXIT_PREVIEW_FAIL',error:String(e.message||e).slice(0,160)})}
    const th=profitThresholds(c),peak=n(pos.peakReturnPct,ret??0),giveback=peak-n(ret,peak);
    if(Number.isFinite(ret)){
      if(!pos.tp1Done&&ret>=th.tp1){const r=await sellFraction(st,0.15,'SMART_TP1');if(!r.closed&&st.position){st.position.tp1Done=true;st.position.scaleInLockedAfterProfit=true;atomic(statePath,st)}return{action:'PARTIAL_SELL',reason:'SMART_TP1'}}
      if(!pos.tp2Done&&ret>=th.tp2){const r=await sellFraction(st,0.20,'SMART_TP2');if(!r.closed&&st.position){st.position.tp2Done=true;st.position.scaleInLockedAfterProfit=true;atomic(statePath,st)}return{action:'PARTIAL_SELL',reason:'SMART_TP2'}}
      if(!pos.tp3Done&&ret>=th.tp3){const r=await sellFraction(st,0.15,'SMART_TP3_RUNNER_LOCK');if(!r.closed&&st.position){st.position.tp3Done=true;st.position.scaleInLockedAfterProfit=true;atomic(statePath,st)}return{action:'PARTIAL_SELL',reason:'SMART_TP3_RUNNER_LOCK'}}
      const protectGiveback=Math.max(10,peak*0.35);
      if(!pos.profitProtectDone&&peak>=25&&giveback>=protectGiveback&&pos.weakExitCount>=1&&ret>0){const r=await sellFraction(st,0.25,'SMART_PROFIT_GIVEBACK');if(!r.closed&&st.position){st.position.profitProtectDone=true;st.position.scaleInLockedAfterProfit=true;atomic(statePath,st)}return{action:'PARTIAL_SELL',reason:'SMART_PROFIT_GIVEBACK'}}
    }
    if(age>=75&&pos.weakExitCount>=4){await sell(st,'CONFIRMED_TREND_BREAK');return{action:'SELL',reason:'CONFIRMED_TREND_BREAK'}}
    if(gate.allowed&&!pos.scaleInLockedAfterProfit&&pos.weakExitCount===0){const t=tier(c,p),last=Date.parse(pos.lastAddAt||pos.openedAt||0),addAge=(Date.now()-last)/1000;if(t.pct>0&&addAge>=p.minAddIntervalSec){const r=await placeBuy(st,c,t,true);if(r.placed)return{action:'ADD',reason:t.name}}}
    await observeCapital(st);return{action:'HOLD',reason:!gate.allowed?'ENTRY_GATE_CLOSED_HOLD':(weak?'WEAKNESS_CONFIRMING':'TREND_HEALTHY')};
  }"""
s2,nsub=re.subn(pat,replacement,s,count=1,flags=re.S)
if nsub!=1:raise SystemExit('POSITION_BRANCH_PATTERN_NOT_FOUND')
s=s2

s=s.replace('MICRO_LIVE_EXECUTOR_V290_FAST_TREND=STARTED','MICRO_LIVE_EXECUTOR_V210_SMART_EXIT=STARTED',1)
s=s.replace('MICRO_EXECUTOR_V290_SELF_TEST=PASS','MICRO_EXECUTOR_V210_SELF_TEST=PASS')
p.write_text(s)
PY

node --check "$DST"
# Existing deterministic self-test must remain safe. If it is absent/fails, stage aborts.
node "$DST" --self-test | tee /tmp/v210-exec.txt
grep -q 'MICRO_EXECUTOR_V210_SELF_TEST=PASS' /tmp/v210-exec.txt
rm -f /tmp/v210-exec.txt

grep -q 'HARD_SAFETY_BREAK' "$DST"
grep -q 'CONFIRMED_TREND_BREAK' "$DST"
grep -q 'SMART_TP1' "$DST"
grep -q 'SMART_TP2' "$DST"
grep -q 'SMART_TP3_RUNNER_LOCK' "$DST"
grep -q 'SMART_PROFIT_GIVEBACK' "$DST"
grep -q 'scaleInLockedAfterProfit' "$DST"
grep -q "fractionRequested" "$DST"
grep -q "if(!gate.allowed)pos.gateClosedCount" "$DST"

install -m 0755 "$ROOT/ops/meme-alpha/v210-root-apply-smart-profit-exit.sh" "$APP/ops/meme-alpha/v210-root-apply-smart-profit-exit.sh"

echo RUNNER_ISOLATION=PASS
echo FULL_EXIT_ON_TRANSIENT_GATE_CLOSE=REMOVED
echo HARD_SAFETY_EXIT=IMMEDIATE
echo SEVERE_TREND_BREAK_EXIT=IMMEDIATE
echo SOFT_TREND_BREAK_CONFIRM_TICKS=4
echo SOFT_TREND_MIN_HOLD_SEC=75
echo PROFIT_TP1_NORMAL_PCT=22
echo PROFIT_TP1_STRONG_TREND_PCT=30
echo PROFIT_TP1_SELL_FRACTION=15PCT_REMAINING
echo PROFIT_TP2_NORMAL_PCT=50
echo PROFIT_TP2_STRONG_TREND_PCT=70
echo PROFIT_TP2_SELL_FRACTION=20PCT_REMAINING
echo PROFIT_TP3_NORMAL_PCT=100
echo PROFIT_TP3_STRONG_TREND_PCT=130
echo PROFIT_TP3_SELL_FRACTION=15PCT_REMAINING
echo PROFIT_GIVEBACK_PARTIAL_PROTECT=25PCT_REMAINING
echo RUNNER_REMAINS_OPEN_WHILE_TREND_HEALTHY=TRUE
echo SCALE_IN_LOCKS_AFTER_FIRST_PROFIT_HARVEST=TRUE
echo JUPITER_EXIT_PREVIEW_NON_SIGNING=TRUE
echo LIVE_RUNTIME_CHANGED=FALSE
echo ROOT_APPLY_REQUIRED=TRUE
echo V210_SMART_PROFIT_EXIT_STAGE_PASS
