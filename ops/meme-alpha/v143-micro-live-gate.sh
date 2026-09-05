#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v1.4.3 MICRO LIVE GATE ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('CURRENT_MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
NODE

mkdir -p runtime-status
chmod 2775 runtime-status

cat > src/micro-live-gate.js <<'NODE'
import fs from 'node:fs';
import net from 'node:net';

const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/paper';
const ARM='/etc/meme-alpha/micro-live-armed';
const SOCK='/run/meme-alpha-signer/signer.sock';
const readJson=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const ageSec=(ts)=>Number.isFinite(Date.parse(ts))?(Date.now()-Date.parse(ts))/1000:Infinity;
const exists=(p)=>{try{return fs.existsSync(p)}catch{return false}};

async function signerHealth(){
  return await new Promise((resolve)=>{
    const s=net.createConnection(SOCK); let data=''; let done=false;
    const finish=(v)=>{if(done)return;done=true;try{s.destroy()}catch{};resolve(v)};
    s.setTimeout(1200);
    s.on('connect',()=>s.write(JSON.stringify({op:'health'})+'\n'));
    s.on('data',(b)=>{data+=b.toString(); if(data.includes('\n')){try{finish(JSON.parse(data.split('\n')[0]))}catch{finish({ok:false,error:'BAD_JSON'})}}});
    s.on('timeout',()=>finish({ok:false,error:'TIMEOUT'}));
    s.on('error',(e)=>finish({ok:false,error:e.code||e.message}));
  });
}

const runtime=readJson(`${APP}/config/runtime.json`);
const validation=readJson(`${DATA}/validation.json`);
const stressPath=`${DATA}/stress-test.json`;
const stress=readJson(stressPath);
const source=readJson(`${DATA}/scanner-source-health.json`);
const risk=readJson(`${DATA}/risk-state.json`);
const signer=await signerHealth();
const reasons=[];

let armOk=false;
try {
  const st=fs.statSync(ARM);
  const txt=fs.readFileSync(ARM,'utf8').trim();
  armOk=st.uid===0 && (st.mode & 0o777)===0o600 && txt==='ARMED=YES';
} catch {}

if(runtime.mode!=='MICRO_LIVE') reasons.push('MODE_NOT_MICRO_LIVE');
if(!armOk) reasons.push('ROOT_ARMING_FILE_ABSENT_OR_INVALID');
if(!(signer?.ok===true && signer?.mode==='READY' && signer?.signingEnabled===true && signer?.walletLoaded===true)) reasons.push('SIGNER_NOT_READY');
if(!(source?.status==='HEALTHY' && source?.allowNewEntries===true && source?.usingCache!==true && ageSec(source?.checkedAt)<180)) reasons.push('SOURCE_HEALTH_NOT_READY');
if(!(risk?.entryAllowed===true && ageSec(risk?.timestamp)<120)) reasons.push('RISK_NOT_READY');

const completed=Number(validation?.completedLifecycles ?? validation?.summary?.completedLifecycles ?? 0);
if(completed < 20) reasons.push(`VALIDATION_LIFECYCLES_${completed}_LT_20`);
if(!exists(stressPath)) reasons.push('STRESS_REPORT_MISSING');
const stressFail=Number(stress?.fail ?? stress?.summary?.fail ?? stress?.FAIL ?? 0);
if(stressFail>0) reasons.push(`STRESS_FAIL_${stressFail}`);

