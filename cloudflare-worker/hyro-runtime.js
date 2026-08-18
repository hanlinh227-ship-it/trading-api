import {hyroDynamicScan} from "./hyro-scanner.js";
import {getHyroControl,getHyroProfile,getHyroTelemetry,executeHyroPlan,cancelHyroPending,hyroExecutionConfig,hyroDynamicRiskView} from "./hyro-execution.js";
import {manageHyroPositions} from "./hyro-position-manager.js";
import {enrichHyroPlans} from "./hyro-market-context.js";
import {evaluateHyroPortfolio,markHyroPortfolioEntry,portfolioQuality,HYRO_PORTFOLIO_POLICY} from "./hyro-portfolio-guard.js";

const RUNTIME_KEY="v7718:hyro:runtime";
async function put(env,v){if(env.TRADING_STATE)await env.TRADING_STATE.put(RUNTIME_KEY,JSON.stringify(v));}
async function done(env,base,extra={}){const out={...base,...extra,finishedAt:Date.now()};out.elapsedMs=out.finishedAt-base.startedAt;await put(env,out);return out;}
const microScore=x=>Number(x?.context?.microstructure?.score??.5);

export async function runHyroAutoCycle(env,opts={}){
  const marketOnly=!!opts.marketOnly;
  const startedAt=Date.now(),cfg=hyroExecutionConfig(env),base={ok:true,executed:false,mode:cfg.mode,startedAt,silentTelegram:true,source:marketOnly?"HYRO_QUICK_ABC_MICRO_PORTFOLIO":"HYRO_INDEPENDENT_SCANNER_MICRO_PORTFOLIO",marketOnly};
  try{
    const profile=await getHyroProfile(env),control=await getHyroControl(env);
    if(!profile)return done(env,base,{reason:"PROFILE_NOT_CONFIGURED"});
    const telemetry=await getHyroTelemetry(env);
    const telemetryView=telemetry?.connected?{equity:telemetry.equity,walletBalance:telemetry.walletBalance,available:telemetry.available,positions:telemetry.positions.length,openOrders:telemetry.openOrders.length}:null;
    if(!telemetry.connected)return done(env,base,{reason:telemetry.reason||"ACCOUNT_NOT_CONNECTED",telemetry:telemetryView,diagnostics:telemetry.diagnostics||null});
    if(!(Number(telemetry.equity)>0))return done(env,base,{reason:"ACCOUNT_EQUITY_ZERO_OR_UNAVAILABLE",telemetry:telemetryView,failClosed:true});
    const dynamicRisk=hyroDynamicRiskView(profile,telemetry),management=await manageHyroPositions(env,telemetry).catch(e=>({ok:false,reason:String(e?.message||e),managed:[]}));
    if(control.manualPaused){if(telemetry.openOrders?.length)await cancelHyroPending(env).catch(()=>{});return done(env,base,{reason:"MANUAL_PAUSED",telemetry:telemetryView,dynamicRisk,management});}
    if(!cfg.autoExecutionRequested)return done(env,base,{reason:"AUTO_EXECUTION_DISABLED",telemetry:telemetryView,dynamicRisk,management});
    if((telemetry.day?.pnlFromDayStart||0)>=dynamicRisk.targetUsd){if(telemetry.openOrders?.length)await cancelHyroPending(env).catch(()=>{});return done(env,base,{reason:"DAILY_PROFIT_TARGET_REACHED",targetUsd:dynamicRisk.targetUsd,telemetry:telemetryView,dynamicRisk,management});}
    if((telemetry.day?.drawdownFromPeak||0)>=dynamicRisk.dailyHardStopUsd){if(telemetry.openOrders?.length)await cancelHyroPending(env).catch(()=>{});return done(env,base,{reason:"DAILY_HARD_STOP",hardStopUsd:dynamicRisk.dailyHardStopUsd,telemetry:telemetryView,dynamicRisk,management});}
    const active=new Set([...(telemetry.positions||[]).map(x=>x.symbol),...(telemetry.openOrders||[]).map(x=>x.symbol)]);
    if(active.size>=HYRO_PORTFOLIO_POLICY.maxSlots)return done(env,base,{reason:"MAX_ACTIVE_SLOTS_REACHED",telemetry:telemetryView,dynamicRisk,management,portfolioPolicy:HYRO_PORTFOLIO_POLICY});
    const rawScan=await hyroDynamicScan({maxBroad:100,maxDeep:12,minTurnover:8000000}),enriched=await enrichHyroPlans(rawScan.results||[],{limit:6}),scan={...rawScan,results:enriched,tiers:enriched.reduce((a,x)=>(a[x.tier||"C"]=(a[x.tier||"C"]||0)+1,a),{})};
    const rawEligible=(scan.results||[]).filter(x=>{if(active.has(x.symbol))return false;if(marketOnly)return ["MARKET_PLAN","NEAR_MARKET_PLAN"].includes(x.status);if(["MARKET_PLAN","LIMIT_PLAN"].includes(x.status))return true;return x.status==="NEAR_MARKET_PLAN"&&microScore(x)>=.58;});
    const candidates=[],portfolioBlocked=[];
    for(const plan of rawEligible){const guard=await evaluateHyroPortfolio(env,plan,telemetry);if(guard.ok)candidates.push({...plan,_portfolio:guard});else portfolioBlocked.push({symbol:plan.symbol,side:plan.side,tier:plan.tier,reason:guard.reason,cluster:guard.cluster||null});}
    candidates.sort((a,b)=>portfolioQuality(b,b._portfolio)-portfolioQuality(a,a._portfolio)||(microScore(b)-microScore(a))||(Number(b.rr||0)-Number(a.rr||0)));
    const preview=(scan.results||[]).slice(0,3).map(x=>({symbol:x.symbol,status:x.status,tier:x.tier,side:x.side,rr:Number(x.rr||0),strategy:x.strategy,profile:x.profile,entry:x.entry,sl:x.sl,tp1:x.tp1,tp2:x.tp2,tp3:x.tp3??x.tp,riskMultiplier:x.riskMultiplier,microScore:microScore(x),openInterest:x.context?.microstructure?.openInterest||null,longShort:x.context?.microstructure?.longShort||null,orderbook:x.context?.microstructure?.orderbook||null,funding:x.context?.funding||null,reason:x.reason}));
    if(!candidates.length){const reason=rawEligible.length?"PORTFOLIO_GUARD_BLOCKED":(marketOnly?"NO_ABC_MARKET_ENTRY":"NO_ELIGIBLE_CANDIDATE");return done(env,base,{reason,candidateCount:0,rawEligibleCount:rawEligible.length,portfolioBlocked,portfolioPolicy:HYRO_PORTFOLIO_POLICY,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount,profile:scan.profile,tiers:scan.tiers,microstructure:true},preview,telemetry:telemetryView,dynamicRisk,management});}
    let execution=null,lastGate=null,lastError=null;
    for(const plan of candidates){
      try{const r=await executeHyroPlan(env,{...plan,setupId:`hyro-${marketOnly?"quick":"auto"}:${plan.tier||"X"}:${plan.symbol}:${plan.side}:${Math.round((plan.entry||0)*1e8)}`});if(r?.gate)lastGate=r.gate;if(r?.executed){execution=r;await markHyroPortfolioEntry(env,r.order).catch(()=>{});break;}}catch(e){lastError=String(e?.message||e);}
    }
    if(execution?.executed){const selected=candidates.find(x=>x.symbol===execution.order?.symbol);return done(env,base,{reason:"ORDER_SUBMITTED",executed:true,execution:execution.order,candidateCount:candidates.length,selectedTier:selected?.tier||null,selectedMicroScore:microScore(selected),selectedCluster:selected?._portfolio?.cluster||null,portfolioPolicy:HYRO_PORTFOLIO_POLICY,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount,profile:scan.profile,tiers:scan.tiers,microstructure:true},preview,telemetry:telemetryView,dynamicRisk,management});}
    return done(env,base,{reason:lastError?"EXECUTION_REJECTED":"CANDIDATES_BLOCKED",lastError,lastGate,candidateCount:candidates.length,portfolioBlocked,portfolioPolicy:HYRO_PORTFOLIO_POLICY,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount,profile:scan.profile,tiers:scan.tiers,microstructure:true},preview,telemetry:telemetryView,dynamicRisk,management});
  }catch(e){return done(env,base,{ok:false,reason:"CYCLE_ERROR",error:String(e?.message||e),failClosed:true});}
}

export async function getHyroRuntime(env){try{return await env.TRADING_STATE?.get(RUNTIME_KEY,"json")||null;}catch{return null;}}
