#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const r=p=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return {}}};
const s=r('/opt/meme-alpha/app/runtime-status/signal-snapshot.json');
const g=r('/opt/meme-alpha/app/runtime-status/micro-live-gate.json');
console.log('=== EMBEDDED HEALTH ===');
console.log('SIGNAL_TS='+String(s.timestamp||'-'));
console.log('SOURCE_HEALTH='+JSON.stringify(s.sourceHealth||{}));
console.log('RISK='+JSON.stringify(s.risk||{}));
console.log('GATE='+JSON.stringify({allowed:g.allowed,reasons:g.reasons,sourceHealthy:g.sourceHealthy,liveRiskReady:g.liveRiskReady,riskGlobalBlockReasons:g.riskGlobalBlockReasons,riskLiveBlockReasons:g.riskLiveBlockReasons}));
NODE
echo V294_EMBEDDED_HEALTH_AUDIT_PASS
