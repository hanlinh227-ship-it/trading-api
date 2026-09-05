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
console.log('=== MEME ALPHA CURRENT LIVE/TREND + CAPITAL FLOW DIAGNOSTIC ===');
console.log(`GATE_ALLOWED=${!!g.allowed} GATE_REASONS=${(g.reasons||[]).join(',')||'NONE'} EXEC=${g.executionMode||'-'} ARM=${!!g.armOk}`);
console.log(`RISK_SOURCE=${Object.keys(directRisk).length?'DIRECT':'SAFE_SIGNAL'} RISK_ENTRY_ALLOWED=${risk.entryAllowed??'UNKNOWN'} REGIME=${risk.riskRegime||'-'} GLOBAL_BLOCK=${(risk.globalBlockReasons||[]).join(',')||'NONE'} OPEN_PAPER=${risk.openPositions??'-'} EXPOSURE_PCT=${risk.exposurePct??'-'}`);
console.log(`RISK_HEALTH=${JSON.stringify(risk.health||{})}`);
console.log(`SIGNAL_VERSION=${sig.version} SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`MICRO_POSITION=${ms.position?.symbol||'NONE'} CLOSED=${ms.closed||0}`);
const cap=ms.capital||{};
const lam=n=>Number.isFinite(Number(n))?Number(n):0;
const last=lam(cap.lastObservedSolLamports),dep=lam(cap.depositsLamports),wd=lam(cap.withdrawalsLamports),pnl=lam(cap.realizedTradingPnlLamports),net=lam(cap.netExternalFlowLamports);
let stateAge='INF';try{stateAge=((Date.now()-fs.statSync(`${M}/state.json`).mtimeMs)/1000).toFixed(1)}catch{}
console.log(`MICRO_STATE_AGE_SEC=${stateAge}`);
console.log(`BOT_OBSERVED_SOL=${(last/1e9).toFixed(9)}`);
console.log(`DEPOSITS_DETECTED_SOL=${(dep/1e9).toFixed(9)}`);
console.log(`WITHDRAWALS_DETECTED_SOL=${(wd/1e9).toFixed(9)}`);
console.log(`NET_EXTERNAL_FLOW_SOL=${(net/1e9).toFixed(9)}`);
console.log(`REALIZED_TRADING_PNL_SOL=${(pnl/1e9).toFixed(9)}`);
console.log(`LAST_EXTERNAL_FLOW_AT=${cap.lastExternalFlowAt||'NONE'}`);
const ranked=cs.filter(x=>x.universeClass==='MEME_CONFIRMED').sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,10);
for(const x of ranked) console.log(JSON.stringify({symbol:x.symbol,mint:x.mint,score:x.score,priceChange5m:x.priceChange5m??null,netBuyers5m:x.netBuyers5m??null,organicRatio5m:x.organicRatio5m??null,liquidityUsd:x.liquidityUsd??null,token2022:x.token2022,decision:x.decision,securityDecision:x.securityDecision,holderClusterDecision:x.holderClusterDecision||null,sellRoute:x.sellRoute,sellPriceImpactPct:x.sellPriceImpactPct??null,persistenceDecision:x.persistenceDecision||null,consecutiveEligible:x.consecutiveEligible||0,avgScoreLast2:x.avgScoreLast2??null,avgNetBuyersLast2:x.avgNetBuyersLast2??null,scoreSlopeLast2:x.scoreSlopeLast2??null}));
console.log(`COMPLETED=${Number(v.completedLifecycleTrades||0)} VALIDATION=${v.readinessStatus||'-'} MICRO_GATE=${!!g.allowed}`);
NODE
echo '=== RECENT MICRO CAPITAL/TRADE EVENTS ==='
if [ -f /var/lib/meme-alpha/data/micro-live/events.jsonl ]; then
  tail -n 80 /var/lib/meme-alpha/data/micro-live/events.jsonl | grep -E 'CAPITAL_DEPOSIT_DETECTED|CAPITAL_WITHDRAWAL_DETECTED|MICRO_BUY|MICRO_SELL|EXECUTOR_ERROR' | tail -n 25 || true
else
  echo MICRO_EVENTS_FILE_MISSING
fi
echo CURRENT_CAPITAL_FLOW_DIAGNOSTIC_PASS
