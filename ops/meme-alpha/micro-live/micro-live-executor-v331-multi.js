import fs from 'node:fs';
import net from 'node:net';

const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/micro-live';
const GATE=`${APP}/runtime-status/micro-live-gate.json`;
const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;
const TREND=`${APP}/runtime-status/trend-pulse.json`;
const POLICY='/etc/meme-alpha/micro-live-policy.json';
const SOCK='/run/meme-alpha-signer/signer.sock';
const WSOL='So11111111111111111111111111111111111111112';
const DEFAULT_EXIT_RESERVE_LAMPORTS=5_000_000;
const ENTRY_OVERHEAD_LAMPORTS=3_000_000;
const MULTI_POSITION_CAP_PCT={PROBE:6,CONFIRMED:10,STRONG:15,MAX:20};

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
  const exitReserve=n(p.perPositionExitReserveLamports,DEFAULT_EXIT_RESERVE_LAMPORTS);
  if(!Number.isInteger(reserve)||reserve<10_000_000)throw new Error('POLICY_RESERVE_INVALID');
  if(!Number.isInteger(exitReserve)||exitReserve<2_000_000||exitReserve>20_000_000)throw new Error('POLICY_EXIT_RESERVE_INVALID');
  if(!Number.isInteger(minOrder)||minOrder<1_000_000||minOrder>50_000_000)throw new Error('POLICY_MIN_ORDER_INVALID');
  if(!(probe>=10&&probe<=25&&confirmed>=probe&&confirmed<=45&&strong>=confirmed&&strong<=75&&max>=strong&&max<=95))throw new Error('POLICY_UTILIZATION_INVALID');
  if(!(buyImpact>0&&buyImpact<=1.25&&sellImpact>=buyImpact&&sellImpact<=10))throw new Error('POLICY_IMPACT_INVALID');
  if(!Number.isInteger(flow)||flow<100_000||flow>2_000_000)throw new Error('POLICY_FLOW_INVALID');
  if(!Number.isFinite(addSec)||addSec<15||addSec>600)throw new Error('POLICY_ADD_INTERVAL_INVALID');
  return {...p,reserveLamports:reserve,perPositionExitReserveLamports:exitReserve,minOrderLamports:minOrder,probeUtilizationPct:probe,confirmedUtilizationPct:confirmed,strongUtilizationPct:strong,maxUtilizationPct:max,maxBuyPriceImpactPct:buyImpact,maxSellPriceImpactPct:sellImpact,externalFlowThresholdLamports:flow,minAddIntervalSec:addSec};
}

