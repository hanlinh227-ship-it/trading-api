#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.1.6 STRICT FAST PERSISTENCE + 15s CADENCE ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));if(c.mode!=='PAPER')throw new Error('ABORT_NOT_PAPER');console.log('MODE=PAPER');console.log('LIVE_EXECUTION=DISABLED');
NODE
B="code-backups/v216-$(date -u +%Y%m%d-%H%M%S)";mkdir -p "$B";cp -a src/persistence.js src/safe-signal-export.js run-paper.sh "$B"/
python3 - <<'PY'
from pathlib import Path
p=Path('src/persistence.js');s=p.read_text()
old='''    c.universeClass !==\n      "NON_MEME" &&''';new='''    c.universeClass ===\n      "MEME_CONFIRMED" &&'''
if old in s:s=s.replace(old,new,1)
elif new not in s:raise SystemExit('UNIVERSE_ELIGIBILITY_PATTERN_NOT_FOUND')
old2='''    c.sellRoute !== false;''';new2='''    c.sellRoute === true;'''
if old2 in s:s=s.replace(old2,new2,1)
elif new2 not in s:raise SystemExit('SELL_ROUTE_ELIGIBILITY_PATTERN_NOT_FOUND')
marker='''  if (\n    c.universeClass ===\n      "NON_MEME"\n  ) {'''
if 'const fastTrackReady =' not in s:
    insert='''  const last2 = obs.slice(-2);\n  const avgScoreLast2 = last2.length\n    ? last2.reduce((sum,x)=>sum+Number(x.score||0),0)/last2.length\n    : 0;\n  const avgNetBuyersLast2 = last2.length\n    ? last2.reduce((sum,x)=>sum+Number(x.netBuyers5m||0),0)/last2.length\n    : 0;\n  const buyersPositiveLast2 = last2.length === 2 && last2.every(x=>Number(x.netBuyers5m||0)>0);\n  const liquidityLast2 = last2.map(x=>Number(x.liquidityUsd||0));\n  const liquidityStableLast2 = last2.length === 2 && Math.min(...liquidityLast2) >= 0.85*Math.max(...liquidityLast2);\n  const scoreSlopeLast2 = last2.length === 2 ? Number(last2[1].score||0)-Number(last2[0].score||0) : -Infinity;\n  const currentPriceMove5m = Number(c.priceChange5m);\n  const currentSellImpact = Number(c.sellPriceImpactPct);\n  const currentSourceCount = new Set(c.sources||[]).size;\n  const fastTrackReady =\n    t.consecutiveEligible >= 2 &&\n    c.universeClass === "MEME_CONFIRMED" &&\n    c.securityDecision === "PASS" &&\n    c.decision === "PROBE_CANDIDATE" &&\n    !c.token2022 &&\n    (c.hardReject||[]).length === 0 &&\n    c.sellRoute === true &&\n    Number(c.score||0) >= 80 &&\n    avgScoreLast2 >= 78 &&\n    avgNetBuyersLast2 > 0 &&\n    buyersPositiveLast2 &&\n    scoreSlopeLast2 >= 0 &&\n    liquidityStableLast2 &&\n    Number.isFinite(currentPriceMove5m) && currentPriceMove5m >= -4 && currentPriceMove5m <= 18 &&\n    Number.isFinite(currentSellImpact) && Math.abs(currentSellImpact) <= 1.25 &&\n    currentSourceCount >= 3;\n\n'''
    if marker not in s:raise SystemExit('FAST_TRACK_INSERT_MARKER_NOT_FOUND')
    s=s.replace(marker,insert+marker,1)
branch='''  } else if (\n    t.consecutiveEligible >= 3 &&'''
if '  } else if (fastTrackReady) {' not in s:
    repl='''  } else if (fastTrackReady) {\n    t.persistenceDecision =\n      "PAPER_ENTRY_READY";\n\n  } else if (\n    t.consecutiveEligible >= 3 &&'''
    if branch not in s:raise SystemExit('FAST_TRACK_BRANCH_PATTERN_NOT_FOUND')
    s=s.replace(branch,repl,1)
metrics='''  t.metrics = {'''
if 'fastTrackReady,' not in s:
    repl='''  t.metrics = {\n    fastTrackReady,\n    avgScoreLast2:Number(avgScoreLast2.toFixed(2)),\n    avgNetBuyersLast2:Number(avgNetBuyersLast2.toFixed(2)),\n    scoreSlopeLast2:Number.isFinite(scoreSlopeLast2)?Number(scoreSlopeLast2.toFixed(2)):null,\n    liquidityStableLast2,\n    sourceCountCurrent:currentSourceCount,'''
    if metrics not in s:raise SystemExit('METRICS_PATTERN_NOT_FOUND')
    s=s.replace(metrics,repl,1)
