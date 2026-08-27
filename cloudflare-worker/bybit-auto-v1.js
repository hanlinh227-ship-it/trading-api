import {bybitAutoConfig,bybitExecutionMode} from "./bybit-auto-config.js";
import {bybitV5,roundTick} from "./bybit-v5-client.js";
import {scanBybitAuto,sizeBybitAuto} from "./bybit-scalp-engine.js";
import {prepareBybitScalpForReview,reviewBybitScalp,revalidateBybitScalpAfterAi} from "./bybit-ai-scalp-gate.js";
import {recordBybitLearningEvent} from "./bybit-learning-engine.js";
import {reconcileBybitPaperPlans} from "./bybit-shadow-lifecycle.js";
import {bybitRiskPreflight,validateProtectionGeometry} from "./bybit-risk-guard.js";
import {manageBybitScalpPosition} from "./bybit-position-manager.js";

const KEY="bybit:auto:v1:state";
const PNL_RECONCILE_GRACE_MS=15*60*1000;
const now=()=>Date.now(),iso=()=>new Date().toISOString(),envBool=v=>String(v||"").toLowerCase()==="true";
async function get(env){try{return await env.TRADING_STATE?.get(KEY,{type:"json"})||{};}catch{return {};}}
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}
function day(){return new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Bangkok",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());}
function dayStartMs(){return Date.parse(`${day()}T00:00:00+07:00`);}
function reset(s){if(s.day===day())return s;return {...s,day:day(),trades:0,realizedUsd:0,lossStreak:0,pauseUntil:0,exchangeClosedTrades:0,openPlans:s.openPlans||{},reconcileQuarantine:s.reconcileQuarantine||[],dayRolloverAt:iso()};}
function liveGuard(env,mode){if(mode!=="LIVE")return null;if(!envBool(env.BYBIT_AUTO_LIVE_ACK))return "LIVE_ACK_REQUIRED";return null;}
function tpForReward(side,entry,qty,rewardUsd){const q=Math.abs(Number(qty||0));if(!(q>0))return null;const d=Number(rewardUsd||0)/q;return side==="Buy"?entry+d:entry-d;}
async function fill(api,symbol,orderId){for(let i=0;i<8;i++){const p=await api.orderStatus(symbol,orderId),x=p?.result?.list?.[0],qty=Number(x?.cumExecQty||0),avg=Number(x?.avgPrice||0);if(qty>0&&avg>0)return {ok:true,orderId,executedQty:qty,avgPrice:avg,status:x.orderStatus};await new Promise(r=>setTimeout(r,250));}return {ok:false,reason:"MARKET_FILL_TIMEOUT",orderId};}
async function emergencyFlat(api,setup,qty){try{return await api.order({symbol:setup.symbol,side:setup.side==="Buy"?"Sell":"Buy",orderType:"Market",qty:String(qty),reduceOnly:true,positionIdx:0});}catch{return null;}}
async function learn(env,event){try{await recordBybitLearningEvent(env,event);}catch{}}
const closedAt=x=>Number(x?.updatedTime||x?.createdTime||0);
const closedKey=x=>String(x?.orderId||x?.execId||`${x?.symbol||""}:${closedAt(x)}:${x?.closedPnl||""}:${x?.closedSize||x?.qty||""}`);
const planCreated=plan=>Number(plan?.createdAtMs||Date.parse(plan?.createdAt||"")||0);
function closedHistoryStart(){return dayStartMs();}
function lastPnlHealthyMs(state){const direct=Number(state?.lastPnlReconcileHealthyAtMs||0);if(direct>0)return direct;const parsed=Date.parse(state?.lastPnlReconcile?.at||"");return Number.isFinite(parsed)?parsed:0;}
function livePositionRiskState(state,positions=[]){
  const live=new Set((positions||[]).filter(x=>Number(x?.size||0)>0).map(x=>String(x.symbol||"")));
  const source=state?.openPlans||{},openPlans=Object.fromEntries(Object.entries(source).filter(([symbol,p])=>String(p?.mode||"").toUpperCase()!=="LIVE"||live.has(symbol)));
  return {...state,openPlans};
}
function quarantineUnresolvedPlan(state,symbol,plan,reason,historyStart){
  const row={symbol,mode:"LIVE",reason,quarantinedAt:iso(),createdAtMs:planCreated(plan)||null,historyStart,orderId:plan?.orderId||null,side:plan?.side||null,entry:plan?.entry||null,riskUsd:plan?.riskUsd||null,rewardUsd:plan?.rewardUsd||null,plan:{...plan,closeReconcileStatus:reason}};
  const previous=Array.isArray(state.reconcileQuarantine)?state.reconcileQuarantine:[];
  state.reconcileQuarantine=[row,...previous.filter(x=>!(x?.symbol===symbol&&String(x?.orderId||"")===String(row.orderId||"")))].slice(0,100);
  delete state.openPlans[symbol];
  return row;
}
async function fetchClosedPnlAll(api,startTime,endTime){
  const rows=[],seen=new Set(),seenCursor=new Set();let cursor="",requests=0,truncated=false;
  for(let i=0;i<20;i++){
    const p=await api.closedPnl(startTime,endTime,cursor);requests++;
    const list=p?.result?.list||[];for(const x of list){const k=closedKey(x);if(!seen.has(k)){seen.add(k);rows.push(x);}}
    const next=String(p?.result?.nextPageCursor||"");if(!next||seenCursor.has(next)){cursor="";break;}seenCursor.add(next);cursor=next;
  }
  if(cursor)truncated=true;rows.sort((a,b)=>closedAt(b)-closedAt(a));return {rows,pages:requests,truncated,startTime,endTime};
}
function rowMatchesPlan(x,symbol,plan){
  if(String(x?.symbol||"")!==symbol)return false;
  const created=planCreated(plan),t=closedAt(x);if(!(created>0&&t>=created-5000))return false;
  const side=String(x?.side||"");if(side&&plan?.side&&side!==String(plan.side))return false;
  const planEntry=Number(plan?.entry||0),rowEntry=Number(x?.avgEntryPrice||0),tick=Math.abs(Number(plan?.tickSize||plan?.filters?.tickSize||0));
  if(planEntry>0&&rowEntry>0){const tol=Math.max(tick*3,planEntry*.0015);if(Math.abs(rowEntry-planEntry)>tol)return false;}return true;
}
function aggregateLiveOutcome(symbol,plan,rows){
  const matching=rows.filter(x=>rowMatchesPlan(x,symbol,plan));if(!matching.length)return null;
  const netPnlUsd=matching.reduce((s,x)=>s+Number(x.closedPnl||0),0),feesUsd=matching.reduce((s,x)=>s+Math.abs(Number(x.openFee||0))+Math.abs(Number(x.closeFee||0)),0),riskUsd=Math.abs(Number(plan.riskUsd)||0),netR=riskUsd>0?netPnlUsd/riskUsd:null;
  const qty=matching.reduce((s,x)=>s+Math.abs(Number(x.closedSize||x.qty||0)),0),plannedQty=Math.abs(Number(plan.qty||0));if(plannedQty>0&&qty>0&&qty<plannedQty*.90)return null;
  let grossPnl=0,grossKnown=false;for(const x of matching){const q=Math.abs(Number(x.closedSize||x.qty||0)),entry=Number(x.avgEntryPrice||plan.entry||0),exit=Number(x.avgExitPrice||0);if(q>0&&entry>0&&exit>0){grossKnown=true;grossPnl+=(plan.side==="Buy"?exit-entry:entry-exit)*q;}}
  const rMultiple=grossKnown&&riskUsd>0?grossPnl/riskUsd:netR,latest=Math.max(...matching.map(closedAt)),created=planCreated(plan)||latest,holdSec=Math.max(0,Math.round((latest-created)/1000)),status=netPnlUsd>1e-9?"WIN":netPnlUsd<-1e-9?"LOSS":"BREAKEVEN",sourceId=matching.map(closedKey).sort().join("|").slice(0,160);
  return {status,authority:"BYBIT_CLOSED_PNL",sourceId,pnlUsd:grossKnown?grossPnl:netPnlUsd,netPnlUsd,rMultiple,netR,feesUsd,holdSec,closedAt:latest,closedRows:matching.length,closedQty:qty};
}
async function reconcileLiveClosedPlans(env,state,positions,closedRows,historyStart){
  const live=new Set((positions||[]).map(p=>String(p.symbol||""))),results=[];
  for(const [symbol,plan] of Object.entries(state.openPlans||{})){
    if(String(plan?.mode||"").toUpperCase()!=="LIVE"||live.has(symbol))continue;
    const out=aggregateLiveOutcome(symbol,plan,closedRows);
    if(!out){
      plan.closeReconcilePendingSince=plan.closeReconcilePendingSince||iso();const created=planCreated(plan),outside=created>0&&created<historyStart;
      if(outside){const q=quarantineUnresolvedPlan(state,symbol,plan,"OUTCOME_UNRESOLVED_OUTSIDE_DAILY_WINDOW",historyStart);results.push({symbol,reconciled:false,quarantined:true,reason:q.reason,createdAtMs:created||null,historyStart});continue;}
      plan.closeReconcileStatus="CLOSED_PENDING_RECONCILE";results.push({symbol,reconciled:false,reason:plan.closeReconcileStatus,createdAtMs:created||null,historyStart});continue;
    }
    const lifecycleId=String(plan.orderId||`${symbol}:${planCreated(plan)||0}`),eventId=`BYBIT_OUTCOME:LIVE:${lifecycleId}`;
    await recordBybitLearningEvent(env,{id:eventId,stage:"OUTCOME",mode:"LIVE",symbol,side:plan.side,strategy:plan.strategy,score:plan.score,rr:plan.rr,riskUsd:plan.riskUsd,rewardUsd:plan.rewardUsd,entry:plan.entry,sl:plan.initialSl||plan.sl,tp:plan.tp,leverage:plan.leverage,ai:plan.ai,postAi:plan.postAiQuote,execution:plan.execution,outcome:out,reason:`BYBIT_${out.status}`});
    delete state.openPlans[symbol];results.push({symbol,reconciled:true,status:out.status,netPnlUsd:out.netPnlUsd,netR:out.netR,closedRows:out.closedRows});
  }
  state.lastLiveOutcomeReconcile={at:iso(),historyStart,historyEnd:now(),results,quarantineCount:Array.isArray(state.reconcileQuarantine)?state.reconcileQuarantine.length:0};return results;
}
function reconcileLivePnlRows(state,cfg,list,meta={}){
  state.realizedUsd=list.reduce((s,x)=>s+Number(x.closedPnl||0),0);state.exchangeClosedTrades=list.length;
  const ordered=[...list].sort((a,b)=>closedAt(b)-closedAt(a));let streak=0;for(const x of ordered){if(Number(x.closedPnl||0)<0)streak++;else break;}
  state.lossStreak=streak;
  const newestLossAt=streak>0?closedAt(ordered[0]):0,trigger=Math.max(3,Number(cfg.risk.maxLossStreak||3));
  if(streak>=trigger&&newestLossAt>Number(state.lastLossPauseTriggerAt||0)){
    state.pauseUntil=now()+Number(cfg.risk.pauseMinutes||30)*60000;state.lastLossPauseTriggerAt=newestLossAt;state.lastLossPauseReason="THREE_CONSECUTIVE_LOSSES";
  }else if(Number(state.pauseUntil||0)<=now())state.pauseUntil=0;
  state.lastPnlReconcileHealthyAtMs=now();state.lastPnlReconcileError=null;state.lastPnlReconcileDegraded=null;
  state.lastPnlReconcile={at:iso(),scope:"CURRENT_TRADING_DAY_ASIA_BANGKOK",closedTrades:list.length,realizedUsd:state.realizedUsd,lossStreak:state.lossStreak,pauseUntil:state.pauseUntil||0,lastLossPauseTriggerAt:state.lastLossPauseTriggerAt||0,pages:Number(meta.pages||1),truncated:!!meta.truncated,historyStart:meta.startTime||null,authority:"BYBIT_CLOSED_PNL"};
}
async function manageLivePositions(env,api,state,positions,cfg){
  const live=new Map((positions||[]).map(p=>[String(p.symbol||""),p])),results=[];
  for(const [symbol,plan] of Object.entries(state.openPlans||{})){
    if(String(plan?.mode||"").toUpperCase()!=="LIVE")continue;const p=live.get(symbol);
    if(!p){plan.closeReconcilePendingSince=plan.closeReconcilePendingSince||iso();plan.closeReconcileStatus=plan.closeReconcileStatus||"CLOSED_PENDING_RECONCILE";results.push({symbol,managed:false,verdict:"PENDING_RECONCILE",reason:plan.closeReconcileStatus});continue;}
    try{const r=await manageBybitScalpPosition(env,api,plan,p,cfg);if(r?.nextSl>0)plan.managedSl=r.nextSl;if(r?.phase)plan.managementPhase=r.phase;if(Number.isFinite(Number(r?.peakR)))plan.peakR=Number(r.peakR);if(r?.cutExecuted){plan.exitRequestedAt=iso();plan.exitReason=r.reason||"MANAGER_CUT";}results.push({symbol,...r});}
    catch(e){results.push({symbol,managed:false,verdict:"ERROR",reason:"MANAGER_FAILED",error:String(e?.message||e)});}
  }
  state.lastPositionManagement={at:iso(),results};return results;
}
async function verifyProtection(api,symbol,expectedSl,expectedTp,expectedTrailing=0){
  const p=await api.positions(),x=(p?.result?.list||[]).find(v=>String(v.symbol)===symbol&&Number(v.size||0)>0);if(!x)return {ok:false,reason:"POSITION_NOT_FOUND_AFTER_PROTECTION"};
  const sl=Number(x.stopLoss||0),tp=Number(x.takeProfit||0),trail=Number(x.trailingStop||0),slTol=Math.max(Math.abs(expectedSl)*0.000001,1e-12),tpTol=Math.max(Math.abs(expectedTp)*0.000001,1e-12);
  if(!(sl>0&&tp>0))return {ok:false,reason:"PROTECTION_MISSING_AFTER_SET",stopLoss:sl,takeProfit:tp,trailingStop:trail};
  if(Math.abs(sl-expectedSl)>slTol||Math.abs(tp-expectedTp)>tpTol)return {ok:false,reason:"PROTECTION_MISMATCH",stopLoss:sl,takeProfit:tp,expectedSl,expectedTp,trailingStop:trail};
  if(expectedTrailing>0&&!(trail>0))return {ok:false,reason:"NATIVE_TRAILING_MISSING_AFTER_SET",stopLoss:sl,takeProfit:tp,trailingStop:trail,expectedTrailing};return {ok:true,stopLoss:sl,takeProfit:tp,trailingStop:trail};
}

export async function runBybitAutoV1(env,{forceScan=false,entryBlockReason=null}={}){
  const cfg=bybitAutoConfig(env),mode=bybitExecutionMode(env),guard=liveGuard(env,mode),api=bybitV5(env);let state=reset(await get(env));
  if(mode==="PAPER"){try{const rec=await reconcileBybitPaperPlans(env,state);state.openPlans=rec.plans;state.lastShadowReconcile={at:iso(),closed:rec.closed};if(rec.closed.length)await put(env,state);}catch(e){state.lastShadowReconcile={at:iso(),error:String(e?.message||e)};}}
  if(guard)return {ok:true,executed:false,mode,reason:guard,state};

  let equity=cfg.startingCapitalUsd,positions=[],lifecycles=[],riskState=state;
  if(mode==="LIVE"){
    const [walletResult,posResult]=await Promise.allSettled([api.wallet(),api.positions()]);
    if(posResult.status!=="fulfilled")return {ok:true,executed:false,mode,reason:"LIVE_POSITION_FETCH_FAILED",managementOnly:true,error:String(posResult.reason?.message||posResult.reason||"POSITION_FETCH_FAILED"),state};
    positions=(posResult.value?.result?.list||[]).filter(x=>Number(x.size||0)>0);
    let closedHistory=null,pnlReconcileError=null,pnlReconcileAgeMs=Infinity,pnlGraceActive=false;
    try{
      const t=now(),start=closedHistoryStart();closedHistory=await fetchClosedPnlAll(api,start,t);
      await reconcileLiveClosedPlans(env,state,positions,closedHistory.rows,start);
      const dailyRows=closedHistory.rows;reconcileLivePnlRows(state,cfg,dailyRows,closedHistory);
      state.lastClosedHistoryWindow={at:iso(),start,end:t,scope:"CURRENT_TRADING_DAY_ONLY",lookbackHours:Math.round((t-start)/3600000*10)/10,totalRows:closedHistory.rows.length,dailyRows:dailyRows.length,pages:closedHistory.pages,truncated:closedHistory.truncated};
    }catch(e){
      pnlReconcileError=String(e?.message||e);const healthy=lastPnlHealthyMs(state);pnlReconcileAgeMs=healthy>0?Math.max(0,now()-healthy):Infinity;pnlGraceActive=Number.isFinite(pnlReconcileAgeMs)&&pnlReconcileAgeMs<=PNL_RECONCILE_GRACE_MS;
      state.lastPnlReconcileError={at:iso(),error:pnlReconcileError,lastHealthyAtMs:healthy||null,ageMs:Number.isFinite(pnlReconcileAgeMs)?pnlReconcileAgeMs:null,graceActive:pnlGraceActive,graceMs:PNL_RECONCILE_GRACE_MS};
      state.lastPnlReconcileDegraded=pnlGraceActive?{at:iso(),reason:"TRANSIENT_CLOSED_PNL_FAILURE_WITHIN_GRACE",ageMs:pnlReconcileAgeMs}:null;
      state.lastLiveOutcomeReconcile={at:iso(),error:pnlReconcileError};
    }
    lifecycles=await manageLivePositions(env,api,state,positions,cfg);riskState=livePositionRiskState(state,positions);
    state.lastLiveRiskAccounting={at:iso(),authority:"BYBIT_LIVE_POSITIONS_ONLY",liveSymbols:positions.map(x=>String(x.symbol||"")),trackedPlans:Object.keys(state.openPlans||{}),riskCountedPlans:Object.keys(riskState.openPlans||{}),pendingClosedPlans:Object.entries(state.openPlans||{}).filter(([symbol,p])=>String(p?.mode||"").toUpperCase()==="LIVE"&&!positions.some(x=>String(x.symbol||"")===symbol)).map(([symbol])=>symbol),quarantinedUnresolvedPlans:Array.isArray(state.reconcileQuarantine)?state.reconcileQuarantine.length:0};
    await put(env,state);
    const wallet=walletResult.status==="fulfilled"?walletResult.value:null,acct=wallet?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{};equity=Number(acct.totalEquity||coin.equity||coin.walletBalance||0);
    const managerCut=lifecycles.find(x=>x.cutExecuted===true||x.verdict==="CUT");if(managerCut)return {ok:true,executed:false,mode,reason:"POSITION_CUT_BY_MANAGER",managerCut,lifecycles,equity,state};
    const untracked=positions.filter(p=>!state.openPlans?.[String(p.symbol||"")]);if(untracked.length)return {ok:true,executed:false,mode,reason:"UNTRACKED_LIVE_POSITION",symbols:untracked.map(x=>x.symbol),lifecycles,state};
    const managerFailure=lifecycles.find(x=>x.reason==="MANAGER_FAILED"||x.reason==="POSITION_DATA_INVALID");if(managerFailure)return {ok:true,executed:false,mode,reason:"POSITION_MANAGEMENT_DEGRADED",managerFailure,lifecycles,state};
    if(walletResult.status!=="fulfilled"||!(equity>0))return {ok:true,executed:false,mode,reason:"LIVE_EQUITY_INVALID",managementOnly:true,equity,lifecycles,error:walletResult.status==="rejected"?String(walletResult.reason?.message||walletResult.reason):null,state};
    if(pnlReconcileError&&!pnlGraceActive)return {ok:true,executed:false,mode,reason:"DAILY_PNL_RECONCILIATION_STALE",managementOnly:true,error:pnlReconcileError,pnlReconcileAgeMs:Number.isFinite(pnlReconcileAgeMs)?pnlReconcileAgeMs:null,pnlReconcileGraceMs:PNL_RECONCILE_GRACE_MS,lifecycles,equity,state};
    if(closedHistory?.truncated)return {ok:true,executed:false,mode,reason:"CURRENT_DAY_CLOSED_PNL_TRUNCATED",managementOnly:true,lifecycles,equity,state};
    if(entryBlockReason)return {ok:true,executed:false,mode,reason:entryBlockReason,managementOnly:true,lifecycles,equity,state};
    if(Number(state.pauseUntil||0)>now())return {ok:true,executed:false,mode,reason:"LOSS_STREAK_PAUSE",managementOnly:true,pauseUntil:state.pauseUntil,lifecycles,equity,state};
    const baseRisk=bybitRiskPreflight({cfg,equityUsd:equity,state:riskState,candidateRiskUsd:0});if(!baseRisk.ok)return {ok:true,executed:false,mode,reason:baseRisk.reason,risk:baseRisk,equity,lifecycles,state};
  }else{
    if(entryBlockReason)return {ok:true,executed:false,mode,reason:entryBlockReason,managementOnly:true,state};if(Number(state.pauseUntil||0)>now())return {ok:true,executed:false,mode,reason:"LOSS_STREAK_PAUSE",managementOnly:true,state};
  }
  if(Number(state.trades||0)>=cfg.maxTradesPerDay)return {ok:true,executed:false,mode,reason:"MAX_TRADES_PER_DAY",state,lifecycles};

  const scan=await scanBybitAuto(env),scannedSetup=scan.best;
  if(!scannedSetup)return {ok:true,executed:false,mode,reason:scan.reason||"NO_SETUP",scan,lifecycles,state};
  if(positions.some(p=>String(p.symbol||"")===scannedSetup.symbol))return {ok:true,executed:false,mode,reason:"SYMBOL_ALREADY_OPEN",setup:scannedSetup,scan,lifecycles,state};
  if(state.openPlans?.[scannedSetup.symbol])return {ok:true,executed:false,mode,reason:"PLAN_ALREADY_TRACKED_OR_PENDING_RECONCILE",setup:scannedSetup,scan,lifecycles,state};

  const preparation=await prepareBybitScalpForReview(env,scannedSetup,api);
  state.lastPreAiPreparation={symbol:scannedSetup.symbol,side:scannedSetup.side,at:iso(),reason:preparation.reason,ok:preparation.ok,quote:preparation.quote||null,entryState:preparation.setup?.entryState||"DISCARDED",reanchorCount:Number(preparation.setup?.reanchorCount||0)};
  if(!preparation.ok){await learn(env,{stage:"PRE_AI_REJECT",mode,symbol:scannedSetup.symbol,side:scannedSetup.side,strategy:scannedSetup.strategy,score:scannedSetup.score,rr:scannedSetup.rr,entry:scannedSetup.entry,sl:scannedSetup.sl,tp:scannedSetup.tp,preparation,reason:preparation.reason});await put(env,state);return {ok:true,executed:false,mode,reason:preparation.reason,preparation,setup:scannedSetup,scan,lifecycles,state};}
  const setup=preparation.setup;
  const sizing=sizeBybitAuto(setup,cfg,equity);if(!sizing.ok)return {ok:true,executed:false,mode,reason:sizing.reason,preparation,setup,sizing,scan,lifecycles,state};
  const riskPreflight=bybitRiskPreflight({cfg,equityUsd:equity,state:riskState,candidateRiskUsd:sizing.riskUsd,candidateInitialMarginUsd:sizing.initialMarginUsd});if(!riskPreflight.ok)return {ok:true,executed:false,mode,reason:riskPreflight.reason,risk:riskPreflight,preparation,setup,sizing,scan,lifecycles,state};
  const fp=`${setup.symbol}:${setup.side}:${setup.strategy}:${Math.round(setup.entry*1e6)}`;if(!forceScan&&state.lastFingerprint===fp&&now()-Number(state.lastTradeAt||0)<cfg.execution.cooldownSec*1000)return {ok:true,executed:false,mode,reason:"DUPLICATE_COOLDOWN",preparation,setup,scan,lifecycles,state};

  const ai=await reviewBybitScalp(env,setup,preparation.quote);state.lastAiReview={symbol:setup.symbol,side:setup.side,at:iso(),entryState:setup.entryState,reanchorCount:setup.reanchorCount,...ai};
  if(!ai.allow){await learn(env,{stage:"AI_REJECT",mode,symbol:setup.symbol,side:setup.side,strategy:setup.strategy,score:setup.score,rr:setup.rr,riskUsd:sizing.riskUsd,rewardUsd:sizing.rewardUsd,entry:setup.entry,sl:setup.sl,tp:setup.tp,preparation,ai,reason:ai.reason});await put(env,state);return {ok:true,executed:false,mode,reason:ai.reason||"AI_SCALP_GATE",preparation,ai,setup,sizing,scan,lifecycles,state};}
  const postAi=await revalidateBybitScalpAfterAi(env,api,setup);state.lastPostAiQuote={symbol:setup.symbol,side:setup.side,at:iso(),entryState:setup.entryState,reanchorCount:setup.reanchorCount,...postAi};
  if(!postAi.ok){await learn(env,{stage:"POST_AI_REJECT",mode,symbol:setup.symbol,side:setup.side,strategy:setup.strategy,score:setup.score,rr:setup.rr,riskUsd:sizing.riskUsd,rewardUsd:sizing.rewardUsd,entry:setup.entry,sl:setup.sl,tp:setup.tp,preparation,ai,postAi,reason:postAi.reason});await put(env,state);return {ok:true,executed:false,mode,reason:postAi.reason||"POST_AI_REVALIDATION_FAILED",preparation,ai,postAi,setup,sizing,scan,lifecycles,state};}

  const rewardTp=tpForReward(setup.side,setup.entry,sizing.qty,sizing.rewardUsd),plan={mode,symbol:setup.symbol,side:setup.side,qty:sizing.qty,entry:setup.entry,originalEntry:setup.originalEntry||setup.entry,entryState:setup.entryState||"ORIGINAL",reanchorCount:Number(setup.reanchorCount||0),reanchor:setup.reanchor||null,sl:setup.sl,initialSl:setup.sl,tp:rewardTp||setup.tp,structureTp:setup.tp,atr1:Number(setup.atr1||0),exitPlan:setup.exitPlan||null,tickSize:Number(setup.filters?.tickSize||0),filters:setup.filters,rr:sizing.targetRR,strategy:setup.strategy,score:setup.score,riskUsd:sizing.riskUsd,rewardUsd:sizing.rewardUsd,leverage:Number(sizing.leverage||cfg.leverage),margin:{marginUsePct:sizing.marginUsePct,marginBudgetUsd:sizing.marginBudgetUsd,initialMarginUsd:sizing.initialMarginUsd,notional:sizing.notional},riskPreflight,ai:{mode:ai.mode,reason:ai.reason,pass:ai.pass,reject:ai.reject,blocked:ai.blocked,unavailable:ai.unavailable,verdicts:ai.verdicts},postAiQuote:{px:postAi.px,spreadBps:postAi.spreadBps,driftBps:postAi.driftBps,checkedAt:postAi.checkedAt},peakR:0,lastReview:null,createdAt:iso(),createdAtMs:now()};
  if(mode==="PAPER"){state.trades=Number(state.trades||0)+1;state.lastTradeAt=now();state.lastFingerprint=fp;state.openPlans={...(state.openPlans||{}),[setup.symbol]:plan};await learn(env,{stage:"PAPER_ACCEPT",mode,symbol:setup.symbol,side:setup.side,strategy:setup.strategy,score:setup.score,rr:plan.rr,riskUsd:plan.riskUsd,rewardUsd:plan.rewardUsd,entry:plan.entry,sl:plan.sl,tp:plan.tp,leverage:plan.leverage,preparation,ai,postAi,reason:"PAPER_ORDER_ACCEPTED_AFTER_AI"});await put(env,state);return {ok:true,executed:true,paper:true,mode,reason:"PAPER_ORDER_ACCEPTED_AFTER_AI",plan,preparation,ai,postAi,risk:riskPreflight,scan,state};}

  let leverageSet;try{leverageSet=await api.setLeverage(setup.symbol,sizing.leverage);}catch(e){await learn(env,{stage:"LEVERAGE_REJECT",mode,symbol:setup.symbol,side:setup.side,entry:setup.entry,sl:setup.sl,tp:setup.tp,riskUsd:sizing.riskUsd,rewardUsd:sizing.rewardUsd,leverage:sizing.leverage,reason:"LEVERAGE_SET_FAILED"});await put(env,state);return {ok:true,executed:false,mode,reason:"LEVERAGE_SET_FAILED",error:String(e?.message||e),bybit:e?.bybit||null,leverage:sizing.leverage,preparation,ai,postAi,setup,sizing,scan,lifecycles,state};}
  state.lastLeverageSet={symbol:setup.symbol,at:iso(),requested:Number(sizing.leverage),idempotent:!!leverageSet?.idempotent,retMsg:leverageSet?.retMsg||"OK"};
  const order=await api.order({symbol:setup.symbol,side:setup.side,orderType:"Market",qty:String(sizing.qty),positionIdx:cfg.execution.positionIdx,timeInForce:"IOC"}),orderId=order?.result?.orderId;if(!orderId)return {ok:false,executed:false,mode,reason:"BYBIT_ORDER_ID_MISSING",order,preparation,ai,postAi,setup,scan,state};
  const f=await fill(api,setup.symbol,orderId);if(!f.ok){await emergencyFlat(api,setup,sizing.qty);return {ok:false,executed:false,mode,reason:f.reason,fill:f,preparation,ai,postAi,setup,scan,state};}
  const tick=Number(setup.filters?.tickSize||0),sl=roundTick(setup.sl,tick),actualRewardTp=tpForReward(setup.side,f.avgPrice,f.executedQty,sizing.rewardUsd),structureTp=Number(setup.tp||0),boundedTp=setup.side==="Buy"?Math.min(Number(actualRewardTp||Infinity),structureTp):Math.max(Number(actualRewardTp||-Infinity),structureTp),tp=roundTick(boundedTp,tick),actualRiskPerUnit=Math.abs(f.avgPrice-sl),actualRisk=actualRiskPerUnit*f.executedQty,actualReward=Math.abs(tp-f.avgPrice)*f.executedQty,actualRR=actualRisk>0?actualReward/actualRisk:null;
  const geometry=validateProtectionGeometry({side:setup.side,entry:f.avgPrice,sl,tp});if(!geometry.ok||!(actualRR>=cfg.risk.minRR)){await emergencyFlat(api,setup,f.executedQty);return {ok:true,executed:false,mode,reason:geometry.ok?"ACTUAL_RR_INVALID":geometry.reason,actualRR,fill:f,preparation,setup,scan,state};}
  const actualRiskGuard=bybitRiskPreflight({cfg,equityUsd:equity,state:riskState,candidateRiskUsd:actualRisk,candidateInitialMarginUsd:sizing.initialMarginUsd});if(!actualRiskGuard.ok){await emergencyFlat(api,setup,f.executedQty);return {ok:true,executed:false,mode,reason:"ACTUAL_"+actualRiskGuard.reason,risk:actualRiskGuard,actualRisk,fill:f,preparation,setup,scan,state};}
  const plannedTrailAt=Number(setup.exitPlan?.positiveTrailTriggerR||0),plannedTrailAtr=Number(setup.exitPlan?.trailAtr||0),trailAtR=Math.max(1.70,Number(env.BYBIT_TRAIL_TRIGGER_R||0)||plannedTrailAt||1.85);
  const plannedDistanceR=plannedTrailAtr>0&&Number(setup.atr1||0)>0?plannedTrailAtr*Number(setup.atr1)/Math.max(actualRiskPerUnit,1e-12):.50,trailDistanceR=Math.max(.25,Math.min(1.0,Number(env.BYBIT_TRAIL_DISTANCE_R||plannedDistanceR||.50))),trailingStop=roundTick(actualRiskPerUnit*trailDistanceR,tick),activePrice=roundTick(setup.side==="Buy"?f.avgPrice+actualRiskPerUnit*trailAtR:f.avgPrice-actualRiskPerUnit*trailAtR,tick);
  try{await api.tradingStop({symbol:setup.symbol,tpslMode:"Full",positionIdx:cfg.execution.positionIdx,takeProfit:String(tp),stopLoss:String(sl),trailingStop:String(trailingStop),activePrice:String(activePrice),tpTriggerBy:"MarkPrice",slTriggerBy:"MarkPrice"});}
  catch(e){await emergencyFlat(api,setup,f.executedQty);return {ok:false,executed:false,mode,reason:"PROTECTION_SET_FAILED",error:String(e?.message||e),fill:f,preparation,ai,postAi,setup,scan,state};}
  let protection;try{protection=await verifyProtection(api,setup.symbol,sl,tp,trailingStop);}catch(e){protection={ok:false,reason:"PROTECTION_VERIFY_FAILED",error:String(e?.message||e)};}if(!protection.ok){await emergencyFlat(api,setup,f.executedQty);return {ok:false,executed:false,mode,reason:protection.reason,protection,fill:f,preparation,setup,scan,state};}
  const actual={...plan,entry:f.avgPrice,qty:f.executedQty,sl,initialSl:sl,tp,rr:actualRR,orderId:f.orderId,riskUsd:actualRisk,rewardUsd:actualReward,riskPreflight:actualRiskGuard,protectionVerified:true,nativeTrailing:{armed:true,trailingStop,activePrice,triggerR:trailAtR,distanceR:trailDistanceR},managementPhase:"INITIAL",execution:{status:f.status,fillPrice:f.avgPrice,executedQty:f.executedQty},leverageSet:{requested:Number(sizing.leverage),idempotent:!!leverageSet?.idempotent,retMsg:leverageSet?.retMsg||"OK"}};
  state.trades=Number(state.trades||0)+1;state.lastTradeAt=now();state.lastFingerprint=fp;state.openPlans={...(state.openPlans||{}),[setup.symbol]:actual};await learn(env,{stage:"LIVE_ACCEPT",mode,symbol:actual.symbol,side:actual.side,strategy:actual.strategy,score:actual.score,rr:actual.rr,riskUsd:actual.riskUsd,rewardUsd:actual.rewardUsd,entry:actual.entry,sl:actual.sl,tp:actual.tp,leverage:actual.leverage,preparation,ai,postAi,execution:actual.execution,reason:"ORDER_SUBMITTED_PROTECTED_VERIFIED_TRAILING_ARMED"});await put(env,state);
  return {ok:true,executed:true,mode,reason:"ORDER_SUBMITTED_PROTECTED_VERIFIED_TRAILING_ARMED",plan:actual,preparation,ai,postAi,risk:actualRiskGuard,protection,scan,lifecycles,state};
}

export async function getBybitAutoV1State(env){return get(env);}
