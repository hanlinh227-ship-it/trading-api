#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.7.2 OPPORTUNITY AUDIT ==='
echo '=== LIVE SNAPSHOT ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const r=p=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return {}}};
const s=r('/opt/meme-alpha/app/runtime-status/signal-snapshot.json');
const g=r('/opt/meme-alpha/app/runtime-status/micro-live-gate.json');
const cs=s.candidates||[];
console.log(`SIGNAL_TS=${s.timestamp||'-'} TOTAL=${cs.length} MEME=${cs.filter(x=>x.universeClass==='MEME_CONFIRMED').length} GATE=${g.allowed===true}`);
const x=cs.filter(c=>c.universeClass==='MEME_CONFIRMED').sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,20);
for(const c of x)console.log(JSON.stringify({symbol:c.symbol,score:c.score,decision:c.decision,security:c.securityDecision,holder:c.holderClusterDecision??null,sell:c.sellRoute??null,impact:c.sellPriceImpactPct??null,liq:c.liquidityUsd,chg5m:c.priceChange5m,buyers:c.netBuyers5m,avgBuyers:c.avgNetBuyersLast2,slope:c.scoreSlopeLast2,stable:c.liquidityStableLast2,elig:c.consecutiveEligible,token2022:c.token2022,hardReject:c.hardReject}));
NODE

echo '=== SECURITY/HOLDER/SELL PIPELINE TRACE ==='
for f in src/*.js; do
  [ -f "$f" ] || continue
  if grep -qEi 'securityDecision|holderClusterDecision|sellRoute|PROBE_CANDIDATE|consecutiveEligible|deep.?check|rug|holder' "$f"; then
    echo "--- $f ---"
    grep -nEi 'securityDecision|holderClusterDecision|sellRoute|PROBE_CANDIDATE|consecutiveEligible|deep.?check|rug|holder|REVIEW|PASS' "$f" | head -n 180 || true
  fi
done

echo '=== SERVICE CADENCE TRACE ==='
systemctl cat meme-alpha-paper.service --no-pager 2>/dev/null || true
systemctl show meme-alpha-paper.service -p MainPID -p ActiveState -p SubState -p ExecMainStartTimestamp --no-pager || true

echo V272_OPPORTUNITY_AUDIT_PASS
