#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SEC=$APP/ops/security
cd "$APP"

echo '=== MEME ALPHA v2.0.1 UNIVERSE COMPAT + OBSERVABILITY ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));if(c.mode!=='PAPER')throw new Error('ABORT_NOT_PAPER');console.log('ANALYSIS_MODE=PAPER');console.log('LIVE_EXECUTION=DISABLED');
NODE

python3 - <<'PY'
from pathlib import Path
p=Path('src/micro-live-gate.js')
s=p.read_text()
old="universe?.version==='1.6'&&universe?.unknownEntryEligible===false"
new="['1.6','1.6.1'].includes(universe?.version)&&universe?.unknownEntryEligible===false"
if old in s:s=s.replace(old,new)
elif new not in s:raise SystemExit('MICRO_GATE_UNIVERSE_CHECK_NOT_FOUND')
p.write_text(s)
PY
node --check src/micro-live-gate.js

cat > src/safe-signal-export.js.new-$$ <<'NODE'
import fs from 'node:fs';
const P='/var/lib/meme-alpha/data/paper',OUT='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';
const read=(n,d={})=>{try{return JSON.parse(fs.readFileSync(`${P}/${n}`,'utf8'))}catch{return d}};
const scan=read('scanner-latest.json',{candidates:[]}),persist=read('persistence-state.json'),risk=read('risk-state.json'),source=read('scanner-source-health.json');
function findP(m){for(const root of [persist.tokens,persist.candidates,persist.state,persist]){if(!root)continue;if(Array.isArray(root)){const x=root.find(v=>v?.mint===m);if(x)return x}else if(typeof root==='object'&&root[m])return root[m]}return null}
const candidates=(scan.candidates||[]).map(c=>{const p=findP(c.mint);return{mint:c.mint,symbol:c.symbol,name:c.name,score:Number(c.score||0),decision:c.decision,universeClass:c.universeClass,universeConfidence:c.universeConfidence,securityDecision:c.securityDecision,hardReject:c.hardReject||[],token2022:!!c.token2022,sellRoute:c.sellRoute===true,liquidityUsd:Number(c.liquidityUsd||0),sellImpactPct:Number.isFinite(Number(c.sellImpactPct))?Number(c.sellImpactPct):null,priceImpactPct:Number.isFinite(Number(c.priceImpactPct))?Number(c.priceImpactPct):null,organicRatio5m:Number(c.organicRatio5m||0),netBuyers5m:Number(c.netBuyers5m||0),sources:c.sources||[],persistenceDecision:p?.persistenceDecision||null,consecutiveEligible:Number(p?.consecutiveEligible||0)}}).sort((a,b)=>b.score-a.score).slice(0,30);
const safeRisk={};for(const k of Object.keys(risk||{})){const v=risk[k];if(['string','number','boolean'].includes(typeof v)||v===null)safeRisk[k]=v;else if(Array.isArray(v))safeRisk[k]=v.slice(0,10);else if(v&&typeof v==='object'&&JSON.stringify(v).length<12000)safeRisk[k]=v}
const sourceHealth={status:source?.status||null,checkedAt:source?.checkedAt||null,successfulSources:Number(source?.successfulSources||0),failedSources:Number(source?.failedSources||0),usingCache:source?.usingCache===true,allowNewEntries:source?.allowNewEntries===true};
const out={version:'2.0.1',timestamp:new Date().toISOString(),scannerVersion:scan.version||null,sourceHealth,risk:safeRisk,candidates};const t=OUT+'.tmp';fs.writeFileSync(t,JSON.stringify(out,null,2));fs.renameSync(t,OUT);try{fs.chmodSync(OUT,0o664)}catch{};console.log(`SAFE_SIGNAL_EXPORT=${candidates.length} SOURCE=${sourceHealth.status}`);
NODE
chmod 664 src/safe-signal-export.js.new-$$
mv -f src/safe-signal-export.js.new-$$ src/safe-signal-export.js
node --check src/safe-signal-export.js

python3 - <<'PY'
from pathlib import Path
for name in ['v180-root-create-wallet-after-validation.sh','v193-root-arm-micro-live.sh','v181-root-arm-micro-live-legacy.sh']:
 p=Path('/opt/meme-alpha/app/ops/security')/name
 if not p.exists():continue
 s=p.read_text();old="u.get('version')=='1.6'";new="u.get('version') in ('1.6','1.6.1')"
 if old in s:s=s.replace(old,new)
 elif new not in s:raise SystemExit('UNIVERSE_COMPAT_PATTERN_NOT_FOUND_'+name)
 t=p.with_name(p.name+'.new');t.write_text(s);t.chmod(p.stat().st_mode & 0o777);t.replace(p)
 print('PATCHED='+name)
PY
for f in "$SEC"/v180-root-create-wallet-after-validation.sh "$SEC"/v193-root-arm-micro-live.sh; do bash -n "$f"; done

sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 55
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null

node --input-type=module - <<'NODE'
import fs from 'node:fs';const R='/opt/meme-alpha/app/runtime-status';const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));const u=read('universe.json'),g=read('micro-live-gate.json'),sig=read('signal-snapshot.json');
console.log(`UNIVERSE_VERSION=${u.version}`);console.log(`UNKNOWN_ENTRY_ELIGIBLE=${u.unknownEntryEligible}`);console.log(`GATE_ALLOWED=${g.allowed}`);console.log(`GATE_REASONS=${(g.reasons||[]).join(',')}`);console.log(`SIGNAL_SNAPSHOT=${sig.version}`);console.log(`SOURCE=${JSON.stringify(sig.sourceHealth)}`);
if(u.version!=='1.6.1'||u.unknownEntryEligible!==false)throw new Error('UNIVERSE_INVARIANT');if(g.allowed!==false||g.executionMode!=='DISABLED')throw new Error('LIVE_GATE_INVARIANT');if((g.reasons||[]).includes('POSITIVE_MEME_GATE_NOT_PROVEN'))throw new Error('UNIVERSE_GATE_COMPAT_FAIL');if(sig.version!=='2.0.1'||sig.sourceHealth?.status!=='HEALTHY'||sig.sourceHealth?.usingCache===true||Number(sig.sourceHealth?.successfulSources)<2)throw new Error('SAFE_SOURCE_OBSERVABILITY_FAIL');console.log('V201_COMPAT_OBSERVABILITY_PASS');
NODE

echo WALLET_CREATED=FALSE
echo MICRO_LIVE_ACTIVE=FALSE
echo LIVE_EXECUTION=FALSE
