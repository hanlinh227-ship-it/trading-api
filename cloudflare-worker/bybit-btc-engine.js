import {bybitAutoConfig} from "./bybit-auto-config.js";
import {bybitV5,normalizeBybitFilter,roundTick} from "./bybit-v5-client.js";
import {buildBtcMarketState} from "./bybit-btc-market-state.js";
import {selectBtcSetup} from "./bybit-btc-strategy.js";
import {activeRiskUsd,addTranche,btcRiskDecision,closeAllTranches,sizeBtcSetup,updateTrancheProtection} from "./bybit-btc-risk-engine.js";

const KEY="bybit:btc:hyperscale:v2:state";
const SYMBOL="BTCUSDT";
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const iso=()=>new Date().toISOString();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const envBool=v=>String(v||"").toLowerCase()==="true";
async function get(env){try{return await env.TRADING_STATE?.get(KEY,{type:"json"})||{};}catch{return {};}}
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}
function liveMode(env){return envBool(env.BYBIT_AUTO_LIVE)&&envBool(env.BYBIT_BTC_LIVE_ACK)?"LIVE":"PAPER";}
function walletEquity(w={}){const a=w?.result?.list?.[0]||{},c=(a.coin||[]).find(x=>x.coin==="USDT")||{};return num(a.totalEquity||c.equity||c.walletBalance);}
function btcPosition(p={}){return (p?.result?.list||[]).find(x=>String(x.symbol)===SYMBOL&&num(x.size)>0)||null;}
function openTranches(state={}){return (state.tranches||[]).filter(x=>String(x.status||"OPEN")==="OPEN");}
function qstr(v,step){const d=String(step||"0.001").split(".")[1]?.length||3;return Number(v).toFixed(Math.min(8,d)).replace(/0+$/,"").replace(/\.$/,"");}
async function filter(api){const p=await api.market("/v5/market/instruments-info",{category:"linear",symbol:SYMBOL,limit:1}),x=p?.result?.list?.[0];if(!x)throw new Error("BTCUSDT_INSTRUMENT_NOT_FOUND");return normalizeBybitFilter(x);}
async function fill(api,orderId){for(let i=0;i<10;i++){const p=await api.orderStatus(SYMBOL,orderId),x=p?.result?.list?.[0],q=num(x?.cumExecQty),a=num(x?.avgPrice);if(q>0&&a>0)return {ok:true,qty:q,avgPrice:a,status:x.orderStatus};await sleep(200);}return {ok:false,reason:"BTC_FILL_TIMEOUT"};}
function leverageFor(cfg,setup,ddMult=1,scale={}){let x=setup?.strength==="A_PLUS"?num(cfg.leverage?.aPlus||11):setup?.strength==="STRONG"?num(cfg.leverage?.strong||8):num(cfg.leverage?.normal||6);x+=Math.max(0,Math.round(num(scale?.leverageBonus)));if(setup?.regime==="RANGE"||setup?.regime==="SQUEEZE")x=Math.min(x,6);if(ddMult<.8)x=Math.min(x,5);if(ddMult<.6)x=Math.min(x,4);return Math.max(num(cfg.leverage?.min)||1,Math.min(num(cfg.leverage?.max)||15,x));}
function tighten(side,current,candidate){if(!(candidate>0))return current;if(!(current>0))return candidate;return side==="Buy"?Math.max(current,candidate):Math.min(current,candidate);}
function rewardToTarget(side,entry,target,qty){if(!(entry>0&&target>0&&qty>0))return 0;return Math.max(0,side==="Buy"?target-entry:entry-target)*qty;}
function clusterPlan(state={},position=null,lastSetup=null){const t=openTranches(state),q=t.reduce((s,x)=>s+Math.abs(num(x.qty)),0);if(!t.length&&!position)return null;const side=String(position?.side||t[0]?.side||""),entry=num(position?.avgPrice)||(q>0?t.reduce((s,x)=>s+num(x.entry)*Math.abs(num(x.qty)),0)/q:0),sl=num(position?.stopLoss)||num(state.aggregateStop),latest=t.at(-1)||{},risk=activeRiskUsd(t),target=num(state.virtualTarget||latest.tp||lastSetup?.tp),qty=num(position?.size)||q;return {symbol:SYMBOL,side,qty,entry,sl,managedSl:sl,tp:target,riskUsd:risk,rewardUsd:rewardToTarget(side,entry,target,qty),rr:num(latest.rr||lastSetup?.rr),leverage:num(position?.leverage||latest.leverage),orderId:latest.orderId||latest.id||null,createdAtMs:num(latest.createdAt),mode:state.executionMode||"PAPER",setup:latest.setup||lastSetup?.setup,regime:lastSetup?.regime||state.lastRegime,tickSize:num(latest.tickSize),trancheCount:t.length};}