async function signer(req){return await new Promise(resolve=>{const s=net.createConnection(SOCK);let d='',done=false;const fin=x=>{if(done)return;done=true;try{s.destroy()}catch{}resolve(x)};s.setTimeout(5000);s.on('connect',()=>s.write(JSON.stringify(req)+'\n'));s.on('data',b=>{d+=b.toString();if(d.includes('\n')){try{fin(JSON.parse(d.split('\n')[0]))}catch{fin({ok:false,error:'BAD_SIGNER_JSON'})}}});s.on('timeout',()=>fin({ok:false,error:'SIGNER_TIMEOUT'}));s.on('error',e=>fin({ok:false,error:e.code||e.message}))})}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'content-type':'application/json','accept':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});const txt=await r.text();let j;try{j=JSON.parse(txt)}catch{j={raw:txt}};if(!r.ok)throw new Error(`HTTP_${r.status}`);return j}
async function getJson(url){const r=await fetch(url,{headers:{'accept':'application/json','user-agent':'meme-alpha-v331-multi-position'},signal:AbortSignal.timeout(12000)});const txt=await r.text();let j;try{j=JSON.parse(txt)}catch{j={raw:txt}};if(!r.ok)throw new Error(`HTTP_${r.status}`);return j}
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
function pulseFor(c){if(!c)return null;const t=read(TREND,{}),age=(Date.now()-Date.parse(t.timestamp||0))/1000;if(!Number.isFinite(age)||age<0||age>10)return null;return (t.rows||[]).find(x=>x.mint===c.mint)||null}
function themeStrength(c){const t=read(TREND,{}),age=(Date.now()-Date.parse(t.timestamp||0))/1000,p=pulseFor(c);if(!p||!Number.isFinite(age)||age>10)return 0;return n((t.themes||[]).find(x=>x.narrative===p.narrative)?.strength)}
function opportunityScore(c){const base=n(c.score),p=pulseFor(c);if(!p)return base;let add=0;if(n(p.volumeAcceleration)>=1.45)add+=4;else if(n(p.volumeAcceleration)>=1.10)add+=2;if(n(p.txnAcceleration)>=1.30)add+=3;else if(n(p.txnAcceleration)>=1.05)add+=1;if(n(p.buySellRatio)>=1.25)add+=2;if(themeStrength(c)>=60)add+=2;if(n(p.pulseScore)>=70)add+=1;if(p.status==='EXHAUSTED')add-=8;if(p.promotionFlag===true&&n(p.pulseScore)<65)add-=3;return Math.max(base-8,Math.min(base+12,base+add))}
function opportunityLane(c){const score=opportunityScore(c),base=n(c.score),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net);if(base<58)return false;const standard=score>=72;const liquid=score>=66&&liq>=500000&&net>=1&&imp<=0.80;const flow=score>=62&&liq>=100000&&net>=5&&avg>=3&&chg>=0.20&&imp<=0.80;return standard||liquid||flow}
function trendEntryEligible(c){if(!coreSafe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.consecutiveEligible)<1)return false;const p=pulseFor(c),chg=p?n(p.price5m,-999):n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net),slope=n(c.scoreSlopeLast2,0),stable=c.liquidityStableLast2!==false;const pulseFlow=!!p&&p.status!=='EXHAUSTED'&&n(p.pulseScore)>=55&&n(p.volumeAcceleration)>=1.05&&n(p.txnAcceleration)>=1.0&&n(p.buySellRatio)>=1.10&&n(p.tx5)>=4;const buyerFlow=net>=2&&avg>=1.5;const fastFlow=net>=1&&pulseFlow;const momentumFloor=pulseFlow?0.05:0.15;return chg>=momentumFloor&&chg<=15&&(buyerFlow||fastFlow)&&slope>=-4&&stable&&opportunityLane(c)}
function hardSafetyBroken(c){if(!c)return false;if((Array.isArray(c.hardReject)&&c.hardReject.length>0)||c.sellRoute===false||c.token2022===true)return true;if(c.securityDecision==='BLOCK'||c.holderClusterDecision==='BLOCK')return true;if(n(c.liquidityUsd,999999)<20_000)return true;return false}
function severeTrendBreak(c){if(!c)return false;const p=pulseFor(c),chg=p?n(p.price5m,n(c.priceChange5m)):n(c.priceChange5m),net=n(c.netBuyers5m),bs=p?n(p.buySellRatio,1):n(c.buySellRatio5m,1);return chg<=-13||net<=-30||(chg<=-9&&bs<0.55)}
function softTrendWeak(c){if(!c)return false;const p=pulseFor(c),chg=p?n(p.price5m,n(c.priceChange5m)):n(c.priceChange5m),net=n(c.netBuyers5m),bs=p?n(p.buySellRatio,1):n(c.buySellRatio5m,1),pulse=n(p?.pulseScore,50);return n(c.score)<52||chg<=-7||net<=-12||(p?.status==='EXHAUSTED'&&pulse<50&&bs<0.85)}
function holdSafe(c){return !hardSafetyBroken(c)&&!severeTrendBreak(c)&&!softTrendWeak(c)}
function profitThresholds(c){const p=pulseFor(c),strong=!!p&&p.status==='BREAKOUT'&&n(p.pulseScore)>=75&&n(p.buySellRatio)>=1.10;return strong?{tp1:30,tp2:70,tp3:130}:{tp1:22,tp2:50,tp3:100}}
function tier(c,p){if(!trendEntryEligible(c))return {name:'NONE',pct:0};const score=n(c.score),con=n(c.consecutiveEligible),net=n(c.netBuyers5m),avg=n(c.avgNetBuyersLast2),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m);const maxQuality=(score>=82&&net>=10&&avg>=7)||(score>=76&&net>=18&&avg>=10);if(con>=5&&maxQuality&&liq>=250000&&imp<=0.50&&chg>=0.50&&chg<=8)return{name:'MAX',pct:p.maxUtilizationPct};const strongQuality=(score>=76&&net>=6&&avg>=4)||(score>=70&&net>=10&&avg>=6);if(con>=3&&strongQuality&&liq>=150000&&imp<=0.80&&chg>=0.30&&chg<=10)return{name:'STRONG',pct:p.strongUtilizationPct};const confirmedQuality=(score>=70&&net>=3&&avg>=2)||(score>=66&&net>=6&&avg>=4);if(con>=2&&confirmedQuality&&liq>=100000&&imp<=1.00&&chg>=0.15&&chg<=12)return{name:'CONFIRMED',pct:p.confirmedUtilizationPct};return{name:'PROBE',pct:p.probeUtilizationPct}}
function multiTier(c,p){const t=tier(c,p);return {...t,pct:t.name==='NONE'?0:Math.min(t.pct,MULTI_POSITION_CAP_PCT[t.name]||6)}}
function rank(c){return n(c.score)*100+n(c.netBuyers5m)*2+n(c.avgNetBuyersLast2)+n(c.organicRatio5m)*30-Math.max(0,n(c.priceChange5m)-10)*10}
function bestCandidate(p,held){return candidates().filter(c=>!held.has(c.mint)&&trendEntryEligible(c)).sort((a,b)=>{const ta=multiTier(a,p).pct,tb=multiTier(b,p).pct;return tb-ta||rank(b)-rank(a)})[0]||null}

