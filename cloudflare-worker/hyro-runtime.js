import {hyroDynamicScan} from "./hyro-scanner.js";
import {getHyroControl,getHyroProfile,getHyroTelemetry,executeHyroPlan,cancelHyroPending,hyroExecutionConfig} from "./hyro-execution.js";

const RUNTIME_KEY="v7718:hyro:runtime";
async function put(env,v){if(env.TRADING_STATE)await env.TRADING_STATE.put(RUNTIME_KEY,JSON.stringify(v));}
async function done(env,base,extra={}){const out={...base,...extra,finishedAt:Date.now()};out.elapsedMs=out.finishedAt-base.startedAt;await put(env,out);return out;}

export async function runHyroAutoCycle(env){
  const startedAt=Date.now(),cfg=hyroExecutionConfig(env),base={ok:true,executed:false,mode:cfg.mode,startedAt,silentTelegram:true,source:"HYRO_INDEPENDENT_SCANNER"};
  try{
    const profile=await getHyroProfile(env),control=await getHyroControl(env);
    if(!profile)return done(env,base,{reason:"PROFILE_NOT_CONFIGURED"});
    const telemetry=await getHyroTelemetry(env);
    const telemetryView=telemetry?.connected?{equity:telemetry.equity,day:telemetry.day,positions:telemetry.positions.length,openOrders:telemetry.openOrders.length}:null;
    if(!telemetry.connected)return done(env,base,{reason:telemetry.reason||"ACCOUNT_NOT_CONNECTED",telemetry:telemetryView,diagnostics:telemetry.diagnostics||null});
    if(control.manualPaused){if(telemetry.openOrders?.length)await cancelHyroPending(env).catch(()=>{});return done(env,base,{reason:"MANUAL_PAUSED",telemetry:telemetryView});}
    if(!cfg.autoExecutionRequested)return done(env,base,{reason:"AUTO_EXECUTION_DISABLED",telemetry:telemetryView});
    const targetUsd=Number(profile.accountSize||0)*.05;
    if((telemetry.day?.pnlFromDayStart||0)>=targetUsd){if(telemetry.openOrders?.length)await cancelHyroPending(env).catch(()=>{});return done(env,base,{reason:"DAILY_PROFIT_TARGET_REACHED",targetUsd,telemetry:telemetryView});}
    const hard=Number(profile.internal?.dailyHardStopUsd||0);
    if(hard>0&&(telemetry.day?.drawdownFromPeak||0)>=hard){if(telemetry.openOrders?.length)await cancelHyroPending(env).catch(()=>{});return done(env,base,{reason:"DAILY_HARD_STOP",hardStopUsd:hard,telemetry:telemetryView});}
    const active=new Set([...(telemetry.positions||[]).map(x=>x.symbol),...(telemetry.openOrders||[]).map(x=>x.symbol)]);
    if(active.size>=2)return done(env,base,{reason:"MAX_ACTIVE_SLOTS_REACHED",telemetry:telemetryView});

    const scan=await hyroDynamicScan({maxBroad:100,maxDeep:10,minTurnover:10000000});
    const candidates=(scan.results||[]).filter(x=>x.status==="MARKET_PLAN"||x.status==="LIMIT_PLAN").filter(x=>!active.has(x.symbol));
    if(!candidates.length)return done(env,base,{reason:"NO_ELIGIBLE_CANDIDATE",candidateCount:0,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount},telemetry:telemetryView});

    let execution=null,lastGate=null,lastError=null;
    for(const plan of candidates){
      try{
        const r=await executeHyroPlan(env,{...plan,setupId:`hyro-auto:${plan.symbol}:${plan.side}:${Math.round((plan.entry||0)*1e8)}`});
        execution=r;
        if(r?.gate)lastGate=r.gate;
        if(r?.executed)break;
      }catch(e){lastError=String(e?.message||e);}
    }
    if(execution?.executed)return done(env,base,{executed:true,reason:"ORDER_SUBMITTED",execution:execution.order,candidateCount:candidates.length,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount},telemetry:telemetryView});
    return done(env,base,{reason:lastError?"EXECUTION_REJECTED":"CANDIDATES_BLOCKED",error:lastError,lastGate,candidateCount:candidates.length,scanSummary:{broadCount:scan.broadCount,deepCount:scan.deepCount},telemetry:telemetryView});
  }catch(e){
    return done(env,{...base,ok:false},{reason:"CYCLE_ERROR",error:String(e?.message||e)});
  }
}

export async function getHyroRuntime(env){try{return await env.TRADING_STATE?.get(RUNTIME_KEY,"json")||null;}catch{return null;}}
