#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
node - <<'NODE'
const fs=require('fs'); const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8')); if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER'); console.log('MODE=PAPER');
NODE
B=/var/lib/meme-alpha/data/backups/v120-$(date -u +%Y%m%d-%H%M%S); mkdir -p "$B"; cp -a src package.json "$B"/
cat > src/entry-exit-intelligence.js <<'NODE'
const fs=require('fs');
const P='/var/lib/meme-alpha/data/paper';
const read=(f,d)=>{try{return JSON.parse(fs.readFileSync(`${P}/${f}`,'utf8'))}catch{return d}};
const scanner=read('scanner-latest.json',{candidates:[]});
const persist=read('persistence-state.json',{candidates:{}});
const health=read('scanner-source-health.json',{});
const paper=read('state.json',{openPositions:[]});
const now=Date.now(); const healthy=health.status==='HEALTHY'&&health.allowNewEntries===true&&health.usingCache!==true&&(now-Date.parse(health.checkedAt||0))<180000;
const arr=(scanner.candidates||[]).map(c=>{
 const p=(persist.candidates||{})[c.mint]||{}; const obs=(p.observations||[]).slice(-3); const scores=obs.map(x=>Number(x.score||0)); const buyers=obs.map(x=>Number(x.netBuyers5m||x.netBuyers||0));
 const score=Number(c.score||0), avg2=scores.length>=2?(scores.at(-1)+scores.at(-2))/2:score, slope=scores.length>=2?scores.at(-1)-scores.at(-2):0, buyerSlope=buyers.length>=2?buyers.at(-1)-buyers.at(-2):0;
 const impact=Number(c.sellImpactPct ?? c.priceImpactPct); const impactOk=Number.isFinite(impact)&&Math.abs(impact)<=1.25;
 const hardSafe=c.securityDecision==='PASS'&&c.sellRoute===true&&!c.hardReject&&c.universe!=='NON_MEME'&&c.tokenProgram!=='Token-2022';
 const fast=healthy&&hardSafe&&score>=82&&avg2>=79&&slope>=0&&buyerSlope>=0&&impactOk&&Number(c.liquidityUsd||0)>=50000&&Number(c.move5mPct||c.priceChange5m||0)<15;
 return {mint:c.mint,symbol:c.symbol,score,avg2:+avg2.toFixed(2),scoreSlope:slope,buyerSlope,sellImpactPct:Number.isFinite(impact)?impact:null,liquidityUsd:c.liquidityUsd||0,shadowFastEntry:fast};
}).sort((a,b)=>b.score-a.score);
const positions=(paper.openPositions||[]).map(p=>({positionId:p.positionId||null,mint:p.mint,symbol:p.symbol,mfePct:p.mfePct||0,maePct:p.maePct||0,entryPrice:p.entryPrice||null,shadowExitRules:['LIQUIDITY_COLLAPSE','ADVERSE_SHOCK','PROFIT_GIVEBACK','THESIS_BREAK']}));
const out={version:'1.2-shadow',timestamp:new Date().toISOString(),behaviorChange:false,sourceHealthy:healthy,shadowFastEntryCount:arr.filter(x=>x.shadowFastEntry).length,topCandidates:arr.slice(0,20),positions};
fs.writeFileSync(`${P}/entry-exit-intelligence.json.tmp`,JSON.stringify(out,null,2)); fs.renameSync(`${P}/entry-exit-intelligence.json.tmp`,`${P}/entry-exit-intelligence.json`);
console.log('=== MEME ALPHA v1.2 ENTRY EXIT INTELLIGENCE SHADOW ==='); console.log(`SOURCE_HEALTHY=${healthy}`); console.log(`SHADOW_FAST_ENTRY=${out.shadowFastEntryCount}`); console.log(`OPEN_POSITIONS=${positions.length}`); console.log('BEHAVIOR_CHANGE=false'); console.log('V120_SHADOW_PASS');
NODE
node --check src/entry-exit-intelligence.js
node src/entry-exit-intelligence.js
node - <<'NODE'
const fs=require('fs'); const p='package.json'; const j=JSON.parse(fs.readFileSync(p)); j.scripts=j.scripts||{}; j.scripts.intelligence='node src/entry-exit-intelligence.js'; fs.writeFileSync(p,JSON.stringify(j,null,2)+'\n');
NODE
systemctl is-active meme-alpha-paper.service
systemctl is-enabled meme-alpha-paper.service
node - <<'NODE'
const fs=require('fs'); const c=JSON.parse(fs.readFileSync('config/runtime.json')); const x=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/entry-exit-intelligence.json')); if(c.mode!=='PAPER'||x.behaviorChange!==false||x.version!=='1.2-shadow') process.exit(1); console.log('MODE=PAPER'); console.log('LIVE_EXECUTION=DISABLED'); console.log('V120_INVARIANT_PASS');
NODE
free -h
echo "V120_DEPLOY_COMPLETE"
echo "BACKUP=$B"
