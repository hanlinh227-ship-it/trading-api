import {hyroDynamicScan} from "./hyro-scanner.js";
import {getHyroControl,getHyroProfile,getHyroTelemetry,executeHyroPlan,cancelHyroPending,hyroExecutionConfig,hyroDynamicRiskView} from "./hyro-execution.js";
import {manageHyroPositions} from "./hyro-position-manager.js";

const RUNTIME_KEY="v7718:hyro:runtime";
async function put(env,v){if(env.TRADING_STATE)await env.TRADING_STATE.put(RUNTIME_KEY,JSON.stringify(v));}
async function done(env,base,extra={}){const out={...base,...extra,finishedAt:Date.now()};out.elapsedMs=out.finishedAt-base.startedAt;await put(env,out);return out;}

export async function runHyroAutoCycle(env,opts={}){
  const marketOnly=!!opts.marketOnly;
  const startedAt=Date.now(),cfg=hyroExecutionConfig(env),base={ok:true,executed:false,mode:cfg.mode,startedAt,silentTelegram:true,source:marketOnly?"HYRO_QUICK_ABC_SCAN":"HYRO_INDEPENDENT_SCANNER",marketOnly};
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
    if(active.size>=2)return done(env,base,{reason:"MAX_ACTIVE_SLOTS_REACHED",telemetry:telemetryView,dynamicRisk,management});
    const scan=await hyroDynamicScan({maxBroad:100,maxDeep:12,minTurnover:8000000});
    const eligibleStatuses=marketOnly?["MARKET_PLAN","NEAR_MARKET_PLAN"]:["MARKET_PLAN","LIMIT_PLAN"];
    const allEligible=(scan.results||[]).filter(x=>eligibleStatuses.includes(x.status)).filter(x=>!active.has(x.symbol));
    const candidates=[...allEligible].sort((a,b)=>((a.tier==="A"?2:a.tier==="B"?1:0)-(b.tier==="A"?2:b.tier==="B"?1:0))*-1||(Number(b.rr||0)-Number(a.rr||0))||(Number(b.context?.turnover24h||0)-Number(a.context?.turnover24h||0)));
    const preview=(scan.results||[]).slice(0,3).map(x=>({symbol:x.symbol,status:x.status,tier:x.tier,side:x.side,rr:Number(x.rr||0),strategy:x.strategy,profile:x.profile,entry:x.entry,sl:x.sl,tp1:x.tp1,tp2:x.tp2,tp3:x.tp3??x.tp,riskMultiplier:x.riskMultiplier,funding:x.context?.funding||null,reason:x.reason}));
    if(!candidates.length)return done(env,base,{reason:marketOnly?"NO_ABC_MARKET_ENTRY":"NO_ELIGIBLE_CANDIDATE",candidateCount:0,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount,profile:scan.profile,tiers:scan.tiers},preview,telemetry:telemetryView,dynamicRisk,management});
    let execution=null,lastGate=null,lastError=null;
    for(const plan of candidates){
      try{const r=await executeHyroPlan(env,{...plan,setupId:`hyro-${marketOnly?"quick":"auto"}:${plan.tier||"X"}:${plan.symbol}:${plan.side}:${Math.round((plan.entry||0)*1e8)}`});if(r?.gate)lastGate=r.gate;if(r?.executed){execution=r;break;}}catch(e){lastError=String(e?.message||e);}
    }
    if(execution?.executed)return done(env,base,{reason:"ORDER_SUBMITTED",executed:true,execution:execution.order,candidateCount:candidates.length,selectedTier:candidates.find(x=>x.symbol===execution.order?.symbol)?.tier||null,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount,profile:scan.profile,tiers:scan.tiers},preview,telemetry:telemetryView,dynamicRisk,management});
    return done(env,base,{reason:lastError?"EXECUTION_REJECTED":"CANDIDATES_BLOCKED",lastError,lastGate,candidateCount:candidates.length,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount,profile:scan.profile,tiers:scan.tiers},preview,telemetry:telemetryView,dynamicRisk,management});
  }catch(e){return done(env,base,{ok:false,reason:"CYCLE_ERROR",error:String(e?.message||e),failClosed:true});}
}

export async function getHyroRuntime(env){try{return await env.TRADING_STATE?.get(RUNTIME_KEY,"json")||null;}catch{return null;}}
