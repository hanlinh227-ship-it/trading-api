const PROVIDERS=["claude","codex","deepseek","qwen","openrouter"];
const num=v=>Number.isFinite(Number(v))?Number(v):null;
const upper=v=>String(v||"").toUpperCase();
const envBool=(v,d=true)=>v==null?d:String(v).toLowerCase()==="true";

function compactSetup(setup){return {
  symbol:setup.symbol,side:setup.side,strategy:setup.strategy,score:num(setup.score),entry:num(setup.entry),sl:num(setup.sl),tp:num(setup.tp),rr:num(setup.rr),spreadBps:num(setup.spreadBps),atr1:num(setup.atr1),profile:setup.profile,
  context:{vwapAligned:!!setup.context?.vwapAligned,volumeRatio:num(setup.context?.volumeRatio),distanceFromVwapAtr:num(setup.context?.distanceFromVwapAtr),confluence:Array.isArray(setup.context?.confluence)?setup.context.confluence.slice(0,8):[]},
  liquidity:{quoteVolume:num(setup.liquidity?.quoteVolume),spreadBps:num(setup.liquidity?.universeSpreadBps)}
};}

function safeProviderDiagnostics(providers={}){
  const out={};
  for(const p of PROVIDERS){const x=providers?.[p]||{};out[p]={status:upper(x.status||"UNAVAILABLE"),latencySeconds:num(x.latencySeconds),error:x.error?String(x.error).slice(0,180):null,hasReview:!!(x.review&&typeof x.review==="object")};}
  return out;
}

export async function probeBybitAiBridge(env){
  if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=="function")return {ok:false,error:"AI_BRIDGE_BINDING_MISSING",providers:{}};
  const secret=String(env.V11_AI_BRIDGE_SECRET||"");
  if(!secret)return {ok:false,error:"AI_BRIDGE_SECRET_MISSING",providers:{}};
  const started=Date.now();
  try{
    const r=await env.AI_BRIDGE.fetch(new Request("http://127.0.0.1:8789/health",{headers:{accept:"application/json","authorization":"Bearer "+secret},signal:AbortSignal.timeout(5000)}));
    const j=await r.json().catch(()=>({}));
    const providers={};let configured=0,online=0;
    for(const p of PROVIDERS){const x=j?.providers?.[p]||{};providers[p]={configured:!!x.configured,state:upper(x.state||x.status||"UNKNOWN"),model:String(x.model||"").slice(0,80),last_seen:num(x.last_seen)};if(providers[p].configured)configured++;if(["ONLINE","PASS","RUNNING"].includes(providers[p].state))online++;}
    return {ok:r.ok&&configured>0,httpStatus:r.status,latencyMs:Date.now()-started,configured,online,providers,error:r.ok?null:String(j?.error||"AI_BRIDGE_HEALTH_HTTP_"+r.status)};
  }catch(e){return {ok:false,latencyMs:Date.now()-started,error:"AI_BRIDGE_HEALTH_FETCH:"+String(e?.message||e),providers:{}};}
}

async function callCouncil(env,setup){
  if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=="function")return {ok:false,error:"AI_BRIDGE_BINDING_MISSING",providers:{},diagnostics:{}};
  const secret=String(env.V11_AI_BRIDGE_SECRET||"");
  if(!secret)return {ok:false,error:"AI_BRIDGE_SECRET_MISSING",providers:{},diagnostics:{}};
  const timeoutMs=Math.max(8000,Math.min(45000,Number(env.BYBIT_AI_TIMEOUT_MS||25000))),started=Date.now();
  const instruction=[
    "You are reviewing a very short-horizon crypto scalp on Bybit USDT perpetuals.",
    "Judge only whether the supplied LONG/SHORT setup is reasonable for the next roughly 1-5 minutes.",
    "Do not demand high certainty and do not reject merely because no daily profit target is guaranteed.",
    "Do not change position size, leverage, stop loss or take profit; deterministic risk rules own those.",
    "PASS when direction/context/liquidity are acceptable for a scalp.",
    "REJECT when the directional thesis is materially weak or contradictory.",
    "BLOCKED only for a critical data/staleness/inconsistency problem that makes evaluation unsafe.",
    "Keep findings concise and evidence-grounded."
  ].join(" ");
  try{
    const r=await env.AI_BRIDGE.fetch(new Request("http://127.0.0.1:8789/review",{method:"POST",headers:{"content-type":"application/json","accept":"application/json","authorization":"Bearer "+secret},body:JSON.stringify({evidence:{mode:"BYBIT_SCALP_DECISION",task_id:"bybit-scalp-"+Date.now()+"-"+crypto.randomUUID().slice(0,8),instruction,context:{setup:compactSetup(setup),horizon:"1-5m",exchange:"BYBIT",dailyTargetPolicy:"NOT_AN_AI_VETO_INPUT"},requestedProviders:PROVIDERS}}),signal:AbortSignal.timeout(timeoutMs)}));
    const j=await r.json().catch(()=>({})),providers=j?.providers||{};
    return {ok:r.ok,providers,diagnostics:safeProviderDiagnostics(providers),bridgeStatus:r.status,latencyMs:Date.now()-started,timeoutMs,error:r.ok?null:(j?.error||"AI_BRIDGE_HTTP_"+r.status)};
  }catch(e){return {ok:false,error:"AI_BRIDGE_TIMEOUT_OR_FETCH:"+String(e?.message||e),providers:{},diagnostics:{},latencyMs:Date.now()-started,timeoutMs};}
}

