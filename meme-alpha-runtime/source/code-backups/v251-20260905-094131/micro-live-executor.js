import fs from 'node:fs';
import net from 'node:net';

const APP='/opt/meme-alpha/app';
const PAPER='/var/lib/meme-alpha/data/paper';
const DATA='/var/lib/meme-alpha/data/micro-live';
const GATE=`${APP}/runtime-status/micro-live-gate.json`;
const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;
const POLICY='/etc/meme-alpha/micro-live-policy.json';
const SOCK='/run/meme-alpha-signer/signer.sock';
const WSOL='So11111111111111111111111111111111111111112';

const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const atomic=(p,x)=>{fs.mkdirSync(DATA,{recursive:true});const t=p+'.tmp';fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p)};
const statePath=`${DATA}/state.json`,eventsPath=`${DATA}/events.jsonl`;
const event=x=>{fs.mkdirSync(DATA,{recursive:true});fs.appendFileSync(eventsPath,JSON.stringify({timestamp:new Date().toISOString(),...x})+'\n')};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

function rootPolicy(){
  const st=fs.statSync(POLICY);
  if(st.uid!==0 || (st.mode&0o777)!==0o640) throw new Error('POLICY_CONTROL_INVALID');
  const p=read(POLICY,null); if(!p) throw new Error('POLICY_MISSING');
  const microMax=Number(p.microMaxEntryLamports), microReserve=Number(p.microReserveLamports), scaledReserve=Number(p.scaledReserveLamports), impact=Number(p.maxPriceImpactPct);
  const base=Number(p.baseUtilizationPct), strong=Number(p.strongUtilizationPct), max=Number(p.maxUtilizationPct), flow=Number(p.externalFlowThresholdLamports);
  if(!Number.isInteger(microMax)||microMax<1_000_000||microMax>5_000_000) throw new Error('POLICY_MICRO_ENTRY_INVALID');
  if(!Number.isInteger(microReserve)||microReserve<20_000_000) throw new Error('POLICY_MICRO_RESERVE_INVALID');
  if(!Number.isInteger(scaledReserve)||scaledReserve<10_000_000) throw new Error('POLICY_SCALED_RESERVE_INVALID');
  if(!Number.isFinite(impact)||impact<=0||impact>1.25) throw new Error('POLICY_IMPACT_INVALID');
  if(!(base>=50&&base<=75&&strong>=base&&strong<=85&&max>=strong&&max<=90)) throw new Error('POLICY_UTILIZATION_INVALID');
  if(!Number.isInteger(flow)||flow<100_000||flow>2_000_000) throw new Error('POLICY_FLOW_THRESHOLD_INVALID');
  return {...p,microMaxEntryLamports:microMax,microReserveLamports:microReserve,scaledReserveLamports:scaledReserve,maxPriceImpactPct:impact,baseUtilizationPct:base,strongUtilizationPct:strong,maxUtilizationPct:max,externalFlowThresholdLamports:flow};
}

