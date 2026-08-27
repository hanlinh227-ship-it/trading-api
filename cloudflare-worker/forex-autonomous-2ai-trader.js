import {forexAiQuotaConfig,providerQuotaState,markProviderQuotaExhausted,clearExpiredProviderQuota,looksLikeQuotaExhausted} from "./forex-ai-quota-controller.js";
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const trimBars=(rows,count)=>Array.isArray(rows)?rows.slice(-count).map(r=>({time:r.time,open:n(r.open),high:n(r.high),low:n(r.low),close:n(r.close),volume:n(r.volume)})):[];
const normSide=s=>String(s||"").toUpperCase()==="BUY"?"BUY":String(s||"").toUpperCase()==="SELL"?"SELL":"";
const normOrderType=s=>["MARKET","LIMIT","STOP"].includes(String(s||"").toUpperCase())?String(s||"").toUpperCase():"MARKET";

// F4: Reconcile orderType when both AIs agree symbol+side but differ on order type.
// Conservative rules:
//   Both same type        → use that type
//   MARKET + LIMIT/STOP  → MARKET (immediate execution avoids pending drift)
//   LIMIT  + STOP        → null (different pending semantics, irreconcilable → WAIT)
function reconcileOrderType(typeA,typeB){
  if(typeA===typeB)return typeA;
  if(typeA==="MARKET"||typeB==="MARKET")return "MARKET";
  return null; // LIMIT vs STOP — irreconcilable
}

