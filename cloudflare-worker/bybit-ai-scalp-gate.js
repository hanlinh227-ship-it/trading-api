import {bybitV5} from "./bybit-v5-client.js";

const PROVIDERS=["claude","codex","deepseek"];
const num=v=>Number.isFinite(Number(v))?Number(v):null;
const upper=v=>String(v||"").toUpperCase();
const envBool=(v,d=true)=>v==null?d:String(v).toLowerCase()==="true";
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

// AI policy: the deterministic scanner owns market discovery. The three core AIs are only
// allowed to review one candidate that has already passed scan + one-shot fresh-price
// preparation + sizing + risk validation. AI never searches the market.
const AI_REVIEW_POLICY="FINAL_ENTRY_REVIEW_ONLY";

function compactSetup(setup){
  return {
    symbol:setup.symbol,
    side:setup.side,
    strategy:setup.strategy,
    score:num(setup.score),
    entry:num(setup.entry),
    originalEntry:num(setup.originalEntry),
    entryState:setup.entryState||"ORIGINAL",
    reanchorCount:Number(setup.reanchorCount||0),
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

async function liveQuote(env,api,setup){
  const maxSpreadBps=Math.max(1,Math.min(25,Number(env.BYBIT_MAX_UNIVERSE_SPREAD_BPS||12)));
  try{
    const t=await api.ticker(setup.symbol),x=t?.result?.list?.[0]||{},bid=Number(x.bid1Price||0),ask=Number(x.ask1Price||0);
    if(!(bid>0&&ask>0&&ask>=bid))return {ok:false,reason:"QUOTE_INVALID"};
    const px=setup.side==="Buy"?ask:bid,mid=(bid+ask)/2,spreadBps=(ask-bid)/mid*10000;
    if(spreadBps>maxSpreadBps)return {ok:false,reason:"SPREAD_TOO_WIDE",bid,ask,px,spreadBps,maxSpreadBps};
    return {ok:true,bid,ask,px,spreadBps,maxSpreadBps,checkedAt:Date.now()};
  }catch(e){return {ok:false,reason:"QUOTE_FETCH_FAILED",error:String(e?.message||e)};}
}

// Exactly one preparation refresh per scanner candidate. The scanner snapshot is allowed to
// age while the whole universe is analyzed; this function freshens only the winning candidate.
// It may re-anchor once, never loops, and never relaxes the hard chase cap.
export async function prepareBybitScalpForReview(env,setup,api=bybitV5(env)){
  const q=await liveQuote(env,api,setup);
  if(!q.ok)return {ok:false,reason:`PRE_AI_${q.reason}`,quote:q,setup:null};
  const originalEntry=Number(setup?.entry||0),px=Number(q.px||0),atr=Math.abs(Number(setup?.atr1||0)),sl=Number(setup?.sl||0),tp=Number(setup?.tp||0),score=Number(setup?.score||0),side=String(setup?.side||"");
  if(!(originalEntry>0&&px>0&&atr>0&&sl>0&&tp>0))return {ok:false,reason:"PRE_AI_GEOMETRY_INVALID",quote:q,setup:null};
  const geometryOk=side==="Buy"?sl<px&&tp>px:side==="Sell"?sl>px&&tp<px:false;
  if(!geometryOk)return {ok:false,reason:"PRE_AI_REANCHOR_GEOMETRY_INVALID",quote:q,setup:null};

  const signedMoveBps=(px-originalEntry)/originalEntry*10000;
  const adverseBps=side==="Buy"?Math.max(0,signedMoveBps):Math.max(0,-signedMoveBps);
  const favorableBps=side==="Buy"?Math.max(0,-signedMoveBps):Math.max(0,signedMoveBps);
  const absDriftBps=Math.abs(signedMoveBps),driftAtr=Math.abs(px-originalEntry)/atr;
  const normalBps=clamp(Number(env.BYBIT_AI_NORMAL_PRE_DRIFT_BPS||12),4,15);
  const softBps=Math.max(normalBps,clamp(Number(env.BYBIT_AI_REANCHOR_SOFT_BPS||20),12,24));
  const hardBps=Math.max(softBps,clamp(Number(env.BYBIT_AI_REANCHOR_HARD_BPS||30),20,35));
  const maxFavorableBps=Math.max(hardBps,clamp(Number(env.BYBIT_AI_FAVORABLE_DRIFT_BPS||35),25,45));
  const vwapAligned=!!setup?.context?.vwapAligned,volumeRatio=Number(setup?.context?.volumeRatio||0),confluence=Array.isArray(setup?.context?.confluence)?setup.context.confluence:[];

  if(adverseBps>hardBps)return {ok:false,reason:"PRE_AI_ENTRY_DRIFT_HARD_CAP",quote:{...q,absDriftBps,adverseBps,favorableBps,driftAtr,normalBps,softBps,hardBps},setup:null};
  if(favorableBps>maxFavorableBps||driftAtr>.75)return {ok:false,reason:"PRE_AI_PRICE_MOVE_TOO_LARGE",quote:{...q,absDriftBps,adverseBps,favorableBps,driftAtr,normalBps,softBps,hardBps},setup:null};
  if(adverseBps>normalBps){
    if(score<90||!vwapAligned||driftAtr>.55)return {ok:false,reason:"PRE_AI_REANCHOR_QUALITY_FAIL",quote:{...q,absDriftBps,adverseBps,favorableBps,driftAtr,normalBps,softBps,hardBps},setup:null};
    if(adverseBps>softBps&&(score<95||volumeRatio<.75||confluence.length<2))return {ok:false,reason:"PRE_AI_EXTENDED_REANCHOR_FAIL",quote:{...q,absDriftBps,adverseBps,favorableBps,driftAtr,normalBps,softBps,hardBps},setup:null};
  }

  const riskDist=Math.abs(px-sl),rewardDist=Math.abs(tp-px),structureR=riskDist>0?rewardDist/riskDist:0,minStructureR=Math.max(1,Math.min(2,Number(env.BYBIT_MIN_RR||1)));
  if(!(structureR>=minStructureR))return {ok:false,reason:"PRE_AI_REANCHORED_STRUCTURE_RR_LOW",quote:{...q,absDriftBps,adverseBps,favorableBps,driftAtr,structureR,minStructureR},setup:null};

  const reanchored=adverseBps>normalBps;
  const next={...setup,originalEntry,entry:px,rr:structureR,spreadBps:q.spreadBps,entryState:reanchored?"REANCHORED":"FRESHENED",reanchorCount:reanchored?1:0,reanchor:{originalEntry,currentEntry:px,absDriftBps,adverseBps,favorableBps,driftAtr,structureR,normalBps,softBps,hardBps,checkedAt:q.checkedAt}};
  if(next.context?.vwap>0)next.context={...next.context,distanceFromVwapAtr:Math.abs(px-Number(next.context.vwap))/atr};
  return {ok:true,reason:reanchored?"PRE_AI_REANCHORED_ONCE":"PRE_AI_FRESHENED",setup:next,quote:{...q,absDriftBps,adverseBps,favorableBps,driftAtr,structureR,entryState:next.entryState,reanchorCount:next.reanchorCount}};
}

async function validateQuote(env,api,setup,phase){
  const maxAdverseBps=Math.max(2,Math.min(25,Number(env.BYBIT_AI_MAX_POST_REVIEW_DRIFT_BPS||12))),maxFavorableBps=Math.max(maxAdverseBps,Math.min(25,Number(env.BYBIT_AI_MAX_POST_FAVORABLE_DRIFT_BPS||18)));
  const q=await liveQuote(env,api,setup);
  if(!q.ok)return {...q,ok:false,reason:`${phase}_${q.reason}`};
  const px=Number(q.px||0),entry=Number(setup.entry||0),atr=Math.abs(Number(setup.atr1||0)),side=String(setup.side||""),sl=Number(setup.sl||0),tp=Number(setup.tp||0),signedMoveBps=(px-entry)/Math.max(entry,1e-12)*10000;
  const adverseBps=side==="Buy"?Math.max(0,signedMoveBps):Math.max(0,-signedMoveBps),favorableBps=side==="Buy"?Math.max(0,-signedMoveBps):Math.max(0,signedMoveBps),driftBps=Math.abs(signedMoveBps),driftAtr=atr>0?Math.abs(px-entry)/atr:Infinity;
  const geometryOk=side==="Buy"?sl<px&&tp>px:side==="Sell"?sl>px&&tp<px:false;
  if(!geometryOk)return {...q,ok:false,reason:`${phase}_GEOMETRY_INVALID`,driftBps,adverseBps,favorableBps,driftAtr,maxAdverseBps,maxFavorableBps};
  if(adverseBps>maxAdverseBps)return {...q,ok:false,reason:`${phase}_ENTRY_DRIFT`,driftBps,adverseBps,favorableBps,driftAtr,maxAdverseBps,maxFavorableBps};
  if(favorableBps>maxFavorableBps||driftAtr>.40)return {...q,ok:false,reason:`${phase}_PRICE_MOVE_TOO_LARGE`,driftBps,adverseBps,favorableBps,driftAtr,maxAdverseBps,maxFavorableBps};
  return {...q,ok:true,driftBps,adverseBps,favorableBps,driftAtr,maxAdverseBps,maxFavorableBps};
}

async function callCouncil(env,setup,preAiQuote){if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=="function")return {ok:false,error:"AI_BRIDGE_BINDING_MISSING",providers:{},diagnostics:{}};const secret=String(env.V11_AI_BRIDGE_SECRET||"");if(!secret)return {ok:false,error:"AI_BRIDGE_SECRET_MISSING",providers:{},diagnostics:{}};const timeoutMs=Math.max(9000,Math.min(20000,Number(env.BYBIT_AI_TIMEOUT_MS||16000))),started=Date.now();const instruction=["FINAL ENTRY REVIEW ONLY for one prepared 1-5 minute Bybit USDT perpetual scalp.","Do not search for symbols, alternatives, or new entries.","This candidate already passed deterministic market scan, one-shot price preparation, sizing and risk preflight.","Use only supplied evidence.","PASS when direction/context/liquidity are acceptable.","REJECT when materially weak or contradictory.","BLOCKED only for unsafe/stale/inconsistent evidence.","Do not change size, leverage, SL or TP.","Do not require any daily profit target.","Return only the required concise JSON."].join(" ");try{const r=await env.AI_BRIDGE.fetch(new Request("http://127.0.0.1:8789/review",{method:"POST",headers:{"content-type":"application/json","accept":"application/json","authorization":"Bearer "+secret},body:JSON.stringify({evidence:{mode:"BYBIT_SCALP_DECISION",task_id:"bybit-scalp-"+Date.now()+"-"+crypto.randomUUID().slice(0,8),instruction,context:{reviewPolicy:AI_REVIEW_POLICY,reviewStage:"FINAL_PRE_EXECUTION",setup:compactSetup(setup),freshQuote:{px:num(preAiQuote?.px),spreadBps:num(preAiQuote?.spreadBps),absDriftBps:num(preAiQuote?.absDriftBps),adverseBps:num(preAiQuote?.adverseBps),driftAtr:num(preAiQuote?.driftAtr),checkedAt:num(preAiQuote?.checkedAt)},horizon:"1-5m",exchange:"BYBIT"},requestedProviders:PROVIDERS}}),signal:AbortSignal.timeout(timeoutMs)}));const j=await r.json().catch(()=>({})),providers=j?.providers||{};return {ok:r.ok,providers,diagnostics:safeProviderDiagnostics(providers),bridgeStatus:r.status,latencyMs:Date.now()-started,timeoutMs,fastFirst:!!j?.fastFirst,returnedEarly:!!j?.returnedEarly,decisionLatencyMs:num(j?.decisionLatencyMs),error:r.ok?null:(j?.error||"AI_BRIDGE_HTTP_"+r.status)};}catch(e){return {ok:false,error:"AI_BRIDGE_TIMEOUT_OR_FETCH:"+String(e?.message||e),providers:{},diagnostics:{},latencyMs:Date.now()-started,timeoutMs};}}
function providerVerdict(x,setup){if(upper(x?.status)!=="OK")return "UNAVAILABLE";const r=x?.review||{},v=upper(r.verdict);if(["PASS","REJECT","BLOCKED"].includes(v))return v;const d=upper(r.direction),wanted=String(setup?.side||"")==="Buy"?"LONG":"SHORT";if(d===wanted)return "PASS";if(d==="WAIT")return "REJECT";if(["LONG","SHORT"].includes(d)&&d!==wanted)return "REJECT";return "UNAVAILABLE";}

export async function reviewBybitScalp(env,setup,preparedQuote=null){
  const enabled=envBool(env.BYBIT_AI_ENABLED,true),score=num(setup?.score)||0,rr=num(setup?.rr)||0;
  if(!enabled)return {enabled:false,allow:true,mode:"DISABLED",reason:"AI_DISABLED",score,rr,evaluationUsed:false,reviewPolicy:AI_REVIEW_POLICY};
  const preAiQuote=preparedQuote||await validateQuote(env,bybitV5(env),setup,"PRE_AI");
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