function normalizePosition(pos){
  if(!pos||typeof pos!=='object'||!pos.mint)throw new Error('POSITION_STATE_INVALID');
  if(!Number.isFinite(Number(pos.costBasisLamports)))pos.costBasisLamports=n(pos.entrySolLamports);
  if(!Number.isFinite(Number(pos.targetUtilizationPct)))pos.targetUtilizationPct=0;
  if(!Number.isFinite(Number(pos.addCount)))pos.addCount=0;
  if(!pos.lastAddAt)pos.lastAddAt=pos.openedAt||null;
  if(!Number.isFinite(Number(pos.weakExitCount)))pos.weakExitCount=0;
  if(!Number.isFinite(Number(pos.gateClosedCount)))pos.gateClosedCount=0;
  if(!Number.isFinite(Number(pos.peakReturnPct)))pos.peakReturnPct=null;
  if(!Number.isFinite(Number(pos.lastReturnPct)))pos.lastReturnPct=null;
  pos.tp1Done=pos.tp1Done===true;pos.tp2Done=pos.tp2Done===true;pos.tp3Done=pos.tp3Done===true;pos.profitProtectDone=pos.profitProtectDone===true;pos.scaleInLockedAfterProfit=pos.scaleInLockedAfterProfit===true;
  return pos;
}
function normalizeState(st){
  if(!st||typeof st!=='object')st={};
  st.version='3.31.0-multi';st.closed=n(st.closed);
  if(!Array.isArray(st.positions))st.positions=st.position?[st.position]:[];
  else if(st.position){const same=st.positions.find(x=>x?.mint===st.position?.mint);if(!same)throw new Error('LEGACY_POSITION_CONFLICT');}
  delete st.position;
  st.positions=st.positions.map(normalizePosition);
  const mints=new Set();for(const pos of st.positions){if(mints.has(pos.mint))throw new Error('DUPLICATE_LIVE_POSITION_MINT');mints.add(pos.mint)}
  st.manageCursor=Math.max(0,Math.floor(n(st.manageCursor)));
  return st;
}
function ensureCapital(st){if(!st.capital||typeof st.capital!=='object')st.capital={lastObservedSolLamports:null,depositsLamports:0,withdrawalsLamports:0,realizedTradingPnlLamports:0,lastExternalFlowAt:null};return st.capital}
function observeBalance(st,current,threshold,{suppress=false}={}){const cap=ensureCapital(st),prev=Number(cap.lastObservedSolLamports);if(Number.isFinite(prev)&&prev>=0&&!suppress){const diff=current-prev;if(Math.abs(diff)>=threshold){if(diff>0){cap.depositsLamports=n(cap.depositsLamports)+diff;event({type:'CAPITAL_DEPOSIT_DETECTED',lamports:diff,sol:diff/1e9})}else{cap.withdrawalsLamports=n(cap.withdrawalsLamports)+(-diff);event({type:'CAPITAL_WITHDRAWAL_DETECTED',lamports:-diff,sol:(-diff)/1e9})}cap.lastExternalFlowAt=new Date().toISOString()}}cap.lastObservedSolLamports=current;cap.netExternalFlowLamports=n(cap.depositsLamports)-n(cap.withdrawalsLamports)}
function portfolioInvested(st){return (st.positions||[]).reduce((s,x)=>s+Math.max(0,n(x.costBasisLamports||x.entrySolLamports)),0)}
function requiredReserveLamports(p,count){return Math.max(p.reserveLamports,p.reserveLamports+Math.max(0,count)*p.perPositionExitReserveLamports)}
function targetPlan(solBalanceLamports,st,position,targetPct,p,{isNew=false}={}){
  const invested=Math.max(0,n(position?.costBasisLamports));
  const capitalBase=Math.max(0,solBalanceLamports+portfolioInvested(st));
  const targetInvested=Math.floor(capitalBase*targetPct/100);
  const futureCount=st.positions.length+(isNew?1:0);
  const reserve=requiredReserveLamports(p,futureCount);
  const overhead=isNew?ENTRY_OVERHEAD_LAMPORTS:0;
  const available=Math.max(0,solBalanceLamports-reserve-overhead);
  const amount=Math.min(Math.max(0,targetInvested-invested),available);
  return {capitalBaseLamports:capitalBase,investedLamports:invested,targetInvestedLamports:targetInvested,amountLamports:Math.floor(amount),targetUtilizationPct:targetPct,reserveLamports:reserve,entryOverheadLamports:overhead,futurePositionCount:futureCount};
}

