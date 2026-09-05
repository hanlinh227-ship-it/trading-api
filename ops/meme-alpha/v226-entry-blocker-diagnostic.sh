#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const sig=JSON.parse(fs.readFileSync(`${R}/signal-snapshot.json`,'utf8'));
const v=JSON.parse(fs.readFileSync(`${R}/validation.json`,'utf8'));
const g=JSON.parse(fs.readFileSync(`${R}/micro-live-gate.json`,'utf8'));
const cs=sig.candidates||[];
console.log('=== MEME ALPHA v2.2.6 ENTRY BLOCKER DIAGNOSTIC ===');
console.log(`SIGNAL_VERSION=${sig.version} SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} CACHE=${sig.sourceHealth?.usingCache}`);
for(const x of cs.filter(x=>x.universeClass==='MEME_CONFIRMED').slice(0,20)){
  console.log(JSON.stringify({symbol:x.symbol,mint:x.mint,score:x.score,token2022:x.token2022,topHoldersPct:x.topHoldersPct,decision:x.decision,securityDecision:x.securityDecision,securityReviewReasons:x.securityReviewReasons||x.reviewReasons||[],securityBlockReasons:x.securityBlockReasons||x.blockReasons||[],holderClusterDecision:x.holderClusterDecision||x.holderAuditDecision||null,holderReviewReasons:x.holderReviewReasons||[],holderBlockReasons:x.holderBlockReasons||[],sellRoute:x.sellRoute,sellQuoteHttp:x.sellQuoteHttp??null,sellQuoteError:x.sellQuoteError??null,sellPriceImpactPct:x.sellPriceImpactPct??null,persistenceDecision:x.persistenceDecision||null,consecutiveEligible:x.consecutiveEligible||0,fastTrackReady:!!x.fastTrackReady}));
}
console.log(`COMPLETED=${Number(v.completedLifecycleTrades||0)} MICRO_GATE=${g.allowed}`);
console.log('V226_DIAGNOSTIC_PASS');
NODE
