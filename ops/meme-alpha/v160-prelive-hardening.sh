#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v1.6 PRE-LIVE HARDENING ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs'; const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8')); if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER'); console.log('MODE=PAPER'); console.log('LIVE_EXECUTION=DISABLED');
NODE

mkdir -p runtime-status code-backups
B="code-backups/v160-$(date -u +%Y%m%d-%H%M%S)"; mkdir -p "$B"; cp -a src/universe.js src/validation.js src/micro-live-gate.js package.json "$B"/ 2>/dev/null || true

cat > src/universe.js <<'NODE'
import fs from 'node:fs';
const FILE='/var/lib/meme-alpha/data/paper/scanner-latest.json';
const OUT='/opt/meme-alpha/app/runtime-status/universe.json';
const CFG='/opt/meme-alpha/app/config/runtime.json';
if(!fs.existsSync(FILE)) throw new Error('SCANNER_STATE_MISSING');
const scan=JSON.parse(fs.readFileSync(FILE,'utf8')); const cfg=JSON.parse(fs.readFileSync(CFG,'utf8'));
const uniq=x=>[...new Set(x)];
const NON_MEME_SYMBOLS=new Set(['SOL','WSOL','USDC','USDT','USD1','PYUSD','USDS','DAI','PYTH','HNT','MOBILE','TRX','CBBTC','WBTC','JUPUSD','USDUC','JITOSOL','MSOL','BSOL','STSOL','JUPSOL','JSOL','HSOL','INF','JUP','JTO','RAY','ORCA','DRIFT','MNDE','KMNO','RENDER','RNDR','TNSR','IO','W','WORMHOLE']);
const NON_MEME_MINTS=new Set(['So11111111111111111111111111111111111111112','J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn','EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v']);
const NON_MEME_NAMES=[/\bwrapped\s+(sol|bitcoin|btc)\b/i,/\bcoinbase\s+wrapped\b/i,/\busd\s+coin\b/i,/\btether\b/i,/\bliquid\s+stak/i,/\bstaked\s+sol\b/i,/\bpyth\s+network\b/i,/\bhelium\b/i,/\bwormhole\b/i,/\bjupiter\s+(exchange|governance)\b/i,/\braydium\b/i,/\borca\s+protocol\b/i,/\bdrift\s+protocol\b/i];
const MEME_TERMS=/\b(meme|memecoin|doge|shib|pepe|bonk|wif|cat|kitty|kitten|dog|doggo|frog|goat|monkey|ape|pnut|peanut|popcat|chillguy|fart|moo|pengu|pudgy|wojak|mog|brett|floki|inu|hamster|capy|hippo|sigma|gigachad|chad)\b/i;
function classify(c){
 const symbol=String(c.symbol||'').trim().toUpperCase(); const mint=String(c.mint||'').trim(); const name=String(c.name||c.tokenName||c.metadata?.name||'').trim(); const text=`${symbol} ${name}`;
 const reasons=[]; if(NON_MEME_MINTS.has(mint)) reasons.push('CANONICAL_NON_MEME_MINT'); if(NON_MEME_SYMBOLS.has(symbol)) reasons.push('KNOWN_NON_MEME_SYMBOL'); if(name&&NON_MEME_NAMES.some(r=>r.test(name))) reasons.push('KNOWN_NON_MEME_NAME');
 if(reasons.length) return {universeClass:'NON_MEME',universeConfidence:'HIGH',reasons};
 const sourceCount=new Set(c.sources||[]).size; const organic=Number(c.organicRatio5m||0); const liq=Number(c.liquidityUsd||0); const launchpadPump=mint.toLowerCase().endsWith('pump'); const memeText=MEME_TERMS.test(text);
 if(launchpadPump) return {universeClass:'MEME_CONFIRMED',universeConfidence:'HIGH',reasons:['PUMPFUN_MINT_SUFFIX']};
 if(memeText&&sourceCount>=3&&organic>=0.35&&liq>=Math.max(50000,Number(cfg.minLiquidityUsd||25000))) return {universeClass:'MEME_CONFIRMED',universeConfidence:'MEDIUM',reasons:['MEME_SEMANTIC_SIGNAL','MULTISOURCE_ORGANIC_CONFIRMATION']};
 if(memeText&&sourceCount>=2&&organic>=0.15&&liq>=Number(cfg.minLiquidityUsd||25000)) return {universeClass:'MEME_PROBABLE',universeConfidence:'MEDIUM',reasons:['MEME_SEMANTIC_SIGNAL','ORGANIC_FLOW_SUPPORT']};
 return {universeClass:'UNCLASSIFIED',universeConfidence:'LOW',reasons:['POSITIVE_MEME_EVIDENCE_INSUFFICIENT']};
}
let nonMeme=0,confirmed=0,probable=0,unclassified=0;
for(const c of scan.candidates||[]){ const u=classify(c); c.universeClass=u.universeClass; c.universeConfidence=u.universeConfidence; c.universeReasons=u.reasons;
 if(u.universeClass==='NON_MEME'){nonMeme++;c.decision='IGNORE';c.hardReject=uniq([...(c.hardReject||[]),'NON_MEME_UNIVERSE']);}
 else if(u.universeClass==='UNCLASSIFIED'){unclassified++;c.decision='IGNORE';c.hardReject=uniq([...(c.hardReject||[]),'MEME_EVIDENCE_INSUFFICIENT']);}
 else if(u.universeClass==='MEME_CONFIRMED') confirmed++; else probable++;
 c.reasons=uniq([...(c.reasons||[]),...u.reasons]);
}
scan.universe={version:'1.6',filteredAt:new Date().toISOString(),policy:'POSITIVE_MEME_EVIDENCE_FAIL_CLOSED',memeConfirmed:confirmed,memeProbable:probable,nonMemeBlocked:nonMeme,unclassifiedBlocked:unclassified,unknownEntryEligible:false};
const tmp=`${FILE}.tmp-${process.pid}`; fs.writeFileSync(tmp,JSON.stringify(scan,null,2)); fs.renameSync(tmp,FILE);
fs.writeFileSync(`${OUT}.tmp`,JSON.stringify(scan.universe,null,2)); fs.renameSync(`${OUT}.tmp`,OUT); try{fs.chmodSync(OUT,0o664)}catch{}
console.log('=== MEME ALPHA UNIVERSE v1.6 ==='); console.log(`MEME_CONFIRMED=${confirmed}`); console.log(`MEME_PROBABLE=${probable}`); console.log(`NON_MEME_BLOCKED=${nonMeme}`); console.log(`UNCLASSIFIED_BLOCKED=${unclassified}`); console.log('UNKNOWN_ENTRY_ELIGIBLE=false'); console.log('UNIVERSE_STATUS=PASS');
NODE