async function placeBuy(st,c,targetTier,posIndex=-1){
  const p=rootPolicy(),h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.signingEnabled||!h.walletLoaded)throw new Error('SIGNER_NOT_ARMED');
  const isAdd=posIndex>=0,existing=isAdd?st.positions[posIndex]:null;
  if(!isAdd&&st.positions.some(x=>x.mint===c.mint))return {placed:false,reason:'MINT_ALREADY_HELD'};
  const beforeSol=await solBalance(h.publicKey),plan=targetPlan(beforeSol,st,existing,targetTier.pct,p,{isNew:!isAdd});
  if(plan.amountLamports<p.minOrderLamports)return {placed:false,reason:'RESERVE_OR_TARGET_LIMIT',plan};
  const beforeTok=await tokenBalance(h.publicKey,c.mint),o=await signer({op:'order',inputMint:WSOL,outputMint:c.mint,amount:String(plan.amountLamports),maxPriceImpactPct:p.maxBuyPriceImpactPct});
  if(!o.ok)throw new Error(`SIGNER_${o.error}`);if(Math.abs(n(o.priceImpactPct,99))>p.maxBuyPriceImpactPct)throw new Error('ORDER_IMPACT_GUARD');
  const sig=await executeOrder(o),afterSol=await solBalance(h.publicKey),afterTok=await tokenBalance(h.publicKey,c.mint),delta=afterTok-beforeTok;if(delta<=0n)throw new Error('BUY_TOKEN_DELTA_ZERO');
  const spent=Math.max(0,beforeSol-afterSol);if(spent>plan.amountLamports+ENTRY_OVERHEAD_LAMPORTS)event({type:'POST_FILL_SPEND_OVER_PLAN',mint:c.mint,spentLamports:spent,plannedLamports:plan.amountLamports});
  if(isAdd){const pos=st.positions[posIndex];pos.tokenRaw=(BigInt(pos.tokenRaw||'0')+delta).toString();pos.costBasisLamports=n(pos.costBasisLamports)+spent;pos.entrySolLamports=pos.costBasisLamports;pos.addCount=n(pos.addCount)+1;pos.lastAddAt=new Date().toISOString();pos.targetUtilizationPct=targetTier.pct;pos.tier=targetTier.name;pos.lastAddSignature=sig;pos.walletAfterSolLamports=afterSol;event({type:'MICRO_SCALE_IN',mint:c.mint,symbol:c.symbol,tier:targetTier.name,targetUtilizationPct:targetTier.pct,spentLamports:spent,spentSol:spent/1e9,costBasisLamports:pos.costBasisLamports,signature:sig,openPositions:st.positions.length})}
  else{const pos={mint:c.mint,symbol:c.symbol,tokenRaw:delta.toString(),costBasisLamports:spent,entrySolLamports:spent,entrySignature:sig,openedAt:new Date().toISOString(),lastAddAt:new Date().toISOString(),addCount:0,targetUtilizationPct:targetTier.pct,tier:targetTier.name,walletBeforeSolLamports:beforeSol,walletAfterSolLamports:afterSol,weakExitCount:0,gateClosedCount:0,peakReturnPct:null,lastReturnPct:null,tp1Done:false,tp2Done:false,tp3Done:false,profitProtectDone:false,scaleInLockedAfterProfit:false};st.positions.push(pos);event({type:'MICRO_BUY',mint:c.mint,symbol:c.symbol,tier:targetTier.name,targetUtilizationPct:targetTier.pct,spentLamports:spent,spentSol:spent/1e9,signature:sig,openPositions:st.positions.length,reserveForAllExitsLamports:requiredReserveLamports(p,st.positions.length)})}
  observeBalance(st,afterSol,p.externalFlowThresholdLamports,{suppress:true});
  const reserveNow=requiredReserveLamports(p,st.positions.length);if(afterSol<reserveNow)event({type:'EXIT_RESERVE_MARGIN_LOW',walletSolLamports:afterSol,requiredReserveLamports:reserveNow,openPositions:st.positions.length});
  atomic(statePath,st);return{placed:true,plan,spent,signature:sig};
}