function compactSnapshot(s={}){return {symbol:String(s.symbol||"").toUpperCase(),bid:n(s.bid),ask:n(s.ask),timestamp:s.timestamp,newsBlocked:Boolean(s.newsBlocked),newsCalendarOk:s.newsCalendarOk===true,bars:{M5:trimBars(s?.bars?.M5,36),M15:trimBars(s?.bars?.M15,32),H1:trimBars(s?.bars?.H1,24),H4:trimBars(s?.bars?.H4,18)}};}
function compactPosition(p={}){return {ticket:String(p.ticket||""),symbol:String(p.symbol||"").toUpperCase(),side:normSide(p.side),entry:n(p.entry),sl:n(p.sl),tp:n(p.tp),volume:n(p.volume),profit:n(p.profit),openedAt:p.openedAt||null};}
function evidence(snapshots,account,learning,requiredSide,positions,context={}){return {mode:"FOREX_AUTONOMOUS_TRADER",requiredSide,alternationRule:`Next filled ENTRY must be ${requiredSide}. This never forces a trade. If no qualified ${requiredSide} exists, entry must WAIT.`,dailyObjective:context.dailyObjective||null,userTarget:context.target||null,hardRiskLimits:context.hardRiskLimits||null,account:{balance:n(account?.balance),equity:n(account?.equity),dayStartEquity:n(account?.dayStartEquity),margin:n(account?.margin),freeMargin:n(account?.freeMargin),marginLevelPct:n(account?.marginLevelPct),openRiskPct:n(account?.openRiskPct),openPositions:n(account?.openPositions)},positions:(positions||[]).map(compactPosition),learningMemory:learning||{},markets:(snapshots||[]).map(compactSnapshot)};}
const schema='Return strict JSON only: {"entry":{"decision":"ENTER|WAIT","symbol":"SYMBOL|NONE","side":"BUY|SELL|NONE","orderType":"MARKET|LIMIT|STOP","entryPrice":number,"requestedRiskPct":0-1,"sl":number,"tp":number,"technicalAnalysis":"concrete M5/M15/H1/H4 reasoning","economicAnalysis":"current macro/rates/news/risk reasoning","thesis":"short synthesis","invalidation":"short","riskFlags":[]},"entryCandidates":[{"decision":"ENTER","symbol":"SYMBOL","side":"BUY|SELL","orderType":"MARKET|LIMIT|STOP","entryPrice":number,"requestedRiskPct":0-1,"sl":number,"tp":number,"technicalAnalysis":"reasoning","economicAnalysis":"reasoning","thesis":"short","invalidation":"short","riskFlags":[]}],"management":[{"ticket":"ticket","action":"HOLD|CLOSE|MODIFY_SLTP","sl":number,"tp":number,"reason":"AI reasoning"}],"portfolioView":"short"}. For MARKET entryPrice may be 0 because broker quote is authority. For LIMIT/STOP entryPrice must be the intended trigger price. entryCandidates may contain up to 3 genuinely tradable candidates and must respect requiredSide; keep entry as your single best candidate for backward compatibility.';
function instruction(ev){const tgt=ev?.userTarget||{},daily=ev?.dailyObjective||{};const campaign=tgt?.configured||tgt?.enabled?`Active user campaign: targetUsd=${n(tgt.targetUsd)}, targetPct=${n(tgt.targetPct)}, targetDays=${n(tgt.targetDays)}. Interpret targetDays as trading days only; Saturday and Sunday do not consume a campaign day. Current campaign progressUsd=${n(tgt.profitUsd)}, progressPct=${n(tgt.progressPct)}, reached=${Boolean(tgt.reached)}.`:"No active user campaign.";return `You are the trader, not a reviewer of a precomputed signal. There is no rule-based signal, setup score, indicator gate, automated ranking, confidence gate or deterministic trade manager. Analyze raw MT5 quotes/candles from first principles and independently decide entry and open-position management. Required next filled entry side is ${ev.requiredSide}; if no genuinely tradable ${ev.requiredSide} setup exists, WAIT. You may choose MARKET, LIMIT, or STOP entry based on structure. BUY LIMIT must be below current ask, SELL LIMIT above current bid, BUY STOP above current ask, SELL STOP below current bid. Pending orders are not permission to bracket news. If the selected market has newsBlocked=true or newsCalendarOk=false, WAIT; do not place a MARKET, LIMIT, or STOP order. Pending orders are cancelled by the MT5 execution shell if a red/high-impact news window begins before fill. ${campaign} Daily objective is strictly greater than ${n(daily.minProfitPct,1)}% from broker day-start equity; current daily PnL is ${n(daily.profitPct)}%. Treat both daily objective and campaign target as goals, never guarantees: never force an entry, never chase a missed target, never widen risk budget, and never lower setup quality merely because time is running out. Do NOT be excessively perfectionist: a valid intraday trade does not need perfect alignment across every timeframe, every indicator, or every macro factor. If price structure, invalidation, current context and RR are good enough for a professional discretionary intraday trade, mark it ENTER rather than waiting for an idealized textbook setup. Return up to 3 genuinely tradable ${ev.requiredSide} candidates so another independent AI has a fair chance to reach symbol consensus; do not pad the list with weak ideas. Position size is calculated downstream from stop distance and the allowed risk budget. You MAY produce a structurally tighter stop when genuinely justified by market invalidation, which can result in a larger lot while keeping monetary/risk-percent exposure unchanged; NEVER distort or artificially tighten the stop merely to enlarge lot size. If a larger lot would require more risk, do not do it. Once the campaign target is reached, do not initiate a new entry; only manage existing positions. After the daily objective is exceeded, prioritize preserving the positive day and take another entry only when the setup remains genuinely high quality and campaign progress still justifies exposure. Use current macro/news context when materially useful, but never invent broker prices or override MT5 news state. Think deeply and use available reasoning budget. ${schema}`;}

