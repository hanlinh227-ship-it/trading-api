import {hyroDynamicScan} from "./hyro-scanner.js";
import {getHyroControl,getHyroProfile,getHyroTelemetry,executeHyroPlan,cancelHyroPending,hyroExecutionConfig} from "./hyro-execution.js";

const RUNTIME_KEY="v7718:hyro:runtime";
async function put(env,v){if(env.TRADING_STATE)await env.TRADING_STATE.put(RUNTIME_KEY,JSON.stringify(v));}
async function done(env,base,extra={}){const out={...base,...extra,finishedAt:Date.now()};out.elapsedMs=out.finishedAt-base.startedAt;await put(env,out);return out;}

export async function runHyroAutoCycle(env,opts={}){
  const marketOnly=!!opts.marketOnly;
  const startedAt=Date.now(),cfg=hyroExecutionConfig(env),base={ok:true,executed:false,mode:cfg.mode,startedAt,silentTelegram:true,source:marketOnly?"HYRO_QUICK_MARKET_SCAN":"HYRO_INDEPENDENT_SCANNER",marketOnly};
  try{
    const profile=await getHyroProfile(env),control=await getHyroControl(env);
    if(!profile)return done(env,base,{reason:"PROFILE_NOT_CONFIGURED"});
    const telemetry=await getHyroTelemetry(env);
    const telemetryView=telemetry?.connected?{equity:telemetry.equity,walletBalance:telemetry.walletBalance,available:telemetry.available,positions:telemetry.positions.length,openOrders:telemetry.openOrders.length}:null;
    if(!telemetry.connected)return done(env,base,{reason:telemetry.reason||"ACCOUNT_NOT_CONNECTED",telemetry:telemetryView,diagnostics:telemetry.diagnostics||null});
    if(!(Number(telemetry.equity)>0))return done(env,base,{reason:"ACCOUNT_EQUITY_ZERO_OR_UNAVAILABLE",telemetry:telemetryView,failClosed:true});
    if(control.manualPaused){if(telemetry.openOrders?.length)await cancelHyroPending(env).catch(()=>{});return done(env,base,{reason:"MANUAL_PAUSED",telemetry:telemetryView});}
    if(!cfg.autoExecutionRequested)return done(env,base,{reason:"AUTO_EXECUTION_DISABLED",telemetry:telemetryView});
    const targetUsd=Number(profile.accountSize||0)*.05;
    if((telemetry.day?.pnlFromDayStart||0)>=targetUsd){if(telemetry.openOrders?.length)await cancelHyroPending(env).catch(()=>{});return done(env,base,{reason:"DAILY_PROFIT_TARGET_REACHED",targetUsd,telemetry:telemetryView});}
    const hard=Number(profile.internal?.dailyHardStopUsd||0);
    if(hard>0&&(telemetry.day?.drawdownFromPeak||0)>=hard){if(telemetry.openOrders?.length)await cancelHyroPending(env).catch(()=>{});return done(env,base,{reason:"DAILY_HARD_STOP",hardStopUsd:hard,telemetry:telemetryView});}
    const active=new Set([...(telemetry.positions||[]).map(x=>x.symbol),...(telemetry.openOrders||[]).map(x=>x.symbol)]);
    if(active.size>=2)return done(env,base,{reason:"MAX_ACTIVE_SLOTS_REACHED",telemetry:telemetryView});
    const scan=await hyroDynamicScan({maxBroad:100,maxDeep:10,minTurnover:10000000});
    const eligibleStatuses=marketOnly?["MARKET_PLAN"]:["MARKET_PLAN","LIMIT_PLAN"];
    const allEligible=(scan.results||[]).filter(x=>eligibleStatuses.includes(x.status)).filter(x=>!active.has(x.symbol));
    const candidates=[...allEligible].sort((a,b)=>Number(b.score||b.totalScore||0)-Number(a.score||a.totalScore||0));
    const preview=(scan.results||[]).slice(0,3).map(x=>({symbol:x.symbol,status:x.status,side:x.side,score:Number(x.score||x.totalScore||0),entry:x.entry,sl:x.sl,tp:x.tp2??x.tp}));
    if(!candidates.length)return done(env,base,{reason:marketOnly?"NO_MARKET_CANDIDATE":"NO_ELIGIBLE_CANDIDATE",candidateCount:0,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount},preview,telemetry:telemetryView});
    let execution=null,lastGate=null,lastError=null;
    for(const plan of candidates){
      try{const r=await executeHyroPlan(env,{...plan,setupId:`hyro-${marketOnly?"quick":"auto"}:${plan.symbol}:${plan.side}:${Math.round((plan.entry||0)*1e8)}`});if(r?.gate)lastGate=r.gate;if(r?.executed){execution=r;break;}}catch(e){lastError=String(e?.message||e);}
    }
    if(execution?.executed)return done(env,base,{reason:"ORDER_SUBMITTED",executed:true,execution:execution.order,candidateCount:candidates.length,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount},preview,telemetry:telemetryView});
    return done(env,base,{reason:lastError?"EXECUTION_REJECTED":"CANDIDATES_BLOCKED",lastError,lastGate,candidateCount:candidates.length,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount},preview,telemetry:telemetryView});
  }catch(e){return done(env,base,{ok:false,reason:"CYCLE_ERROR",error:String(e?.message||e),failClosed:true});}
}

export async function getHyroRuntime(env){try{return await env.TRADING_STATE?.get(RUNTIME_KEY,"json")||null;}catch{return null;}}
