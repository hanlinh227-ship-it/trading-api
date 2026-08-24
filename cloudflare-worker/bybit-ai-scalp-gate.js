import {bybitV5} from "./bybit-v5-client.js";

const PROVIDERS=["claude","codex","deepseek"];
const num=v=>Number.isFinite(Number(v))?Number(v):null;
const upper=v=>String(v||"").toUpperCase();
const envBool=(v,d=true)=>v==null?d:String(v).toLowerCase()==="true";

// AI policy: the deterministic scanner owns market discovery. The three core AIs are only
// allowed to review one candidate that has already passed scan + sizing + risk + fresh-quote
// validation. This keeps paid/token-backed models out of broad market search.
const AI_REVIEW_POLICY="FINAL_ENTRY_REVIEW_ONLY";

function compactSetup(setup){
  return {
    symbol:setup.symbol,
    side:setup.side,
    strategy:setup.strategy,
    score:num(setup.score),
    entry:num(setup.entry),
    sl:num(setup.sl),
    tp:num(setup.tp),
    rr:num(setup.rr),
    spreadBps:num(setup.spreadBps),
    atr1:num(setup.atr1),
    profile:setup.profile,
    context:{
      vwapAligned:!!setup.context?.vwapAligned,
      volumeRatio:num(setup.context?.volumeRatio),
      distanceFromVwapAtr:num(setup.context?.distanceFromVwapAtr),
      confluence:Array.isArray(setup.context?.confluence)?setup.context.confluence.slice(0,6):[]
    },
    liquidity:{
      turnover24h:num(setup.liquidity?.turnover24h),
      spreadBps:num(setup.liquidity?.spreadBps)
    }
  };
}
function safeProviderDiagnostics(providers={}){const out={};for(const p of PROVIDERS){const x=providers?.[p]||{};out[p]={status:upper(x.status||"UNAVAILABLE"),latencySeconds:num(x.latencySeconds),error:x.error?String(x.error).slice(0,180):null,hasReview:!!(x.review&&typeof x.review==="object")};}return out;}
export async function probeBybitAiBridge(env){if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=="function")return {ok:false,error:"AI_BRIDGE_BINDING_MISSING",providers:{},requiredProviders:PROVIDERS};const secret=String(env.V11_AI_BRIDGE_SECRET||"");if(!secret)return {ok:false,error:"AI_BRIDGE_SECRET_MISSING",providers:{},requiredProviders:PROVIDERS};const started=Date.now();try{const r=await env.AI_BRIDGE.fetch(new Request("http://127.0.0.1:8789/health",{headers:{accept:"application/json","authorization":"Bearer "+secret},signal:AbortSignal.timeout(5000)}));const j=await r.json().catch(()=>({}));const providers={};let configured=0,online=0;for(const p of PROVIDERS){const x=j?.providers?.[p]||{};providers[p]={configured:!!x.configured,state:upper(x.state||x.status||"UNKNOWN"),model:String(x.model||"").slice(0,80),last_seen:num(x.last_seen)};if(providers[p].configured)configured++;if(["ONLINE","PASS","RUNNING"].includes(providers[p].state))online++;}return {ok:r.ok&&configured>0,httpStatus:r.status,latencyMs:Date.now()-started,configured,online,requiredProviders:PROVIDERS,allRequiredOnline:online===PROVIDERS.length,atLeastOneOnline:online>0,bridgeMode:j?.mode||null,fastFirstGraceSec:num(j?.scalpFastFirstGraceSec),bridgeBudgetSec:num(j?.scalpBridgeBudgetSec),providers,error:r.ok?null:String(j?.error||"AI_BRIDGE_HEALTH_HTTP_"+r.status)};}catch(e){return {ok:false,latencyMs:Date.now()-started,error:"AI_BRIDGE_HEALTH_FETCH:"+String(e?.message||e),providers:{},requiredProviders:PROVIDERS};}}