async function callUnifiedBridge(env,ev){
 await Promise.all([clearExpiredProviderQuota(env,"chatgpt"),clearExpiredProviderQuota(env,"claude")]);
 const [gq,cq]=await Promise.all([providerQuotaState(env,"chatgpt"),providerQuotaState(env,"claude")]);
 if(gq.blocked||cq.blocked)return {ok:false,quotaBlocked:true,error:"2AI_QUOTA_COOLDOWN",providers:{chatgpt:{ok:false,quotaBlocked:gq.blocked,quotaState:gq},claude:{ok:false,quotaBlocked:cq.blocked,quotaState:cq}}};
 if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=="function")return {ok:false,error:"AI_BRIDGE_BINDING_MISSING",providers:{}};
 const secret=String(env.V11_AI_BRIDGE_SECRET||"");
 if(!secret)return {ok:false,error:"AI_BRIDGE_SECRET_MISSING",providers:{}};
 const timeoutMs=Math.max(20000,Math.min(65000,Number(env.FOREX_AI_TIMEOUT_MS||55000))),started=Date.now();
 try{
  const body={evidence:{...ev,task_id:`forex-${Date.now()}-${crypto.randomUUID().slice(0,8)}`,requestedProviders:["claude","codex"],instruction:instruction(ev)}};
  const r=await env.AI_BRIDGE.fetch(new Request("http://127.0.0.1:8789/review",{method:"POST",headers:{"content-type":"application/json","accept":"application/json","authorization":"Bearer "+secret},body:JSON.stringify(body),signal:AbortSignal.timeout(timeoutMs)}));
  const j=await r.json().catch(()=>({})),raw=j?.providers||{},codex=raw.codex||{},claude=raw.claude||{};
  const provider=(name,x)=>({ok:String(x?.status||"").toUpperCase()==="OK"&&!!x?.review,provider:name,review:x?.review||null,latencySeconds:n(x?.latencySeconds),error:x?.error?String(x.error):null,transport:"UNIFIED_2AI_VPC_BRIDGE"});
  const g=provider("chatgpt",codex),c=provider("claude",claude);
  if(!g.ok&&looksLikeQuotaExhausted(r.status,{error:g.error,provider:codex}))await markProviderQuotaExhausted(env,"chatgpt",g.error||`BRIDGE_HTTP_${r.status}`);
  if(!c.ok&&looksLikeQuotaExhausted(r.status,{error:c.error,provider:claude}))await markProviderQuotaExhausted(env,"claude",c.error||`BRIDGE_HTTP_${r.status}`);
  return {ok:r.ok&&j?.ok!==false&&g.ok&&c.ok&&Number(j?.quorum||0)>=2,providers:{chatgpt:g,claude:c},error:r.ok?null:String(j?.error||`AI_BRIDGE_HTTP_${r.status}`),latencyMs:Date.now()-started,decisionLatencyMs:n(j?.decisionLatencyMs),timeoutMs};
 }catch(e){return {ok:false,error:"AI_BRIDGE_TIMEOUT_OR_FETCH:"+String(e?.message||e),providers:{},latencyMs:Date.now()-started,timeoutMs};}
}

function entryOf(x={}){const e=x&&typeof x==="object"?x:{};return {decision:String(e.decision||"WAIT").toUpperCase()==="ENTER"?"ENTER":"WAIT",symbol:String(e.symbol||"NONE").toUpperCase(),side:normSide(e.side),orderType:normOrderType(e.orderType),entryPrice:n(e.entryPrice),requestedRiskPct:Math.max(0,Math.min(1,n(e.requestedRiskPct))),sl:n(e.sl),tp:n(e.tp),technicalAnalysis:String(e.technicalAnalysis||"").trim(),economicAnalysis:String(e.economicAnalysis||"").trim(),thesis:String(e.thesis||"").trim(),invalidation:String(e.invalidation||"").trim(),riskFlags:Array.isArray(e.riskFlags)?e.riskFlags:[]};}
function entriesOf(x={}){const out=[];if(Array.isArray(x?.entryCandidates))for(const e of x.entryCandidates.slice(0,3)){const z=entryOf(e);if(z.decision==="ENTER"&&z.symbol!=="NONE"&&z.side)out.push(z);}const best=entryOf(x?.entry||{});if(best.decision==="ENTER"&&best.symbol!=="NONE"&&best.side&&!out.some(z=>z.symbol===best.symbol&&z.side===best.side&&z.orderType===best.orderType))out.unshift(best);return out.slice(0,3);}
function managementOf(x={}){return (Array.isArray(x?.management)?x.management:[]).map(m=>({ticket:String(m.ticket||""),action:["HOLD","CLOSE","MODIFY_SLTP"].includes(String(m.action||"").toUpperCase())?String(m.action||"").toUpperCase():"HOLD",sl:n(m.sl),tp:n(m.tp),reason:String(m.reason||"").trim()})).filter(m=>m.ticket);}

// candidateGeometry: accepts resolvedOrderType so F4 reconciliation is applied
// before geometry validation, not using each AI's individual preference.
function candidateGeometry(e,m,minRR,resolvedOrderType){
  const bid=n(m.bid),ask=n(m.ask),orderType=resolvedOrderType||normOrderType(e.orderType);
  if(!(bid>0&&ask>0)||Boolean(m.newsBlocked)||m.newsCalendarOk!==true)return null;
  let entry=orderType==="MARKET"?(e.side==="BUY"?ask:bid):n(e.entryPrice);
  if(!(entry>0&&e.sl>0&&e.tp>0))return null;
  if(orderType==="LIMIT"&&e.side==="BUY"&&!(entry<ask))return null;
  if(orderType==="LIMIT"&&e.side==="SELL"&&!(entry>bid))return null;
  if(orderType==="STOP"&&e.side==="BUY"&&!(entry>ask))return null;
  if(orderType==="STOP"&&e.side==="SELL"&&!(entry<bid))return null;
  const stop=e.side==="BUY"?entry-e.sl:e.sl-entry,reward=e.side==="BUY"?e.tp-entry:entry-e.tp,rr=stop>0?reward/stop:0;
  if(!(stop>0&&reward>0&&rr>=minRR))return null;
  return {entry,orderType,sl:e.sl,tp:e.tp,rr};
}

