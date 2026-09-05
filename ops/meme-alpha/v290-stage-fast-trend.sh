#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-signer.service
systemctl is-active --quiet meme-alpha-micro-live.service
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi

echo '=== MEME ALPHA v2.9.0 FAST TREND INTELLIGENCE STAGE ==='
TREND_SRC="$ROOT/ops/meme-alpha/trend-pulse-v290.js"
TREND_STAGE="$APP/ops/meme-alpha/trend-pulse-v290.js"
EXEC_BASE="$APP/ops/meme-alpha/micro-live/micro-live-executor-v280.js"
EXEC_STAGE="$APP/ops/meme-alpha/micro-live/micro-live-executor-v290.js"
SIGNER_BASE="$APP/ops/meme-alpha/signer/ready_signer_v6.py"
SIGNER_STAGE="$APP/ops/meme-alpha/signer/ready_signer_v7.py"
[ -f "$EXEC_BASE" ] || { echo ABORT_V280_EXECUTOR_NOT_STAGED; exit 1; }
[ -f "$SIGNER_BASE" ] || { echo ABORT_V6_SIGNER_NOT_STAGED; exit 1; }
mkdir -p "$APP/ops/meme-alpha/micro-live" "$APP/ops/meme-alpha/signer"
cp "$TREND_SRC" "$TREND_STAGE"
node --check "$TREND_STAGE"
node "$TREND_STAGE" --self-test

cp "$EXEC_BASE" "$EXEC_STAGE"
python3 - "$EXEC_STAGE" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
s=s.replace("const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;","const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;\nconst TREND=`${APP}/runtime-status/trend-pulse.json`;",1)
pat=r"function opportunityLane\(c\)\{.*?\n\}\nfunction trendEntryEligible\(c\)\{.*?\n\}\n"
new="""function pulseFor(c){
  const t=read(TREND,{}),age=(Date.now()-Date.parse(t.timestamp||0))/1000;
  if(!Number.isFinite(age)||age<0||age>10)return null;
  return (t.rows||[]).find(x=>x.mint===c.mint)||null;
}
function themeStrength(c){
  const t=read(TREND,{}),age=(Date.now()-Date.parse(t.timestamp||0))/1000,p=pulseFor(c);
  if(!p||!Number.isFinite(age)||age>10)return 0;
  return n((t.themes||[]).find(x=>x.narrative===p.narrative)?.strength);
}
function opportunityScore(c){
  const base=n(c.score),p=pulseFor(c);if(!p)return base;
  let add=0;
  if(n(p.volumeAcceleration)>=1.45)add+=4;else if(n(p.volumeAcceleration)>=1.10)add+=2;
  if(n(p.txnAcceleration)>=1.30)add+=3;else if(n(p.txnAcceleration)>=1.05)add+=1;
  if(n(p.buySellRatio)>=1.25)add+=2;
  if(themeStrength(c)>=60)add+=2;
  if(n(p.pulseScore)>=70)add+=1;
  if(p.status==='EXHAUSTED')add-=8;
  if(p.promotionFlag===true&&n(p.pulseScore)<65)add-=3;
  return Math.max(base-8,Math.min(base+12,base+add));
}
function opportunityLane(c){
  const score=opportunityScore(c),base=n(c.score),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net);
  if(base<58)return false;
  const standard=score>=72;
  const liquid=score>=66&&liq>=500000&&net>=1&&imp<=0.80;
  const flow=score>=62&&liq>=100000&&net>=5&&avg>=3&&chg>=0.20&&imp<=0.80;
  return standard||liquid||flow;
}
function trendEntryEligible(c){
  if(!coreSafe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.consecutiveEligible)<1)return false;
  const p=pulseFor(c),chg=p?n(p.price5m,-999):n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net),slope=n(c.scoreSlopeLast2,0),stable=c.liquidityStableLast2!==false;
  const pulseFlow=!!p&&p.status!=='EXHAUSTED'&&n(p.pulseScore)>=55&&n(p.volumeAcceleration)>=1.05&&n(p.txnAcceleration)>=1.0&&n(p.buySellRatio)>=1.10&&n(p.tx5)>=4;
  const buyerFlow=net>=2&&avg>=1.5;
  const fastFlow=net>=1&&pulseFlow;
  const momentumFloor=pulseFlow?0.05:0.15;
  return chg>=momentumFloor&&chg<=15&&(buyerFlow||fastFlow)&&slope>=-4&&stable&&opportunityLane(c);
}
"""
s2,nsub=re.subn(pat,new,s,count=1,flags=re.S)
if nsub!=1:raise SystemExit('EXEC_V280_ENTRY_PATTERN_NOT_FOUND')
s2=s2.replace("st.version='2.8.0'","st.version='2.9.0'",1)
s2=s2.replace('MICRO_LIVE_EXECUTOR_V280_OPPORTUNITY=STARTED','MICRO_LIVE_EXECUTOR_V290_FAST_TREND=STARTED',1)
s2=s2.replace('MICRO_EXECUTOR_V280_SELF_TEST=PASS','MICRO_EXECUTOR_V290_SELF_TEST=PASS',1)
p.write_text(s2)
PY
node --check "$EXEC_STAGE"
node "$EXEC_STAGE" --self-test | tee /tmp/v290-exec.txt
grep -q 'MICRO_EXECUTOR_V290_SELF_TEST=PASS' /tmp/v290-exec.txt
rm -f /tmp/v290-exec.txt

