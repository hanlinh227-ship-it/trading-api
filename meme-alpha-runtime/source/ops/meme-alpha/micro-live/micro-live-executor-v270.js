import fs from 'node:fs';
import net from 'node:net';

const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/micro-live';
const GATE=`${APP}/runtime-status/micro-live-gate.json`;
const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;
const POLICY='/etc/meme-alpha/micro-live-policy.json';
const SOCK='/run/meme-alpha-signer/signer.sock';
const WSOL='So11111111111111111111111111111111111111112';

const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const statePath=`${DATA}/state.json`,eventsPath=`${DATA}/events.jsonl`;
const atomic=(p,x)=>{fs.mkdirSync(DATA,{recursive:true});const t=p+'.tmp';fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p)};
const event=x=>{fs.mkdirSync(DATA,{recursive:true});fs.appendFileSync(eventsPath,JSON.stringify({timestamp:new Date().toISOString(),...x})+'\n')};
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;

function rootPolicy(){
  const st=fs.statSync(POLICY);
  if(st.uid!==0 || (st.mode&0o777)!==0o640) throw new Error('POLICY_CONTROL_INVALID');
  const p=read(POLICY,null);if(!p)throw new Error('POLICY_MISSING');
  const reserve=n(p.reserveLamports),minOrder=n(p.minOrderLamports),buyImpact=n(p.maxBuyPriceImpactPct),sellImpact=n(p.maxSellPriceImpactPct);
  const probe=n(p.probeUtilizationPct),confirmed=n(p.confirmedUtilizationPct),strong=n(p.strongUtilizationPct),max=n(p.maxUtilizationPct),flow=n(p.externalFlowThresholdLamports),addSec=n(p.minAddIntervalSec);
  if(!Number.isInteger(reserve)||reserve<10_000_000)throw new Error('POLICY_RESERVE_INVALID');
  if(!Number.isInteger(minOrder)||minOrder<1_000_000||minOrder>50_000_000)throw new Error('POLICY_MIN_ORDER_INVALID');
  if(!(probe>=10&&probe<=25&&confirmed>=probe&&confirmed<=45&&strong>=confirmed&&strong<=75&&max>=strong&&max<=95))throw new Error('POLICY_UTILIZATION_INVALID');
  if(!(buyImpact>0&&buyImpact<=1.25&&sellImpact>=buyImpact&&sellImpact<=10))throw new Error('POLICY_IMPACT_INVALID');
  if(!Number.isInteger(flow)||flow<100_000||flow>2_000_000)throw new Error('POLICY_FLOW_INVALID');
  if(!Number.isFinite(addSec)||addSec<15||addSec>600)throw new Error('POLICY_ADD_INTERVAL_INVALID');
  return {...p,reserveLamports:reserve,minOrderLamports:minOrder,probeUtilizationPct:probe,confirmedUtilizationPct:confirmed,strongUtilizationPct:strong,maxUtilizationPct:max,maxBuyPriceImpactPct:buyImpact,maxSellPriceImpactPct:sellImpact,externalFlowThresholdLamports:flow,minAddIntervalSec:addSec};
}