// F4: Match on symbol+side only; reconcile orderType conservatively.
// Both AIs must still provide independent technical+economic reasoning.
function entryConsensus(g,c,snap,minRR,requiredSide){
  const gs=entriesOf(g).filter(x=>x.side===requiredSide),cs=entriesOf(c).filter(x=>x.side===requiredSide);
  if(!gs.length||!cs.length)return {ok:false,reason:"2AI_WAIT",gptCandidates:gs,claudeCandidates:cs};
  const overlaps=[];
  for(const gp of gs)for(const cp of cs){
    if(gp.symbol!==cp.symbol||gp.side!==cp.side)continue; // F4: symbol+side only
    if(!gp.technicalAnalysis||!cp.technicalAnalysis||!gp.economicAnalysis||!cp.economicAnalysis)continue;
    const m=(snap||[]).find(x=>String(x.symbol||"").toUpperCase()===gp.symbol);
    if(!m)continue;
    const resolvedOrderType=reconcileOrderType(gp.orderType,cp.orderType);
    if(!resolvedOrderType)continue; // LIMIT vs STOP — irreconcilable → skip
    const gg=candidateGeometry(gp,m,minRR,resolvedOrderType),cg=candidateGeometry(cp,m,minRR,resolvedOrderType);
    if(!gg||!cg)continue;
    const chosen=gg.rr<=cg.rr?{plan:gp,geo:gg,provider:"chatgpt"}:{plan:cp,geo:cg,provider:"claude"};
    overlaps.push({gp,cp,m,chosen,resolvedOrderType,orderTypeReconciled:gp.orderType!==cp.orderType,consensusStrength:Math.min(gg.rr,cg.rr),gptGeometry:gg,claudeGeometry:cg});
  }
  if(!overlaps.length)return {ok:false,reason:"2AI_NO_COMMON_TRADABLE_CANDIDATE",requiredSide,gptCandidates:gs,claudeCandidates:cs};
  overlaps.sort((a,b)=>b.consensusStrength-a.consensusStrength);
  const x=overlaps[0],gp=x.gp,cp=x.cp,geo=x.chosen.geo;
  return {ok:true,symbol:gp.symbol,side:gp.side,orderType:x.resolvedOrderType,entry:geo.entry,entryPrice:geo.entry,sl:geo.sl,tp:geo.tp,rr:geo.rr,requestedRiskPct:Math.min(gp.requestedRiskPct||1,cp.requestedRiskPct||1),technicalAnalysis:{chatgpt:gp.technicalAnalysis,claude:cp.technicalAnalysis},economicAnalysis:{chatgpt:gp.economicAnalysis,claude:cp.economicAnalysis},thesis:`GPT/Codex: ${gp.thesis.slice(0,320)} | Claude: ${cp.thesis.slice(0,320)}`,consensusPlanSource:x.chosen.provider,individualRR:{chatgpt:x.gptGeometry.rr,claude:x.claudeGeometry.rr},ai:{chatgpt:gp,claude:cp},candidateOverlapCount:overlaps.length,orderTypeReconciled:x.orderTypeReconciled};
}

