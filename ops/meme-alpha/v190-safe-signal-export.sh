#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
cat > src/safe-signal-export.js.new-$$ <<'NODE'
import fs from 'node:fs';
const P='/var/lib/meme-alpha/data/paper',OUT='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';
const read=(n,d={})=>{try{return JSON.parse(fs.readFileSync(`${P}/${n}`,'utf8'))}catch{return d}};
const scan=read('scanner-latest.json',{candidates:[]}),persist=read('persistence-state.json'),risk=read('risk-state.json');
function findP(m){for(const root of [persist.tokens,persist.candidates,persist.state,persist]){if(!root)continue;if(Array.isArray(root)){const x=root.find(v=>v?.mint===m);if(x)return x}else if(typeof root==='object'&&root[m])return root[m]}return null}
const candidates=(scan.candidates||[]).map(c=>{const p=findP(c.mint);return{mint:c.mint,symbol:c.symbol,name:c.name,score:Number(c.score||0),decision:c.decision,universeClass:c.universeClass,universeConfidence:c.universeConfidence,securityDecision:c.securityDecision,hardReject:c.hardReject||[],token2022:!!c.token2022,sellRoute:c.sellRoute===true,liquidityUsd:Number(c.liquidityUsd||0),sellImpactPct:Number.isFinite(Number(c.sellImpactPct))?Number(c.sellImpactPct):null,priceImpactPct:Number.isFinite(Number(c.priceImpactPct))?Number(c.priceImpactPct):null,organicRatio5m:Number(c.organicRatio5m||0),netBuyers5m:Number(c.netBuyers5m||0),sources:c.sources||[],persistenceDecision:p?.persistenceDecision||null,consecutiveEligible:Number(p?.consecutiveEligible||0),persistenceKeys:p?Object.keys(p).slice(0,60):[]}}).sort((a,b)=>b.score-a.score).slice(0,30);
const safeRisk={};for(const k of Object.keys(risk||{})){const v=risk[k];if(['string','number','boolean'].includes(typeof v)||v===null)safeRisk[k]=v;else if(Array.isArray(v))safeRisk[k]=v.slice(0,10);else if(v&&typeof v==='object'&&JSON.stringify(v).length<12000)safeRisk[k]=v}
const out={version:'1.9',timestamp:new Date().toISOString(),scannerVersion:scan.version||null,persistenceTopLevelKeys:Object.keys(persist||{}),riskTopLevelKeys:Object.keys(risk||{}),risk:safeRisk,candidates};const t=OUT+'.tmp';fs.writeFileSync(t,JSON.stringify(out,null,2));fs.renameSync(t,OUT);try{fs.chmodSync(OUT,0o664)}catch{};console.log(`SAFE_SIGNAL_EXPORT=${candidates.length}`);
NODE
chmod 664 src/safe-signal-export.js.new-$$
mv -f src/safe-signal-export.js.new-$$ src/safe-signal-export.js
node --check src/safe-signal-export.js
node --input-type=module - <<'NODE'
import fs from 'node:fs';const p='package.json',j=JSON.parse(fs.readFileSync(p));let c=j.scripts.cycle5;c=c.replace(/\s*&&\s*node src\/safe-signal-export\.js/g,'');c=c.replace(' && node src/position.js',' && node src/safe-signal-export.js && node src/position.js');j.scripts.cycle5=c;fs.writeFileSync(p,JSON.stringify(j,null,2)+'\n');console.log(c)
NODE
sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 50
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
node --input-type=module - <<'NODE'
import fs from 'node:fs';const p='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';if(!fs.existsSync(p))throw new Error('NO_SIGNAL_SNAPSHOT');const x=JSON.parse(fs.readFileSync(p));console.log(JSON.stringify(x,null,2));console.log('V190_SIGNAL_EXPORT_PASS');
NODE
