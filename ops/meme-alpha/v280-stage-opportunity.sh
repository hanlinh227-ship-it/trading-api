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

echo '=== MEME ALPHA v2.8.0 OPPORTUNITY 9/10 STAGE ==='
mkdir -p "$APP/ops/meme-alpha/micro-live" "$APP/ops/meme-alpha/signer"
EXEC_SRC="$APP/src/micro-live-executor.js"
EXEC_STAGE="$APP/ops/meme-alpha/micro-live/micro-live-executor-v280.js"
SIGNER_BASE="$ROOT/ops/meme-alpha/signer/ready_signer_v5.py"
SIGNER_STAGE="$APP/ops/meme-alpha/signer/ready_signer_v6.py"

grep -q 'MICRO_LIVE_EXECUTOR_V270_FULL_CAPITAL=STARTED' "$EXEC_SRC" || { echo ABORT_LIVE_EXECUTOR_NOT_V270; exit 1; }
cp "$EXEC_SRC" "$EXEC_STAGE"
python3 - "$EXEC_STAGE" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
pattern=r"function trendEntryEligible\(c\)\{.*?\n\}\nfunction holdSafe\(c\)\{.*?\n\}\nfunction tier\(c,p\)\{.*?\n\}\n"
new="""function opportunityLane(c){
  const score=n(c.score),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,-999);
  const standard=score>=72;
  const liquid=score>=66&&liq>=500000&&net>=2&&imp<=0.80;
  const flow=score>=62&&liq>=100000&&net>=8&&avg>=5&&chg>=0.50&&imp<=0.80;
  return standard||liquid||flow;
}
function trendEntryEligible(c){
  if(!coreSafe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.consecutiveEligible)<1)return false;
  const chg=n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,-999),slope=n(c.scoreSlopeLast2,-999);
  const stable=c.liquidityStableLast2!==false;
  return chg>=0.15&&chg<=15&&net>=2&&avg>=1.5&&slope>=-4&&stable&&opportunityLane(c);
}
function holdSafe(c){
  if(!coreSafe(c))return false;
  if(n(c.score)<55)return false;
  if(n(c.priceChange5m,-999)<=-5.5)return false;
  if(n(c.netBuyers5m,0)<=-10)return false;
  return true;
}
function tier(c,p){
  if(!trendEntryEligible(c))return {name:'NONE',pct:0};
  const score=n(c.score),con=n(c.consecutiveEligible),net=n(c.netBuyers5m),avg=n(c.avgNetBuyersLast2),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m);
  const maxQuality=(score>=82&&net>=10&&avg>=7)||(score>=76&&net>=18&&avg>=10);
  if(con>=5&&maxQuality&&liq>=250000&&imp<=0.50&&chg>=0.50&&chg<=8)return{name:'MAX',pct:p.maxUtilizationPct};
  const strongQuality=(score>=76&&net>=6&&avg>=4)||(score>=70&&net>=10&&avg>=6);
  if(con>=3&&strongQuality&&liq>=150000&&imp<=0.80&&chg>=0.30&&chg<=10)return{name:'STRONG',pct:p.strongUtilizationPct};
  const confirmedQuality=(score>=70&&net>=3&&avg>=2)||(score>=66&&net>=6&&avg>=4);
  if(con>=2&&confirmedQuality&&liq>=100000&&imp<=1.00&&chg>=0.15&&chg<=12)return{name:'CONFIRMED',pct:p.confirmedUtilizationPct};
  return{name:'PROBE',pct:p.probeUtilizationPct};
}
"""
s2,nsub=re.subn(pattern,new,s,count=1,flags=re.S)
if nsub!=1: raise SystemExit('EXEC_ENTRY_BLOCK_PATTERN_NOT_FOUND')
s2=s2.replace("st.version='2.7.0'","st.version='2.8.0'",1)
s2=s2.replace("MICRO_LIVE_EXECUTOR_V270_FULL_CAPITAL=STARTED","MICRO_LIVE_EXECUTOR_V280_OPPORTUNITY=STARTED",1)
# Replace self-test candidate/expectations with v2.8 opportunity tests while preserving capital-plan tests.
s2=s2.replace("const c={universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',decision:'PROBE_CANDIDATE',token2022:false,sellRoute:true,hardReject:[],score:94,liquidityUsd:300000,sellPriceImpactPct:.3,consecutiveEligible:8,priceChange5m:2.5,netBuyers5m:20,avgNetBuyersLast2:15,scoreSlopeLast2:2,liquidityStableLast2:true,organicRatio5m:.3};","const c={universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',decision:'PROBE_CANDIDATE',token2022:false,sellRoute:true,hardReject:[],score:84,liquidityUsd:600000,sellPriceImpactPct:.3,consecutiveEligible:5,priceChange5m:2.5,netBuyers5m:20,avgNetBuyersLast2:15,scoreSlopeLast2:0,liquidityStableLast2:true,organicRatio5m:.3};",1)
s2=s2.replace("if(!trendEntryEligible(c)||tier(c,p).pct!==94||trendEntryEligible({...c,priceChange5m:25})||holdSafe({...c,score:60}))throw new Error('TREND_SELFTEST');","if(!trendEntryEligible(c)||tier(c,p).pct!==94||trendEntryEligible({...c,priceChange5m:25})||trendEntryEligible({...c,securityDecision:'REVIEW'})||trendEntryEligible({...c,holderClusterDecision:'REVIEW'})||trendEntryEligible({...c,sellRoute:false})||trendEntryEligible({...c,token2022:true})||!holdSafe({...c,score:60}))throw new Error('TREND_SELFTEST');",1)
s2=s2.replace("MICRO_EXECUTOR_V270_SELF_TEST=PASS","MICRO_EXECUTOR_V280_SELF_TEST=PASS",1)
s2=s2.replace("STAGED_UTILIZATION=15_35_65_94","STAGED_UTILIZATION=15_35_65_94 OPPORTUNITY_ENTRY=9_10_TARGET",1)
p.write_text(s2)
PY
node --check "$EXEC_STAGE"
node "$EXEC_STAGE" --self-test | tee /tmp/meme-alpha-v280-exec-test.txt
grep -q 'MICRO_EXECUTOR_V280_SELF_TEST=PASS' /tmp/meme-alpha-v280-exec-test.txt
rm -f /tmp/meme-alpha-v280-exec-test.txt