function providerVerdict(x,setup){
  if(upper(x?.status)!=="OK")return "UNAVAILABLE";
  const r=x?.review||{},v=upper(r.verdict);
  if(["PASS","REJECT","BLOCKED"].includes(v))return v;
  const d=upper(r.direction),wanted=String(setup?.side||"")==="Buy"?"LONG":"SHORT";
  if(d===wanted)return "PASS";
  if(d==="WAIT")return "REJECT";
  if(["LONG","SHORT"].includes(d)&&d!==wanted)return "REJECT";
  return "UNAVAILABLE";
}

export async function reviewBybitScalp(env,setup){
  const enabled=envBool(env.BYBIT_AI_ENABLED,true),score=num(setup?.score)||0,rr=num(setup?.rr)||0;
  if(!enabled)return {enabled:false,allow:true,mode:"DISABLED",reason:"AI_DISABLED",score,rr};
  const raw=await callCouncil(env,setup),verdicts={};let pass=0,reject=0,blocked=0,unavailable=0;
  for(const p of PROVIDERS){const v=providerVerdict(raw.providers?.[p],setup);verdicts[p]=v;if(v==="PASS")pass++;else if(v==="REJECT")reject++;else if(v==="BLOCKED")blocked++;else unavailable++;}
  const usable=pass+reject+blocked;
  let allow=false,reason="AI_SOFT_GATE_REJECT";
  if(usable===0){allow=score>=82&&rr>=1;reason=allow?"AI_UNAVAILABLE_HIGH_QUALITY_FALLBACK":"AI_UNAVAILABLE_NO_FALLBACK";}
  else if(score>=86){allow=(reject+blocked)<4;reason=allow?"HIGH_QUALITY_SOFT_PASS":"HIGH_QUALITY_STRONG_AI_VETO";}
  else if(score>=80){allow=pass>=2&&pass>=reject&&blocked<2;reason=allow?"MID_QUALITY_AI_PASS":"MID_QUALITY_AI_INSUFFICIENT";}
  else{allow=pass>=3&&blocked===0;reason=allow?"LOW_QUALITY_STRONG_CONSENSUS":"LOW_QUALITY_AI_INSUFFICIENT";}
  return {enabled:true,allow,mode:"SOFT_SCALP",reason,score,rr,usable,pass,reject,blocked,unavailable,verdicts,providerDiagnostics:raw.diagnostics||{},bridgeOk:raw.ok,bridgeStatus:raw.bridgeStatus??null,bridgeLatencyMs:raw.latencyMs??null,timeoutMs:raw.timeoutMs??null,error:raw.error||null};
}

export async function revalidateBybitScalpAfterAi(env,api,setup){
  const maxDriftBps=Math.max(2,Math.min(30,Number(env.BYBIT_AI_MAX_POST_REVIEW_DRIFT_BPS||12))),maxSpreadBps=Math.max(1,Math.min(25,Number(env.BYBIT_MAX_UNIVERSE_SPREAD_BPS||12)));
  try{
    const t=await api.ticker(setup.symbol),x=t?.result?.list?.[0]||{},bid=Number(x.bid1Price||0),ask=Number(x.ask1Price||0);
    if(!(bid>0&&ask>0&&ask>=bid))return {ok:false,reason:"POST_AI_QUOTE_INVALID"};
    const px=setup.side==="Buy"?ask:bid,mid=(bid+ask)/2,spreadBps=(ask-bid)/mid*10000,driftBps=Math.abs(px-Number(setup.entry||0))/Math.max(Number(setup.entry||0),1e-12)*10000;
    if(spreadBps>maxSpreadBps)return {ok:false,reason:"POST_AI_SPREAD_TOO_WIDE",bid,ask,px,spreadBps,driftBps};
    if(driftBps>maxDriftBps)return {ok:false,reason:"POST_AI_ENTRY_DRIFT",bid,ask,px,spreadBps,driftBps};
    return {ok:true,bid,ask,px,spreadBps,driftBps,checkedAt:Date.now()};
  }catch(e){return {ok:false,reason:"POST_AI_QUOTE_FETCH_FAILED",error:String(e?.message||e)};}
}