function positionRisk(side,entry,sl,qty,equity){if(!(sl>0))return Math.max(.01,num(equity));if(side==="Buy"&&sl>=entry)return 0;if(side==="Sell"&&sl<=entry)return 0;return Math.abs(entry-sl)*qty;}
function addReconciledTranche(state,position,qty,equity,suffix="FULL"){
  const side=String(position?.side||""),entry=num(position?.avgPrice),sl=num(position?.stopLoss),actual=Math.max(0,num(qty)),created=num(position?.createdTime)||Date.now();if(!(actual>0&&entry>0&&side))return state;
  const id=`RECON-${created}-${side}-${suffix}-${Math.round(actual*1e6)}`,risk=positionRisk(side,entry,sl,actual,equity),tp=num(position?.takeProfit)||num(state.virtualTarget);
  return addTranche(state,{id,orderId:id,side,qty:actual,entry,sl,managedSl:sl,tp,rr:0,setup:"EXCHANGE_POSITION_RECONCILED",regime:state.lastRegime||"RECONCILED",strength:"NORMAL",initialRiskUsd:risk,riskUsd:risk,initialMarginUsd:num(position?.positionIM),leverage:num(position?.leverage),tickSize:0,equityUsd:equity,capitalBaseUsd:num(state.lastCapitalBaseUsd)||equity,reconciledExternalPosition:true,reconciledAt:Date.now(),nativeProtectionMissing:!(sl>0)});
}
function reconcileTranchesToPosition(state={},position=null,equity=0){
  let next=state,t=openTranches(next);if(!position||num(position.size)<=0){if(t.length)return {state:closeAllTranches(next,{closeReason:"EXCHANGE_POSITION_FLAT"}),changed:true,reason:"EXCHANGE_POSITION_FLAT"};return {state:next,changed:false,reason:null};}
  const actual=Math.abs(num(position.size)),side=String(position.side||""),sl=num(position.stopLoss),tol=1e-9;
  if(t.some(x=>String(x.side||"")!==side)){next=closeAllTranches(next,{closeReason:"EXCHANGE_POSITION_SIDE_RECONCILED"});t=[];}
  let changed=false,reason=null;
  if(!t.length){next=addReconciledTranche(next,position,actual,equity,"FULL");changed=true;reason="EXCHANGE_POSITION_ADOPTED";}
  else{
    const total=t.reduce((s,x)=>s+Math.abs(num(x.qty)),0);
    if(total>actual+tol){const ratio=actual/total;next={...next,tranches:(next.tranches||[]).map(x=>String(x.status||"OPEN")!=="OPEN"?x:{...x,qty:num(x.qty)*ratio,reconciledQtyScale:ratio,reconciledAt:Date.now()})};changed=true;reason="EXCHANGE_POSITION_QTY_REDUCED";}
    else if(actual>total+tol){next=addReconciledTranche(next,position,actual-total,equity,`DELTA-${Math.round(total*1e6)}`);changed=true;reason="EXCHANGE_POSITION_QTY_ADOPTED";}
  }
  if(sl>0){for(const x of openTranches(next))next=updateTrancheProtection(next,x.id,sl);if(num(next.aggregateStop)!==sl){next.aggregateStop=sl;changed=true;reason=reason||"EXCHANGE_STOP_RECONCILED";}}
  if(changed)next.lastPositionReconcile={at:iso(),reason,side,size:actual,entry:num(position.avgPrice),stopLoss:sl};return {state:next,changed,reason};
}

