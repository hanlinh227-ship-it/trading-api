#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/micro-live
SERVICE=meme-alpha-micro-live.service
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
cd "$APP"

echo '=== MEME ALPHA v2.6.1 TREND-QUALIFIED ENTRY ENGINE ==='
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-signer.service
systemctl is-active --quiet "$SERVICE"
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi

# Do not hot-patch the executor while it owns a live position.
node --input-type=module - <<'NODE'
import fs from 'node:fs';
try{
 const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/micro-live/state.json','utf8'));
 if(s.position) throw new Error('ABORT_LIVE_POSITION_OPEN');
 console.log('MICRO_POSITION=NONE');
}catch(e){if(e.message==='ABORT_LIVE_POSITION_OPEN')throw e;console.log('MICRO_STATE_EMPTY_OR_NEW=TRUE')}
NODE

B="code-backups/v261-$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$B"
cp -a src/micro-live-executor.js "$B/micro-live-executor.js"
rollback(){ rc=$?; cp -f "$B/micro-live-executor.js" src/micro-live-executor.js || true; sudo -n /bin/systemctl restart "$SERVICE" >/dev/null 2>&1 || true; echo "V261_ROLLBACK rc=$rc"; exit "$rc"; }
trap rollback ERR

python3 - <<'PY'
from pathlib import Path
p=Path('src/micro-live-executor.js');s=p.read_text()
needle="function eligible(c){if(!c)return false;const impact=Number(c.sellPriceImpactPct??c.sellImpactPct??c.priceImpactPct);return c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&c.decision==='PROBE_CANDIDATE'&&!c.token2022&&c.sellRoute===true&&hardRejectEmpty(c.hardReject)&&Number(c.score)>=82&&Number(c.liquidityUsd)>=50000&&Number.isFinite(impact)&&Math.abs(impact)<=1.25&&Number(c.consecutiveEligible||0)>=2}\n"
insert="""function eligible(c){if(!c)return false;const impact=Number(c.sellPriceImpactPct??c.sellImpactPct??c.priceImpactPct);return c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&c.decision==='PROBE_CANDIDATE'&&!c.token2022&&c.sellRoute===true&&hardRejectEmpty(c.hardReject)&&Number(c.score)>=82&&Number(c.liquidityUsd)>=50000&&Number.isFinite(impact)&&Math.abs(impact)<=1.25&&Number(c.consecutiveEligible||0)>=2}
function trendEntryEligible(c){
  if(!eligible(c))return false;
  const chg=Number(c.priceChange5m),net=Number(c.netBuyers5m),avg=Number(c.avgNetBuyersLast2),slope=Number(c.scoreSlopeLast2);
  return Number.isFinite(chg)&&chg>=0.30&&chg<=18&&Number.isFinite(net)&&net>=3&&Number.isFinite(avg)&&avg>=3&&Number.isFinite(slope)&&slope>=0&&c.liquidityStableLast2===true;
}
"""
if needle in s:s=s.replace(needle,insert,1)
elif 'function trendEntryEligible(c)' not in s:raise SystemExit('ELIGIBLE_PATTERN_NOT_FOUND')
old="const p=opens.find(x=>pid(x)&&pid(x)!==st.lastMirroredPaperPositionId&&eligible(candidate(x.mint)));"
new="const p=opens.find(x=>pid(x)&&pid(x)!==st.lastMirroredPaperPositionId&&trendEntryEligible(candidate(x.mint)));"
if old in s:s=s.replace(old,new,1)
elif 'trendEntryEligible(candidate(x.mint))' not in s:raise SystemExit('ENTRY_SELECT_PATTERN_NOT_FOUND')
s=s.replace("console.log('MICRO_LIVE_EXECUTOR_V250=STARTED');","console.log('MICRO_LIVE_EXECUTOR_V261_TREND=STARTED');",1)
# Add a focused self-test without changing network behavior.
oldtest="const c={score:93,liquidityUsd:300000,sellPriceImpactPct:.3};"
newtest="const c={universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',decision:'PROBE_CANDIDATE',token2022:false,sellRoute:true,hardReject:[],score:93,liquidityUsd:300000,sellPriceImpactPct:.3,consecutiveEligible:2,priceChange5m:2.5,netBuyers5m:12,avgNetBuyersLast2:10,scoreSlopeLast2:2,liquidityStableLast2:true};"
if oldtest in s:s=s.replace(oldtest,newtest,1)
oldassert="if(w.action!=='WAIT'||s.action!=='SELL'||a.amountLamports!==5_000_000||b.amountLamports!==90_000_000)throw new Error('SELFTEST');"
newassert="if(w.action!=='WAIT'||s.action!=='SELL'||a.amountLamports!==5_000_000||b.amountLamports!==90_000_000||!trendEntryEligible(c)||trendEntryEligible({...c,priceChange5m:25})||trendEntryEligible({...c,netBuyers5m:0}))throw new Error('SELFTEST');"
if oldassert in s:s=s.replace(oldassert,newassert,1)
elif '!trendEntryEligible(c)' not in s:raise SystemExit('SELFTEST_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/micro-live-executor.js
node src/micro-live-executor.js --self-test
grep -q 'function trendEntryEligible(c)' src/micro-live-executor.js
grep -q 'chg>=0.30&&chg<=18' src/micro-live-executor.js
grep -q 'net>=3' src/micro-live-executor.js
grep -q 'avg>=3' src/micro-live-executor.js
grep -q 'slope>=0' src/micro-live-executor.js
grep -q "holderClusterDecision==='PASS'" src/micro-live-executor.js
grep -q 'trendEntryEligible(candidate(x.mint))' src/micro-live-executor.js

echo TREND_ENTRY_REQUIRES_POSITIVE_5M_MOMENTUM=TRUE
echo TREND_ENTRY_AVOIDS_PARABOLIC_GT_18PCT_5M=TRUE
echo TREND_ENTRY_REQUIRES_PERSISTENT_BUYERS=TRUE
echo TREND_ENTRY_REQUIRES_NONDECLINING_SCORE=TRUE
echo HOLD_SAFETY_GATE_UNCHANGED=TRUE

echo '=== RESTART MICRO EXECUTOR ==='
sudo -n /bin/systemctl restart "$SERVICE"
sleep 4
systemctl is-active --quiet "$SERVICE"

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const g=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/micro-live-gate.json','utf8'));
const s=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/signal-snapshot.json','utf8'));
let st={};try{st=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/micro-live/state.json','utf8'))}catch{}
console.log(`GATE_ALLOWED=${g.allowed}`);
console.log(`EXECUTION_MODE=${g.executionMode}`);
console.log(`LIVE_RISK_READY=${g.liveRiskReady}`);
const eligible=(s.candidates||[]).filter(c=>c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&c.decision==='PROBE_CANDIDATE'&&!c.token2022&&c.sellRoute===true&&Number(c.score)>=82&&Number(c.liquidityUsd)>=50000&&Number.isFinite(Number(c.sellPriceImpactPct))&&Math.abs(Number(c.sellPriceImpactPct))<=1.25&&Number(c.consecutiveEligible||0)>=2&&Number(c.priceChange5m)>=.30&&Number(c.priceChange5m)<=18&&Number(c.netBuyers5m)>=3&&Number(c.avgNetBuyersLast2)>=3&&Number(c.scoreSlopeLast2)>=0&&c.liquidityStableLast2===true);
console.log(`REAL_TREND_ENTRY_READY_COUNT=${eligible.length}`);
for(const c of eligible.slice(0,5))console.log(`READY ${c.symbol} score=${c.score} chg5m=${c.priceChange5m}% buyers=${c.netBuyers5m} avgBuyers2=${c.avgNetBuyersLast2} slope=${c.scoreSlopeLast2} liq=${Math.round(c.liquidityUsd)}`);
console.log(`MICRO_POSITION=${st.position?.symbol||'NONE'}`);
NODE
journalctl -u "$SERVICE" -n 12 --no-pager 2>/dev/null | tail -12 || true

echo V261_TREND_ENTRY_ENGINE_DEPLOY_PASS
echo FULL_AUTO_BUY_SELL_HOLD=TRUE
echo FORCED_DAILY_TRADE=FALSE
echo "BACKUP=$B"
trap - ERR
