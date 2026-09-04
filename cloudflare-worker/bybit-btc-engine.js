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
function leverageFor(cfg,setup,ddMult=1){let x=setup?.strength==="A_PLUS"?10:setup?.strength==="STRONG"?7:5;if(setup?.regime==="RANGE"||setup?.regime==="SQUEEZE")x=Math.min(x,5);if(ddMult<.8)x=Math.min(x,4);return Math.max(num(cfg.leverage?.min)||1,Math.min(num(cfg.leverage?.max)||15,x));}
function tighten(side,current,candidate){if(!(candidate>0))return current;if(!(current>0))return candidate;return side==="Buy"?Math.max(current,candidate):Math.min(current,candidate);}
function clusterPlan(state={},position=null,lastSetup=null){const t=openTranches(state),q=t.reduce((s,x)=>s+Math.abs(num(x.qty)),0);if(!t.length&&!position)return null;const side=String(position?.side||t[0]?.side||""),entry=num(position?.avgPrice)||(q>0?t.reduce((s,x)=>s+num(x.entry)*Math.abs(num(x.qty)),0)/q:0),sl=num(position?.stopLoss)||num(state.aggregateStop),latest=t.at(-1)||{},risk=activeRiskUsd(t);return {symbol:SYMBOL,side,qty:num(position?.size)||q,entry,sl,managedSl:sl,tp:num(state.virtualTarget||latest.tp||lastSetup?.tp),riskUsd:risk,rewardUsd:Math.max(0,num(state.virtualTarget||latest.tp)-entry)*Math.max(0,num(position?.size)||q),rr:num(latest.rr||lastSetup?.rr),leverage:num(position?.leverage||latest.leverage),orderId:latest.orderId||null,createdAtMs:num(latest.createdAt),mode:state.executionMode||"PAPER",setup:latest.setup||lastSetup?.setup,regime:lastSetup?.regime||state.lastRegime,tickSize:num(latest.tickSize),trancheCount:t.length};}
function scaleTranchesToPosition(state={},position=null){
  const t=openTranches(state);if(!position||num(position.size)<=0){if(t.length)return closeAllTranches(state,{closeReason:"EXCHANGE_POSITION_FLAT"});return state;}
  const actual=num(position.size),total=t.reduce((s,x)=>s+Math.abs(num(x.qty)),0);if(!(total>actual+1e-12))return state;
  const ratio=actual/total;return {...state,tranches:(state.tranches||[]).map(x=>String(x.status||"OPEN")!=="OPEN"?x:{...x,qty:num(x.qty)*ratio,reconciledQtyScale:ratio,reconciledAt:Date.now()})};
}

async function manageCluster(env,api,state,position,market,filters){
  const events=[];if(!position)return {state,events,position:null,cut:false};
  const side=String(position.side),mark=num(position.markPrice||market.mark||market.price),avg=num(position.avgPrice),currentStop=num(position.stopLoss||state.aggregateStop),t=openTranches(state),latest=t.at(-1);
  if(!latest)return {state,events,position,cut:false};
  const d=Math.max(filters.tickSize*4,Math.abs(num(latest.entry)-num(latest.sl))),favour=side==="Buy"?mark-num(latest.entry):num(latest.entry)-mark,r=favour/d;
  let desired=currentStop,phase=null;
  if(r>=.75){const feeBuffer=Math.max(filters.tickSize*2,num(latest.entry)*.0007),be=side==="Buy"?num(latest.entry)+feeBuffer:num(latest.entry)-feeBuffer;desired=tighten(side,desired,be);phase="PROFIT_LOCK";}
  if(r>=1.50){const trailDist=Math.max(filters.tickSize*6,num(market.range5?.width)*.16,mark*.0014),trail=side==="Buy"?mark-trailDist:mark+trailDist;desired=tighten(side,desired,trail);phase="TRAIL";}
  desired=roundTick(desired,filters.tickSize);
  const tighter=desired>0&&(side==="Buy"?desired>currentStop+filters.tickSize/2:currentStop<=0||desired<currentStop-filters.tickSize/2);
  if(tighter&&liveMode(env)==="LIVE"){
    await api.tradingStop({symbol:SYMBOL,tpslMode:"Full",positionIdx:0,stopLoss:String(desired),slTriggerBy:"MarkPrice"});
    for(const x of t)state=updateTrancheProtection(state,x.id,desired);state.aggregateStop=desired;state.lastProtectionAt=iso();events.push({symbol:SYMBOL,managed:true,verdict:"TIGHTEN",phase:phase||"PROTECT",previousSl:currentStop,nextSl:desired,r,peakR:r});
  }
  // Two-cycle structural + executed-flow invalidation. Avoid a single noisy print causing an exit.
  const against=side==="Buy"?((market.regime==="TREND_DOWN"||market.regime==="BREAKOUT_DOWN")&&num(market.trades?.aggressorImbalance)<-.12&&num(market.book?.imbalance)<.05):((market.regime==="TREND_UP"||market.regime==="BREAKOUT_UP")&&num(market.trades?.aggressorImbalance)>.12&&num(market.book?.imbalance)>-.05);
  state.invalidationCount=against?num(state.invalidationCount)+1:0;
  if(state.invalidationCount>=2&&liveMode(env)==="LIVE"){
    const out=await api.order({symbol:SYMBOL,side:side==="Buy"?"Sell":"Buy",orderType:"Market",qty:String(position.size),reduceOnly:true,positionIdx:0});
    state=closeAllTranches(state,{closeReason:"STRUCTURE_FLOW_INVALIDATION"});state.invalidationCount=0;state.aggregateStop=0;state.lastCutAt=iso();events.push({symbol:SYMBOL,cutExecuted:true,verdict:"CUT",reason:"STRUCTURE_FLOW_INVALIDATION",orderId:out?.result?.orderId,markPrice:mark,r});return {state,events,position:null,cut:true};
  }
  return {state,events,position,cut:false};
}