async function signer(req){return await new Promise(resolve=>{const s=net.createConnection(SOCK);let d='',done=false;const fin=x=>{if(done)return;done=true;try{s.destroy()}catch{}resolve(x)};s.setTimeout(5000);s.on('connect',()=>s.write(JSON.stringify(req)+'\n'));s.on('data',b=>{d+=b.toString();if(d.includes('\n')){try{fin(JSON.parse(d.split('\n')[0]))}catch{fin({ok:false,error:'BAD_SIGNER_JSON'})}}});s.on('timeout',()=>fin({ok:false,error:'SIGNER_TIMEOUT'}));s.on('error',e=>fin({ok:false,error:e.code||e.message}))})}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'content-type':'application/json','accept':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});const txt=await r.text();let j;try{j=JSON.parse(txt)}catch{j={raw:txt}};if(!r.ok)throw new Error(`HTTP_${r.status}`);return j}
async function rpc(method,params){const cfg=read(`${APP}/config/runtime.json`);const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(10000)});const j=await r.json();if(j.error)throw new Error(`RPC_${j.error.code}`);return j.result}
async function solBalance(pub){return Number((await rpc('getBalance',[pub,{commitment:'confirmed'}])).value)}
async function tokenBalance(pub,mint){const r=await rpc('getTokenAccountsByOwner',[pub,{mint},{encoding:'jsonParsed',commitment:'confirmed'}]);return (r.value||[]).reduce((a,x)=>a+BigInt(x.account?.data?.parsed?.info?.tokenAmount?.amount||'0'),0n)}
async function confirm(sig){for(let i=0;i<30;i++){const r=await rpc('getSignatureStatuses',[[sig],{searchTransactionHistory:true}]);const x=r.value?.[0];if(x?.err)throw new Error('CHAIN_TX_ERROR');if(['confirmed','finalized'].includes(x?.confirmationStatus))return;await sleep(1000)}throw new Error('CHAIN_CONFIRM_TIMEOUT')}
function signature(j){return j?.signature||j?.txid||j?.transactionSignature||j?.data?.signature||null}
async function executeOrder(o){const cfg=read(`${APP}/config/runtime.json`);const j=await post(`${String(cfg.jupiter).replace(/\/$/,'')}/swap/v2/execute`,{signedTransaction:o.signedTransaction,requestId:o.requestId});const sig=signature(j);if(!sig)throw new Error('EXECUTE_NO_SIGNATURE');await confirm(sig);return sig}

function candidates(){return read(SIGNAL,{candidates:[]}).candidates||[]}
function candidate(mint){return candidates().find(x=>x.mint===mint)}
function hardRejectEmpty(v){return Array.isArray(v)?v.length===0:!v}
function impact(c){return Math.abs(n(c?.sellPriceImpactPct??c?.sellImpactPct??c?.priceImpactPct,99))}
function coreSafe(c){return !!c&&c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&!c.token2022&&c.sellRoute===true&&hardRejectEmpty(c.hardReject)&&n(c.liquidityUsd)>=50_000&&impact(c)<=1.25}
function trendEntryEligible(c){
  if(!coreSafe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.score)<82||n(c.consecutiveEligible)<2)return false;
  const chg=n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,-999),slope=n(c.scoreSlopeLast2,-999);
  return chg>=0.30&&chg<=18&&net>=3&&avg>=3&&slope>=0&&c.liquidityStableLast2===true;
}
function holdSafe(c){
  if(!coreSafe(c))return false;
  if(n(c.score)<70)return false;
  if(n(c.priceChange5m,-999)<=-5)return false;
  if(n(c.netBuyers5m,0)<=-8)return false;
  return true;
}
function tier(c,p){
  if(!trendEntryEligible(c))return {name:'NONE',pct:0};
  const score=n(c.score),con=n(c.consecutiveEligible),net=n(c.netBuyers5m),avg=n(c.avgNetBuyersLast2),slope=n(c.scoreSlopeLast2),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m);
  if(con>=8&&score>=93&&net>=12&&avg>=8&&slope>=0&&liq>=250_000&&imp<=0.50&&chg>=0.50&&chg<=10)return{name:'MAX',pct:p.maxUtilizationPct};
  if(con>=6&&score>=90&&net>=8&&avg>=6&&slope>=0&&liq>=150_000&&imp<=0.80&&chg>=0.40&&chg<=12)return{name:'STRONG',pct:p.strongUtilizationPct};
  if(con>=4&&score>=86&&net>=5&&avg>=5&&slope>=0&&liq>=100_000&&chg>=0.30&&chg<=14)return{name:'CONFIRMED',pct:p.confirmedUtilizationPct};
  return{name:'PROBE',pct:p.probeUtilizationPct};
}
function rank(c){return n(c.score)*100+n(c.netBuyers5m)*2+n(c.avgNetBuyersLast2)+n(c.organicRatio5m)*30-Math.max(0,n(c.priceChange5m)-10)*10}
function bestCandidate(p){return candidates().filter(trendEntryEligible).sort((a,b)=>{const ta=tier(a,p).pct,tb=tier(b,p).pct;return tb-ta||rank(b)-rank(a)})[0]||null}