cat > src/validation.js <<'NODE'
import fs from 'node:fs';
const PAPER='/var/lib/meme-alpha/data/paper/state.json', OUT='/var/lib/meme-alpha/data/paper/validation.json', SAFE='/opt/meme-alpha/app/runtime-status/validation.json';
const s=JSON.parse(fs.readFileSync(PAPER,'utf8')); const trades=s.trades||[], open=s.openPositions||[];
const buys=trades.filter(x=>x.type==='PAPER_BUY_PROBE'), sells=trades.filter(x=>x.type==='PAPER_SELL'); const byId=new Map(); const integrity=[];
for(const b of buys){if(!b.positionId) continue; const r=byId.get(b.positionId)||{positionId:b.positionId,mint:b.mint,symbol:b.symbol,openedAt:b.timestamp,buyEvents:0,sellEvents:0,realizedPnlSol:0,exitReasons:[]}; r.buyEvents++; byId.set(b.positionId,r);}
for(const x of sells){if(!x.positionId) continue; const r=byId.get(x.positionId)||{positionId:x.positionId,mint:x.mint,symbol:x.symbol,buyEvents:0,sellEvents:0,realizedPnlSol:0,exitReasons:[]}; r.sellEvents++; r.realizedPnlSol+=Number(x.pnlSol||0); r.lastSellAt=x.timestamp; if(x.reason) r.exitReasons.push(x.reason); byId.set(x.positionId,r);}
const openIds=new Set(open.map(p=>p.id||p.positionId).filter(Boolean));
const lifecycles=[...byId.values()].map(r=>{const closed=!openIds.has(r.positionId)&&r.buyEvents>0; const opened=Date.parse(r.openedAt||0), ended=Date.parse(r.lastSellAt||0); return {...r,closed,realizedPnlSol:Number(r.realizedPnlSol.toFixed(10)),durationSec:closed&&Number.isFinite(opened)&&Number.isFinite(ended)?Math.max(0,(ended-opened)/1000):null};});
for(const r of lifecycles){if(r.buyEvents===0&&r.sellEvents>0) integrity.push(`ORPHAN_SELL_${r.positionId}`); if(r.buyEvents>1) integrity.push(`DUPLICATE_BUY_${r.positionId}`);}
const completed=lifecycles.filter(x=>x.closed), pnls=completed.map(x=>x.realizedPnlSol), wins=pnls.filter(x=>x>0), losses=pnls.filter(x=>x<0), sum=a=>a.reduce((x,y)=>x+y,0), gp=sum(wins), gl=Math.abs(sum(losses));
const equity=Number(s.equitySol||0), start=Number(s.startingEquitySol||1), high=Number(s.highWaterEquitySol||equity), ret=start>0?(equity/start-1)*100:0, dd=high>0?(1-equity/high)*100:0, expectancy=completed.length?sum(pnls)/completed.length:0, pf=gl>0?gp/gl:(gp>0?Infinity:0);
const criteria={minCompletedLifecycles:completed.length>=20,positiveExpectancy:expectancy>0,profitFactorAtLeast1_10:pf>=1.10,currentDrawdownBelow12Pct:dd<12,dataIntegrityClean:integrity.length===0};
let readinessStatus='ACCUMULATING'; if(completed.length>=20) readinessStatus=Object.values(criteria).every(Boolean)?'PASS':'FAIL';
const result={version:'1.6',timestamp:new Date().toISOString(),readinessStatus,readinessCriteria:criteria,startingEquitySol:start,equitySol:equity,equityReturnPct:Number(ret.toFixed(4)),highWaterEquitySol:high,currentDrawdownPct:Number(dd.toFixed(4)),openPositions:open.length,probeEntries:buys.length,realizedSellEvents:sells.length,lifecycleTrades:lifecycles.length,completedLifecycleTrades:completed.length,winningLifecycleTrades:wins.length,losingLifecycleTrades:losses.length,winRatePct:completed.length?Number((wins.length/completed.length*100).toFixed(2)):0,grossProfitSol:Number(gp.toFixed(8)),grossLossSol:Number(gl.toFixed(8)),profitFactor:Number.isFinite(pf)?Number(pf.toFixed(4)):(pf===Infinity?'INF_NO_LOSS_YET':0),expectancyPerLifecycleSol:Number(expectancy.toFixed(8)),legacyBuyEventsWithoutPositionId:buys.filter(x=>!x.positionId).length,legacySellEventsWithoutPositionId:sells.filter(x=>!x.positionId).length,dataIntegrityErrors:integrity,realizedPnlSol:Number(s.realizedPnlSol||0),unrealizedPnlSol:Number(s.unrealizedPnlSol||0),lifecycles};
for(const p of [OUT,SAFE]){const t=`${p}.tmp`;fs.writeFileSync(t,JSON.stringify(result,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}}
console.log('=== MEME ALPHA VALIDATION v1.6 ==='); console.log(`CompletedLifecycles=${completed.length}`); console.log(`Readiness=${readinessStatus}`); console.log(`ProfitFactor=${result.profitFactor}`); console.log(`Expectancy=${result.expectancyPerLifecycleSol}`); console.log(`IntegrityErrors=${integrity.length}`); console.log('LIVE_EXECUTION=DISABLED'); console.log('VALIDATION_STATUS=PASS');
NODE

cat > src/stress-test.js <<'NODE'
import fs from 'node:fs';
const V='/var/lib/meme-alpha/data/paper/validation.json', OUT='/var/lib/meme-alpha/data/paper/stress-test.json', SAFE='/opt/meme-alpha/app/runtime-status/stress-test.json';
const v=JSON.parse(fs.readFileSync(V,'utf8')); const completed=(v.lifecycles||[]).filter(x=>x.closed&&Number.isFinite(Number(x.realizedPnlSol))); const pnls=completed.map(x=>Number(x.realizedPnlSol)); const sum=a=>a.reduce((x,y)=>x+y,0); const sortedWins=pnls.filter(x=>x>0).sort((a,b)=>b-a); const base=sum(pnls);
const removeTop=(k)=>{const drops=new Set(sortedWins.slice(0,k)); let used=0; return sum(pnls.filter(x=>{if(x>0&&used<k&&sortedWins.slice(0,k).includes(x)){used++;return false}return true}));};
const removePct=(pct)=>removeTop(sortedWins.length?Math.max(1,Math.ceil(sortedWins.length*pct)):0);
const stressed=sum(pnls.map(x=>x>0?x*0.75:x*1.25)); const top1=sortedWins[0]||0; const top1Share=Number(v.grossProfitSol)>0?top1/Number(v.grossProfitSol)*100:0;
const metrics={baseNetSol:Number(base.toFixed(8)),removeTop1WinnerNetSol:Number(removeTop(1).toFixed(8)),removeTop1PctWinnersNetSol:Number(removePct(.01).toFixed(8)),removeTop3PctWinnersNetSol:Number(removePct(.03).toFixed(8)),removeTop5PctWinnersNetSol:Number(removePct(.05).toFixed(8)),winnerHaircut25LossWorsen25NetSol:Number(stressed.toFixed(8)),top1WinnerShareGrossProfitPct:Number(top1Share.toFixed(2))};
const checks={min20Lifecycles:completed.length>=20,validationReadinessPass:v.readinessStatus==='PASS',baseNetPositive:base>0,removeTop1WinnerStillPositive:removeTop(1)>0,stressHaircutStillPositive:stressed>0,topWinnerConcentrationAtMost50Pct:top1Share<=50,currentDrawdownBelow12Pct:Number(v.currentDrawdownPct)<12};
let status='INSUFFICIENT_DATA'; let fail=0; if(completed.length>=20){fail=Object.values(checks).filter(x=>!x).length; status=fail===0?'PASS':'FAIL';}
const result={version:'1.6',timestamp:new Date().toISOString(),status,fail,warn:completed.length<20?1:0,completedLifecycles:completed.length,checks,metrics};
for(const p of [OUT,SAFE]){const t=`${p}.tmp`;fs.writeFileSync(t,JSON.stringify(result,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}}
console.log('=== MEME ALPHA STRESS v1.6 ==='); console.log(`STATUS=${status}`); console.log(`COMPLETED=${completed.length}`); console.log(`FAIL=${fail}`); console.log(`BASE_NET=${metrics.baseNetSol}`); console.log(`REMOVE_TOP1_NET=${metrics.removeTop1WinnerNetSol}`); console.log(`STRESSED_NET=${metrics.winnerHaircut25LossWorsen25NetSol}`); console.log('STRESS_STATUS=PASS');
NODE

cat > src/micro-live-gate.js <<'NODE'
import fs from 'node:fs'; import net from 'node:net';
const APP='/opt/meme-alpha/app', DATA='/var/lib/meme-alpha/data/paper', ARM='/etc/meme-alpha/micro-live-armed', SOCK='/run/meme-alpha-signer/signer.sock';
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}}, age=ts=>Number.isFinite(Date.parse(ts))?(Date.now()-Date.parse(ts))/1000:Infinity;
async function signerHealth(){return await new Promise(resolve=>{const s=net.createConnection(SOCK);let d='',done=false;const fin=v=>{if(done)return;done=true;try{s.destroy()}catch{}resolve(v)};s.setTimeout(1200);s.on('connect',()=>s.write('{"op":"health"}\n'));s.on('data',b=>{d+=b;if(d.includes('\n')){try{fin(JSON.parse(d.split('\n')[0]))}catch{fin({ok:false})}}});s.on('timeout',()=>fin({ok:false,error:'TIMEOUT'}));s.on('error',e=>fin({ok:false,error:e.code||e.message}))})}
const runtime=read(`${APP}/config/runtime.json`), validation=read(`${DATA}/validation.json`), stress=read(`${DATA}/stress-test.json`), source=read(`${DATA}/scanner-source-health.json`), risk=read(`${DATA}/risk-state.json`), universe=read(`${APP}/runtime-status/universe.json`), signer=await signerHealth(); const reasons=[];
let armOk=false;try{const st=fs.statSync(ARM),txt=fs.readFileSync(ARM,'utf8').trim();armOk=st.uid===0&&(st.mode&0o777)===0o600&&txt==='ARMED=YES'}catch{}
if(runtime.mode!=='MICRO_LIVE') reasons.push('MODE_NOT_MICRO_LIVE'); if(!armOk) reasons.push('ROOT_ARMING_FILE_ABSENT_OR_INVALID'); if(!(signer?.ok&&signer?.mode==='READY'&&signer?.signingEnabled===true&&signer?.walletLoaded===true)) reasons.push('SIGNER_NOT_READY');
if(!(source?.status==='HEALTHY'&&source?.allowNewEntries===true&&source?.usingCache!==true&&age(source?.checkedAt)<180)) reasons.push('SOURCE_HEALTH_NOT_READY'); if(!(risk?.entryAllowed===true&&age(risk?.timestamp)<120)) reasons.push('RISK_NOT_READY');
const completed=Number(validation?.completedLifecycleTrades||0); if(completed<20) reasons.push(`VALIDATION_LIFECYCLES_${completed}_LT_20`); if(validation?.readinessStatus!=='PASS') reasons.push(`VALIDATION_READINESS_${validation?.readinessStatus||'MISSING'}`); if(stress?.status!=='PASS') reasons.push(`STRESS_${stress?.status||'MISSING'}`); if(!(universe?.version==='1.6'&&universe?.unknownEntryEligible===false)) reasons.push('POSITIVE_MEME_GATE_NOT_PROVEN');
const allowed=reasons.length===0; const out={version:'1.6',timestamp:new Date().toISOString(),allowed,currentMode:runtime.mode||null,armOk,completedLifecycles:completed,validationReadiness:validation?.readinessStatus||null,stressStatus:stress?.status||null,universeVersion:universe?.version||null,sourceHealthy:source?.status==='HEALTHY',riskEntryAllowed:risk?.entryAllowed===true,signer:{ok:!!signer?.ok,mode:signer?.mode||null,signingEnabled:!!signer?.signingEnabled,walletLoaded:!!signer?.walletLoaded},reasons};
for(const p of [`${DATA}/micro-live-gate.json`,`${APP}/runtime-status/micro-live-gate.json`]){const t=`${p}.tmp`;fs.writeFileSync(t,JSON.stringify(out,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}}
console.log('=== MEME ALPHA MICRO LIVE GATE v1.6 ===');console.log(`MICRO_LIVE_ALLOWED=${allowed}`);console.log(`COMPLETED=${completed}`);console.log(`VALIDATION=${out.validationReadiness}`);console.log(`STRESS=${out.stressStatus}`);console.log(`SIGNER=${out.signer.mode}`);console.log(`BLOCK_REASONS=${reasons.join(',')||'NONE'}`);if(runtime.mode==='PAPER'&&allowed)throw new Error('FAIL_OPEN_IN_PAPER');console.log('FAIL_CLOSED_GATE=PASS');
NODE

for f in src/universe.js src/validation.js src/stress-test.js src/micro-live-gate.js; do chown github-runner:meme-alpha-deploy "$f"; chmod 664 "$f"; node --check "$f"; done

node --input-type=module - <<'NODE'
import fs from 'node:fs';const p='package.json',j=JSON.parse(fs.readFileSync(p,'utf8'));j.scripts['stress']='node src/stress-test.js';let c=j.scripts.cycle5;c=c.replace(/\s*&&\s*node src\/stress-test\.js/g,'').replace(/\s*&&\s*node src\/micro-live-gate\.js/g,'');c+=' && node src/stress-test.js && node src/micro-live-gate.js';j.scripts.cycle5=c;fs.writeFileSync(p,JSON.stringify(j,null,2)+'\n');console.log(j.scripts.cycle5);
NODE

sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 110
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null

node --input-type=module - <<'NODE'
import fs from 'node:fs';const R='/opt/meme-alpha/app/runtime-status';for(const n of ['universe.json','validation.json','stress-test.json','micro-live-gate.json']){const p=`${R}/${n}`;if(!fs.existsSync(p))throw new Error(`MISSING_${n}`);const x=JSON.parse(fs.readFileSync(p));console.log(`--- ${n} ---`);console.log(JSON.stringify(x,null,2));}
const g=JSON.parse(fs.readFileSync(`${R}/micro-live-gate.json`));if(g.version!=='1.6'||g.allowed!==false||g.currentMode!=='PAPER')throw new Error('GATE_INVARIANT');const u=JSON.parse(fs.readFileSync(`${R}/universe.json`));if(u.unknownEntryEligible!==false)throw new Error('UNIVERSE_FAIL_OPEN');console.log('V160_PRELIVE_HARDENING_PASS');
NODE

echo 'NO_WALLET_CREATED=TRUE'
echo 'NO_LIVE_ENABLE=TRUE'
echo "BACKUP=$B"