const allowed=reasons.length===0;
const out={version:'1.4.3',timestamp:new Date().toISOString(),allowed,currentMode:runtime.mode||null,armOk,signer:{ok:!!signer?.ok,mode:signer?.mode||null,signingEnabled:!!signer?.signingEnabled,walletLoaded:!!signer?.walletLoaded},validationCompletedLifecycles:completed,sourceHealthy:source?.status==='HEALTHY',riskEntryAllowed:risk?.entryAllowed===true,reasons};
for (const p of [`${DATA}/micro-live-gate.json`,`${APP}/runtime-status/micro-live-gate.json`]) {
  const tmp=`${p}.tmp`;
  fs.writeFileSync(tmp,JSON.stringify(out,null,2));
  fs.renameSync(tmp,p);
  try{fs.chmodSync(p,0o664)}catch{}
}
console.log(`MICRO_LIVE_ALLOWED=${allowed}`);
console.log(`VALIDATION_COMPLETED_LIFECYCLES=${completed}`);
console.log(`SIGNER_MODE=${out.signer.mode}`);
console.log(`SIGNING_ENABLED=${out.signer.signingEnabled}`);
console.log(`WALLET_LOADED=${out.signer.walletLoaded}`);
console.log(`BLOCK_REASONS=${reasons.join(',')||'NONE'}`);
if(runtime.mode==='PAPER' && allowed) throw new Error('FAIL_OPEN_GATE_IN_PAPER');
console.log('FAIL_CLOSED_GATE=PASS');
NODE

# GitHub runner uses UMask=0077; explicitly grant only deploy-group read access so the bot can execute it.
chown github-runner:meme-alpha-deploy src/micro-live-gate.js
chmod 664 src/micro-live-gate.js
node --check src/micro-live-gate.js

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const p='package.json';
const j=JSON.parse(fs.readFileSync(p,'utf8'));
if(!j.scripts?.cycle5) throw new Error('CYCLE5_NOT_FOUND');
if(!j.scripts.cycle5.includes('src/micro-live-gate.js')) j.scripts.cycle5 += ' && node src/micro-live-gate.js';
fs.writeFileSync(p,JSON.stringify(j,null,2)+'\n');
console.log('CYCLE5_MICRO_LIVE_GATE=INSTALLED');
NODE
chmod g+rw package.json

if [ -r /var/lib/meme-alpha/signer-key ] || [ -x /var/lib/meme-alpha/signer-key ]; then
  echo 'FAIL_RUNNER_SIGNER_KEY_ACCESS'
  exit 1
fi
if [ -S /run/meme-alpha-signer/signer.sock ] && [ -w /run/meme-alpha-signer/signer.sock ]; then
  echo 'FAIL_RUNNER_SIGNER_SOCKET_WRITE'
  exit 1
fi

echo 'RUNNER_SIGNER_KEY_ACCESS=DENIED_PASS'
echo 'RUNNER_SIGNER_SOCKET_WRITE=DENIED_PASS'

sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 90
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const p='/opt/meme-alpha/app/runtime-status/micro-live-gate.json';
if(!fs.existsSync(p)) throw new Error('MICRO_LIVE_STATUS_NOT_PRODUCED');
const x=JSON.parse(fs.readFileSync(p,'utf8'));
console.log(`STATUS_VERSION=${x.version}`);
console.log(`MICRO_LIVE_ALLOWED=${x.allowed}`);
console.log(`CURRENT_MODE=${x.currentMode}`);
console.log(`SIGNER_MODE=${x.signer?.mode}`);
console.log(`SIGNING_ENABLED=${x.signer?.signingEnabled}`);
console.log(`WALLET_LOADED=${x.signer?.walletLoaded}`);
console.log(`VALIDATION_COMPLETED_LIFECYCLES=${x.validationCompletedLifecycles}`);
console.log(`BLOCK_REASONS=${(x.reasons||[]).join(',')}`);
if(x.version!=='1.4.3'||x.allowed!==false||x.currentMode!=='PAPER'||x.signer?.signingEnabled!==false||x.signer?.walletLoaded!==false) throw new Error('V143_FAIL_CLOSED_INVARIANT');
console.log('V143_FAIL_CLOSED_INVARIANT_PASS');
NODE

echo 'NO_WALLET_CREATED=TRUE'
echo 'NO_LIVE_ENABLE=TRUE'
echo 'V143_MICRO_LIVE_GATE_STAGED_PASS'