function normalizeState(st){
  if(!st||typeof st!=='object')st={};
  st.version='2.7.0';st.closed=n(st.closed);st.position=st.position||null;
  if(st.position){
    if(!Number.isFinite(Number(st.position.costBasisLamports)))st.position.costBasisLamports=n(st.position.entrySolLamports);
    if(!Number.isFinite(Number(st.position.targetUtilizationPct)))st.position.targetUtilizationPct=0;
    if(!Number.isFinite(Number(st.position.addCount)))st.position.addCount=0;
    if(!st.position.lastAddAt)st.position.lastAddAt=st.position.openedAt||null;
  }
  return st;
}
function ensureCapital(st){if(!st.capital||typeof st.capital!=='object')st.capital={lastObservedSolLamports:null,depositsLamports:0,withdrawalsLamports:0,realizedTradingPnlLamports:0,lastExternalFlowAt:null};return st.capital}
function observeBalance(st,current,threshold,{suppress=false}={}){
  const cap=ensureCapital(st),prev=Number(cap.lastObservedSolLamports);
  if(Number.isFinite(prev)&&prev>=0&&!suppress){const diff=current-prev;if(Math.abs(diff)>=threshold){if(diff>0){cap.depositsLamports=n(cap.depositsLamports)+diff;event({type:'CAPITAL_DEPOSIT_DETECTED',lamports:diff,sol:diff/1e9})}else{cap.withdrawalsLamports=n(cap.withdrawalsLamports)+(-diff);event({type:'CAPITAL_WITHDRAWAL_DETECTED',lamports:-diff,sol:(-diff)/1e9})}cap.lastExternalFlowAt=new Date().toISOString()}}
  cap.lastObservedSolLamports=current;cap.netExternalFlowLamports=n(cap.depositsLamports)-n(cap.withdrawalsLamports);
}
function targetPlan(solBalanceLamports,position,targetPct,p){
  const invested=Math.max(0,n(position?.costBasisLamports));
  const capitalBase=Math.max(0,solBalanceLamports+invested);
  const targetInvested=Math.floor(capitalBase*targetPct/100);
  const available=Math.max(0,solBalanceLamports-p.reserveLamports);
  const amount=Math.min(Math.max(0,targetInvested-invested),available);
  return {capitalBaseLamports:capitalBase,investedLamports:invested,targetInvestedLamports:targetInvested,amountLamports:Math.floor(amount),targetUtilizationPct:targetPct,reserveLamports:p.reserveLamports};
}

