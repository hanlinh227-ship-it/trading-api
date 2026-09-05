#!/usr/bin/env bash
set -euo pipefail

APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/paper
R=$APP/runtime-status
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service

[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
cd "$APP"

echo '=== MEME ALPHA v2.4.0 FAST LIVE READY ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));if(c.mode!=='PAPER')throw new Error('ANALYSIS_ENGINE_NOT_PAPER');console.log('ANALYSIS_ENGINE=PAPER_CONTINUOUS');
NODE
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-signer.service
! systemctl is-active --quiet meme-alpha-micro-live.service

B="code-backups/v240-$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$B"
cp -a src/micro-live-gate.js "$B/micro-live-gate.js" 2>/dev/null || true

cat > src/micro-live-gate.js <<'NODE'
import fs from 'node:fs';
import net from 'node:net';
const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/paper';
const ARM='/etc/meme-alpha/micro-live-armed';
const EXEC='/etc/meme-alpha/execution-mode';
const SOCK='/run/meme-alpha-signer/signer.sock';
const readJson=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const ageSec=ts=>Number.isFinite(Date.parse(ts))?(Date.now()-Date.parse(ts))/1000:Infinity;
function rootControl(path,expected){try{const s=fs.statSync(path);return s.uid===0&&(s.mode&0o777)===0o640&&fs.readFileSync(path,'utf8').trim()===expected}catch{return false}}
function executionMode(){try{const s=fs.statSync(EXEC);if(s.uid!==0||(s.mode&0o777)!==0o640)return'DISABLED';return fs.readFileSync(EXEC,'utf8').trim()==='MICRO_LIVE'?'MICRO_LIVE':'DISABLED'}catch{return'DISABLED'}}
async function signerHealth(){return await new Promise(resolve=>{const s=net.createConnection(SOCK);let d='',done=false;const fin=v=>{if(done)return;done=true;try{s.destroy()}catch{}resolve(v)};s.setTimeout(1500);s.on('connect',()=>s.write(JSON.stringify({op:'health'})+'\n'));s.on('data',b=>{d+=b.toString();if(d.includes('\n')){try{fin(JSON.parse(d.split('\n')[0]))}catch{fin({ok:false,error:'BAD_JSON'})}}});s.on('timeout',()=>fin({ok:false,error:'TIMEOUT'}));s.on('error',e=>fin({ok:false,error:e.code||e.message}))})}
const runtime=readJson(`${APP}/config/runtime.json`);
const validation=readJson(`${DATA}/validation.json`);
const stress=readJson(`${DATA}/stress-test.json`);
const source=readJson(`${DATA}/scanner-source-health.json`);
const risk=readJson(`${DATA}/risk-state.json`);
const signer=await signerHealth();
const mode=executionMode();
const reasons=[];
if(mode!=='MICRO_LIVE')reasons.push('EXECUTION_MODE_NOT_MICRO_LIVE');
if(!rootControl(ARM,'ARMED=YES'))reasons.push('ROOT_ARMING_FILE_ABSENT_OR_INVALID');
if(!(signer?.ok===true&&signer?.mode==='READY'&&signer?.signingEnabled===true&&signer?.walletLoaded===true&&signer?.arbitraryRawSign===false))reasons.push('SIGNER_NOT_READY');
if(!(source?.status==='HEALTHY'&&source?.allowNewEntries===true&&source?.usingCache!==true&&ageSec(source?.checkedAt)<180))reasons.push('SOURCE_HEALTH_NOT_READY');
if(!(risk?.entryAllowed===true&&ageSec(risk?.timestamp)<180))reasons.push('RISK_NOT_READY');
const completed=Number(validation?.completedLifecycleTrades??validation?.completedLifecycles??validation?.summary?.completedLifecycles??0);
const validationStatus=String(validation?.readinessStatus||'UNKNOWN');
const stressStatus=String(stress?.status||'UNKNOWN');
const stressFail=Number(stress?.fail??stress?.summary?.fail??0);
// No waiting for a sample quota before real micro trading. A known failure still blocks.
if(validationStatus==='FAIL')reasons.push('VALIDATION_KNOWN_FAILURE');
if(stressStatus==='FAIL'||stressFail>0)reasons.push(`STRESS_KNOWN_FAILURE_${stressFail}`);
const evidenceReady=completed>=20&&validationStatus==='PASS'&&stressStatus==='PASS'&&stressFail===0;
const allowed=reasons.length===0;
const out={version:'2.4.0',timestamp:new Date().toISOString(),allowed,analysisMode:runtime.mode||null,executionMode:mode,armOk:rootControl(ARM,'ARMED=YES'),signer:{ok:!!signer?.ok,mode:signer?.mode||null,signingEnabled:!!signer?.signingEnabled,walletLoaded:!!signer?.walletLoaded,arbitraryRawSign:signer?.arbitraryRawSign===true},sourceHealthy:source?.status==='HEALTHY',riskEntryAllowed:risk?.entryAllowed===true,validationStatus,validationCompletedLifecycles:completed,stressStatus,stressFail,evidenceReady,scaleAllowed:evidenceReady,reasons};
for(const p of [`${DATA}/micro-live-gate.json`,`${APP}/runtime-status/micro-live-gate.json`]){const t=p+'.tmp';fs.writeFileSync(t,JSON.stringify(out,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}}
console.log(`MICRO_LIVE_ALLOWED=${allowed}`);console.log(`EXECUTION_MODE=${mode}`);console.log(`VALIDATION=${validationStatus} COMPLETED=${completed} EVIDENCE_READY=${evidenceReady}`);console.log(`STRESS=${stressStatus} FAIL=${stressFail}`);console.log(`BLOCK_REASONS=${reasons.join(',')||'NONE'}`);console.log('PAPER_SAMPLE_QUOTA_BLOCKER=REMOVED_FOR_MICRO_LIVE');console.log('KNOWN_FAILURES_REMAIN_FAIL_CLOSED=TRUE');
NODE

chown github-runner:meme-alpha-deploy src/micro-live-gate.js
chmod 664 src/micro-live-gate.js
node --check src/micro-live-gate.js

# Stage the single root activation entry point. It never contains or prints a private key.
mkdir -p "$APP/ops/meme-alpha"
chmod 2775 "$APP/ops" "$APP/ops/meme-alpha" 2>/dev/null || true
install -m 0755 "$SCRIPT_DIR/v240-root-go-live.sh" "$APP/ops/meme-alpha/v240-root-go-live.sh"
chown github-runner:meme-alpha-deploy "$APP/ops/meme-alpha/v240-root-go-live.sh"

sudo -n /bin/systemctl restart meme-alpha-paper.service
# Do not force extra test cycles. Wait only for the normal service loop to emit the new gate status.
ok=0
for _ in $(seq 1 30); do
  sleep 4
  if [ -f "$R/micro-live-gate.json" ] && node --input-type=module - <<'NODE'
import fs from'node:fs';const x=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/micro-live-gate.json','utf8'));process.exit(x.version==='2.4.0'?0:1)
NODE
  then ok=1; break; fi
done
[ "$ok" -eq 1 ] || { echo ABORT_GATE_STATUS_TIMEOUT; exit 1; }

node --input-type=module - <<'NODE'
import fs from'node:fs';const R='/opt/meme-alpha/app/runtime-status';const x=JSON.parse(fs.readFileSync(`${R}/micro-live-gate.json`,'utf8'));const s=JSON.parse(fs.readFileSync(`${R}/signal-snapshot.json`,'utf8'));console.log(`GATE_VERSION=${x.version}`);console.log(`ANALYSIS_MODE=${x.analysisMode}`);console.log(`EXECUTION_MODE=${x.executionMode}`);console.log(`MICRO_LIVE_ALLOWED=${x.allowed}`);console.log(`VALIDATION=${x.validationStatus} COMPLETED=${x.validationCompletedLifecycles} EVIDENCE_READY=${x.evidenceReady}`);console.log(`STRESS=${x.stressStatus} FAIL=${x.stressFail}`);console.log(`SOURCE=${s.sourceHealth?.status} SOURCES=${s.sourceHealth?.successfulSources} CACHE=${s.sourceHealth?.usingCache}`);console.log(`BLOCK_REASONS=${(x.reasons||[]).join(',')||'NONE'}`);if(x.version!=='2.4.0'||x.executionMode!=='DISABLED'||x.allowed!==false)throw new Error('PRE_ACTIVATION_MUST_REMAIN_LOCKED');if((x.reasons||[]).some(r=>r.startsWith('VALIDATION_LIFECYCLES_')||r==='STRESS_REPORT_MISSING'))throw new Error('OLD_SAMPLE_BLOCKER_STILL_PRESENT');console.log('V240_EVIDENCE_NONBLOCKING_GATE=PASS');
NODE

if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi

echo RUNNER_ISOLATION=PASS
echo ROOT_ACTIVATION_SCRIPT=STAGED
echo WALLET_CREATED_BY_RUNNER=FALSE
echo NETWORK_EXECUTION_PERFORMED=FALSE
echo NO_MORE_PAPER_COUNT_WAIT_FOR_MICRO_LIVE=TRUE
echo SCALE_20_LIFECYCLE_EVIDENCE_GATE=RETAINED
echo V240_FAST_LIVE_READY_PASS
echo "BACKUP=$B"