async function signer(req){return await new Promise(resolve=>{const s=net.createConnection(SOCK);let d='',done=false;const fin=x=>{if(done)return;done=true;try{s.destroy()}catch{}resolve(x)};s.setTimeout(5000);s.on('connect',()=>s.write(JSON.stringify(req)+'\n'));s.on('data',b=>{d+=b.toString();if(d.includes('\n')){try{fin(JSON.parse(d.split('\n')[0]))}catch{fin({ok:false,error:'BAD_SIGNER_JSON'})}}});s.on('timeout',()=>fin({ok:false,error:'SIGNER_TIMEOUT'}));s.on('error',e=>fin({ok:false,error:e.code||e.message}))})}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'content-type':'application/json','accept':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});const txt=await r.text();let j;try{j=JSON.parse(txt)}catch{j={raw:txt}};if(!r.ok)throw new Error(`HTTP_${r.status}`);return j}
async function rpc(method,params){const cfg=read(`${APP}/config/runtime.json`);const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(10000)});const j=await r.json();if(j.error)throw new Error(`RPC_${j.error.code}`);return j.result}
async function solBalance(pub){return Number((await rpc('getBalance',[pub,{commitment:'confirmed'}])).value)}
async function tokenBalance(pub,mint){const r=await rpc('getTokenAccountsByOwner',[pub,{mint},{encoding:'jsonParsed',commitment:'confirmed'}]);return (r.value||[]).reduce((a,x)=>a+BigInt(x.account?.data?.parsed?.info?.tokenAmount?.amount||'0'),0n)}
async function confirm(sig){for(let i=0;i<25;i++){const r=await rpc('getSignatureStatuses',[[sig],{searchTransactionHistory:true}]);const x=r.value?.[0];if(x?.err)throw new Error('CHAIN_TX_ERROR');if(['confirmed','finalized'].includes(x?.confirmationStatus))return;await sleep(1000)}throw new Error('CHAIN_CONFIRM_TIMEOUT')}
function signature(j){return j?.signature||j?.txid||j?.transactionSignature||j?.data?.signature||null}
async function executeOrder(o){const cfg=read(`${APP}/config/runtime.json`);const j=await post(`${String(cfg.jupiter).replace(/\/$/,'')}/swap/v2/execute`,{signedTransaction:o.signedTransaction,requestId:o.requestId});const sig=signature(j);if(!sig)throw new Error('EXECUTE_NO_SIGNATURE');await confirm(sig);return sig}
function candidate(mint){return (read(SIGNAL,{candidates:[]}).candidates||[]).find(x=>x.mint===mint)}
function hardRejectEmpty(v){return Array.isArray(v)?v.length===0:!v}
function eligible(c){if(!c)return false;const impact=Number(c.sellPriceImpactPct??c.sellImpactPct??c.priceImpactPct);return c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&c.decision==='PROBE_CANDIDATE'&&!c.token2022&&c.sellRoute===true&&hardRejectEmpty(c.hardReject)&&Number(c.score)>=82&&Number(c.liquidityUsd)>=50000&&Number.isFinite(impact)&&Math.abs(impact)<=1.25&&Number(c.consecutiveEligible||0)>=2}
function paperOpen(){const s=read(`${PAPER}/state.json`,{openPositions:[]});return Array.isArray(s.openPositions)?s.openPositions:[]}
function pid(p){return p?.positionId||p?.id||null}

function utilizationPct(c,policy){
  const score=Number(c?.score||0),liq=Number(c?.liquidityUsd||0),impact=Math.abs(Number(c?.sellPriceImpactPct??c?.sellImpactPct??c?.priceImpactPct??99));
  if(score>=92&&liq>=250000&&impact<=0.50)return policy.maxUtilizationPct;
  if(score>=88&&liq>=150000&&impact<=0.80)return policy.strongUtilizationPct;
  return policy.baseUtilizationPct;
}
function entryPlan(balance,c,gate,policy){
  if(!gate?.scaleAllowed){
    const amount=Math.min(policy.microMaxEntryLamports,Math.max(0,balance-policy.microReserveLamports));
    return {mode:'MICRO_EVIDENCE',utilizationPct:balance>0?amount/balance*100:0,reserveLamports:policy.microReserveLamports,amountLamports:Math.floor(amount)};
  }
  const pct=utilizationPct(c,policy);
  const byPct=Math.floor(balance*pct/100);
  const byReserve=Math.max(0,balance-policy.scaledReserveLamports);
  const amount=Math.min(byPct,byReserve);
  return {mode:'ADAPTIVE_COMPOUND',utilizationPct:pct,reserveLamports:policy.scaledReserveLamports,amountLamports:Math.floor(amount)};
}
function ensureCapital(st){if(!st.capital||typeof st.capital!=='object')st.capital={lastObservedSolLamports:null,depositsLamports:0,withdrawalsLamports:0,realizedTradingPnlLamports:0,lastExternalFlowAt:null};return st.capital}
function observeBalance(st,current,threshold,{suppress=false}={}){
  const cap=ensureCapital(st),prev=Number(cap.lastObservedSolLamports);
  if(Number.isFinite(prev)&&prev>=0&&!suppress){
    const diff=current-prev;
    if(Math.abs(diff)>=threshold){
      if(diff>0){cap.depositsLamports=Number(cap.depositsLamports||0)+diff;event({type:'CAPITAL_DEPOSIT_DETECTED',lamports:diff,sol:diff/1e9})}
      else{cap.withdrawalsLamports=Number(cap.withdrawalsLamports||0)+(-diff);event({type:'CAPITAL_WITHDRAWAL_DETECTED',lamports:-diff,sol:(-diff)/1e9})}
      cap.lastExternalFlowAt=new Date().toISOString();
    }
  }
  cap.lastObservedSolLamports=current;
  cap.netExternalFlowLamports=Number(cap.depositsLamports||0)-Number(cap.withdrawalsLamports||0);
}

