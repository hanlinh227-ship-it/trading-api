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