async function validateQuote(env,api,setup,phase){
  const isPre=phase==="PRE_AI";
  const maxDriftBps=Math.max(2,Math.min(30,Number(isPre?(env.BYBIT_AI_MAX_PRE_REVIEW_DRIFT_BPS||12):(env.BYBIT_AI_MAX_POST_REVIEW_DRIFT_BPS||12))));
  const maxSpreadBps=Math.max(1,Math.min(25,Number(env.BYBIT_MAX_UNIVERSE_SPREAD_BPS||12)));
  try{
    const t=await api.ticker(setup.symbol),x=t?.result?.list?.[0]||{},bid=Number(x.bid1Price||0),ask=Number(x.ask1Price||0);
    if(!(bid>0&&ask>0&&ask>=bid))return {ok:false,reason:`${phase}_QUOTE_INVALID`};
    const px=setup.side==="Buy"?ask:bid,mid=(bid+ask)/2,spreadBps=(ask-bid)/mid*10000,driftBps=Math.abs(px-Number(setup.entry||0))/Math.max(Number(setup.entry||0),1e-12)*10000;
    if(spreadBps>maxSpreadBps)return {ok:false,reason:`${phase}_SPREAD_TOO_WIDE`,bid,ask,px,spreadBps,driftBps,maxSpreadBps,maxDriftBps};
    if(driftBps>maxDriftBps)return {ok:false,reason:`${phase}_ENTRY_DRIFT`,bid,ask,px,spreadBps,driftBps,maxSpreadBps,maxDriftBps};
    return {ok:true,bid,ask,px,spreadBps,driftBps,maxSpreadBps,maxDriftBps,checkedAt:Date.now()};
  }catch(e){return {ok:false,reason:`${phase}_QUOTE_FETCH_FAILED`,error:String(e?.message||e)};}
}

async function callCouncil(env,setup,preAiQuote){if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=="function")return {ok:false,error:"AI_BRIDGE_BINDING_MISSING",providers:{},diagnostics:{}};const secret=String(env.V11_AI_BRIDGE_SECRET||"");if(!secret)return {ok:false,error:"AI_BRIDGE_SECRET_MISSING",providers:{},diagnostics:{}};const timeoutMs=Math.max(9000,Math.min(20000,Number(env.BYBIT_AI_TIMEOUT_MS||16000))),started=Date.now();const instruction=["FINAL ENTRY REVIEW ONLY for one prepared 1-5 minute Bybit USDT perpetual scalp.","Do not search for symbols, alternatives, or new entries.","This candidate already passed deterministic market scan, sizing, risk preflight, and a fresh pre-AI quote check.","Use only supplied evidence.","PASS when direction/context/liquidity are acceptable.","REJECT when materially weak or contradictory.","BLOCKED only for unsafe/stale/inconsistent evidence.","Do not change size, leverage, SL or TP.","Do not require any daily profit target.","Return only the required concise JSON."].join(" ");try{const r=await env.AI_BRIDGE.fetch(new Request("http://127.0.0.1:8789/review",{method:"POST",headers:{"content-type":"application/json","accept":"application/json","authorization":"Bearer "+secret},body:JSON.stringify({evidence:{mode:"BYBIT_SCALP_DECISION",task_id:"bybit-scalp-"+Date.now()+"-"+crypto.randomUUID().slice(0,8),instruction,context:{reviewPolicy:AI_REVIEW_POLICY,reviewStage:"FINAL_PRE_EXECUTION",setup:compactSetup(setup),freshQuote:{px:num(preAiQuote?.px),spreadBps:num(preAiQuote?.spreadBps),driftBps:num(preAiQuote?.driftBps),checkedAt:num(preAiQuote?.checkedAt)},horizon:"1-5m",exchange:"BYBIT"},requestedProviders:PROVIDERS}}),signal:AbortSignal.timeout(timeoutMs)}));const j=await r.json().catch(()=>({})),providers=j?.providers||{};return {ok:r.ok,providers,diagnostics:safeProviderDiagnostics(providers),bridgeStatus:r.status,latencyMs:Date.now()-started,timeoutMs,fastFirst:!!j?.fastFirst,returnedEarly:!!j?.returnedEarly,decisionLatencyMs:num(j?.decisionLatencyMs),error:r.ok?null:(j?.error||"AI_BRIDGE_HTTP_"+r.status)};}catch(e){return {ok:false,error:"AI_BRIDGE_TIMEOUT_OR_FETCH:"+String(e?.message||e),providers:{},diagnostics:{},latencyMs:Date.now()-started,timeoutMs};}}
function providerVerdict(x,setup){if(upper(x?.status)!=="OK")return "UNAVAILABLE";const r=x?.review||{},v=upper(r.verdict);if(["PASS","REJECT","BLOCKED"].includes(v))return v;const d=upper(r.direction),wanted=String(setup?.side||"")==="Buy"?"LONG":"SHORT";if(d===wanted)return "PASS";if(d==="WAIT")return "REJECT";if(["LONG","SHORT"].includes(d)&&d!==wanted)return "REJECT";return "UNAVAILABLE";}

