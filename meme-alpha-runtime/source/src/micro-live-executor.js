import fs from 'node:fs';
import net from 'node:net';

const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/micro-live';
const GATE=`${APP}/runtime-status/micro-live-gate.json`;
const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;
const TREND=`${APP}/runtime-status/trend-pulse.json`;
const REALTIME=`${APP}/runtime-status/realtime-pool-pulse.json`;
const WHALE=`${APP}/runtime-status/whale-flow-intel.json`;
const POLICY='/etc/meme-alpha/micro-live-policy.json';
const SOCK='/run/meme-alpha-signer/signer.sock';
const WSOL='So11111111111111111111111111111111111111112';
const DEFAULT_EXIT_RESERVE_LAMPORTS=5_000_000; // root-policy ceiling / fallback
const MIN_EXIT_HEADROOM_LAMPORTS=250_000;
const ENTRY_OVERHEAD_LAMPORTS=500_000;
const ESTIMATED_EXIT_COMPUTE_UNITS=350_000;

const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const statePath=`${DATA}/state.json`,eventsPath=`${DATA}/events.jsonl`;
const atomic=(p,x)=>{fs.mkdirSync(DATA,{recursive:true});const t=p+'.tmp';fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p)};
const event=x=>{fs.mkdirSync(DATA,{recursive:true});fs.appendFileSync(eventsPath,JSON.stringify({timestamp:new Date().toISOString(),...x})+'\n')};
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));

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
async function getJson(url){const r=await fetch(url,{headers:{'accept':'application/json','user-agent':'meme-alpha-v336-autonomous-portfolio'},signal:AbortSignal.timeout(12000)});const txt=await r.text();let j;try{j=JSON.parse(txt)}catch{j={raw:txt}};if(!r.ok)throw new Error(`HTTP_${r.status}`);return j}
async function rpc(method,params){const cfg=read(`${APP}/config/runtime.json`);const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(10000)});const j=await r.json();if(j.error)throw new Error(`RPC_${j.error.code}`);return j.result}
async function solBalance(pub){return Number((await rpc('getBalance',[pub,{commitment:'confirmed'}])).value)}
async function tokenBalance(pub,mint){const r=await rpc('getTokenAccountsByOwner',[pub,{mint},{encoding:'jsonParsed',commitment:'confirmed'}]);return (r.value||[]).reduce((a,x)=>a+BigInt(x.account?.data?.parsed?.info?.tokenAmount?.amount||'0'),0n)}
async function confirm(sig){for(let i=0;i<60;i++){const r=await rpc('getSignatureStatuses',[[sig],{searchTransactionHistory:true}]);const x=r.value?.[0];if(x?.err)throw new Error('CHAIN_TX_ERROR');if(['confirmed','finalized'].includes(x?.confirmationStatus))return;await sleep(400)}throw new Error('CHAIN_CONFIRM_TIMEOUT')}
function signature(j){return j?.signature||j?.txid||j?.transactionSignature||j?.data?.signature||(typeof j?.result==='string'?j.result:null)||null}
async function executeOrder(o){
  const cfg=read(`${APP}/config/runtime.json`),started=Date.now(),tx=o?.signedTransaction;
  if(typeof tx==='string'&&tx.length>200){
    const endpoints=['https://singapore.mainnet.block-engine.jito.wtf/api/v1/transactions','https://tokyo.mainnet.block-engine.jito.wtf/api/v1/transactions'];
    try{
      const landed=await Promise.any(endpoints.map(async url=>{const t=Date.now(),j=await post(url,{jsonrpc:'2.0',id:1,method:'sendTransaction',params:[tx,{encoding:'base64'}]});const sig=signature(j);if(!sig)throw new Error('JITO_NO_SIGNATURE');return{sig,url,submitMs:Date.now()-t}}));
      const confirmStart=Date.now();await confirm(landed.sig);event({type:'EXECUTION_FEEDBACK',route:'JITO_REGION_RACE',endpoint:landed.url,submitMs:landed.submitMs,confirmMs:Date.now()-confirmStart,totalMs:Date.now()-started,signature:landed.sig});return landed.sig;
    }catch(e){event({type:'EXECUTION_ROUTE_FALLBACK',from:'JITO_REGION_RACE',to:'JUPITER_EXECUTE',error:String(e?.message||e).slice(0,160)})}
  }
  const t=Date.now(),j=await post(`${String(cfg.jupiter).replace(/\/$/,'')}/swap/v2/execute`,{signedTransaction:o.signedTransaction,requestId:o.requestId}),sig=signature(j);if(!sig)throw new Error('EXECUTE_NO_SIGNATURE');const submitMs=Date.now()-t,confirmStart=Date.now();await confirm(sig);event({type:'EXECUTION_FEEDBACK',route:'JUPITER_EXECUTE',submitMs,confirmMs:Date.now()-confirmStart,totalMs:Date.now()-started,signature:sig});return sig;
}

