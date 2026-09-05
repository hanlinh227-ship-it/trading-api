#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const P='/var/lib/meme-alpha/data/paper';
const M='/var/lib/meme-alpha/data/micro-live';
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sig=read(`${R}/signal-snapshot.json`);
const v=read(`${R}/validation.json`);
const g=read(`${R}/micro-live-gate.json`);
const risk=read(`${P}/risk-state.json`);
const ms=read(`${M}/state.json`);
const cs=sig.candidates||[];
console.log('=== MEME ALPHA CURRENT LIVE/TREND SCHEMA DIAGNOSTIC ===');
console.log(`GATE_ALLOWED=${!!g.allowed} GATE_REASONS=${(g.reasons||[]).join(',')||'NONE'} EXEC=${g.executionMode||'-'} ARM=${!!g.armOk}`);
console.log(`RISK_READABLE=${Object.keys(risk).length>0} RISK_ENTRY_ALLOWED=${risk.entryAllowed??'UNKNOWN'} GLOBAL_BLOCK=${(risk.globalBlockReasons||[]).join(',')||'UNKNOWN'}`);
console.log(`SIGNAL_VERSION=${sig.version} SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`MICRO_POSITION=${ms.position?.symbol||'NONE'} CLOSED=${ms.closed||0}`);
const ranked=cs.filter(x=>x.universeClass==='MEME_CONFIRMED').sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,25);
if(ranked[0]){
  console.log('CANDIDATE_KEYS='+Object.keys(ranked[0]).sort().join(','));
  for(const k of Object.keys(ranked[0]).sort()){
    if(/price|change|volume|buy|sell|txn|moment|trend|liq/i.test(k)){
      let val=ranked[0][k];
      if(val&&typeof val==='object') val=JSON.stringify(val).slice(0,800);
      console.log(`SCHEMA ${k}=${String(val).slice(0,800)}`);
    }
  }
}
for(const x of ranked){
  console.log(JSON.stringify({symbol:x.symbol,mint:x.mint,score:x.score,priceChange5m:x.priceChange5m??null,priceChange1h:x.priceChange1h??null,priceChange24h:x.priceChange24h??null,netBuyers5m:x.netBuyers5m??null,liquidityUsd:x.liquidityUsd??null,volume5m:x.volume5m??null,volume1h:x.volume1h??null,token2022:x.token2022,decision:x.decision,securityDecision:x.securityDecision,holderClusterDecision:x.holderClusterDecision||x.holderAuditDecision||null,sellRoute:x.sellRoute,sellPriceImpactPct:x.sellPriceImpactPct??null,persistenceDecision:x.persistenceDecision||null,consecutiveEligible:x.consecutiveEligible||0,fastTrackReady:!!x.fastTrackReady,avgScoreLast2:x.avgScoreLast2??null,avgNetBuyersLast2:x.avgNetBuyersLast2??null,scoreSlopeLast2:x.scoreSlopeLast2??null,liquidityStableLast2:x.liquidityStableLast2??null}));
}
console.log(`COMPLETED=${Number(v.completedLifecycleTrades||0)} VALIDATION=${v.readinessStatus||'-'} MICRO_GATE=${!!g.allowed}`);
console.log('CURRENT_LIVE_TREND_SCHEMA_DIAGNOSTIC_PASS');
NODE