async function placeBuy(st,c,targetTier,isAdd=false){
  const p=rootPolicy(),h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.signingEnabled||!h.walletLoaded)throw new Error('SIGNER_NOT_ARMED');
  const beforeSol=await solBalance(h.publicKey),existing=isAdd?st.position:null,plan=targetPlan(beforeSol,existing,targetTier.pct,p);
  if(plan.amountLamports<p.minOrderLamports)return {placed:false,reason:'TARGET_ALREADY_SATISFIED_OR_ORDER_TOO_SMALL',plan};
  const beforeTok=await tokenBalance(h.publicKey,c.mint),o=await signer({op:'order',inputMint:WSOL,outputMint:c.mint,amount:String(plan.amountLamports),maxPriceImpactPct:p.maxBuyPriceImpactPct});
  if(!o.ok)throw new Error(`SIGNER_${o.error}`);if(Math.abs(n(o.priceImpactPct,99))>p.maxBuyPriceImpactPct)throw new Error('ORDER_IMPACT_GUARD');
  const sig=await executeOrder(o),afterSol=await solBalance(h.publicKey),afterTok=await tokenBalance(h.publicKey,c.mint),delta=afterTok-beforeTok;if(delta<=0n)throw new Error('BUY_TOKEN_DELTA_ZERO');
  const spent=Math.max(0,beforeSol-afterSol);if(spent>plan.amountLamports+2_000_000)throw new Error('POST_FILL_SPEND_GUARD');
  if(isAdd){st.position.tokenRaw=(BigInt(st.position.tokenRaw||'0')+delta).toString();st.position.costBasisLamports=n(st.position.costBasisLamports)+spent;st.position.entrySolLamports=st.position.costBasisLamports;st.position.addCount=n(st.position.addCount)+1;st.position.lastAddAt=new Date().toISOString();st.position.targetUtilizationPct=targetTier.pct;st.position.tier=targetTier.name;st.position.lastAddSignature=sig;st.position.walletAfterSolLamports=afterSol;event({type:'MICRO_SCALE_IN',mint:c.mint,symbol:c.symbol,tier:targetTier.name,targetUtilizationPct:targetTier.pct,spentLamports:spent,spentSol:spent/1e9,costBasisLamports:st.position.costBasisLamports,signature:sig})}
  else{st.position={mint:c.mint,symbol:c.symbol,tokenRaw:delta.toString(),costBasisLamports:spent,entrySolLamports:spent,entrySignature:sig,openedAt:new Date().toISOString(),lastAddAt:new Date().toISOString(),addCount:0,targetUtilizationPct:targetTier.pct,tier:targetTier.name,walletBeforeSolLamports:beforeSol,walletAfterSolLamports:afterSol};event({type:'MICRO_BUY',mint:c.mint,symbol:c.symbol,tier:targetTier.name,targetUtilizationPct:targetTier.pct,spentLamports:spent,spentSol:spent/1e9,signature:sig})}
  observeBalance(st,afterSol,p.externalFlowThresholdLamports,{suppress:true});atomic(statePath,st);return{placed:true,plan,spent,signature:sig};
}

async function sell(st,reason){
  const p=rootPolicy(),h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)throw new Error('SIGNER_WALLET_UNAVAILABLE');const pos=st.position,m=pos.mint,beforeTok=await tokenBalance(h.publicKey,m),beforeSol=await solBalance(h.publicKey),amount=beforeTok>0n?beforeTok:BigInt(pos.tokenRaw||0);
  if(amount<=0n){event({type:'MICRO_POSITION_CLEARED_NO_TOKEN',reason,mint:m});st.position=null;atomic(statePath,st);return}
  const o=await signer({op:'order',inputMint:m,outputMint:WSOL,amount:amount.toString(),maxPriceImpactPct:p.maxSellPriceImpactPct});if(!o.ok)throw new Error(`SIGNER_${o.error}`);
  const sig=await executeOrder(o),afterTok=await tokenBalance(h.publicKey,m),afterSol=await solBalance(h.publicKey);if(afterTok>=beforeTok)throw new Error('SELL_TOKEN_DELTA_ZERO');
  const received=Math.max(0,afterSol-beforeSol),cost=n(pos.costBasisLamports||pos.entrySolLamports),pnl=received-cost,cap=ensureCapital(st);cap.realizedTradingPnlLamports=n(cap.realizedTradingPnlLamports)+pnl;observeBalance(st,afterSol,p.externalFlowThresholdLamports,{suppress:true});
  event({type:'MICRO_SELL',mint:m,symbol:pos.symbol,reason,signature:sig,tokenRawSold:(beforeTok-afterTok).toString(),solLamportsReceived:received,costBasisLamports:cost,pnlLamports:pnl,pnlSol:pnl/1e9,realizedTradingPnlLamports:cap.realizedTradingPnlLamports});st.closed=n(st.closed)+1;st.position=null;atomic(statePath,st);
}

async function observeCapital(st){const h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)return;const p=rootPolicy(),bal=await solBalance(h.publicKey);observeBalance(st,bal,p.externalFlowThresholdLamports);atomic(statePath,st)}

