#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.9.1 TREND DECISION AUDIT ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const r=p=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return {}}};
const s=r('/opt/meme-alpha/app/runtime-status/signal-snapshot.json');
let t=r('/opt/meme-alpha/app/runtime-status/trend-pulse.json');
const g=r('/opt/meme-alpha/app/runtime-status/micro-live-gate.json');
const sm=new Map((s.candidates||[]).map(x=>[x.mint,x]));
console.log(`SIGNAL_TS=${s.timestamp||'-'} TREND_TS=${t.timestamp||'-'} GATE=${g.allowed===true} EXEC=${g.executionMode||'-'}`);
for(const p of (t.rows||[]).slice(0,15)){
 const c=sm.get(p.mint)||{};
 console.log(JSON.stringify({symbol:p.symbol,mint:p.mint,pulse:p.pulseScore,status:p.status,narrative:p.narrative,volAccel:p.volumeAcceleration,txnAccel:p.txnAcceleration,buySell:p.buySellRatio,chg5:p.price5m,liq:p.liquidityUsd,boosted:p.promotionFlag,score:c.score,decision:c.decision,universe:c.universeClass,security:c.securityDecision,securityReview:c.securityReviewReasons||[],holder:c.holderClusterDecision,holderReview:c.holderReviewReasons||[],sell:c.sellRoute,impact:c.sellPriceImpactPct,eligible:c.consecutiveEligible,netBuyers:c.netBuyers5m,hardReject:c.hardReject||[],token2022:c.token2022}));
}
NODE
echo V291_TREND_DECISION_AUDIT_PASS
