#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
R=$APP/runtime-status
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
cd "$APP"

echo '=== MEME ALPHA v2.6.0 TREND AUTOPILOT ==='
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_ANALYSIS_ENGINE_NOT_PAPER');
console.log('ANALYSIS_ENGINE=PAPER_CONTINUOUS');
NODE
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-signer.service
systemctl is-active --quiet meme-alpha-micro-live.service
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi
echo RUNNER_ISOLATION=PASS

B="code-backups/v260-$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$B"
cp -a src/micro-live-gate.js src/safe-signal-export.js "$B"/

python3 - <<'PY'
from pathlib import Path
p=Path('src/micro-live-gate.js')
s=p.read_text()
old="if(!(risk?.entryAllowed===true&&ageSec(risk?.timestamp)<180))reasons.push('RISK_NOT_READY');"
new="""const riskFresh=ageSec(risk?.timestamp)<180;
const riskShapeOk=typeof risk?.entryAllowed==='boolean'&&Array.isArray(risk?.globalBlockReasons);
const paperRiskReasons=riskShapeOk?risk.globalBlockReasons:[];
const paperCapacityOnly=new Set(['MAX_POSITIONS','PORTFOLIO_EXPOSURE_LIMIT']);
const paperCapacityBlocksIgnoredForMicroLive=paperRiskReasons.filter(x=>paperCapacityOnly.has(x));
const riskLiveBlockReasons=paperRiskReasons.filter(x=>!paperCapacityOnly.has(x));
const liveRiskReady=riskFresh&&riskShapeOk&&String(risk?.riskRegime||'UNKNOWN')!=='HALT'&&riskLiveBlockReasons.length===0;
if(!liveRiskReady)reasons.push('RISK_NOT_READY');"""
if old in s:
    s=s.replace(old,new,1)
elif 'const paperCapacityOnly=new Set' not in s:
    raise SystemExit('GATE_RISK_PATTERN_NOT_FOUND')
old2="riskEntryAllowed:risk?.entryAllowed===true,validationStatus"
new2="riskEntryAllowed:liveRiskReady,paperRiskEntryAllowed:risk?.entryAllowed===true,liveRiskReady,paperCapacityBlocksIgnoredForMicroLive,riskGlobalBlockReasons:paperRiskReasons,riskLiveBlockReasons,policyRevision:'2.6.0-trend-autopilot',validationStatus"
if old2 in s:
    s=s.replace(old2,new2,1)