async function tick(){
  const gate=read(GATE,{allowed:false}),st=normalizeState(read(statePath,{})),p=rootPolicy();
  if(st.position){
    const c=candidate(st.position.mint);
    if(!gate.allowed){await sell(st,'GATE_CLOSED');return{action:'SELL',reason:'GATE_CLOSED'}}
    if(!holdSafe(c)){await sell(st,'SAFETY_OR_TREND_COLLAPSE');return{action:'SELL',reason:'SAFETY_OR_TREND_COLLAPSE'}}
    const t=tier(c,p),last=Date.parse(st.position.lastAddAt||st.position.openedAt||0),addAge=(Date.now()-last)/1000;
    if(t.pct>0&&addAge>=p.minAddIntervalSec){const r=await placeBuy(st,c,t,true);if(r.placed)return{action:'ADD',reason:t.name}}
    await observeCapital(st);return{action:'HOLD',reason:t.name||'SAFE'};
  }
  if(!gate.allowed){await observeCapital(st);return{action:'WAIT',reason:'GATE_CLOSED'}}
  const c=bestCandidate(p);if(!c){await observeCapital(st);return{action:'WAIT',reason:'NO_TREND_QUALIFIED_CANDIDATE'}}
  const t=tier(c,p),r=await placeBuy(st,c,t,false);if(!r.placed){await observeCapital(st);return{action:'WAIT',reason:r.reason}}
  return{action:'BUY',reason:t.name,symbol:c.symbol};
}

async function main(){fs.mkdirSync(DATA,{recursive:true});console.log('MICRO_LIVE_EXECUTOR_V270_FULL_CAPITAL=STARTED');while(true){try{const d=await tick();console.log(`${new Date().toISOString()} ACTION=${d.action} REASON=${d.reason||''} SYMBOL=${d.symbol||''}`)}catch(e){event({type:'EXECUTOR_ERROR',error:String(e.message||e).slice(0,240)});console.error('EXECUTOR_ERROR',e.message);await sleep(15000)}await sleep(5000)}}

if(process.argv.includes('--self-test')){
  const p={reserveLamports:10_000_000,minOrderLamports:10_000_000,probeUtilizationPct:15,confirmedUtilizationPct:35,strongUtilizationPct:65,maxUtilizationPct:94,maxBuyPriceImpactPct:1.25,maxSellPriceImpactPct:8,externalFlowThresholdLamports:500_000,minAddIntervalSec:30};
  const c={universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',decision:'PROBE_CANDIDATE',token2022:false,sellRoute:true,hardReject:[],score:94,liquidityUsd:300000,sellPriceImpactPct:.3,consecutiveEligible:8,priceChange5m:2.5,netBuyers5m:20,avgNetBuyersLast2:15,scoreSlopeLast2:2,liquidityStableLast2:true,organicRatio5m:.3};
  if(!trendEntryEligible(c)||tier(c,p).pct!==94||trendEntryEligible({...c,priceChange5m:25})||holdSafe({...c,score:60}))throw new Error('TREND_SELFTEST');
  const a=targetPlan(714_000_000,null,15,p);if(a.amountLamports!==107_100_000)throw new Error('PROBE_PLAN');
  const b=targetPlan(606_900_000,{costBasisLamports:107_100_000},35,p);if(b.amountLamports!==142_800_000)throw new Error('CONFIRMED_PLAN');
  const z=targetPlan(42_840_000,{costBasisLamports:671_160_000},94,p);if(z.amountLamports!==0)throw new Error('MAX_PLAN');
  console.log('MICRO_EXECUTOR_V270_SELF_TEST=PASS');console.log('STAGED_UTILIZATION=15_35_65_94');console.log('ABSOLUTE_RESERVE_SOL=0.010');console.log('MIN_REAL_ORDER_SOL=0.010');console.log('EXTERNAL_DEPOSIT_WITHDRAWAL_AWARE=TRUE');console.log('NETWORK_EXECUTION=NOT_CALLED');
}else if(import.meta.url===`file://${process.argv[1]}`)main();