grep -q "securityDecision==='PASS'" "$EXEC_STAGE"
grep -q "holderClusterDecision==='PASS'" "$EXEC_STAGE"
grep -q "sellRoute===true" "$EXEC_STAGE"
grep -q '!c.token2022' "$EXEC_STAGE"
grep -q 'chg>=0.15&&chg<=15' "$EXEC_STAGE"
grep -q 'score>=66&&liq>=500000' "$EXEC_STAGE"

cp "$SIGNER_BASE" "$SIGNER_STAGE"
python3 - "$SIGNER_STAGE" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
pat=r"def candidate_ok\(mint_out,p\):\n.*?\n return False\n"
new="""def candidate_ok(mint_out,p):
 path=str(p['signalPath']);s=readj(path)
 if not file_fresh(path,180):return False
 for c in s.get('candidates',[]) or []:
  if c.get('mint')!=mint_out:continue
  impact=c.get('sellPriceImpactPct',c.get('sellImpactPct',c.get('priceImpactPct')))
  try:
   impact=abs(float(impact));score=float(c.get('score',0));liq=float(c.get('liquidityUsd',0));chg=float(c.get('priceChange5m'));net=float(c.get('netBuyers5m'));avg=float(c.get('avgNetBuyersLast2') if c.get('avgNetBuyersLast2') is not None else net);slope=float(c.get('scoreSlopeLast2') if c.get('scoreSlopeLast2') is not None else 0);con=int(c.get('consecutiveEligible',0))
  except:return False
  hard=c.get('universeClass')=='MEME_CONFIRMED' and c.get('securityDecision')=='PASS' and c.get('holderClusterDecision')=='PASS' and c.get('decision')=='PROBE_CANDIDATE' and not c.get('token2022') and c.get('sellRoute') is True and hard_empty(c.get('hardReject')) and liq>=50000 and impact<=float(p['maxBuyPriceImpactPct'])
  if not hard or con<1:return False
  stable=c.get('liquidityStableLast2') is not False
  standard=score>=72
  liquid=score>=66 and liq>=500000 and net>=2 and impact<=0.80
  flow=score>=62 and liq>=100000 and net>=8 and avg>=5 and chg>=0.50 and impact<=0.80
  return chg>=0.15 and chg<=15 and net>=2 and avg>=1.5 and slope>=-4 and stable and (standard or liquid or flow)
 return False
"""
s2,nsub=re.subn(pat,new,s,count=1,flags=re.S)
if nsub!=1: raise SystemExit('SIGNER_CANDIDATE_PATTERN_NOT_FOUND')
s2=s2.replace("version':'5.0'","version':'6.0'",1)
s2=s2.replace("meme-alpha-signer-v5","meme-alpha-signer-v6")
s2=s2.replace("TREND_GATE_STAGED_FULL_CAPITAL","OPPORTUNITY_9_10_HARD_SAFETY_STAGED_CAPITAL")
s2=s2.replace("READY_SIGNER_V5_SELF_TEST=PASS","READY_SIGNER_V6_SELF_TEST=PASS")
s2=s2.replace("BUY_REQUIRES_FRESH_TREND_GATE=TRUE","BUY_REQUIRES_FRESH_HARD_SAFETY_TREND_GATE=TRUE")
p.write_text(s2)
PY
python3 "$SIGNER_STAGE" --self-test | tee /tmp/meme-alpha-v280-signer-test.txt
grep -q 'READY_SIGNER_V6_SELF_TEST=PASS' /tmp/meme-alpha-v280-signer-test.txt
grep -q 'ARBITRARY_RAW_SIGN_OP=NOT_IMPLEMENTED' /tmp/meme-alpha-v280-signer-test.txt
rm -f /tmp/meme-alpha-v280-signer-test.txt

install -m 0755 "$ROOT/ops/meme-alpha/v280-root-apply-opportunity.sh" "$APP/ops/meme-alpha/v280-root-apply-opportunity.sh"

echo RUNNER_ISOLATION=PASS
echo HARD_RUG_SECURITY_STAYS_FAIL_CLOSED=TRUE
echo HOLDER_PASS_REQUIRED=TRUE
echo SELL_ROUTE_REQUIRED=TRUE
echo TOKEN2022_STILL_BLOCKED_FOR_LIVE=TRUE
echo OPPORTUNITY_ENTRY_DYNAMIC_SCORE_LANES=62_66_72
echo MOMENTUM_FLOOR_5M_PCT=0.15
echo MIN_NET_BUYERS_5M=2
echo INITIAL_CONSECUTIVE_ELIGIBLE=1
echo CAPITAL_STAGES_UNCHANGED=15_35_65_94
echo LIVE_RUNTIME_CHANGED=FALSE
echo ROOT_APPLY_REQUIRED=TRUE
echo V280_STAGE_PASS