grep -q "securityDecision==='PASS'" "$EXEC_STAGE"
grep -q "holderClusterDecision==='PASS'" "$EXEC_STAGE"
grep -q "sellRoute===true" "$EXEC_STAGE"
grep -q '!c.token2022' "$EXEC_STAGE"
grep -q 'opportunityScore' "$EXEC_STAGE"
grep -q 'volumeAcceleration' "$EXEC_STAGE"

cp "$SIGNER_BASE" "$SIGNER_STAGE"
python3 - "$SIGNER_STAGE" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
s=s.replace("'signalPath':'/opt/meme-alpha/app/runtime-status/signal-snapshot.json'","'signalPath':'/opt/meme-alpha/app/runtime-status/signal-snapshot.json','trendPath':'/opt/meme-alpha/app/runtime-status/trend-pulse.json'",1)
pat=r"def candidate_ok\(mint_out,p\):\n.*?\n return False\n"
new="""def candidate_ok(mint_out,p):
 path=str(p['signalPath']);s=readj(path)
 if not file_fresh(path,180):return False
 trend_path=str(p.get('trendPath','/opt/meme-alpha/app/runtime-status/trend-pulse.json'));trend=readj(trend_path) if file_fresh(trend_path,10) else {};rows=trend.get('rows',[]) or [];themes=trend.get('themes',[]) or []
 for c in s.get('candidates',[]) or []:
  if c.get('mint')!=mint_out:continue
  impact=c.get('sellPriceImpactPct',c.get('sellImpactPct',c.get('priceImpactPct')))
  try:
   impact=abs(float(impact));base=float(c.get('score',0));liq=float(c.get('liquidityUsd',0));scan_chg=float(c.get('priceChange5m'));net=float(c.get('netBuyers5m'));avg=float(c.get('avgNetBuyersLast2') if c.get('avgNetBuyersLast2') is not None else net);slope=float(c.get('scoreSlopeLast2') if c.get('scoreSlopeLast2') is not None else 0);con=int(c.get('consecutiveEligible',0))
  except:return False
  hard=c.get('universeClass')=='MEME_CONFIRMED' and c.get('securityDecision')=='PASS' and c.get('holderClusterDecision')=='PASS' and c.get('decision')=='PROBE_CANDIDATE' and not c.get('token2022') and c.get('sellRoute') is True and hard_empty(c.get('hardReject')) and liq>=50000 and impact<=float(p['maxBuyPriceImpactPct'])
  if not hard or con<1 or base<58:return False
  pulse=next((x for x in rows if x.get('mint')==mint_out),None);score=base;chg=scan_chg;pulse_flow=False
  if pulse:
   try:
    va=float(pulse.get('volumeAcceleration',0));ta=float(pulse.get('txnAcceleration',0));br=float(pulse.get('buySellRatio',0));ps=float(pulse.get('pulseScore',0));tx5=float(pulse.get('tx5',0));chg=float(pulse.get('price5m',scan_chg));strength=float(next((x.get('strength',0) for x in themes if x.get('narrative')==pulse.get('narrative')),0));add=(4 if va>=1.45 else 2 if va>=1.10 else 0)+(3 if ta>=1.30 else 1 if ta>=1.05 else 0)+(2 if br>=1.25 else 0)+(2 if strength>=60 else 0)+(1 if ps>=70 else 0);add+=(-8 if pulse.get('status')=='EXHAUSTED' else 0)+(-3 if pulse.get('promotionFlag') is True and ps<65 else 0);score=max(base-8,min(base+12,base+add));pulse_flow=pulse.get('status')!='EXHAUSTED' and ps>=55 and va>=1.05 and ta>=1.0 and br>=1.10 and tx5>=4
   except:pass
  stable=c.get('liquidityStableLast2') is not False
  standard=score>=72;liquid=score>=66 and liq>=500000 and net>=1 and impact<=0.80;flow=score>=62 and liq>=100000 and net>=5 and avg>=3 and scan_chg>=0.20 and impact<=0.80
  buyer_flow=net>=2 and avg>=1.5;fast_flow=net>=1 and pulse_flow;floor=0.05 if pulse_flow else 0.15
  return chg>=floor and chg<=15 and (buyer_flow or fast_flow) and slope>=-4 and stable and (standard or liquid or flow)
 return False
"""
s2,nsub=re.subn(pat,new,s,count=1,flags=re.S)
if nsub!=1:raise SystemExit('SIGNER_V6_CANDIDATE_PATTERN_NOT_FOUND')
s2=s2.replace("version':'6.0'","version':'7.0'",1)
s2=s2.replace('meme-alpha-signer-v6','meme-alpha-signer-v7')
s2=s2.replace('OPPORTUNITY_9_10_HARD_SAFETY_STAGED_CAPITAL','FAST_TREND_9_10_HARD_SAFETY_STAGED_CAPITAL')
s2=s2.replace('READY_SIGNER_V6_SELF_TEST=PASS','READY_SIGNER_V7_SELF_TEST=PASS')
p.write_text(s2)
PY
python3 "$SIGNER_STAGE" --self-test | tee /tmp/v290-signer.txt
grep -q 'READY_SIGNER_V7_SELF_TEST=PASS' /tmp/v290-signer.txt
grep -q 'ARBITRARY_RAW_SIGN_OP=NOT_IMPLEMENTED' /tmp/v290-signer.txt
rm -f /tmp/v290-signer.txt