p.write_text(s)
PY
node --check src/persistence.js
python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js');s=p.read_text()
needle='consecutiveEligible:Number(p?.consecutiveEligible||0)'
repl='consecutiveEligible:Number(p?.consecutiveEligible||0),fastTrackReady:!!p?.metrics?.fastTrackReady,avgScoreLast2:p?.metrics?.avgScoreLast2??null,avgNetBuyersLast2:p?.metrics?.avgNetBuyersLast2??null,scoreSlopeLast2:p?.metrics?.scoreSlopeLast2??null,liquidityStableLast2:p?.metrics?.liquidityStableLast2??null'
if needle in s:s=s.replace(needle,repl,1)
elif 'fastTrackReady:!!p?.metrics?.fastTrackReady' not in s:raise SystemExit('SAFE_EXPORT_PERSIST_PATTERN_NOT_FOUND')
for old in ["version:'2.1.4'","version:'2.1.2'","version:'2.0.1'"]:
    if old in s:s=s.replace(old,"version:'2.1.6'",1);break
if "version:'2.1.6'" not in s:raise SystemExit('SAFE_EXPORT_VERSION_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/safe-signal-export.js
python3 - <<'PY'
from pathlib import Path
p=Path('run-paper.sh');s=p.read_text();replacements=[('HEALTHY_FULL_GAP_SEC=20','HEALTHY_FULL_GAP_SEC=15'),('HEALTHY_FULL_GAP=20','HEALTHY_FULL_GAP=15'),('FULL_CYCLE_HEALTHY_SEC=20','FULL_CYCLE_HEALTHY_SEC=15')];changed=False
for a,b in replacements:
    if a in s:s=s.replace(a,b,1);changed=True;break
if not changed and not any(x in s for x in ['HEALTHY_FULL_GAP_SEC=15','HEALTHY_FULL_GAP=15','FULL_CYCLE_HEALTHY_SEC=15']):raise SystemExit('HEALTHY_CADENCE_PATTERN_NOT_FOUND')
p.write_text(s)
PY
bash -n run-paper.sh
sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 155
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
node --input-type=module - <<'NODE'
import fs from 'node:fs';const R='/opt/meme-alpha/app/runtime-status';const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));const sig=read('signal-snapshot.json'),v=read('validation.json'),s=read('stress-test.json'),g=read('micro-live-gate.json');const cs=sig.candidates||[],n=f=>cs.filter(f).length;console.log(`SIGNAL_VERSION=${sig.version}`);console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} FAIL=${sig.sourceHealth?.failedSources} CACHE=${sig.sourceHealth?.usingCache}`);console.log(`CANDIDATES=${cs.length} MEME_CONFIRMED=${n(x=>x.universeClass==='MEME_CONFIRMED')} SECURITY_PASS=${n(x=>x.securityDecision==='PASS')} PROBE=${n(x=>x.decision==='PROBE_CANDIDATE')} SELLABLE=${n(x=>x.sellRoute===true)} FAST_TRACK_READY=${n(x=>x.fastTrackReady===true)} PAPER_READY=${n(x=>x.persistenceDecision==='PAPER_ENTRY_READY')}`);for(const x of cs.filter(x=>x.universeClass==='MEME_CONFIRMED').slice(0,12))console.log(`MEME ${x.symbol} score=${x.score} sec=${x.securityDecision} sell=${x.sellRoute} persist=${x.persistenceDecision||'-'} streak=${x.consecutiveEligible||0} fast=${x.fastTrackReady} avg2=${x.avgScoreLast2} buyers2=${x.avgNetBuyersLast2} slope2=${x.scoreSlopeLast2}`);console.log(`VALIDATION=${v.readinessStatus} COMPLETED=${v.completedLifecycleTrades||0}`);console.log(`STRESS=${s.status} FAIL=${s.fail}`);console.log(`MICRO_GATE=${g.allowed} EXECUTION_MODE=${g.executionMode}`);if(sig.version!=='2.1.6')throw new Error('SIGNAL_VERSION');if(sig.sourceHealth?.status!=='HEALTHY'||sig.sourceHealth?.usingCache===true||Number(sig.sourceHealth?.successfulSources)<2)throw new Error('SOURCE_HEALTH');if(g.allowed!==false||g.executionMode!=='DISABLED')throw new Error('LIVE_GATE');console.log('V216_STRICT_FAST_PERSISTENCE_SOAK_PASS');
NODE
grep -E 'HEALTHY_FULL_GAP|FULL_CYCLE_HEALTHY' run-paper.sh | head -n 5 || true
echo LIVE_EXECUTION=FALSE
echo "BACKUP=$B"