// F2: managementConsensus — fixed SELL SL direction.
// BUY:  SL is below entry. Higher SL price = further from market = safer.
// SELL: SL is above entry. Higher SL price = further from market = safer.
// → Math.max is correct for BOTH directions. Never tighten beyond currentSl.
// TP: conservative — cap BUY TP at minimum of the two; floor SELL TP at maximum.
function managementConsensus(g,c,positions=[]){
  const gm=managementOf(g),cm=managementOf(c),out=[];
  for(const p of positions||[]){
    const ticket=String(p.ticket||""),a=gm.find(x=>x.ticket===ticket),b=cm.find(x=>x.ticket===ticket);
    if(!a||!b||a.action!==b.action||a.action==="HOLD"){out.push({ticket,action:"HOLD",reason:!a||!b?"2AI_MANAGEMENT_MISSING":"2AI_HOLD_OR_DISAGREE"});continue;}
    if(a.action==="CLOSE"){out.push({ticket,action:"CLOSE",reason:`GPT/Codex: ${a.reason} | Claude: ${b.reason}`});continue;}
    const side=normSide(p.side),currentSl=n(p.sl),currentTp=n(p.tp);
    // F2: Math.max for both BUY and SELL — always expands toward safer wider stop.
    const slCandidates=[a.sl,b.sl,currentSl].filter(x=>x>0);
    let sl=slCandidates.length>0?Math.max(...slCandidates):currentSl;
    if(!(sl>0))sl=currentSl;
    let tp=currentTp;
    if(a.tp>0&&b.tp>0)tp=side==="BUY"?Math.min(a.tp,b.tp):Math.max(a.tp,b.tp);
    out.push({ticket,action:"MODIFY_SLTP",sl,tp,reason:`GPT/Codex: ${a.reason} | Claude: ${b.reason}`});
  }
  return out;
}

export async function runForexAutonomous2Ai(env,snapshots=[],account={},learning={},requiredSide="BUY",positions=[],context={}){
 const ev=evidence(snapshots,account,learning,requiredSide,positions,context),council=await callUnifiedBridge(env,ev),g=council?.providers?.chatgpt||{},c=council?.providers?.claude||{};
 if(!(council.ok&&g.ok&&c.ok))return {ok:false,consensus:false,reason:council.quotaBlocked?"2AI_QUOTA_COOLDOWN":"2AI_PROVIDER_UNAVAILABLE",providers:{chatgpt:g,claude:c},bridge:{error:council.error,latencyMs:council.latencyMs,decisionLatencyMs:council.decisionLatencyMs},requiredSide};
 const entry=entryConsensus(g.review,c.review,snapshots,n(context?.hardRiskLimits?.minRR,1.5),requiredSide),management=managementConsensus(g.review,c.review,positions);
 return {ok:true,consensus:entry.ok,reason:entry.ok?"PURE_AI_2AI_ENTRY_CONSENSUS":"PURE_AI_2AI_NO_ENTRY",proposal:entry.ok?entry:null,entryDetail:entry,management,primaryManagement:management.find(x=>x.action!=="HOLD")||null,providers:{chatgpt:g,claude:c},bridge:{transport:"UNIFIED_2AI_VPC_BRIDGE",latencyMs:council.latencyMs,decisionLatencyMs:council.decisionLatencyMs},evidenceMode:ev.mode,requiredSide,portfolioView:{chatgpt:String(g.review?.portfolioView||""),claude:String(c.review?.portfolioView||"")}};
}
export function forexAutonomous2AiHealth(env){const q=forexAiQuotaConfig(env),bridgeConfigured=!!env.AI_BRIDGE&&typeof env.AI_BRIDGE.fetch==="function"&&!!String(env.V11_AI_BRIDGE_SECRET||"");return {mode:"PURE_AI_GPT_CODEX_CLAUDE_2AI_BRIDGE",authority:"AI_SELECTS_MARKET_LIMIT_STOP_ENTRY_RISK_AND_POSITION_MANAGEMENT_FROM_RAW_MT5",transport:"UNIFIED_2AI_VPC_BRIDGE",ruleBasedSignalAuthority:false,precomputedScoreAuthority:false,confidenceGateAuthority:false,deterministicTradeManager:false,technicalReasoningRequired:true,currentEconomicContextRequired:true,redNewsFailClosed:true,pendingOrdersCancelledOnRedNews:true,orderTypes:["MARKET","LIMIT","STOP"],alternatingFilledSideRequired:true,quotaCooldownHours:q.cooldownMs/3600000,quotaStateAvailableDuringRuntimeCalls:true,entryConsensusMode:"SYMBOL_SIDE_WITH_ORDER_TYPE_RECONCILIATION",chatgpt:{configured:bridgeConfigured,providerAlias:"codex",model:"gpt-5.6-sol via Codex CLI",maxOutputTokens:q.openAiMaxOutputTokens},claude:{configured:bridgeConfigured,providerAlias:"claude",model:"Claude CLI Sonnet",maxOutputTokens:q.claudeMaxOutputTokens}};}