async function buy(st,p,gate){
  const policy=rootPolicy(),h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.signingEnabled||!h.walletLoaded)throw new Error('SIGNER_NOT_ARMED');
  const pub=h.publicKey,beforeSol=await solBalance(pub),c=candidate(p.mint),plan=entryPlan(beforeSol,c,gate,policy);
  if(plan.amountLamports<1_000_000)throw new Error('RESERVE_GUARD');
  const beforeTok=await tokenBalance(pub,p.mint),o=await signer({op:'order',inputMint:WSOL,outputMint:p.mint,amount:String(plan.amountLamports),maxPriceImpactPct:policy.maxPriceImpactPct});if(!o.ok)throw new Error(`SIGNER_${o.error}`);
  if(Number(o.priceImpactPct)>policy.maxPriceImpactPct)throw new Error('ORDER_IMPACT_GUARD');
  const sig=await executeOrder(o),afterSol=await solBalance(pub),afterTok=await tokenBalance(pub,p.mint),delta=afterTok-beforeTok;if(delta<=0n)throw new Error('BUY_TOKEN_DELTA_ZERO');
  const spent=Math.max(0,beforeSol-afterSol);if(spent>plan.amountLamports+2_000_000)throw new Error('POST_FILL_SPEND_GUARD');
  st.position={paperPositionId:pid(p),mint:p.mint,symbol:p.symbol,tokenRaw:delta.toString(),entrySolLamports:spent,entrySignature:sig,openedAt:new Date().toISOString(),capitalMode:plan.mode,targetUtilizationPct:Number(plan.utilizationPct.toFixed(2)),walletBeforeSolLamports:beforeSol,walletAfterSolLamports:afterSol};
  st.lastMirroredPaperPositionId=st.position.paperPositionId;observeBalance(st,afterSol,policy.externalFlowThresholdLamports,{suppress:true});event({type:'MICRO_BUY',...st.position,scaleAllowed:!!gate.scaleAllowed});atomic(statePath,st);
}
async function sell(st,reason){
  const h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)throw new Error('SIGNER_WALLET_UNAVAILABLE');const pub=h.publicKey,m=st.position.mint,beforeTok=await tokenBalance(pub,m),beforeSol=await solBalance(pub),amount=beforeTok>0n?beforeTok:BigInt(st.position.tokenRaw||0);
  if(amount<=0n){event({type:'MICRO_POSITION_CLEARED_NO_TOKEN',reason,mint:m});st.position=null;return atomic(statePath,st)}
  const policy=rootPolicy(),o=await signer({op:'order',inputMint:m,outputMint:WSOL,amount:amount.toString(),maxPriceImpactPct:policy.maxPriceImpactPct});if(!o.ok)throw new Error(`SIGNER_${o.error}`);const sig=await executeOrder(o),afterTok=await tokenBalance(pub,m),afterSol=await solBalance(pub);if(afterTok>=beforeTok)throw new Error('SELL_TOKEN_DELTA_ZERO');
  const received=Math.max(0,afterSol-beforeSol),pnl=received-Number(st.position.entrySolLamports||0),cap=ensureCapital(st);cap.realizedTradingPnlLamports=Number(cap.realizedTradingPnlLamports||0)+pnl;observeBalance(st,afterSol,policy.externalFlowThresholdLamports,{suppress:true});
  event({type:'MICRO_SELL',mint:m,reason,signature:sig,tokenRawSold:(beforeTok-afterTok).toString(),solLamportsReceived:received,pnlLamports:pnl,realizedTradingPnlLamports:cap.realizedTradingPnlLamports});st.closed=(st.closed||0)+1;st.position=null;atomic(statePath,st)
}
export function decide(gate,opens,st){if(st.position){const p=opens.find(x=>pid(x)===st.position.paperPositionId);if(!gate.allowed)return{action:'SELL',reason:'GATE_CLOSED'};if(!p)return{action:'SELL',reason:'PAPER_POSITION_CLOSED'};if(!eligible(candidate(st.position.mint)))return{action:'SELL',reason:'SAFETY_OR_SIGNAL_DEGRADED'};return{action:'HOLD'}}if(!gate.allowed)return{action:'WAIT',reason:'GATE_CLOSED'};const p=opens.find(x=>pid(x)&&pid(x)!==st.lastMirroredPaperPositionId&&eligible(candidate(x.mint)));return p?{action:'BUY',position:p}:{action:'WAIT',reason:'NO_ELIGIBLE_NEW_PAPER_POSITION'}}
async function observeIdleCapital(st){const h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)return;const policy=rootPolicy(),bal=await solBalance(h.publicKey);observeBalance(st,bal,policy.externalFlowThresholdLamports);atomic(statePath,st)}
async function tick(){const gate=read(GATE,{allowed:false}),st=read(statePath,{version:'2.5.0',position:null,closed:0,lastMirroredPaperPositionId:null}),d=decide(gate,paperOpen(),st);if(d.action==='BUY')await buy(st,d.position,gate);else if(d.action==='SELL')await sell(st,d.reason);else await observeIdleCapital(st);return d}
async function main(){fs.mkdirSync(DATA,{recursive:true});console.log('MICRO_LIVE_EXECUTOR_V250=STARTED');while(true){try{const d=await tick();console.log(`${new Date().toISOString()} ACTION=${d.action} REASON=${d.reason||''}`)}catch(e){event({type:'EXECUTOR_ERROR',error:String(e.message||e).slice(0,200)});console.error('EXECUTOR_ERROR',e.message);await sleep(15000)}await sleep(5000)}}
if(process.argv.includes('--self-test')){
  const policy={microMaxEntryLamports:5_000_000,microReserveLamports:20_000_000,scaledReserveLamports:10_000_000,baseUtilizationPct:70,strongUtilizationPct:82,maxUtilizationPct:90};
  const c={score:93,liquidityUsd:300000,sellPriceImpactPct:.3};
  const a=entryPlan(100_000_000,c,{scaleAllowed:false},policy),b=entryPlan(100_000_000,c,{scaleAllowed:true},policy);
  const w=decide({allowed:false},[],{position:null}),s=decide({allowed:false},[],{position:{paperPositionId:'p',mint:'x'}});
  if(w.action!=='WAIT'||s.action!=='SELL'||a.amountLamports!==5_000_000||b.amountLamports!==90_000_000)throw new Error('SELFTEST');
  console.log('MICRO_EXECUTOR_V250_SELF_TEST=PASS');console.log('MICRO_PRE_EVIDENCE_MAX_SOL=0.005');console.log('POST_EVIDENCE_MAX_UTILIZATION_PCT=90');console.log('EXTERNAL_DEPOSIT_WITHDRAWAL_AWARE=TRUE');console.log('NETWORK_EXECUTION=NOT_CALLED');
}else if(import.meta.url===`file://${process.argv[1]}`)main();