async function previewExitReturn(pos,pub){
  const now=Date.now(),last=Date.parse(pos.lastMarkAt||0);if(Number.isFinite(last)&&now-last<10_000&&Number.isFinite(Number(pos.lastReturnPct)))return Number(pos.lastReturnPct);
  const amount=await tokenBalance(pub,pos.mint);if(amount<=0n)return null;
  const cfg=read(`${APP}/config/runtime.json`),u=new URL(`${String(cfg.jupiter).replace(/\/$/,'')}/swap/v2/order`);u.searchParams.set('inputMint',pos.mint);u.searchParams.set('outputMint',WSOL);u.searchParams.set('amount',amount.toString());u.searchParams.set('taker',pub);
  const q=await getJson(u.toString()),out=n(q.outAmount??q.outputAmount??q.otherAmountThreshold,-1),cost=n(pos.costBasisLamports||pos.entrySolLamports);if(out<=0||cost<=0)throw new Error('EXIT_PREVIEW_INVALID');const ret=(out-cost)/cost*100;pos.lastReturnPct=ret;pos.peakReturnPct=Number.isFinite(Number(pos.peakReturnPct))?Math.max(Number(pos.peakReturnPct),ret):ret;pos.lastMarkAt=new Date().toISOString();pos.lastPreviewOutLamports=out;pos.lastPreviewImpactPct=n(q.priceImpactPct,0);return ret;
}
async function sellFraction(st,index,fraction,reason){
  const p=rootPolicy(),h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)throw new Error('SIGNER_WALLET_UNAVAILABLE');const pos=st.positions[index];if(!pos)throw new Error('POSITION_INDEX_INVALID');const m=pos.mint,beforeTok=await tokenBalance(h.publicKey,m),beforeSol=await solBalance(h.publicKey);
  if(beforeTok<=0n){event({type:'MICRO_POSITION_CLEARED_NO_TOKEN',reason,mint:m});st.positions.splice(index,1);atomic(statePath,st);return{closed:true}}
  const f=Math.max(0.01,Math.min(1,n(fraction,1)));let amount=f>=0.999?beforeTok:(beforeTok*BigInt(Math.max(1,Math.floor(f*1_000_000))))/1_000_000n;if(amount<=0n)amount=beforeTok;
  const o=await signer({op:'order',inputMint:m,outputMint:WSOL,amount:amount.toString(),maxPriceImpactPct:p.maxSellPriceImpactPct});if(!o.ok)throw new Error(`SIGNER_${o.error}`);
  const sig=await executeOrder(o),afterTok=await tokenBalance(h.publicKey,m),afterSol=await solBalance(h.publicKey);if(afterTok>=beforeTok)throw new Error('SELL_TOKEN_DELTA_ZERO');
  const sold=beforeTok-afterTok,received=Math.max(0,afterSol-beforeSol),oldCost=n(pos.costBasisLamports||pos.entrySolLamports),allocatedCost=Math.min(oldCost,Math.round(oldCost*Number(sold)/Number(beforeTok))),pnl=received-allocatedCost,cap=ensureCapital(st);cap.realizedTradingPnlLamports=n(cap.realizedTradingPnlLamports)+pnl;observeBalance(st,afterSol,p.externalFlowThresholdLamports,{suppress:true});
  const fullyClosed=afterTok<=0n||f>=0.999;if(fullyClosed){st.closed=n(st.closed)+1;st.positions.splice(index,1)}else{pos.tokenRaw=afterTok.toString();pos.costBasisLamports=Math.max(0,oldCost-allocatedCost);pos.entrySolLamports=pos.costBasisLamports;pos.scaleInLockedAfterProfit=true;pos.lastProfitActionAt=new Date().toISOString()}
  event({type:fullyClosed?'MICRO_SELL':'MICRO_PARTIAL_SELL',mint:m,symbol:pos.symbol,reason,fractionRequested:f,signature:sig,tokenRawSold:sold.toString(),solLamportsReceived:received,allocatedCostBasisLamports:allocatedCost,pnlLamports:pnl,pnlSol:pnl/1e9,remainingTokenRaw:afterTok.toString(),remainingCostBasisLamports:fullyClosed?0:pos.costBasisLamports,realizedTradingPnlLamports:cap.realizedTradingPnlLamports,openPositions:st.positions.length});atomic(statePath,st);return{closed:fullyClosed,pnl,signature:sig};
}
async function sell(st,index,reason){return await sellFraction(st,index,1,reason)}
async function observeCapital(st){const h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)return;const p=rootPolicy(),bal=await solBalance(h.publicKey);observeBalance(st,bal,p.externalFlowThresholdLamports);atomic(statePath,st)}