function candidates(){return read(SIGNAL,{candidates:[]}).candidates||[]}
function candidate(mint){return candidates().find(x=>x.mint===mint)}
function hardRejectEmpty(v){return Array.isArray(v)?v.length===0:!v}
function impact(c){return Math.abs(n(c?.sellPriceImpactPct??c?.sellImpactPct??c?.priceImpactPct,99))}
function insiderSafe(c){if(!c||c.insiderRiskDecision!=='PASS')return false;const top=Number(c.topHoldersPct),cluster=Number(c.holderClusterMaxAccountsSameOwner);if(!Number.isFinite(top)||top>35||!Number.isFinite(cluster)||cluster>2)return false;const wt=c.whaleTop10Pct,wd=c.whaleDeltaTop10Pct;if(wt!==null&&wt!==undefined&&wt!==''&&Number.isFinite(Number(wt))&&Number(wt)>=70&&Number(wt)<100)return false;if(wd!==null&&wd!==undefined&&wd!==''&&Number.isFinite(Number(wd))&&Number(wd)>=8)return false;return true}
function coreSafe(c){return !!c&&c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&insiderSafe(c)&&!c.token2022&&c.sellRoute===true&&hardRejectEmpty(c.hardReject)&&n(c.liquidityUsd)>=50_000&&impact(c)<=1.25}
function pulseFor(c){if(!c)return null;const t=read(TREND,{}),age=(Date.now()-Date.parse(t.timestamp||0))/1000;if(!Number.isFinite(age)||age<0||age>10)return null;return (t.rows||[]).find(x=>x.mint===c.mint)||null}
function themeStrength(c){const t=read(TREND,{}),age=(Date.now()-Date.parse(t.timestamp||0))/1000,p=pulseFor(c);if(!p||!Number.isFinite(age)||age>10)return 0;return n((t.themes||[]).find(x=>x.narrative===p.narrative)?.strength)}
function intelRow(path,c,maxAgeSec=20){if(!c)return null;const x=read(path,{}),age=(Date.now()-Date.parse(x.updatedAt||0))/1000;if(!Number.isFinite(age)||age<0||age>maxAgeSec||x.status==='DEGRADED')return null;return (x.rows||[]).find(r=>r.mint===c.mint)||null}
function realtimeFor(c){return intelRow(REALTIME,c,8)}
function whaleFor(c){return intelRow(WHALE,c,45)}
function learningState(st){if(!st.learning||typeof st.learning!=='object')st.learning={version:1,totalClosed:0,totalWins:0,meanReturnPct:0,buckets:{}};if(!st.learning.buckets)st.learning.buckets={};return st.learning}
function featureKeys(c){const p=pulseFor(c),keys=[];keys.push(n(c.score)>=78?'SCORE_HIGH':n(c.score)>=68?'SCORE_MID':'SCORE_LOW');keys.push(n(c.liquidityUsd)>=500000?'LIQ_HIGH':n(c.liquidityUsd)>=150000?'LIQ_MID':'LIQ_LOW');keys.push(n(c.netBuyers5m)>=10?'FLOW_HIGH':n(c.netBuyers5m)>=3?'FLOW_MID':'FLOW_LOW');keys.push(n(p?.pulseScore)>=70?'PULSE_HIGH':n(p?.pulseScore)>=55?'PULSE_MID':'PULSE_LOW');keys.push(impact(c)<=.5?'IMPACT_LOW':impact(c)<=.9?'IMPACT_MID':'IMPACT_HIGH');const rt=realtimeFor(c);if(rt)keys.push(n(rt.eventMomentum)>=1.5&&n(rt.events5s)>=3?'RT_ACCEL':'RT_NORMAL');const w=whaleFor(c);if(w)keys.push(n(w.whaleFlowScore)>=2?'WHALE_HEALTHY':n(w.whaleFlowScore)<=-3?'WHALE_RISK':'WHALE_NEUTRAL');return keys}
function learnedBoost(st,c){const L=learningState(st),vals=[];for(const k of featureKeys(c)){const b=L.buckets[k];if(!b||n(b.count)<1)continue;const shrink=n(b.count)/(n(b.count)+18),m=clamp(n(b.meanReturnPct),-40,80);vals.push(m*shrink)}if(!vals.length)return 0;return clamp(vals.reduce((a,b)=>a+b,0)/vals.length/4,-8,12)}
function captureEntryFeatures(c,profile={}){return{keys:featureKeys(c),score:n(c.score),opportunityScore:opportunityScore(c),liquidityUsd:n(c.liquidityUsd),netBuyers5m:n(c.netBuyers5m),impactPct:impact(c),allocationPct:n(profile.pct),capturedAt:new Date().toISOString()}}
function learnClosedTrade(st,pos){const life=Math.max(1,n(pos.lifetimeCostLamports,n(pos.costBasisLamports))),pnl=n(pos.realizedPnlLamports),ret=clamp(pnl/life*100,-95,300),L=learningState(st);L.totalClosed=n(L.totalClosed)+1;L.totalWins=n(L.totalWins)+(ret>0?1:0);L.meanReturnPct+=(ret-n(L.meanReturnPct))/L.totalClosed;for(const k of pos.entryFeatures?.keys||[]){const b=L.buckets[k]||(L.buckets[k]={count:0,wins:0,meanReturnPct:0});b.count=n(b.count)+1;b.wins=n(b.wins)+(ret>0?1:0);b.meanReturnPct+=(ret-n(b.meanReturnPct))/b.count}event({type:'ONLINE_LEARNING_UPDATE',mint:pos.mint,symbol:pos.symbol,returnPct:ret,totalClosed:L.totalClosed,winRate:L.totalClosed?L.totalWins/L.totalClosed:0})}
function expectedEdge(st,c){return opportunityScore(c)+learnedBoost(st,c)}

