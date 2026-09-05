#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== ENTRY BLOCKER AUDIT ==='
echo '--- HOLDER CLUSTER DECISIONS ---'
grep -n -C 8 -E 'DEV_IDENTITY|securityDecision|clusterDecision|REVIEW|BLOCK|holderCluster' src/holder-cluster.js | head -n 420 || true
echo '--- PERSISTENCE READINESS ---'
grep -n -C 8 -E 'PROBE|READY|consecutiveEligible|securityDecision|sellRoute|hardReject|universeClass' src/persistence.js | head -n 500 || true
echo '--- RISK ENTRY GATES ---'
grep -n -C 8 -E 'PROBE|securityDecision|sellRoute|hardReject|universeClass|entryAllowed|candidates' src/risk.js | head -n 500 || true
echo '--- CURRENT HIGH SCORE STATE ---'
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const read=p=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return {}}};
const scan=read('/var/lib/meme-alpha/data/paper/scanner-latest.json'), per=read('/var/lib/meme-alpha/data/paper/persistence-state.json'), risk=read('/var/lib/meme-alpha/data/paper/risk-state.json');
const tokens=per.tokens||{};
for(const c of (scan.candidates||[]).filter(x=>Number(x.score)>=65).sort((a,b)=>b.score-a.score).slice(0,20)){
 const p=tokens[c.mint]||{};
 console.log(JSON.stringify({symbol:c.symbol,name:c.name,mint:c.mint,score:c.score,decision:c.decision,universe:c.universeClass,security:c.securityDecision,hardReject:c.hardReject,sellRoute:c.sellRoute,sellImpact:c.sellPriceImpactPct,token2022:c.token2022,persistence:p.persistenceDecision,consecutive:p.consecutiveEligible,holderCluster:c.holderClusterDecision||c.holderCluster?.decision||null,securityReasons:c.securityReasons||c.security?.reasons||null},null,0));
}
console.log('RISK_ENTRY_ALLOWED='+risk.entryAllowed);console.log('RISK_CANDIDATE_COUNT='+(risk.candidates||[]).length);console.log('RISK_BLOCKS='+JSON.stringify(risk.globalBlockReasons||[]));
NODE
echo V201_ENTRY_BLOCKER_AUDIT_PASS