async function safetyPass(st,gate){
  for(let i=0;i<st.positions.length;i++){
    const pos=st.positions[i],c=candidate(pos.mint);
    if(!gate.allowed)pos.gateClosedCount=n(pos.gateClosedCount)+1;else pos.gateClosedCount=0;
    if(hardSafetyBroken(c)){await sell(st,i,'HARD_SAFETY_BREAK');return{action:'SELL',reason:'HARD_SAFETY_BREAK',symbol:pos.symbol}}
    if(severeTrendBreak(c)){await sell(st,i,'SEVERE_TREND_BREAK');return{action:'SELL',reason:'SEVERE_TREND_BREAK',symbol:pos.symbol}}
    const weak=softTrendWeak(c);pos.weakExitCount=weak?Math.min(12,n(pos.weakExitCount)+1):Math.max(0,n(pos.weakExitCount)-1);
  }
  return null;
}
async function manageOnePosition(st,gate,p){
  if(!st.positions.length)return null;
  const idx=st.manageCursor%st.positions.length;st.manageCursor=(idx+1)%Math.max(1,st.positions.length);const pos=st.positions[idx],c=candidate(pos.mint),age=(Date.now()-Date.parse(pos.openedAt||0))/1000;
  let ret=null;try{const h=await signer({op:'health'});if(h.ok&&h.publicKey&&h.walletLoaded)ret=await previewExitReturn(pos,h.publicKey)}catch(e){event({type:'EXIT_PREVIEW_FAIL',mint:pos.mint,error:String(e.message||e).slice(0,160)})}
  const th=profitThresholds(c),peak=n(pos.peakReturnPct,ret??0),giveback=peak-n(ret,peak);
  if(Number.isFinite(ret)){
    if(!pos.tp1Done&&ret>=th.tp1){const r=await sellFraction(st,idx,0.15,'SMART_TP1');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.tp1Done=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'SMART_TP1',symbol:pos.symbol}}
    if(!pos.tp2Done&&ret>=th.tp2){const r=await sellFraction(st,idx,0.20,'SMART_TP2');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.tp2Done=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'SMART_TP2',symbol:pos.symbol}}
    if(!pos.tp3Done&&ret>=th.tp3){const r=await sellFraction(st,idx,0.15,'SMART_TP3_RUNNER_LOCK');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.tp3Done=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'SMART_TP3_RUNNER_LOCK',symbol:pos.symbol}}
    const protectGiveback=Math.max(10,peak*0.35);if(!pos.profitProtectDone&&peak>=25&&giveback>=protectGiveback&&pos.weakExitCount>=1&&ret>0){const r=await sellFraction(st,idx,0.25,'SMART_PROFIT_GIVEBACK');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.profitProtectDone=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'SMART_PROFIT_GIVEBACK',symbol:pos.symbol}}
  }
  if(age>=75&&pos.weakExitCount>=4){await sell(st,idx,'CONFIRMED_TREND_BREAK');return{action:'SELL',reason:'CONFIRMED_TREND_BREAK',symbol:pos.symbol}}
  return null;
}
async function maybeScaleIn(st,p){
  if(!st.positions.length)return null;
  const ranked=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c&&!x.pos.scaleInLockedAfterProfit&&x.pos.weakExitCount===0).sort((a,b)=>rank(b.c)-rank(a.c));
  for(const x of ranked){const t=multiTier(x.c,p),last=Date.parse(x.pos.lastAddAt||x.pos.openedAt||0),age=(Date.now()-last)/1000;if(t.pct>0&&age>=p.minAddIntervalSec){const r=await placeBuy(st,x.c,t,x.index);if(r.placed)return{action:'ADD',reason:t.name,symbol:x.c.symbol}}}
  return null;
}