function opportunityScore(c){const base=n(c.score),p=pulseFor(c);let add=0;if(p){if(n(p.volumeAcceleration)>=1.45)add+=4;else if(n(p.volumeAcceleration)>=1.10)add+=2;if(n(p.txnAcceleration)>=1.30)add+=3;else if(n(p.txnAcceleration)>=1.05)add+=1;if(n(p.buySellRatio)>=1.25)add+=2;if(themeStrength(c)>=60)add+=2;if(n(p.pulseScore)>=70)add+=1;if(p.status==='EXHAUSTED')add-=8;if(p.promotionFlag===true&&n(p.pulseScore)<65)add-=3}const rt=realtimeFor(c);if(rt&&n(rt.lastEventAgeMs,99999)<=2500){if(n(rt.eventMomentum)>=1.8&&n(rt.events5s)>=3)add+=5;else if(n(rt.events5s)>=2)add+=2}const w=whaleFor(c);if(w)add+=clamp(n(w.whaleFlowScore),-6,4);return clamp(base+add,base-10,base+18)}
function opportunityLane(c){const score=opportunityScore(c),base=n(c.score),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net);if(base<58)return false;const standard=score>=72;const liquid=score>=66&&liq>=500000&&net>=1&&imp<=0.80;const flow=score>=62&&liq>=100000&&net>=5&&avg>=3&&chg>=0.20&&imp<=0.80;return standard||liquid||flow}
function trendEntryEligible(c){if(!coreSafe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.consecutiveEligible)<1)return false;const p=pulseFor(c),chg=p?n(p.price5m,-999):n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net),slope=n(c.scoreSlopeLast2,0),stable=c.liquidityStableLast2!==false;const pulseFlow=!!p&&p.status!=='EXHAUSTED'&&n(p.pulseScore)>=55&&n(p.volumeAcceleration)>=1.05&&n(p.txnAcceleration)>=1.0&&n(p.buySellRatio)>=1.10&&n(p.tx5)>=4;const buyerFlow=net>=2&&avg>=1.5;const fastFlow=net>=1&&pulseFlow;const momentumFloor=pulseFlow?0.05:0.15;return chg>=momentumFloor&&chg<=15&&(buyerFlow||fastFlow)&&slope>=-4&&stable&&opportunityLane(c)}
function hardSafetyBroken(c){if(!c)return false;if((Array.isArray(c.hardReject)&&c.hardReject.length>0)||c.sellRoute===false||c.token2022===true)return true;if(c.securityDecision==='BLOCK'||c.holderClusterDecision==='BLOCK')return true;if(n(c.liquidityUsd,999999)<20_000)return true;return false}
function severeTrendBreak(c){if(!c)return false;const p=pulseFor(c),chg=p?n(p.price5m,n(c.priceChange5m)):n(c.priceChange5m),net=n(c.netBuyers5m),bs=p?n(p.buySellRatio,1):n(c.buySellRatio5m,1);return chg<=-13||net<=-30||(chg<=-9&&bs<0.55)}
function softTrendWeak(c){if(!c)return false;const p=pulseFor(c),chg=p?n(p.price5m,n(c.priceChange5m)):n(c.priceChange5m),net=n(c.netBuyers5m),bs=p?n(p.buySellRatio,1):n(c.buySellRatio5m,1),pulse=n(p?.pulseScore,50);return n(c.score)<52||chg<=-7||net<=-12||(p?.status==='EXHAUSTED'&&pulse<50&&bs<0.85)}
function holdSafe(c){return !hardSafetyBroken(c)&&!severeTrendBreak(c)&&!softTrendWeak(c)}
function profitPlan(c,pos){
  const pulse=pulseFor(c),strength=clamp(n(pulse?.pulseScore,50),0,100),chg=Math.abs(n(pulse?.price5m,n(c?.priceChange5m,0))),bs=n(pulse?.buySellRatio,n(c?.buySellRatio5m,1));
  const breakout=!!pulse&&pulse.status==='BREAKOUT'&&strength>=70&&bs>=1.05;
  const tp1=clamp(10+strength*0.14+chg*0.35,10,36),tp2=tp1*(breakout?2.1:1.75),tp3=tp2*(breakout?1.8:1.55);
  const givebackRatio=breakout?0.45:0.30,minGiveback=clamp(5+chg*0.65,5,16);
  const f1=breakout?0.12:0.18,f2=breakout?0.16:0.22,f3=breakout?0.12:0.18;
  return {tp1,tp2,tp3,givebackRatio,minGiveback,f1,f2,f3,breakout};
}
function profitAwareWeakDecision(x={}){
  const ret=n(x.ret),peak=Math.max(n(x.peak),ret),giveback=Math.max(0,n(x.giveback)),minGiveback=Math.max(3,n(x.minGiveback,5)),weakCount=n(x.weakCount),severe=x.severe===true,softWeak=x.softWeak===true,hadProfit=x.hadProfit===true||peak>=4||ret>0;
  if(severe)return{mode:'FULL',reason:'SEVERE_TREND_BREAK',frac:1};
  if(!softWeak)return{mode:'HOLD',reason:'TREND_RECOVERED',frac:0};
  if(ret<=-8)return{mode:'FULL',reason:'LOSS_LIMIT',frac:1};
  if(hadProfit&&ret>-3){
    const frac=clamp(.18+giveback/120+Math.max(0,weakCount-4)*.025,.18,.35);
    return{mode:'TRIM',reason:'PROFIT_AWARE_WEAKNESS',frac};
  }
  if(ret<=-3&&weakCount>=6)return{mode:'FULL',reason:'PERSISTENT_WEAKNESS_NEGATIVE',frac:1};
  return{mode:'TRIM',reason:'DEFENSIVE_WEAKNESS_TRIM',frac:clamp(.16+Math.max(0,weakCount-4)*.02,.16,.28)};
}
function profitAwareWeakAction(ret,peak,giveback,plan,c,pos){
  return profitAwareWeakDecision({ret,peak,giveback,minGiveback:plan?.minGiveback,weakCount:pos?.weakExitCount,severe:severeTrendBreak(c),softWeak:softTrendWeak(c),hadProfit:peak>=4||pos?.tp1Done||pos?.tp2Done||pos?.tp3Done||pos?.profitProtectDone});
}
function weakTrimReady(pos,minMs=20000,maxTrims=2){
  if(n(pos?.profitWeakTrimCount)>=maxTrims)return false;
  const last=Date.parse(pos?.lastProfitWeakTrimAt||0);
  return !Number.isFinite(last)||last<=0||Date.now()-last>=minMs;
}
function markWeakTrim(st,mint){
  const x=st.positions.find(z=>z.mint===mint);if(!x)return;
  x.profitWeakTrimCount=n(x.profitWeakTrimCount)+1;x.lastProfitWeakTrimAt=new Date().toISOString();x.scaleInLockedAfterProfit=true;atomic(statePath,st);
}
function resetWeakTrimEpisode(st,pos,c){
  if(!c||softTrendWeak(c)||(!n(pos.profitWeakTrimCount)&&!pos.lastProfitWeakTrimAt))return;
  const x=st.positions.find(z=>z.mint===pos.mint);if(!x)return;
  x.profitWeakTrimCount=0;x.lastProfitWeakTrimAt=null;atomic(statePath,st);
}