install -m 0755 "$ROOT/ops/meme-alpha/v290-root-apply-fast-trend.sh" "$APP/ops/meme-alpha/v290-root-apply-fast-trend.sh"

# Produce a fresh shadow pulse now. This performs market-data reads only.
node "$TREND_STAGE" --once || true
if [ -f "$APP/runtime-status/trend-pulse.json" ]; then
 node --input-type=module - <<'NODE'
import fs from 'node:fs';const x=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/trend-pulse.json','utf8'));
console.log('=== FAST TREND SHADOW ===');for(const t of (x.themes||[]).slice(0,6))console.log(`THEME=${t.narrative} STRENGTH=${t.strength} COUNT=${t.count} BREAKOUT=${t.breakouts} PULSE=${t.avgPulse} VOL_ACCEL=${t.avgVolAccel} SYMBOLS=${t.symbols.join(',')}`);
for(const r of (x.rows||[]).filter(x=>x.status==='BREAKOUT').slice(0,8))console.log(`BREAKOUT=${r.symbol} PULSE=${r.pulseScore} NARRATIVE=${r.narrative} VACC=${r.volumeAcceleration} TACC=${r.txnAcceleration} BSR=${r.buySellRatio} CHG5=${r.price5m} LIQ=${r.liquidityUsd}`);
NODE
fi

echo RUNNER_ISOLATION=PASS
echo TREND_POLL_MS=3000
echo DEXSCREENER_BATCH_MAX=30
echo NARRATIVE_BREADTH_ENABLED=TRUE
echo VOLUME_ACCELERATION_ENABLED=TRUE
echo TXN_ACCELERATION_ENABLED=TRUE
echo BUY_SELL_PRESSURE_ENABLED=TRUE
echo PAID_BOOST_DISCOUNT_ENABLED=TRUE
echo HARD_RUG_SECURITY_STAYS_FAIL_CLOSED=TRUE
echo HOLDER_PASS_REQUIRED=TRUE
echo SELL_ROUTE_REQUIRED=TRUE
echo TOKEN2022_LIVE_BLOCK_PRESERVED=TRUE
echo LIVE_RUNTIME_CHANGED=FALSE
echo ROOT_APPLY_REQUIRED=TRUE
echo V290_STAGE_PASS