async function tick(){
  const gate=read(GATE,{allowed:false}),st=normalizeState(read(statePath,{})),p=rootPolicy();
  const emergency=await safetyPass(st,gate);if(emergency)return emergency;
  const managed=await manageOnePosition(st,gate,p);if(managed)return managed;
  if(gate.allowed){
    const held=new Set(st.positions.map(x=>x.mint)),c=bestCandidate(p,held);
    if(c){const t=multiTier(c,p),r=await placeBuy(st,c,t,-1);if(r.placed)return{action:'BUY',reason:t.name,symbol:c.symbol};if(r.reason!=='RESERVE_OR_TARGET_LIMIT')return{action:'WAIT',reason:r.reason}}
    const add=await maybeScaleIn(st,p);if(add)return add;
  }
  await observeCapital(st);
  if(!gate.allowed)return{action:st.positions.length?'HOLD':'WAIT',reason:'GATE_CLOSED'};
  return{action:st.positions.length?'HOLD':'WAIT',reason:st.positions.length?'PORTFOLIO_HEALTHY_NO_NEW_FILL':'NO_TREND_QUALIFIED_CANDIDATE'};
}

async function main(){fs.mkdirSync(DATA,{recursive:true});console.log('MICRO_LIVE_EXECUTOR_V331_MULTI_POSITION=STARTED');while(true){try{const d=await tick();const st=normalizeState(read(statePath,{}));console.log(`${new Date().toISOString()} ACTION=${d.action} REASON=${d.reason||''} SYMBOL=${d.symbol||''} OPEN_POSITIONS=${st.positions.length}`)}catch(e){event({type:'EXECUTOR_ERROR',error:String(e.message||e).slice(0,240)});console.error('EXECUTOR_ERROR',e.message);await sleep(15000)}await sleep(5000)}}

