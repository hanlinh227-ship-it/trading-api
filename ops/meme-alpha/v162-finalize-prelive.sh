#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v1.6.2 FINALIZE PRE-LIVE ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));if(c.mode!=='PAPER')throw new Error('ABORT_NOT_PAPER');console.log('ANALYSIS_MODE=PAPER');
NODE

# Replace inodes through the setgid deploy directory so bot-readable group permissions
# are deterministic even when an older file was owned by meme-alpha.
for f in src/universe.js src/validation.js src/stress-test.js; do
  [ -f "$f" ] || { echo "MISSING=$f"; exit 1; }
  t="$f.runner-new-$$"
  cat "$f" > "$t"
  chmod 664 "$t"
  mv -f "$t" "$f"
  node --check "$f"
done

cat > src/micro-live-gate.js.runner-new-$$ <<'NODE'
import fs from 'node:fs';
import net from 'node:net';
const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/paper';
const EXEC='/etc/meme-alpha/execution-mode';
const ARM='/etc/meme-alpha/micro-live-armed';
const SOCK='/run/meme-alpha-signer/signer.sock';
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const age=ts=>Number.isFinite(Date.parse(ts))?(Date.now()-Date.parse(ts))/1000:Infinity;
const rootControl=(path,expected)=>{try{const st=fs.statSync(path);const txt=fs.readFileSync(path,'utf8').trim();return st.uid===0&&(st.mode&0o777)===0o640&&txt===expected}catch{return false}};
const text=(p,d='DISABLED')=>{try{return fs.readFileSync(p,'utf8').trim()}catch{return d}};
async function signerHealth(){return await new Promise(resolve=>{const s=net.createConnection(SOCK);let d='',done=false;const fin=v=>{if(done)return;done=true;try{s.destroy()}catch{}resolve(v)};s.setTimeout(1200);s.on('connect',()=>s.write('{"op":"health"}\n'));s.on('data',b=>{d+=b.toString();if(d.includes('\n')){try{fin(JSON.parse(d.split('\n')[0]))}catch{fin({ok:false,error:'BAD_JSON'})}}});s.on('timeout',()=>fin({ok:false,error:'TIMEOUT'}));s.on('error',e=>fin({ok:false,error:e.code||e.message}))})}
const runtime=read(`${APP}/config/runtime.json`),validation=read(`${DATA}/validation.json`),stress=read(`${DATA}/stress-test.json`),source=read(`${DATA}/scanner-source-health.json`),risk=read(`${DATA}/risk-state.json`),universe=read(`${APP}/runtime-status/universe.json`),signer=await signerHealth();
const executionMode=text(EXEC,'DISABLED');
const execControlled=rootControl(EXEC,'MICRO_LIVE');
const armOk=rootControl(ARM,'ARMED=YES');
const reasons=[];
if(runtime.mode!=='PAPER') reasons.push('ANALYSIS_MODE_NOT_PAPER');
if(!execControlled) reasons.push(`EXECUTION_MODE_${executionMode||'DISABLED'}_NOT_MICRO_LIVE_OR_INVALID_CONTROL`);
if(!armOk) reasons.push('ROOT_MICRO_LIVE_ARM_ABSENT_OR_INVALID');
if(!(signer?.ok===true&&signer?.mode==='READY'&&signer?.signingEnabled===true&&signer?.walletLoaded===true)) reasons.push('SIGNER_NOT_READY');
if(!(source?.status==='HEALTHY'&&source?.allowNewEntries===true&&source?.usingCache!==true&&age(source?.checkedAt)<180)) reasons.push('SOURCE_HEALTH_NOT_READY');
if(!(risk?.entryAllowed===true&&age(risk?.timestamp)<120)) reasons.push('RISK_NOT_READY');
const completed=Number(validation?.completedLifecycleTrades||0);
if(completed<20) reasons.push(`VALIDATION_LIFECYCLES_${completed}_LT_20`);
if(validation?.readinessStatus!=='PASS') reasons.push(`VALIDATION_READINESS_${validation?.readinessStatus||'MISSING'}`);
if(stress?.status!=='PASS') reasons.push(`STRESS_${stress?.status||'MISSING'}`);
if(!(universe?.version==='1.6'&&universe?.unknownEntryEligible===false)) reasons.push('POSITIVE_MEME_GATE_NOT_PROVEN');
const allowed=reasons.length===0;
const out={version:'1.6.2',timestamp:new Date().toISOString(),allowed,analysisMode:runtime.mode||null,executionMode,executionModeRootControlled:execControlled,armOk,completedLifecycles:completed,validationReadiness:validation?.readinessStatus||null,stressStatus:stress?.status||null,universeVersion:universe?.version||null,sourceHealthy:source?.status==='HEALTHY',riskEntryAllowed:risk?.entryAllowed===true,signer:{ok:!!signer?.ok,mode:signer?.mode||null,signingEnabled:!!signer?.signingEnabled,walletLoaded:!!signer?.walletLoaded},reasons};
for(const p of [`${DATA}/micro-live-gate.json`,`${APP}/runtime-status/micro-live-gate.json`]){const t=`${p}.tmp`;fs.writeFileSync(t,JSON.stringify(out,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}}
console.log('=== MEME ALPHA MICRO LIVE GATE v1.6.2 ===');
console.log(`MICRO_LIVE_ALLOWED=${allowed}`);console.log(`ANALYSIS_MODE=${out.analysisMode}`);console.log(`EXECUTION_MODE=${executionMode}`);console.log(`COMPLETED=${completed}`);console.log(`VALIDATION=${out.validationReadiness}`);console.log(`STRESS=${out.stressStatus}`);console.log(`SIGNER=${out.signer.mode}`);console.log(`BLOCK_REASONS=${reasons.join(',')||'NONE'}`);console.log('ROOT_CONTROLLED_EXECUTION_GATE=PASS');
NODE
chmod 664 src/micro-live-gate.js.runner-new-$$
mv -f src/micro-live-gate.js.runner-new-$$ src/micro-live-gate.js
node --check src/micro-live-gate.js

node --input-type=module - <<'NODE'
import fs from 'node:fs';const p='package.json',j=JSON.parse(fs.readFileSync(p,'utf8'));j.scripts ||= {};j.scripts.stress='node src/stress-test.js';let c=j.scripts.cycle5||'';c=c.replace(/\s*&&\s*node src\/stress-test\.js/g,'').replace(/\s*&&\s*node src\/micro-live-gate\.js/g,'');c+=' && node src/stress-test.js && node src/micro-live-gate.js';j.scripts.cycle5=c;fs.writeFileSync(p,JSON.stringify(j,null,2)+'\n');console.log(`CYCLE5=${c}`);
NODE

sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 115
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null

node --input-type=module - <<'NODE'
import fs from 'node:fs';const R='/opt/meme-alpha/app/runtime-status';for(const n of ['universe.json','validation.json','stress-test.json','micro-live-gate.json']){const p=`${R}/${n}`;if(!fs.existsSync(p))throw new Error(`MISSING_${n}`);const x=JSON.parse(fs.readFileSync(p));console.log(`STATUS_${n}=${JSON.stringify(x)}`);}
const u=JSON.parse(fs.readFileSync(`${R}/universe.json`));const v=JSON.parse(fs.readFileSync(`${R}/validation.json`));const s=JSON.parse(fs.readFileSync(`${R}/stress-test.json`));const g=JSON.parse(fs.readFileSync(`${R}/micro-live-gate.json`));if(u.version!=='1.6'||u.unknownEntryEligible!==false)throw new Error('UNIVERSE_INVARIANT');if(v.version!=='1.6')throw new Error('VALIDATION_VERSION');if(s.version!=='1.6')throw new Error('STRESS_VERSION');if(g.version!=='1.6.2'||g.allowed!==false||g.analysisMode!=='PAPER'||g.executionMode!=='DISABLED')throw new Error('GATE_INVARIANT');console.log('V162_PRELIVE_FINALIZE_PASS');
NODE

echo 'WALLET_CREATED=FALSE'
echo 'LIVE_EXECUTION=FALSE'