export async function reviewBybitScalp(env,setup){
  const enabled=envBool(env.BYBIT_AI_ENABLED,true),score=num(setup?.score)||0,rr=num(setup?.rr)||0;
  if(!enabled)return {enabled:false,allow:true,mode:"DISABLED",reason:"AI_DISABLED",score,rr,evaluationUsed:false,reviewPolicy:AI_REVIEW_POLICY};

  // Token-saving gate: refresh the one prepared candidate before spending any AI tokens.
  // If the price/spread has already invalidated the entry, deterministic code rejects it and
  // the three providers are never called.
  const preAiQuote=await validateQuote(env,bybitV5(env),setup,"PRE_AI");
  if(!preAiQuote.ok)return {enabled:true,allow:false,mode:"PRE_AI_REJECT",reason:preAiQuote.reason,score,rr,evaluationUsed:false,reviewPolicy:AI_REVIEW_POLICY,aiCalled:false,preAiQuote};

  const raw=await callCouncil(env,setup,preAiQuote),verdicts={};let pass=0,reject=0,blocked=0,unavailable=0;
  for(const p of PROVIDERS){const v=providerVerdict(raw.providers?.[p],setup);verdicts[p]=v;if(v==="PASS")pass++;else if(v==="REJECT")reject++;else if(v==="BLOCKED")blocked++;else unavailable++;}
  const usable=pass+reject+blocked;
  if(usable===0)return {enabled:true,allow:true,mode:"WAIT_AI_PROVIDER",reason:"AI_ALL_UNAVAILABLE_BYPASS",score,rr,evaluationUsed:false,reviewPolicy:AI_REVIEW_POLICY,aiCalled:true,preAiQuote,requiredProviders:PROVIDERS,usable,pass,reject,blocked,unavailable,verdicts,providerDiagnostics:raw.diagnostics||{},bridgeOk:raw.ok,bridgeStatus:raw.bridgeStatus??null,bridgeLatencyMs:raw.latencyMs??null,decisionLatencyMs:raw.decisionLatencyMs??null,fastFirst:!!raw.fastFirst,returnedEarly:!!raw.returnedEarly,timeoutMs:raw.timeoutMs??null,error:raw.error||null};
  const activeProviders=PROVIDERS.filter(p=>verdicts[p]!=="UNAVAILABLE"),waitingProviders=PROVIDERS.filter(p=>verdicts[p]==="UNAVAILABLE");let allow=false,reason="AI_AVAILABLE_VOTE_REJECT";
  if(blocked>0){allow=false;reason="AI_AVAILABLE_BLOCKED";}else if(pass>reject){allow=true;reason=usable===3?"THREE_AI_PASS":"PARTIAL_AI_PASS";}else if(reject>pass){allow=false;reason=usable===3?"THREE_AI_REJECT":"PARTIAL_AI_REJECT";}else{allow=pass>0;reason=allow?"PARTIAL_AI_TIE_PASS":"AI_AVAILABLE_NO_PASS";}
  return {enabled:true,allow,mode:usable===3?"THREE_AI_SCALP":"PARTIAL_AI_SCALP",reason,score,rr,evaluationUsed:true,reviewPolicy:AI_REVIEW_POLICY,aiCalled:true,preAiQuote,requiredProviders:PROVIDERS,activeProviders,waitingProviders,usable,pass,reject,blocked,unavailable,verdicts,providerDiagnostics:raw.diagnostics||{},bridgeOk:raw.ok,bridgeStatus:raw.bridgeStatus??null,bridgeLatencyMs:raw.latencyMs??null,decisionLatencyMs:raw.decisionLatencyMs??null,fastFirst:!!raw.fastFirst,returnedEarly:!!raw.returnedEarly,timeoutMs:raw.timeoutMs??null,error:raw.error||null};
}

export async function revalidateBybitScalpAfterAi(env,api,setup){return validateQuote(env,api,setup,"POST_AI");}
