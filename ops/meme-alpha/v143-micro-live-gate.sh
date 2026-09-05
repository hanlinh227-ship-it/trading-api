#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/paper
cd "$APP"

echo '=== MEME ALPHA v1.4.3 MICRO LIVE GATE ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('CURRENT_MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
NODE

cat > src/micro-live-gate.js <<'NODE'
import fs from 'node:fs';
import net from 'node:net';

const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/paper';
const ARM='/etc/meme-alpha/micro-live-armed';
const SOCK='/run/meme-alpha-signer/signer.sock';
const readJson=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const ageSec=(ts)=>Number.isFinite(Date.parse(ts))?(Date.now()-Date.parse(ts))/1000:Infinity;

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
const stress=readJson(`${DATA}/stress-test.json`);
const source=readJson(`${DATA}/scanner-source-health.json`);
const risk=readJson(`${DATA}/risk-state.json`);
const signer=await signerHealth();
const reasons=[];

// Arming file is deliberately root-controlled and absent during PAPER staging.
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
const stressFail=Number(stress?.fail ?? stress?.summary?.fail ?? stress?.FAIL ?? 0);
if(stressFail>0) reasons.push(`STRESS_FAIL_${stressFail}`);

// Fail closed if wallet path is not present. Do not create or inspect secret contents.
let walletFiles=0;
try{walletFiles=fs.readdirSync('/var/lib/meme-alpha/signer-key').filter(x=>!x.startsWith('.')).length}catch{}
if(walletFiles===0) reasons.push('NO_SIGNER_WALLET');

const allowed=reasons.length===0;
const out={version:'1.4.3',timestamp:new Date().toISOString(),allowed,currentMode:runtime.mode||null,signer:{ok:!!signer?.ok,mode:signer?.mode||null,signingEnabled:!!signer?.signingEnabled,walletLoaded:!!signer?.walletLoaded},validationCompletedLifecycles:completed,sourceHealthy:source?.status==='HEALTHY',riskEntryAllowed:risk?.entryAllowed===true,reasons};
fs.writeFileSync(`${DATA}/micro-live-gate.json.tmp`,JSON.stringify(out,null,2));
fs.renameSync(`${DATA}/micro-live-gate.json.tmp`,`${DATA}/micro-live-gate.json`);
console.log(`MICRO_LIVE_ALLOWED=${allowed}`);
console.log(`VALIDATION_COMPLETED_LIFECYCLES=${completed}`);
console.log(`SIGNER_MODE=${out.signer.mode}`);
console.log(`SIGNING_ENABLED=${out.signer.signingEnabled}`);
console.log(`WALLET_LOADED=${out.signer.walletLoaded}`);
console.log(`BLOCK_REASONS=${reasons.join(',')||'NONE'}`);
if(allowed) throw new Error('UNEXPECTED_MICRO_LIVE_ALLOWED_DURING_STAGING');
console.log('FAIL_CLOSED_GATE=PASS');
NODE

node --check src/micro-live-gate.js
sudo -n -u meme-alpha /usr/bin/node "$APP/src/micro-live-gate.js"

# Runner must still be unable to access signer secrets/socket.
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
echo 'NO_WALLET_CREATED=TRUE'
echo 'NO_LIVE_ENABLE=TRUE'
echo 'V143_MICRO_LIVE_GATE_STAGED_PASS'