function tier(c,p){if(!trendEntryEligible(c))return {name:'NONE',pct:0};const score=n(c.score),con=n(c.consecutiveEligible),net=n(c.netBuyers5m),avg=n(c.avgNetBuyersLast2),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m);const maxQuality=(score>=82&&net>=10&&avg>=7)||(score>=76&&net>=18&&avg>=10);if(con>=5&&maxQuality&&liq>=250000&&imp<=0.50&&chg>=0.50&&chg<=8)return{name:'MAX',pct:p.maxUtilizationPct};const strongQuality=(score>=76&&net>=6&&avg>=4)||(score>=70&&net>=10&&avg>=6);if(con>=3&&strongQuality&&liq>=150000&&imp<=0.80&&chg>=0.30&&chg<=10)return{name:'STRONG',pct:p.strongUtilizationPct};const confirmedQuality=(score>=70&&net>=3&&avg>=2)||(score>=66&&net>=6&&avg>=4);if(con>=2&&confirmedQuality&&liq>=100000&&imp<=1.00&&chg>=0.15&&chg<=12)return{name:'CONFIRMED',pct:p.confirmedUtilizationPct};return{name:'PROBE',pct:p.probeUtilizationPct}}
function ensureAutonomy(st,capitalBaseLamports=0){if(!st.autonomy||typeof st.autonomy!=='object')st.autonomy={};if(!(n(st.autonomy.referenceCapitalLamports)>0)&&capitalBaseLamports>0)st.autonomy.referenceCapitalLamports=capitalBaseLamports;return st.autonomy}
function allocationProfile(c,p,st,capitalBaseLamports){
  if(!trendEntryEligible(c)||capitalBaseLamports<=0)return{name:'NONE',pct:0,quality:0};
  const scoreQ=clamp((opportunityScore(c)-58)/32,0,1),netQ=clamp((n(c.netBuyers5m)+2)/24,0,1),avgQ=clamp((n(c.avgNetBuyersLast2)+1)/16,0,1);
  const liq=Math.max(50_000,n(c.liquidityUsd,50_000)),liqQ=clamp(Math.log10(liq/50_000)/1.6,0,1),impactQ=clamp(1-impact(c)/1.25,0,1),pulse=pulseFor(c),pulseQ=clamp(n(pulse?.pulseScore,55)/100,0,1);
  const rt=realtimeFor(c),rtQ=rt?clamp((n(rt.eventMomentum)-.8)/2.2,0,1):.35,w=whaleFor(c),whaleQ=w?clamp((n(w.whaleFlowScore)+10)/16,0,1):.50,learn=learnedBoost(st,c),learnQ=clamp(.5+learn/24,0,1);
  const quality=clamp(scoreQ*.26+netQ*.15+avgQ*.09+liqQ*.13+impactQ*.13+pulseQ*.08+rtQ*.07+whaleQ*.05+learnQ*.04,0,1);
  const a=ensureAutonomy(st,capitalBaseLamports),ref=Math.max(1,n(a.referenceCapitalLamports,capitalBaseLamports)),growth=clamp(Math.pow(capitalBaseLamports/ref,.28),.80,2.00);
  const invested=portfolioInvested(st),exposure=clamp(invested/capitalBaseLamports,0,1),freeRatio=clamp((capitalBaseLamports-invested)/capitalBaseLamports,0,1),basePct=4+31*Math.pow(quality,1.20),cashBoost=1+0.38*freeRatio,pct=clamp(basePct*growth*cashBoost,0,p.maxUtilizationPct);
  return{name:'AUTO_ALPHA',pct,quality,growth,exposure,freeRatio,cashBoost,learnedBoost:learn,expectedEdge:expectedEdge(st,c),score:opportunityScore(c)};
}
function rank(c){const rt=realtimeFor(c),w=whaleFor(c);return opportunityScore(c)*100+n(c.netBuyers5m)*2+n(c.avgNetBuyersLast2)+n(c.organicRatio5m)*30+n(rt?.eventMomentum)*16+n(w?.whaleFlowScore)*8-Math.max(0,n(c.priceChange5m)-10)*10}
function bestCandidate(p,held,st){return candidates().filter(c=>!held.has(c.mint)&&trendEntryEligible(c)).sort((a,b)=>expectedEdge(st,b)-expectedEdge(st,a)||rank(b)-rank(a))[0]||null}

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
  if(!Number.isFinite(Number(pos.lifetimeCostLamports)))pos.lifetimeCostLamports=n(pos.costBasisLamports);if(!Number.isFinite(Number(pos.realizedPnlLamports)))pos.realizedPnlLamports=0;
  if(!Number.isFinite(Number(pos.profitWeakTrimCount)))pos.profitWeakTrimCount=0;if(!pos.lastProfitWeakTrimAt)pos.lastProfitWeakTrimAt=null;
  return pos;
}
function normalizeState(st){
  if(!st||typeof st!=='object')st={};
  st.version='3.60.0-profit-aware-exits';st.closed=n(st.closed);
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
async function networkExitHeadroomLamports(p){
  try{const rows=await rpc('getRecentPrioritizationFees',[]),vals=(rows||[]).map(x=>n(x.prioritizationFee)).filter(x=>x>=0).sort((a,b)=>a-b);const q=vals.length?vals[Math.min(vals.length-1,Math.floor(vals.length*.75))]:0;const priority=Math.ceil(q*ESTIMATED_EXIT_COMPUTE_UNITS/1_000_000),estimated=Math.ceil((10_000+priority)*8);return Math.floor(clamp(estimated,MIN_EXIT_HEADROOM_LAMPORTS,p.perPositionExitReserveLamports))}catch{return Math.floor(clamp(750_000,MIN_EXIT_HEADROOM_LAMPORTS,p.perPositionExitReserveLamports))}
}
function requiredReserveLamports(p,count,exitHeadroomLamports=MIN_EXIT_HEADROOM_LAMPORTS){const per=Math.floor(clamp(exitHeadroomLamports,MIN_EXIT_HEADROOM_LAMPORTS,p.perPositionExitReserveLamports));return p.reserveLamports+Math.max(0,count)*per}
function targetPlan(solBalanceLamports,st,position,targetPct,p,{isNew=false,exitHeadroomLamports=MIN_EXIT_HEADROOM_LAMPORTS}={}){
  const invested=Math.max(0,n(position?.costBasisLamports)),capitalBase=Math.max(0,solBalanceLamports+portfolioInvested(st)),targetInvested=Math.floor(capitalBase*targetPct/100),futureCount=st.positions.length+(isNew?1:0),reserve=requiredReserveLamports(p,futureCount,exitHeadroomLamports),overhead=isNew?Math.max(ENTRY_OVERHEAD_LAMPORTS,exitHeadroomLamports):0,available=Math.max(0,solBalanceLamports-reserve-overhead),amount=Math.min(Math.max(0,targetInvested-invested),available);
  return {capitalBaseLamports:capitalBase,investedLamports:invested,targetInvestedLamports:targetInvested,amountLamports:Math.floor(amount),targetUtilizationPct:targetPct,reserveLamports:reserve,entryOverheadLamports:overhead,futurePositionCount:futureCount,availableLamports:available,exitHeadroomLamports};
}

async function placeBuy(st,c,posIndex=-1){
  const p=rootPolicy(),h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.signingEnabled||!h.walletLoaded)throw new Error('SIGNER_NOT_ARMED');
  const isAdd=posIndex>=0,existing=isAdd?st.positions[posIndex]:null;if(!isAdd&&st.positions.some(x=>x.mint===c.mint))return{placed:false,reason:'MINT_ALREADY_HELD'};
  const beforeSol=await solBalance(h.publicKey),capitalBase=Math.max(0,beforeSol+portfolioInvested(st)),profile=allocationProfile(c,p,st,capitalBase),exitHeadroomLamports=await networkExitHeadroomLamports(p),plan=targetPlan(beforeSol,st,existing,profile.pct,p,{isNew:!isAdd,exitHeadroomLamports});
  if(plan.targetInvestedLamports<p.minOrderLamports)return{placed:false,reason:'ALLOCATION_BELOW_MIN_ORDER',plan,profile};if(plan.availableLamports<p.minOrderLamports)return{placed:false,reason:'CAPITAL_HEADROOM_LOW',plan,profile};if(plan.amountLamports<p.minOrderLamports)return{placed:false,reason:'TARGET_ALREADY_SATISFIED',plan,profile};
  const beforeTok=await tokenBalance(h.publicKey,c.mint),o=await signer({op:'order',inputMint:WSOL,outputMint:c.mint,amount:String(plan.amountLamports),maxPriceImpactPct:p.maxBuyPriceImpactPct});if(!o.ok)throw new Error(`SIGNER_${o.error}`);if(Math.abs(n(o.priceImpactPct,99))>p.maxBuyPriceImpactPct)throw new Error('ORDER_IMPACT_GUARD');
  const sig=await executeOrder(o),afterSol=await solBalance(h.publicKey),afterTok=await tokenBalance(h.publicKey,c.mint),delta=afterTok-beforeTok;if(delta<=0n)throw new Error('BUY_TOKEN_DELTA_ZERO');const spent=Math.max(0,beforeSol-afterSol);if(spent>plan.amountLamports+Math.max(ENTRY_OVERHEAD_LAMPORTS,exitHeadroomLamports))event({type:'POST_FILL_SPEND_OVER_PLAN',mint:c.mint,spentLamports:spent,plannedLamports:plan.amountLamports});
  if(isAdd){const pos=st.positions[posIndex];pos.tokenRaw=(BigInt(pos.tokenRaw||'0')+delta).toString();pos.costBasisLamports=n(pos.costBasisLamports)+spent;pos.entrySolLamports=pos.costBasisLamports;pos.lifetimeCostLamports=n(pos.lifetimeCostLamports)+spent;pos.addCount=n(pos.addCount)+1;pos.lastAddAt=new Date().toISOString();pos.targetUtilizationPct=profile.pct;pos.tier='AUTO';pos.lastAddSignature=sig;pos.walletAfterSolLamports=afterSol;event({type:'MICRO_SCALE_IN',mint:c.mint,symbol:c.symbol,allocationPct:profile.pct,quality:profile.quality,spentLamports:spent,spentSol:spent/1e9,costBasisLamports:pos.costBasisLamports,signature:sig,openPositions:st.positions.length})}
  else{const pos={mint:c.mint,symbol:c.symbol,tokenRaw:delta.toString(),costBasisLamports:spent,entrySolLamports:spent,entrySignature:sig,openedAt:new Date().toISOString(),lastAddAt:new Date().toISOString(),addCount:0,targetUtilizationPct:profile.pct,tier:'AUTO',walletBeforeSolLamports:beforeSol,walletAfterSolLamports:afterSol,weakExitCount:0,gateClosedCount:0,peakReturnPct:null,lastReturnPct:null,tp1Done:false,tp2Done:false,tp3Done:false,profitProtectDone:false,scaleInLockedAfterProfit:false};pos.entryFeatures=captureEntryFeatures(c,profile);pos.lifetimeCostLamports=spent;pos.realizedPnlLamports=0;st.positions.push(pos);event({type:'MICRO_BUY',mint:c.mint,symbol:c.symbol,allocationPct:profile.pct,quality:profile.quality,growthFactor:profile.growth,spentLamports:spent,spentSol:spent/1e9,signature:sig,openPositions:st.positions.length,reserveForAllExitsLamports:requiredReserveLamports(p,st.positions.length,exitHeadroomLamports)})}
  observeBalance(st,afterSol,p.externalFlowThresholdLamports,{suppress:true});const reserveNow=requiredReserveLamports(p,st.positions.length,exitHeadroomLamports);if(afterSol<reserveNow)event({type:'EXIT_RESERVE_MARGIN_LOW',walletSolLamports:afterSol,requiredReserveLamports:reserveNow,openPositions:st.positions.length});atomic(statePath,st);return{placed:true,plan,profile,spent,signature:sig};
}

