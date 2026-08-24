import {binance20Config} from "./binance-futures20-config.js";
import {scanBinance20,sizeBinance20} from "./binance-futures20-engine.js";
import {binanceUsdm} from "./binance-usdm-client.js";
import {chooseCandidateForSlots,totalOpenRiskGuard} from "./binance-position-cap.js";
import {preflightExecution} from "./binance-execution-guard.js";

const now=()=>Date.now();
function check(name,pass,detail={}){return {name,pass:!!pass,detail};}
function isTestnetBase(env){const b=String(env.BINANCE_FUTURES_BASE_URL||"").toLowerCase();return b.includes("testnet")||b.includes("demo");}

export async function runBinanceTestnetStress(env={}){
  const startedAt=now(),checks=[],cfg=binance20Config(env);
  checks.push(check("TESTNET_BASE",isTestnetBase(env),{base:String(env.BINANCE_FUTURES_BASE_URL||"")}));
  checks.push(check("LIVE_DISABLED",String(env.BINANCE_AUTO_LIVE||"").toLowerCase()!=="true"));
  checks.push(check("MAX_3_POSITIONS",Number(cfg.maxOpenPositions)===3,{value:cfg.maxOpenPositions}));
  checks.push(check("BALANCE_LADDER",cfg.risk.mode==="BALANCE_DOLLAR_LADDER",{risk:cfg.risk}));
  if(!checks.every(x=>x.pass))return {ok:false,stage:"CONFIG",checks,startedAt,finishedAt:now()};

  const api=binanceUsdm(env);
  let account,positions;
  try{[account,positions]=await Promise.all([api.account(),api.positions()]);checks.push(check("SIGNED_API",true));}
  catch(e){checks.push(check("SIGNED_API",false,{error:String(e?.message||e)}));return {ok:false,stage:"API",checks,startedAt,finishedAt:now()};}

  const equity=Number(account.totalWalletBalance||account.totalMarginBalance||cfg.startingCapitalUsd);
  const open=(positions||[]).filter(x=>Math.abs(Number(x.positionAmt||0))>0);
  checks.push(check("POSITION_COUNT_SAFE",open.length<=3,{open:open.length}));

  let scan;
  try{scan=await scanBinance20(env);checks.push(check("UNIVERSE_50_PLUS",Number(scan?.analyzed||0)>=50,{analyzed:scan?.analyzed,qualified:scan?.qualified}));}
  catch(e){checks.push(check("SCAN_PIPELINE",false,{error:String(e?.message||e)}));return {ok:false,stage:"SCAN",checks,startedAt,finishedAt:now()};}

  const slot=chooseCandidateForSlots(scan.candidates||[],open,cfg);
  checks.push(check("SLOT_GUARD",open.length>=3?slot.candidate===null:true,{reason:slot.reason}));
  if(slot.candidate){
    const sizing=sizeBinance20(slot.candidate,slot.candidate.filters,cfg,equity);
    checks.push(check("SIZING",sizing.ok,{sizing}));
    if(sizing.ok){
      const trg=totalOpenRiskGuard({openPlans:{},candidateRiskUsd:sizing.riskUsd,equityUsd:equity,cfg});
      checks.push(check("TOTAL_RISK_GUARD",trg.ok,{totalRisk:trg}));
      try{const pre=await preflightExecution(api,slot.candidate,env);checks.push(check("EXECUTION_PREFLIGHT",pre.ok,{preflight:pre}));}
      catch(e){checks.push(check("EXECUTION_PREFLIGHT",false,{error:String(e?.message||e)}));}
    }
  }else{
    checks.push(check("NO_CANDIDATE_IS_VALID_STATE",true,{reason:slot.reason||scan.reason||"NO_SETUP"}));
  }

  const pass=checks.every(x=>x.pass);
  return {ok:pass,stage:pass?"READY_FOR_TESTNET_ORDER_CYCLE":"FAILED_GATE",mode:"TESTNET_STRESS_REVIEW",equity,openPositions:open.length,universeAnalyzed:scan?.analyzed||0,qualified:scan?.qualified||0,best:slot.candidate?{symbol:slot.candidate.symbol,side:slot.candidate.side,rr:slot.candidate.rr,score:slot.candidate.score}:null,checks,startedAt,finishedAt:now(),durationMs:now()-startedAt};
}