export async function runBtcHyperscale(env,{entryBlockReason=null}={}){
  const cfg=bybitAutoConfig(env),api=bybitV5(env),mode=liveMode(env),[wallet,positions,filters,market]=await Promise.all([api.wallet(),api.positions(),filter(api),buildBtcMarketState(env,api,SYMBOL)]),equity=walletEquity(wallet);if(!(equity>0))return {version:"BYBIT-BTC-HYPERSCALE-2.0",mode,executed:false,reason:"EQUITY_INVALID",equity,market};
  let state=await get(env);state={...state,version:"BYBIT-BTC-HYPERSCALE-2.0",executionMode:mode,highWaterUsd:Math.max(equity,num(state.highWaterUsd)),lastEquityUsd:equity,lastCycleAt:iso(),lastRegime:market.regime};
  let pos=btcPosition(positions);state=scaleTranchesToPosition(state,pos);
  const managed=await manageCluster(env,api,state,pos,market,filters);state=managed.state;pos=managed.position;
  if(managed.cut){state.openPlans={};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:"SMART_CUT",market,lifecycles:managed.events,state,plan:null,scan:{best:null,qualified:0,reason:"CUT_MANAGEMENT"}};}

  const picked=selectBtcSetup(market),scan={best:picked.ok?picked.setup:null,qualified:picked.ok?1:0,analyzed:1,rawCandidates:picked.ok?1:0,universe:{count:1,symbols:[SYMBOL]},reason:picked.ok?null:picked.reason,scannedAt:Date.now()};
  if(!picked.ok||entryBlockReason){state.openPlans=pos?{[SYMBOL]:clusterPlan(state,pos,picked.setup)}:{};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:entryBlockReason||picked.reason,market,scan,lifecycles:managed.events,state,plan:state.openPlans[SYMBOL]||null};}

  const setup=picked.setup,preRisk=btcRiskDecision({cfg,equityUsd:equity,state,setup,markPrice:market.mark||market.price});
  if(!preRisk.ok){state.lastRiskReject={at:iso(),reason:preRisk.reason};state.openPlans=pos?{[SYMBOL]:clusterPlan(state,pos,setup)}:{};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:preRisk.reason,risk:preRisk,market,scan,lifecycles:managed.events,state,plan:state.openPlans[SYMBOL]||null};}
  const leverage=leverageFor(cfg,setup,preRisk.multiplier),sized=sizeBtcSetup({setup,riskUsd:preRisk.candidateRiskUsd,filters,leverage,equityUsd:equity});if(!sized.ok){state.lastRiskReject={at:iso(),reason:sized.reason};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:sized.reason,risk:preRisk,size:sized,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup)};}
  const risk=btcRiskDecision({cfg,equityUsd:equity,state,setup,markPrice:market.mark||market.price,candidateInitialMarginUsd:sized.initialMarginUsd});if(!risk.ok){await put(env,state);return {version:state.version,mode,equity,executed:false,reason:risk.reason,risk,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup)};}
  if(mode!=="LIVE"){state.lastPaperCandidate={at:iso(),setup,risk,size:sized};state.openPlans=pos?{[SYMBOL]:clusterPlan(state,pos,setup)}:{};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:"BTC_LIVE_ACK_REQUIRED_PAPER_SIGNAL",risk,size:sized,market,scan,lifecycles:managed.events,state,plan:state.openPlans[SYMBOL]||null,candidate:setup};}

  await api.setLeverage(SYMBOL,leverage);
  const existingStop=num(pos?.stopLoss||state.aggregateStop),initialStop=roundTick(setup.sl,filters.tickSize),body={symbol:SYMBOL,side:setup.side,orderType:"Market",qty:qstr(sized.qty,filters.qtyStep),positionIdx:0};
  if(!pos){body.stopLoss=String(initialStop);body.slTriggerBy="MarkPrice";body.tpslMode="Full";if(setup.setup.includes("RANGE")){body.takeProfit=String(roundTick(setup.tp,filters.tickSize));body.tpTriggerBy="MarkPrice";}}
  const order=await api.order(body),orderId=String(order?.result?.orderId||"");if(!orderId)throw new Error("BTC_ORDER_ID_MISSING");const f=await fill(api,orderId);if(!f.ok)throw new Error(f.reason);
  const entry=f.avgPrice,stopDist=Math.abs(num(setup.entry)-num(setup.sl)),candidateStop=roundTick(setup.side==="Buy"?entry-stopDist:entry+stopDist,filters.tickSize),effectiveStop=tighten(setup.side,existingStop,candidateStop),actualRisk=Math.abs(entry-effectiveStop)*f.qty;
  const posAfter=btcPosition(await api.positions());if(!posAfter)throw new Error("BTC_POSITION_MISSING_AFTER_FILL");
  const protectionBody={symbol:SYMBOL,tpslMode:"Full",positionIdx:0,stopLoss:String(roundTick(effectiveStop,filters.tickSize)),slTriggerBy:"MarkPrice"};if(setup.setup.includes("RANGE"))protectionBody.takeProfit=String(roundTick(setup.side==="Buy"?entry+stopDist*1.45:entry-stopDist*1.45,filters.tickSize));
  await api.tradingStop(protectionBody);
  const verified=btcPosition(await api.positions());if(!verified||!(num(verified.stopLoss)>0)){
    try{await api.order({symbol:SYMBOL,side:setup.side==="Buy"?"Sell":"Buy",orderType:"Market",qty:String(posAfter.size),reduceOnly:true,positionIdx:0});}catch{}
    throw new Error("BTC_NATIVE_STOP_VERIFICATION_FAILED_EMERGENCY_FLAT");
  }
  state=addTranche(state,{orderId,side:setup.side,qty:f.qty,entry,sl:effectiveStop,tp:setup.tp,rr:setup.rr,setup:setup.setup,regime:setup.regime,strength:setup.strength,initialRiskUsd:actualRisk,riskUsd:actualRisk,initialMarginUsd:f.qty*entry/leverage,leverage,tickSize:filters.tickSize,equityUsd:equity,reason:setup.reason});state.aggregateStop=num(verified.stopLoss);state.virtualTarget=setup.tp;state.lastTradeAt=Date.now();state.lastEntryAt=iso();state.lastEntrySetup=setup.setup;state.highWaterUsd=Math.max(num(state.highWaterUsd),equity);state.openPlans={[SYMBOL]:clusterPlan(state,verified,setup)};await put(env,state);
  const plan={...state.openPlans[SYMBOL],orderId,qty:f.qty,entry,sl:effectiveStop,managedSl:effectiveStop,tp:setup.tp,riskUsd:actualRisk,rewardUsd:Math.abs(setup.tp-entry)*f.qty,rr:setup.rr,leverage,mode:"LIVE",createdAtMs:Date.now(),tickSize:filters.tickSize,setup:setup.setup,regime:setup.regime};
  return {version:state.version,mode,equity,executed:true,reason:"BTC_ENTRY_EXECUTED",risk,size:sized,market,scan,lifecycles:managed.events,state,plan,candidate:setup};
}

export async function getBtcHyperscaleState(env){return get(env);}
export const BTC_HYPERSCALE_ENGINE_VERSION="BYBIT-BTC-HYPERSCALE-2.0";