async function previewExitReturn(pos,pub){
  const now=Date.now(),last=Date.parse(pos.lastMarkAt||0);if(Number.isFinite(last)&&now-last<5_000&&Number.isFinite(Number(pos.lastReturnPct)))return Number(pos.lastReturnPct);
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
  pos.realizedPnlLamports=n(pos.realizedPnlLamports)+pnl;const fullyClosed=afterTok<=0n||f>=0.999;if(fullyClosed){learnClosedTrade(st,pos);st.closed=n(st.closed)+1;st.positions.splice(index,1)}else{pos.tokenRaw=afterTok.toString();pos.costBasisLamports=Math.max(0,oldCost-allocatedCost);pos.entrySolLamports=pos.costBasisLamports;pos.scaleInLockedAfterProfit=true;pos.lastProfitActionAt=new Date().toISOString()}
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
  if(!st.positions.length)return null;const idx=st.manageCursor%st.positions.length;st.manageCursor=(idx+1)%Math.max(1,st.positions.length);const pos=st.positions[idx],c=candidate(pos.mint);
  let ret=null;try{const h=await signer({op:'health'});if(h.ok&&h.publicKey&&h.walletLoaded)ret=await previewExitReturn(pos,h.publicKey)}catch(e){event({type:'EXIT_PREVIEW_FAIL',mint:pos.mint,error:String(e.message||e).slice(0,160)})}
  const plan=profitPlan(c,pos),peak=n(pos.peakReturnPct,ret??0),giveback=peak-n(ret,peak);
  if(Number.isFinite(ret)){
    resetWeakTrimEpisode(st,pos,c);
    if(!pos.tp1Done&&ret>=plan.tp1){const r=await sellFraction(st,idx,plan.f1,'AUTO_TP1');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.tp1Done=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'AUTO_TP1',symbol:pos.symbol}}
    if(!pos.tp2Done&&ret>=plan.tp2){const r=await sellFraction(st,idx,plan.f2,'AUTO_TP2');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.tp2Done=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'AUTO_TP2',symbol:pos.symbol}}
    if(!pos.tp3Done&&ret>=plan.tp3){const r=await sellFraction(st,idx,plan.f3,'AUTO_TP3_RUNNER');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.tp3Done=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'AUTO_TP3_RUNNER',symbol:pos.symbol}}
    const protectGiveback=Math.max(plan.minGiveback,peak*plan.givebackRatio);if(!pos.profitProtectDone&&peak>=plan.tp1*.85&&giveback>=protectGiveback&&ret>0){const frac=plan.breakout?.20:.30,r=await sellFraction(st,idx,frac,'AUTO_PROFIT_GIVEBACK');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.profitProtectDone=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'AUTO_PROFIT_GIVEBACK',symbol:pos.symbol}}
    if(pos.weakExitCount>=4){
      const wa=profitAwareWeakAction(ret,peak,giveback,plan,c,pos);
      if(wa.mode==='FULL'){
        const reason=wa.reason==='SEVERE_TREND_BREAK'?'AUTO_SEVERE_TREND_BREAK':wa.reason==='LOSS_LIMIT'?'AUTO_LOSS_LIMIT':'AUTO_CONFIRMED_WEAKNESS_NEGATIVE';
        event({type:'PROFIT_AWARE_EXIT_DECISION',mint:pos.mint,symbol:pos.symbol,decision:'FULL',reason,ret,peak,giveback,weakExitCount:pos.weakExitCount});
        await sell(st,idx,reason);return{action:'SELL',reason,symbol:pos.symbol};
      }
      if(wa.mode==='TRIM'&&weakTrimReady(pos,20000,2)){
        const r=await sellFraction(st,idx,wa.frac,'AUTO_PROFIT_AWARE_WEAKNESS_TRIM');
        if(!r.closed)markWeakTrim(st,pos.mint);
        event({type:'PROFIT_AWARE_WEAKNESS_TRIM',mint:pos.mint,symbol:pos.symbol,ret,peak,giveback,fraction:wa.frac,weakExitCount:pos.weakExitCount,reason:wa.reason,closed:r.closed});
        return{action:r.closed?'SELL':'PARTIAL_SELL',reason:'AUTO_PROFIT_AWARE_WEAKNESS_TRIM',symbol:pos.symbol};
      }
    }
  }else if(softTrendWeak(c)){
    const peak=n(pos.peakReturnPct),hadProfit=peak>=4||pos.tp1Done||pos.tp2Done||pos.tp3Done||pos.profitProtectDone;
    if(severeTrendBreak(c)&&pos.weakExitCount>=4){event({type:'NO_QUOTE_EXIT_DECISION',mint:pos.mint,decision:'FULL',reason:'SEVERE_TREND_BREAK',peak,weakExitCount:pos.weakExitCount});await sell(st,idx,'AUTO_SEVERE_TREND_BREAK_NO_QUOTE');return{action:'SELL',reason:'AUTO_SEVERE_TREND_BREAK_NO_QUOTE',symbol:pos.symbol}}
    if(hadProfit&&pos.weakExitCount>=7&&weakTrimReady(pos,30000,2)){const frac=.22,r=await sellFraction(st,idx,frac,'AUTO_WINNER_DEFENSE_NO_QUOTE');if(!r.closed)markWeakTrim(st,pos.mint);event({type:'NO_QUOTE_WINNER_DEFENSE',mint:pos.mint,symbol:pos.symbol,peak,fraction:frac,weakExitCount:pos.weakExitCount,closed:r.closed});return{action:r.closed?'SELL':'PARTIAL_SELL',reason:'AUTO_WINNER_DEFENSE_NO_QUOTE',symbol:pos.symbol}}
    if(!hadProfit&&pos.weakExitCount>=10){event({type:'NO_QUOTE_EXIT_DECISION',mint:pos.mint,decision:'FULL',reason:'PERSISTENT_WEAKNESS',peak,weakExitCount:pos.weakExitCount});await sell(st,idx,'AUTO_PERSISTENT_WEAKNESS_NO_QUOTE');return{action:'SELL',reason:'AUTO_PERSISTENT_WEAKNESS_NO_QUOTE',symbol:pos.symbol}}
  }
  return null;
}
async function maybeScaleIn(st,p){
  if(!st.positions.length)return null;const ranked=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c&&!x.pos.scaleInLockedAfterProfit&&x.pos.weakExitCount===0).sort((a,b)=>rank(b.c)-rank(a.c));
  for(const x of ranked){const last=Date.parse(x.pos.lastAddAt||x.pos.openedAt||0),age=(Date.now()-last)/1000;if(age>=p.minAddIntervalSec){const r=await placeBuy(st,x.c,x.index);if(r.placed)return{action:'ADD',reason:'AUTO_SCALE',symbol:x.c.symbol}}}return null;
}
function rotationSource(st,newC){
  const ns=expectedEdge(st,newC),newImpact=impact(newC),rows=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c).map(x=>({...x,oldScore:expectedEdge(st,x.c),weak:softTrendWeak(x.c),severe:severeTrendBreak(x.c)})).sort((a,b)=>a.oldScore-b.oldScore);
  for(const x of rows){
    const switchingCost=(newImpact+Math.max(0,n(x.pos.lastPreviewImpactPct,impact(x.c))))*1.5,advantage=ns-x.oldScore-switchingCost,ret=n(x.pos.lastReturnPct),peak=n(x.pos.peakReturnPct),winner=ret>0||peak>=8||x.pos.tp1Done||x.pos.tp2Done||x.pos.tp3Done||x.pos.profitProtectDone;
    const threshold=x.severe?0:(winner?(ret>=12||peak>=20?34:28):(x.weak?5:13));
    if(x.severe||advantage>=threshold)return{...x,advantage,switchingCost,winner,threshold,ret,peak};
  }
  return null;
}
async function maybeRotate(st,newC){
  const x=rotationSource(st,newC);if(!x)return null;
  const frac=x.severe?.50:x.winner?clamp(.15+x.advantage/180,.15,.28):x.weak?.50:clamp(.20+x.advantage/100,.20,.45),reason=x.winner?'AUTO_WINNER_ROTATE_TO_STRONGER_OPPORTUNITY':'AUTO_ROTATE_TO_STRONGER_OPPORTUNITY';
  const r=await sellFraction(st,x.index,frac,reason),a=ensureAutonomy(st);a.lastRotationAt=new Date().toISOString();a.lastRotationFromMint=x.pos.mint;a.lastRotationToMint=newC.mint;atomic(statePath,st);
  event({type:x.winner?'WINNER_ROTATION':'AUTO_ROTATION',fromMint:x.pos.mint,toMint:newC.mint,advantage:x.advantage,threshold:x.threshold,switchingCost:x.switchingCost,fraction:frac,ret:x.ret,peak:x.peak,severe:x.severe,closed:r.closed});
  return{action:'ROTATE',reason:x.winner?'WINNER_TO_MATERIALLY_STRONGER_OPPORTUNITY':'STRONGER_OPPORTUNITY',symbol:x.pos.symbol,targetSymbol:newC.symbol};
}