async function manageCluster(env,api,state,position,market,filters){
  const events=[];if(!position)return {state,events,position:null,cut:false};
  const side=String(position.side),mark=num(position.markPrice||market.mark||market.price),t=openTranches(state),latest=t.at(-1);if(!latest)return {state,events,position,cut:false};
  let currentStop=num(position.stopLoss||state.aggregateStop);
  if(!(currentStop>0)&&liveMode(env)==="LIVE"){
    const emergencyDist=Math.max(filters.tickSize*10,num(market.range5?.width)*.70,num(market.range15?.width)*.35,mark*.0040),emergency=roundTick(side==="Buy"?mark-emergencyDist:mark+emergencyDist,filters.tickSize);
    await api.tradingStop({symbol:SYMBOL,tpslMode:"Full",positionIdx:0,stopLoss:String(emergency),slTriggerBy:"MarkPrice"});const verify=btcPosition(await api.positions());currentStop=num(verify?.stopLoss);
    if(!(currentStop>0)){try{await api.order({symbol:SYMBOL,side:side==="Buy"?"Sell":"Buy",orderType:"Market",qty:String(position.size),reduceOnly:true,positionIdx:0});}catch{}state=closeAllTranches(state,{closeReason:"UNPROTECTED_POSITION_EMERGENCY_FLAT"});state.aggregateStop=0;events.push({symbol:SYMBOL,cutExecuted:true,verdict:"CUT",reason:"UNPROTECTED_POSITION_EMERGENCY_FLAT",markPrice:mark,r:0});return {state,events,position:null,cut:true};}
    for(const x of t)state=updateTrancheProtection(state,x.id,currentStop);state.aggregateStop=currentStop;state.lastProtectionAt=iso();events.push({symbol:SYMBOL,managed:true,verdict:"TIGHTEN",phase:"EMERGENCY_PROTECT",previousSl:0,nextSl:currentStop,r:0,peakR:0});
  }
  const baseSl=num(latest.sl)||currentStop,d=Math.max(filters.tickSize*4,Math.abs(num(latest.entry)-baseSl)),favour=side==="Buy"?mark-num(latest.entry):num(latest.entry)-mark,r=favour/d;
  let desired=currentStop,phase=null;if(r>=.75){const feeBuffer=Math.max(filters.tickSize*2,num(latest.entry)*.0007),be=side==="Buy"?num(latest.entry)+feeBuffer:num(latest.entry)-feeBuffer;desired=tighten(side,desired,be);phase="PROFIT_LOCK";}if(r>=1.50){const trailDist=Math.max(filters.tickSize*6,num(market.range5?.width)*.16,mark*.0014),trail=side==="Buy"?mark-trailDist:mark+trailDist;desired=tighten(side,desired,trail);phase="TRAIL";}
  desired=roundTick(desired,filters.tickSize);const tighter=desired>0&&(side==="Buy"?desired>currentStop+filters.tickSize/2:currentStop<=0||desired<currentStop-filters.tickSize/2);
  if(tighter&&liveMode(env)==="LIVE"){await api.tradingStop({symbol:SYMBOL,tpslMode:"Full",positionIdx:0,stopLoss:String(desired),slTriggerBy:"MarkPrice"});for(const x of t)state=updateTrancheProtection(state,x.id,desired);state.aggregateStop=desired;state.lastProtectionAt=iso();events.push({symbol:SYMBOL,managed:true,verdict:"TIGHTEN",phase:phase||"PROTECT",previousSl:currentStop,nextSl:desired,r,peakR:r});currentStop=desired;}
  const against=side==="Buy"?((market.regime==="TREND_DOWN"||market.regime==="BREAKOUT_DOWN")&&num(market.trades?.aggressorImbalance)<-.12&&num(market.book?.imbalance)<.05):((market.regime==="TREND_UP"||market.regime==="BREAKOUT_UP")&&num(market.trades?.aggressorImbalance)>.12&&num(market.book?.imbalance)>-.05);state.invalidationCount=against?num(state.invalidationCount)+1:0;
  if(state.invalidationCount>=2&&liveMode(env)==="LIVE"){const out=await api.order({symbol:SYMBOL,side:side==="Buy"?"Sell":"Buy",orderType:"Market",qty:String(position.size),reduceOnly:true,positionIdx:0});state=closeAllTranches(state,{closeReason:"STRUCTURE_FLOW_INVALIDATION"});state.invalidationCount=0;state.aggregateStop=0;state.lastCutAt=iso();events.push({symbol:SYMBOL,cutExecuted:true,verdict:"CUT",reason:"STRUCTURE_FLOW_INVALIDATION",orderId:out?.result?.orderId,markPrice:mark,r});return {state,events,position:null,cut:true};}
  return {state,events,position,cut:false};
}

