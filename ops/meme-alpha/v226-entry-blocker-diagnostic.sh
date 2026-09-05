#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const P='/var/lib/meme-alpha/data/paper';
const M='/var/lib/meme-alpha/data/micro-live';
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sig=read(`${R}/signal-snapshot.json`),v=read(`${R}/validation.json`),g=read(`${R}/micro-live-gate.json`);
const directRisk=read(`${P}/risk-state.json`),risk=Object.keys(directRisk).length?directRisk:(sig.risk||{}),ms=read(`${M}/state.json`),cs=sig.candidates||[];
console.log('=== MEME ALPHA CURRENT LIVE/TREND + SANITIZED RISK DIAGNOSTIC ===');
console.log(`GATE_ALLOWED=${!!g.allowed} GATE_REASONS=${(g.reasons||[]).join(',')||'NONE'} EXEC=${g.executionMode||'-'} ARM=${!!g.armOk}`);
console.log(`RISK_SOURCE=${Object.keys(directRisk).length?'DIRECT':'SAFE_SIGNAL'} RISK_ENTRY_ALLOWED=${risk.entryAllowed??'UNKNOWN'} REGIME=${risk.riskRegime||'-'} GLOBAL_BLOCK=${(risk.globalBlockReasons||[]).join(',')||'NONE'} OPEN_PAPER=${risk.openPositions??'-'} EXPOSURE_PCT=${risk.exposurePct??'-'}`);
console.log(`RISK_HEALTH=${JSON.stringify(risk.health||{})}`);
console.log(`SIGNAL_VERSION=${sig.version} SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`MICRO_POSITION=${ms.position?.symbol||'NONE'} CLOSED=${ms.closed||0}`);
const ranked=cs.filter(x=>x.universeClass==='MEME_CONFIRMED').sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,15);
for(const x of ranked) console.log(JSON.stringify({symbol:x.symbol,mint:x.mint,score:x.score,netBuyers5m:x.netBuyers5m??null,organicRatio5m:x.organicRatio5m??null,liquidityUsd:x.liquidityUsd??null,token2022:x.token2022,decision:x.decision,securityDecision:x.securityDecision,holderClusterDecision:x.holderClusterDecision||null,sellRoute:x.sellRoute,sellPriceImpactPct:x.sellPriceImpactPct??null,persistenceDecision:x.persistenceDecision||null,consecutiveEligible:x.consecutiveEligible||0,fastTrackReady:!!x.fastTrackReady,avgScoreLast2:x.avgScoreLast2??null,avgNetBuyersLast2:x.avgNetBuyersLast2??null,scoreSlopeLast2:x.scoreSlopeLast2??null}));
console.log(`COMPLETED=${Number(v.completedLifecycleTrades||0)} VALIDATION=${v.readinessStatus||'-'} MICRO_GATE=${!!g.allowed}`);
NODE
echo '=== SCANNER MOMENTUM FIELD TRACE ==='
grep -nEi 'priceChange|volume|txns|netBuyers|organicRatio|pair\.|m5|h1|h24' src/scanner.js | head -n 160 || true
echo '=== SAFE EXPORT MOMENTUM FIELD TRACE ==='
grep -nEi 'priceChange|volume|netBuyers|organicRatio|sellPriceImpact' src/safe-signal-export.js | head -n 120 || true
echo CURRENT_LIVE_TREND_FIELD_TRACE_PASS