async function tick(){
  const gate=read(GATE,{allowed:false}),st=normalizeState(read(statePath,{})),p=rootPolicy();const emergency=await safetyPass(st,gate);if(emergency)return emergency;const managed=await manageOnePosition(st,gate,p);if(managed)return managed;
  if(gate.allowed){const held=new Set(st.positions.map(x=>x.mint)),c=bestCandidate(p,held,st);if(c){const r=await placeBuy(st,c,-1);if(r.placed)return{action:'BUY',reason:'AUTO_ALLOC',symbol:c.symbol};if(r.reason==='CAPITAL_HEADROOM_LOW'){const rotate=await maybeRotate(st,c);if(rotate)return rotate}else if(!['ALLOCATION_BELOW_MIN_ORDER','TARGET_ALREADY_SATISFIED'].includes(r.reason))return{action:'WAIT',reason:r.reason}}
    const add=await maybeScaleIn(st,p);if(add)return add;
  }
  await observeCapital(st);if(!gate.allowed)return{action:st.positions.length?'HOLD':'WAIT',reason:'GATE_CLOSED'};return{action:st.positions.length?'HOLD':'WAIT',reason:st.positions.length?'AUTONOMOUS_PORTFOLIO_MONITORING':'NO_TREND_QUALIFIED_CANDIDATE'};
}