if(process.argv.includes('--self-test')){
  const p={reserveLamports:10_000_000,perPositionExitReserveLamports:5_000_000,minOrderLamports:10_000_000,probeUtilizationPct:15,confirmedUtilizationPct:35,strongUtilizationPct:65,maxUtilizationPct:94,maxBuyPriceImpactPct:1.25,maxSellPriceImpactPct:8,externalFlowThresholdLamports:500_000,minAddIntervalSec:30};
  const c={universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',decision:'PROBE_CANDIDATE',token2022:false,sellRoute:true,hardReject:[],score:84,liquidityUsd:600000,sellPriceImpactPct:.3,consecutiveEligible:5,priceChange5m:2.5,netBuyers5m:20,avgNetBuyersLast2:15,scoreSlopeLast2:0,liquidityStableLast2:true,organicRatio5m:.3};
  if(!trendEntryEligible(c)||multiTier(c,p).pct!==20||trendEntryEligible({...c,priceChange5m:25})||trendEntryEligible({...c,securityDecision:'REVIEW'})||trendEntryEligible({...c,holderClusterDecision:'REVIEW'})||trendEntryEligible({...c,sellRoute:false})||trendEntryEligible({...c,token2022:true})||!holdSafe({...c,score:60}))throw new Error('TREND_SELFTEST');
  const migrated=normalizeState({position:{mint:'A',costBasisLamports:10000000,openedAt:new Date().toISOString()}});if(migrated.positions.length!==1||migrated.position!==undefined)throw new Error('LEGACY_MIGRATION');
  let conflict=false;try{normalizeState({position:{mint:'A'},positions:[{mint:'B'}]})}catch{conflict=true}if(!conflict)throw new Error('LEGACY_CONFLICT_FAIL_CLOSED');
  if(requiredReserveLamports(p,1)!==15_000_000||requiredReserveLamports(p,10)!==60_000_000)throw new Error('DYNAMIC_EXIT_RESERVE');
  const empty=normalizeState({});const a=targetPlan(714_000_000,empty,null,6,p,{isNew:true});if(a.amountLamports!==42_840_000||a.reserveLamports!==15_000_000)throw new Error('MULTI_PROBE_PLAN');
  const many=normalizeState({positions:Array.from({length:10},(_,i)=>({mint:'M'+i,costBasisLamports:10_000_000,openedAt:new Date().toISOString()}))});const z=targetPlan(60_000_000,many,null,6,p,{isNew:true});if(z.amountLamports!==0||z.reserveLamports!==65_000_000)throw new Error('RESERVE_STOPS_NEW_ENTRY');
  console.log('MICRO_EXECUTOR_V331_MULTI_SELF_TEST=PASS');console.log('NO_HARD_POSITION_COUNT_LIMIT=TRUE');console.log('PER_POSITION_EXIT_RESERVE_SOL=0.005');console.log('BASE_RESERVE_SOL=0.010');console.log('MULTI_POSITION_CAPS_PCT=6_10_15_20');console.log('EXITS_AND_HARD_SAFETY_REMAIN_PRIORITY=TRUE');console.log('NETWORK_EXECUTION=NOT_CALLED');
}else if(import.meta.url===`file://${process.argv[1]}`)main();
