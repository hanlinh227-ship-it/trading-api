#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-micro-live.service
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
SRC="$APP/src/micro-live-executor.js"
DST="$APP/ops/meme-alpha/micro-live/micro-live-executor-v218.js"
[ -f "$SRC" ] || { echo ABORT_EXECUTOR_MISSING; exit 1; }
grep -q 'MICRO_LIVE_EXECUTOR_V210_SMART_EXIT=STARTED' "$SRC" || { echo ABORT_EXPECTED_V210_RUNTIME; exit 1; }
cp "$SRC" "$DST"
python3 - "$DST" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
# Freshness helper and defense-in-depth entry freshness.
s=s.replace("const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;", "const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;\nconst fileAgeSec=p=>{try{return Math.max(0,(Date.now()-fs.statSync(p).mtimeMs)/1000)}catch{return Infinity}};\nconst ENTRY_SIGNAL_MAX_AGE_SEC=45,HARD_STALE_EXIT_SEC=180;",1)
s=s.replace("function trendEntryEligible(c){\n  if(!coreSafe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.consecutiveEligible)<1)return false;", "function trendEntryEligible(c){\n  if(fileAgeSec(SIGNAL)>ENTRY_SIGNAL_MAX_AGE_SEC)return false;\n  if(!coreSafe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.consecutiveEligible)<1)return false;",1)
# Make fast trend opportunity score affect scale tiers/ranking as well as eligibility.
s=s.replace("const score=n(c.score),con=n(c.consecutiveEligible),net=n(c.netBuyers5m)", "const score=opportunityScore(c),con=n(c.consecutiveEligible),net=n(c.netBuyers5m)",1)
s=s.replace("function rank(c){return n(c.score)*100+n(c.netBuyers5m)*2", "function rank(c){return opportunityScore(c)*100+n(c.netBuyers5m)*2",1)
# State watchdog.
s=s.replace("if(!Number.isFinite(Number(st.position.gateClosedCount)))st.position.gateClosedCount=0;", "if(!Number.isFinite(Number(st.position.gateClosedCount)))st.position.gateClosedCount=0;\n    if(!Number.isFinite(Number(st.position.dataStaleCount)))st.position.dataStaleCount=0;",1)
s=s.replace("profitProtectDone:false,scaleInLockedAfterProfit:false};event({type:'MICRO_BUY'", "profitProtectDone:false,scaleInLockedAfterProfit:false,dataStaleCount:0};event({type:'MICRO_BUY'",1)
# Distinguish normal profit-taking impact from emergency escape impact.
needle="async function sellFraction(st,fraction,reason){\n"
helper="""function sellImpactLimit(p,reason){
  const r=String(reason||'');
  if(r==='HARD_SAFETY_BREAK'||r==='SEVERE_TREND_BREAK'||r==='ANALYSIS_HARD_STALE')return p.maxSellPriceImpactPct;
  if(r==='CONFIRMED_TREND_BREAK')return Math.min(4,p.maxSellPriceImpactPct);
  if(r==='SMART_PROFIT_GIVEBACK')return Math.min(3,p.maxSellPriceImpactPct);
  if(r.startsWith('SMART_TP'))return Math.min(2,p.maxSellPriceImpactPct);
  return Math.min(4,p.maxSellPriceImpactPct);
}
async function sellFraction(st,fraction,reason){
"""
if needle not in s:raise SystemExit('SELL_FRACTION_NOT_FOUND')
s=s.replace(needle,helper,1)
s=s.replace("const o=await signer({op:'order',inputMint:m,outputMint:WSOL,amount:amount.toString(),maxPriceImpactPct:p.maxSellPriceImpactPct});if(!o.ok)throw new Error(`SIGNER_${o.error}`);", "const allowedSellImpact=sellImpactLimit(p,reason),o=await signer({op:'order',inputMint:m,outputMint:WSOL,amount:amount.toString(),maxPriceImpactPct:allowedSellImpact});if(!o.ok){if(o.error==='PRICE_IMPACT_LIMIT'){event({type:'SELL_DEFERRED_IMPACT',reason,mint:m,allowedSellImpactPct:allowedSellImpact});return{closed:false,skipped:true,reason:'PRICE_IMPACT_LIMIT'}}throw new Error(`SIGNER_${o.error}`)};",1)
# Do not mark a profit tier done when execution was deferred.
s=s.replace("if(!r.closed&&st.position){st.position.tp1Done=true", "if(!r.closed&&!r.skipped&&st.position){st.position.tp1Done=true",1)
s=s.replace("if(!r.closed&&st.position){st.position.tp2Done=true", "if(!r.closed&&!r.skipped&&st.position){st.position.tp2Done=true",1)
s=s.replace("if(!r.closed&&st.position){st.position.tp3Done=true", "if(!r.closed&&!r.skipped&&st.position){st.position.tp3Done=true",1)
s=s.replace("if(!r.closed&&st.position){st.position.profitProtectDone=true", "if(!r.closed&&!r.skipped&&st.position){st.position.profitProtectDone=true",1)
# Data staleness is tolerated transiently but cannot persist forever while holding risk.
s=s.replace("const c=candidate(st.position.mint),pos=st.position,age=(Date.now()-Date.parse(pos.openedAt||0))/1000;\n    if(!gate.allowed)pos.gateClosedCount=n(pos.gateClosedCount)+1;else pos.gateClosedCount=0;", "const c=candidate(st.position.mint),pos=st.position,age=(Date.now()-Date.parse(pos.openedAt||0))/1000,sigAge=fileAgeSec(SIGNAL);\n    if(!gate.allowed)pos.gateClosedCount=n(pos.gateClosedCount)+1;else pos.gateClosedCount=0;\n    const dataStale=!c||sigAge>60;pos.dataStaleCount=dataStale?Math.min(120,n(pos.dataStaleCount)+1):Math.max(0,n(pos.dataStaleCount)-1);",1)
s=s.replace("if(age>=75&&pos.weakExitCount>=4){await sell(st,'CONFIRMED_TREND_BREAK');return{action:'SELL',reason:'CONFIRMED_TREND_BREAK'}}", "if(sigAge>=HARD_STALE_EXIT_SEC||pos.dataStaleCount>=36){await sell(st,'ANALYSIS_HARD_STALE');return{action:'SELL',reason:'ANALYSIS_HARD_STALE'}}\n    if(age>=75&&pos.weakExitCount>=4){await sell(st,'CONFIRMED_TREND_BREAK');return{action:'SELL',reason:'CONFIRMED_TREND_BREAK'}}",1)
# Initial entries always start as a probe. A persistent strong/max candidate scales only after the first confirmed fill.
s=s.replace("const t=tier(c,p),r=await placeBuy(st,c,t,false);if(!r.placed)", "const qualified=tier(c,p),t={name:'PROBE_INITIAL_'+qualified.name,pct:p.probeUtilizationPct},r=await placeBuy(st,c,t,false);if(!r.placed)",1)
# Version markers.
s=s.replace("st.version='2.10.0'","st.version='2.18.0'",1)
s=s.replace("MICRO_LIVE_EXECUTOR_V210_SMART_EXIT=STARTED","MICRO_LIVE_EXECUTOR_V218_COHERENT=STARTED",1)
s=s.replace("MICRO_EXECUTOR_V210_SELF_TEST=PASS","MICRO_EXECUTOR_V218_SELF_TEST=PASS")
p.write_text(s)
PY
node --check "$DST"
node "$DST" --self-test | tee /tmp/v218-selftest.txt
grep -q 'MICRO_EXECUTOR_V218_SELF_TEST=PASS' /tmp/v218-selftest.txt
rm -f /tmp/v218-selftest.txt
grep -q 'PROBE_INITIAL_' "$DST"
grep -q 'ENTRY_SIGNAL_MAX_AGE_SEC=45' "$DST"
grep -q 'ANALYSIS_HARD_STALE' "$DST"
grep -q "Math.min(2,p.maxSellPriceImpactPct)" "$DST"
grep -q 'opportunityScore(c),con=' "$DST"
grep -q 'SELL_DEFERRED_IMPACT' "$DST"

echo RUNNER_ISOLATION=PASS
echo INITIAL_ENTRY_ALWAYS_PROBE_15_PCT=TRUE
echo SCALE_TIER_USES_FAST_TREND_SCORE=TRUE
echo ENTRY_SIGNAL_FRESHNESS_MAX_SEC=45
echo TRANSIENT_DATA_STALE_HOLD=TRUE
echo HARD_STALE_POSITION_EXIT_SEC=180
echo TP_SELL_IMPACT_CAP_PCT=2
echo GIVEBACK_SELL_IMPACT_CAP_PCT=3
echo CONFIRMED_BREAK_SELL_IMPACT_CAP_PCT=4
echo EMERGENCY_SELL_IMPACT_CAP_PCT=8
echo DEFER_PROFIT_SELL_IF_IMPACT_TOO_HIGH=TRUE
echo LIVE_RUNTIME_CHANGED=FALSE
echo ROOT_APPLY_REQUIRED=TRUE
echo V218_RUNTIME_COHERENCE_STAGE_PASS