async function main(){fs.mkdirSync(DATA,{recursive:true});console.log('MICRO_LIVE_EXECUTOR_V360_PROFIT_AWARE=STARTED');while(true){try{const d=await tick();const st=normalizeState(read(statePath,{}));console.log(`${new Date().toISOString()} ACTION=${d.action} REASON=${d.reason||''} SYMBOL=${d.symbol||''} OPEN_POSITIONS=${st.positions.length}`)}catch(e){event({type:'EXECUTOR_ERROR',error:String(e.message||e).slice(0,240)});console.error('EXECUTOR_ERROR',e.message);await sleep(15000)}await sleep(1500)}}

if(process.argv.includes('--self-test')){
  const p={reserveLamports:10_000_000,perPositionExitReserveLamports:5_000_000,minOrderLamports:10_000_000,probeUtilizationPct:15,confirmedUtilizationPct:35,strongUtilizationPct:65,maxUtilizationPct:94,maxBuyPriceImpactPct:1.25,maxSellPriceImpactPct:8,externalFlowThresholdLamports:500_000,minAddIntervalSec:30};
  const c={mint:'C',universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',insiderRiskDecision:'PASS',topHoldersPct:20,holderClusterMaxAccountsSameOwner:1,whaleTop10Pct:25,whaleDeltaTop10Pct:0,decision:'PROBE_CANDIDATE',token2022:false,sellRoute:true,hardReject:[],score:84,liquidityUsd:600000,sellPriceImpactPct:.3,consecutiveEligible:5,priceChange5m:2.5,netBuyers5m:20,avgNetBuyersLast2:15,scoreSlopeLast2:0,liquidityStableLast2:true,organicRatio5m:.3};
  if(!trendEntryEligible(c)||trendEntryEligible({...c,priceChange5m:25})||trendEntryEligible({...c,securityDecision:'REVIEW'})||trendEntryEligible({...c,sellRoute:false})||trendEntryEligible({...c,token2022:true})||trendEntryEligible({...c,insiderRiskDecision:'REVIEW'})||trendEntryEligible({...c,topHoldersPct:40})||trendEntryEligible({...c,holderClusterMaxAccountsSameOwner:3}))throw new Error('ENTRY_SAFETY_SELFTEST');
  const migrated=normalizeState({position:{mint:'A',costBasisLamports:10000000,openedAt:new Date().toISOString()}});if(migrated.positions.length!==1||migrated.position!==undefined)throw new Error('LEGACY_MIGRATION');
  const empty=normalizeState({});const prof=allocationProfile(c,p,empty,714_000_000);if(!(prof.pct>3&&prof.pct<p.maxUtilizationPct))throw new Error('CONTINUOUS_ALLOCATOR');const a=targetPlan(714_000_000,empty,null,prof.pct,p,{isNew:true,exitHeadroomLamports:300_000});if(!(a.amountLamports>10_000_000)||a.reserveLamports!==10_300_000)throw new Error('DYNAMIC_PLAN');
  const grown=normalizeState({autonomy:{referenceCapitalLamports:714_000_000}}),p1=allocationProfile(c,p,grown,714_000_000),p2=allocationProfile(c,p,grown,1_428_000_000);if(!(p2.pct>p1.pct))throw new Error('EQUITY_SCALE_FACTOR');
  const many=normalizeState({positions:Array.from({length:10},(_,i)=>({mint:'M'+i,costBasisLamports:10_000_000,openedAt:new Date().toISOString()}))});if(requiredReserveLamports(p,10,300_000)!==13_000_000)throw new Error('DYNAMIC_EXIT_RESERVE');
  const s1=normalizeState({positions:[{mint:'A',openedAt:new Date().toISOString()},{mint:'B',openedAt:new Date().toISOString()}]});s1.positions.splice(0,1);if(s1.positions.length!==1||s1.positions[0].mint!=='B')throw new Error('POSITION_ISOLATION');
  const pa=profitAwareWeakDecision({ret:5,peak:9,giveback:4,minGiveback:5,weakCount:4,softWeak:true,severe:false,hadProfit:true});if(pa.mode!=='TRIM')throw new Error('POSITIVE_SOFT_WEAKNESS_MUST_TRIM');
  const pb=profitAwareWeakDecision({ret:-9,peak:2,giveback:0,minGiveback:5,weakCount:4,softWeak:true,severe:false,hadProfit:false});if(pb.mode!=='FULL'||pb.reason!=='LOSS_LIMIT')throw new Error('LOSS_LIMIT_MUST_FULL_EXIT');
  const pc=profitAwareWeakDecision({ret:7,peak:12,giveback:5,minGiveback:5,weakCount:4,softWeak:true,severe:true,hadProfit:true});if(pc.mode!=='FULL'||pc.reason!=='SEVERE_TREND_BREAK')throw new Error('SEVERE_BREAK_MUST_FULL_EXIT');
  const pd=profitAwareWeakDecision({ret:2,peak:7,giveback:5,minGiveback:5,weakCount:4,softWeak:false,severe:false,hadProfit:true});if(pd.mode!=='HOLD')throw new Error('RECOVERED_TREND_MUST_HOLD');
  console.log('PROFIT_AWARE_WEAK_EXIT=TRUE');console.log('POSITIVE_SOFT_WEAKNESS=PARTIAL_ONLY');console.log('WINNER_ROTATION_PROTECTION=TRUE');console.log('NO_QUOTE_WINNER_DEFENSE=TRUE');console.log('SEVERE_TREND_BREAK_FULL_EXIT=KEPT');
  console.log('MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS');console.log('OBJECTIVE_INSIDER_RISK_DEFENSE_IN_DEPTH=TRUE');console.log('CONTINUOUS_ALLOCATION=TRUE');console.log('CAPITAL_UTILIZATION_FIRST=TRUE');console.log('FREE_CAPITAL_BOOSTS_NEW_BUYS=TRUE');console.log('EQUITY_GROWTH_SCALES_NEW_BUYS=TRUE');console.log('DYNAMIC_NETWORK_EXIT_HEADROOM=TRUE');console.log('MULTI_POSITION_NO_HARD_COUNT_LIMIT=TRUE');console.log('ROTATION_TO_STRONGER_OPPORTUNITY=TRUE');console.log('HARD_SECURITY_AND_SELLABILITY_FAILSAFE=KEPT');console.log('REALTIME_POOL_PULSE_INTEGRATION=TRUE');console.log('ONCHAIN_WHALE_FLOW_INTEGRATION=TRUE');console.log('ONLINE_EXPECTANCY_LEARNING=TRUE');console.log('OPPORTUNITY_COST_ROTATION=TRUE');console.log('JITO_REGION_RACE_WITH_SAFE_FALLBACK=TRUE');console.log('EXECUTION_FEEDBACK_LOOP=TRUE');console.log('ADAPTIVE_FAST_LOOP_MS=1500');console.log('NETWORK_EXECUTION=NOT_CALLED');
}else if(import.meta.url===`file://${process.argv[1]}`)main();