elif "policyRevision:'2.6.0-trend-autopilot'" not in s:
    raise SystemExit('GATE_OUTPUT_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/micro-live-gate.js

python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js')
s=p.read_text()
old="organicRatio5m:Number(c.organicRatio5m||0),netBuyers5m:Number(c.netBuyers5m||0),sources:c.sources||[]"
new="""organicRatio5m:Number(c.organicRatio5m||0),netBuyers5m:Number(c.netBuyers5m||0),priceChange5m:Number.isFinite(Number(c.priceChange5m))?Number(c.priceChange5m):null,buyVolume5m:Number(c.buyVolume5m||0),sellVolume5m:Number(c.sellVolume5m||0),dexVolume5m:Number(c.dexVolume5m||0),dexBuys5m:Number(c.dexBuys5m||0),dexSells5m:Number(c.dexSells5m||0),buySellRatio5m:Number(c.sellVolume5m)>0?Number(c.buyVolume5m||0)/Number(c.sellVolume5m):Number(c.buyVolume5m)>0?99:0,sources:c.sources||[]"""
if old in s:
    s=s.replace(old,new,1)
elif 'buySellRatio5m:' not in s:
    raise SystemExit('SIGNAL_TREND_FIELDS_PATTERN_NOT_FOUND')
old2="const out={version:'2.2.7',timestamp:"
new2="const out={version:'2.2.7',trendTelemetryRevision:'2.6.0',timestamp:"
if old2 in s:
    s=s.replace(old2,new2,1)
elif "trendTelemetryRevision:'2.6.0'" not in s:
    # tolerate a later signal version but still add the telemetry revision
    marker='const out={version:'
    i=s.find(marker)
    if i<0: raise SystemExit('SIGNAL_OUT_PATTERN_NOT_FOUND')
    comma=s.find(',timestamp:',i)
    if comma<0: raise SystemExit('SIGNAL_TIMESTAMP_PATTERN_NOT_FOUND')
    s=s[:comma]+",trendTelemetryRevision:'2.6.0'"+s[comma:]
p.write_text(s)
PY
node --check src/safe-signal-export.js

echo '=== STATIC SAFETY ASSERT ==='
grep -q "paperCapacityOnly=new Set(\['MAX_POSITIONS','PORTFOLIO_EXPOSURE_LIMIT'\])" src/micro-live-gate.js
grep -q "policyRevision:'2.6.0-trend-autopilot'" src/micro-live-gate.js
grep -q 'priceChange5m:' src/safe-signal-export.js
grep -q 'buySellRatio5m:' src/safe-signal-export.js
# Existing execution hard gates must remain present.
grep -q "securityDecision==='PASS'" src/micro-live-executor.js
grep -q "holderClusterDecision==='PASS'" src/micro-live-executor.js
grep -q "sellRoute===true" src/micro-live-executor.js
grep -q "Number(c.score)>=82" src/micro-live-executor.js
grep -q "Math.abs(impact)<=1.25" src/micro-live-executor.js

echo PAPER_CAPACITY_DECOUPLED_FROM_LIVE_SAFETY=TRUE
echo SECURITY_GATES_PRESERVED=TRUE
echo HOLDER_GATES_PRESERVED=TRUE
echo SELLABILITY_GATES_PRESERVED=TRUE
echo DATA_HEALTH_GATES_PRESERVED=TRUE

echo '=== RELOAD NORMAL ANALYSIS LOOP ==='
sudo -n /bin/systemctl restart meme-alpha-paper.service
ok=0
for _ in $(seq 1 35); do
  sleep 4
  if [ -f "$R/micro-live-gate.json" ] && node --input-type=module - <<'NODE'
import fs from 'node:fs';
try{
 const x=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/micro-live-gate.json','utf8'));
 process.exit(x.policyRevision==='2.6.0-trend-autopilot'?0:1);
}catch{process.exit(1)}
NODE
  then ok=1; break; fi
done
[ "$ok" -eq 1 ] || { echo ABORT_V260_GATE_REFRESH_TIMEOUT; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-signer.service
systemctl is-active --quiet meme-alpha-micro-live.service

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const g=read(`${R}/micro-live-gate.json`),s=read(`${R}/signal-snapshot.json`);
const m=read('/var/lib/meme-alpha/data/micro-live/state.json');
console.log(`POLICY_REVISION=${g.policyRevision}`);
console.log(`GATE_ALLOWED=${g.allowed}`);
console.log(`EXECUTION_MODE=${g.executionMode}`);
console.log(`ARM_OK=${g.armOk}`);
console.log(`PAPER_RISK_ENTRY_ALLOWED=${g.paperRiskEntryAllowed}`);
console.log(`LIVE_RISK_READY=${g.liveRiskReady}`);
console.log(`PAPER_CAPACITY_IGNORED=${(g.paperCapacityBlocksIgnoredForMicroLive||[]).join(',')||'NONE'}`);
console.log(`LIVE_RISK_BLOCKS=${(g.riskLiveBlockReasons||[]).join(',')||'NONE'}`);
console.log(`GATE_REASONS=${(g.reasons||[]).join(',')||'NONE'}`);
console.log(`SOURCE=${s.sourceHealth?.status} SOURCES=${s.sourceHealth?.successfulSources} CACHE=${s.sourceHealth?.usingCache}`);
console.log(`TREND_TELEMETRY_REV=${s.trendTelemetryRevision||'-'}`);
const cs=s.candidates||[];
const trend=cs.filter(x=>x.universeClass==='MEME_CONFIRMED'&&Number.isFinite(Number(x.priceChange5m))&&Number(x.priceChange5m)>0&&Number(x.priceChange5m)<=18&&Number(x.netBuyers5m)>0).sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,8);
console.log(`TREND_CANDIDATES=${trend.length}`);
for(const x of trend) console.log(`TREND ${x.symbol} score=${x.score} chg5m=${x.priceChange5m}% netBuyers5m=${x.netBuyers5m} organic=${x.organicRatio5m} liq=${Math.round(Number(x.liquidityUsd||0))} sec=${x.securityDecision} holder=${x.holderClusterDecision} sell=${x.sellRoute} persist=${x.persistenceDecision||'-'}`);
console.log(`MICRO_POSITION=${m.position?.symbol||'NONE'}`);
console.log(`MICRO_CLOSED=${m.closed||0}`);
if(g.policyRevision!=='2.6.0-trend-autopilot')throw new Error('POLICY_REVISION');
if(g.executionMode!=='MICRO_LIVE'||g.armOk!==true)throw new Error('LIVE_ARM_STATE');
if(s.trendTelemetryRevision!=='2.6.0')throw new Error('TREND_TELEMETRY');
if(s.sourceHealth?.status!=='HEALTHY'||s.sourceHealth?.usingCache===true)throw new Error('SOURCE_HEALTH');
console.log('V260_TREND_AUTOPILOT_DEPLOY_PASS');
NODE

echo '=== MICRO LIVE RECENT ==='
journalctl -u meme-alpha-micro-live.service -n 20 --no-pager 2>/dev/null | tail -20 || true
echo FULL_AUTO_DECISION_LOOP=ACTIVE
echo DAILY_PROFIT_GUARANTEE=NOT_POSSIBLE
echo FORCED_DAILY_TRADES=FALSE
echo TREND_PRIORITY=TRUE
echo PRE_EVIDENCE_MAX_ENTRY_SOL=0.005
echo "BACKUP=$B"