export async function runBtcHyperscale(env,{entryBlockReason=null}={}){
  const cfg=bybitAutoConfig(env),api=bybitV5(env),mode=liveMode(env),[wallet,positions,filters,market]=await Promise.all([api.wallet(),api.positions(),filter(api),buildBtcMarketState(env,api,SYMBOL)]),equity=walletEquity(wallet);if(!(equity>0))return {version:"BYBIT-BTC-HYPERSCALE-2.5",mode,executed:false,reason:"EQUITY_INVALID",equity,market};
  let state=await get(env);state={...state,version:"BYBIT-BTC-HYPERSCALE-2.5",executionMode:mode,highWaterUsd:Math.max(equity,num(state.highWaterUsd)),lastEquityUsd:equity,lastCycleAt:iso(),lastRegime:market.regime};
  let pos=btcPosition(positions);const reconciled=reconcileTranchesToPosition(state,pos,equity);state=reconciled.state;if(reconciled.changed)await put(env,state);
  const managed=await manageCluster(env,api,state,pos,market,filters);state=managed.state;pos=managed.position;if(managed.cut){state.openPlans={};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:"SMART_CUT",market,lifecycles:managed.events,state,plan:null,scan:{best:null,qualified:0,reason:"CUT_MANAGEMENT"}};}

  const picked=selectBtcSetup(market),scan={best:picked.ok?picked.setup:null,qualified:picked.ok?1:0,analyzed:1,rawCandidates:picked.ok?1:0,universe:{count:1,symbols:[SYMBOL]},reason:picked.ok?null:picked.reason,scannedAt:Date.now()};
  if(!picked.ok||entryBlockReason){state.openPlans=pos?{[SYMBOL]:clusterPlan(state,pos,picked.setup)}:{};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:entryBlockReason||picked.reason,market,scan,lifecycles:managed.events,state,plan:state.openPlans[SYMBOL]||null};}

  const setup=picked.setup,preRisk=btcRiskDecision({cfg,equityUsd:equity,state,setup,markPrice:market.mark||market.price});if(!preRisk.ok){state.lastRiskReject={at:iso(),reason:preRisk.reason};state.openPlans=pos?{[SYMBOL]:clusterPlan(state,pos,setup)}:{};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:preRisk.reason,risk:preRisk,market,scan,lifecycles:managed.events,state,plan:state.openPlans[SYMBOL]||null};}
  const leverage=leverageFor(cfg,setup,preRisk.multiplier,preRisk.scale),sized=sizeBtcSetup({setup,riskUsd:preRisk.candidateRiskUsd,maxRiskUsd:preRisk.maxCandidateRiskUsd,filters,leverage,equityUsd:equity,capitalBaseUsd:preRisk.capital?.capitalBaseUsd,marginCapPct:preRisk.scale?.marginCapPct});if(!sized.ok){state.lastRiskReject={at:iso(),reason:sized.reason};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:sized.reason,risk:preRisk,size:sized,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup)};}
  const risk=btcRiskDecision({cfg,equityUsd:equity,state,setup,markPrice:market.mark||market.price,candidateInitialMarginUsd:sized.initialMarginUsd,candidateActualRiskUsd:sized.actualRiskUsd});if(!risk.ok){state.lastRiskReject={at:iso(),reason:risk.reason};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:risk.reason,risk,size:sized,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup)};}
  state.lastCapitalBaseUsd=num(risk.capital?.capitalBaseUsd||preRisk.capital?.capitalBaseUsd);state.lastScaleTierUsd=num(risk.scale?.tierEquityUsd||preRisk.scale?.tierEquityUsd);state.lastSizing={at:iso(),qty:sized.qty,targetRiskUsd:sized.targetRiskUsd,actualRiskUsd:sized.actualRiskUsd,costReserveUsd:sized.costReserveUsd,policy:sized.selectionPolicy};
  if(mode!=="LIVE"){state.lastPaperCandidate={at:iso(),setup,risk,size:sized};state.openPlans=pos?{[SYMBOL]:clusterPlan(state,pos,setup)}:{};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:"BTC_LIVE_ACK_REQUIRED_PAPER_SIGNAL",risk,size:sized,market,scan,lifecycles:managed.events,state,plan:state.openPlans[SYMBOL]||null,candidate:setup};}

  await api.setLeverage(SYMBOL,leverage);const existingStop=num(pos?.stopLoss||state.aggregateStop),initialStop=roundTick(setup.sl,filters.tickSize),body={symbol:SYMBOL,side:setup.side,orderType:"Market",qty:qstr(sized.qty,filters.qtyStep),positionIdx:0};if(!pos){body.stopLoss=String(initialStop);body.slTriggerBy="MarkPrice";body.tpslMode="Full";if(setup.setup.includes("RANGE")){body.takeProfit=String(roundTick(setup.tp,filters.tickSize));body.tpTriggerBy="MarkPrice";}}
  const order=await api.order(body),orderId=String(order?.result?.orderId||"");if(!orderId)throw new Error("BTC_ORDER_ID_MISSING");const f=await fill(api,orderId);if(!f.ok)throw new Error(f.reason);
  const entry=f.avgPrice,stopDist=Math.abs(num(setup.entry)-num(setup.sl)),candidateStop=roundTick(setup.side==="Buy"?entry-stopDist:entry+stopDist,filters.tickSize),effectiveStop=tighten(setup.side,existingStop,candidateStop),actualRisk=Math.abs(entry-effectiveStop)*f.qty;const posAfter=btcPosition(await api.positions());if(!posAfter)throw new Error("BTC_POSITION_MISSING_AFTER_FILL");
  const protectionBody={symbol:SYMBOL,tpslMode:"Full",positionIdx:0,stopLoss:String(roundTick(effectiveStop,filters.tickSize)),slTriggerBy:"MarkPrice"};if(setup.setup.includes("RANGE"))protectionBody.takeProfit=String(roundTick(setup.side==="Buy"?entry+stopDist*1.45:entry-stopDist*1.45,filters.tickSize));await api.tradingStop(protectionBody);
  const verified=btcPosition(await api.positions());if(!verified||!(num(verified.stopLoss)>0)){try{await api.order({symbol:SYMBOL,side:setup.side==="Buy"?"Sell":"Buy",orderType:"Market",qty:String(posAfter.size),reduceOnly:true,positionIdx:0});}catch{}throw new Error("BTC_NATIVE_STOP_VERIFICATION_FAILED_EMERGENCY_FLAT");}
  state=addTranche(state,{orderId,side:setup.side,qty:f.qty,entry,sl:effectiveStop,tp:setup.tp,rr:setup.rr,setup:setup.setup,regime:setup.regime,strength:setup.strength,initialRiskUsd:actualRisk,riskUsd:actualRisk,costReserveUsd:sized.costReserveUsd,initialMarginUsd:f.qty*entry/leverage,leverage,tickSize:filters.tickSize,equityUsd:equity,capitalBaseUsd:state.lastCapitalBaseUsd,scaleRiskMult:num(risk.scale?.riskMult),reason:setup.reason,sizingPolicy:sized.selectionPolicy});state.aggregateStop=num(verified.stopLoss);state.virtualTarget=setup.tp;state.lastTradeAt=Date.now();state.lastEntryAt=iso();state.lastEntrySetup=setup.setup;state.highWaterUsd=Math.max(num(state.highWaterUsd),equity);state.openPlans={[SYMBOL]:clusterPlan(state,verified,setup)};await put(env,state);
  const plan={...state.openPlans[SYMBOL],orderId,qty:f.qty,entry,sl:effectiveStop,managedSl:effectiveStop,tp:setup.tp,riskUsd:actualRisk,rewardUsd:Math.abs(setup.tp-entry)*f.qty,rr:setup.rr,leverage,mode:"LIVE",createdAtMs:Date.now(),tickSize:filters.tickSize,setup:setup.setup,regime:setup.regime,capitalBaseUsd:state.lastCapitalBaseUsd,scaleTierUsd:state.lastScaleTierUsd,scaleRiskMult:num(risk.scale?.riskMult),costReserveUsd:sized.costReserveUsd,sizingPolicy:sized.selectionPolicy};
  return {version:state.version,mode,equity,executed:true,reason:"BTC_ENTRY_EXECUTED",risk,size:sized,market,scan,lifecycles:managed.events,state,plan,candidate:setup};
}

export async function getBtcHyperscaleState(env){return get(env);}
export const BTC_HYPERSCALE_ENGINE_VERSION="BYBIT-BTC-HYPERSCALE-2.6-RECONCILED";
