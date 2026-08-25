import {betaCluster,edgeKey,parseRegimeFromStrategy} from "./bybit-adaptive-edge.js";

// V2 store is retained for continuity, but classification is now strict net-only.
// Gross-only outcomes are quarantined from adaptive statistics instead of being treated as net evidence.
const PREFIX="bybit:learning:v2";
const K={events:`${PREFIX}:events`,state:`${PREFIX}:state`,champion:`${PREFIX}:champion`,challenger:`${PREFIX}:challenger`};
const PROVIDERS=["claude","codex","deepseek"];
const PROVIDER_SET="AUTO_CORE_3_V2_STRICT_NET";
const DATA_INTEGRITY_VERSION="BYBIT_LEARNING_NET_PNL_V2";
const LEARNING_POLICY_VERSION="STRICT_NET_ONLY_V1";
const now=()=>Date.now(),EPS=1e-9;
async function get(env,key,def){try{return await env.TRADING_STATE?.get(key,{type:"json"})??def;}catch{return def;}}
async function put(env,key,val){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(val));}
const num=v=>Number.isFinite(Number(v))?Number(v):null;
function boundedEvent(x={}){const strategy=String(x.strategy||"").slice(0,120),symbol=String(x.symbol||"").toUpperCase().slice(0,30),regime=String(x.regime||parseRegimeFromStrategy(strategy)||"UNKNOWN").slice(0,32);return {
  id:String(x.id||crypto.randomUUID()).slice(0,120),at:Number(x.at||now()),stage:String(x.stage||"UNKNOWN").slice(0,40),mode:String(x.mode||"UNKNOWN").slice(0,20),providerSet:PROVIDER_SET,dataIntegrityVersion:DATA_INTEGRITY_VERSION,learningPolicyVersion:LEARNING_POLICY_VERSION,
  symbol,side:String(x.side||"").slice(0,10),strategy,regime,betaCluster:String(x.betaCluster||betaCluster(symbol)).slice(0,40),exitProfile:String(x.exitProfile||"BALANCED").slice(0,24),
  score:num(x.score),rr:num(x.rr),riskUsd:num(x.riskUsd),rewardUsd:num(x.rewardUsd),entry:num(x.entry),sl:num(x.sl),tp:num(x.tp),leverage:num(x.leverage),
  entryState:String(x.preparation?.setup?.entryState||x.entryState||"").slice(0,24)||null,reanchorCount:num(x.preparation?.setup?.reanchorCount??x.reanchorCount),
  preparation:x.preparation&&typeof x.preparation==="object"?{reason:String(x.preparation.reason||"").slice(0,100),ok:!!x.preparation.ok,driftBps:num(x.preparation.quote?.absDriftBps),adverseBps:num(x.preparation.quote?.adverseBps),favorableBps:num(x.preparation.quote?.favorableBps),driftAtr:num(x.preparation.quote?.driftAtr)}:null,
  ai:x.ai&&typeof x.ai==="object"?{reason:String(x.ai.reason||"").slice(0,120),pass:num(x.ai.pass),reject:num(x.ai.reject),blocked:num(x.ai.blocked),unavailable:num(x.ai.unavailable),verdicts:x.ai.verdicts||{}}:null,
  postAi:x.postAi&&typeof x.postAi==="object"?{spreadBps:num(x.postAi.spreadBps),driftBps:num(x.postAi.driftBps),adverseBps:num(x.postAi.adverseBps),favorableBps:num(x.postAi.favorableBps),px:num(x.postAi.px)}:null,
  execution:x.execution&&typeof x.execution==="object"?{signalPrice:num(x.execution.signalPrice),preparedPrice:num(x.execution.preparedPrice),submittedPrice:num(x.execution.submittedPrice),fillPrice:num(x.execution.fillPrice),entrySlippageBps:num(x.execution.entrySlippageBps),exitSlippageBps:num(x.execution.exitSlippageBps),feesUsd:num(x.execution.feesUsd),latencyMs:num(x.execution.latencyMs)}:null,
  outcome:x.outcome&&typeof x.outcome==="object"?{status:String(x.outcome.status||"").slice(0,40),authority:String(x.outcome.authority||"").slice(0,40)||null,sourceId:String(x.outcome.sourceId||"").slice(0,160)||null,pnlUsd:num(x.outcome.pnlUsd),netPnlUsd:num(x.outcome.netPnlUsd),rMultiple:num(x.outcome.rMultiple),netR:num(x.outcome.netR),holdSec:num(x.outcome.holdSec),mfeR:num(x.outcome.mfeR),maeR:num(x.outcome.maeR),feesUsd:num(x.outcome.feesUsd),exitReason:String(x.outcome.exitReason||x.outcome.status||"").slice(0,50)}:null,
  reason:String(x.reason||"").slice(0,160)
};}
function effectiveNetR(e){
  const o=e?.outcome||{},risk=Number(e?.riskUsd),netR=Number(o.netR),netPnl=Number(o.netPnlUsd),gross=Number(o.rMultiple),fees=Number(o.feesUsd??e?.execution?.feesUsd);
  if(Number.isFinite(netR))return netR;
  if(Number.isFinite(netPnl)&&risk>0)return netPnl/risk;
  if(Number.isFinite(gross)&&Number.isFinite(fees)&&risk>0)return gross-fees/risk;
  // Critical integrity rule: gross-only outcomes must never drive V2 adaptive decisions.
  return null;
}
function netEvidenceKind(e){const o=e?.outcome||{},risk=Number(e?.riskUsd);if(Number.isFinite(Number(o.netR)))return "NET_R";if(Number.isFinite(Number(o.netPnlUsd))&&risk>0)return "NET_PNL";if(Number.isFinite(Number(o.rMultiple))&&Number.isFinite(Number(o.feesUsd??e?.execution?.feesUsd))&&risk>0)return "GROSS_MINUS_EXPLICIT_FEES";return "INVALID_OR_GROSS_ONLY";}
function grossR(e){const r=Number(e?.outcome?.rMultiple);return Number.isFinite(r)?r:null;}
function sign(v){return v>EPS?1:v<-EPS?-1:0;}
function bucket(){return {trades:0,wins:0,losses:0,breakevens:0,sumR:0,grossSamples:0,sumNetR:0,netSamples:0,sumMfeR:0,sumMaeR:0,sumHoldSec:0,sumFeesUsd:0,mfeSamples:0,maeSamples:0,holdSamples:0,feeSamples:0};}
function addBucket(b,e){const net=effectiveNetR(e);if(!Number.isFinite(net))return;b.trades++;const s=sign(net);if(s>0)b.wins++;else if(s<0)b.losses++;else b.breakevens++;b.sumNetR+=net;b.netSamples++;const r=grossR(e);if(Number.isFinite(r)){b.sumR+=r;b.grossSamples++;}const o=e.outcome||{},fees=Number(o.feesUsd??e.execution?.feesUsd);if(Number.isFinite(Number(o.mfeR))){b.sumMfeR+=Number(o.mfeR);b.mfeSamples++;}if(Number.isFinite(Number(o.maeR))){b.sumMaeR+=Number(o.maeR);b.maeSamples++;}if(Number.isFinite(Number(o.holdSec))){b.sumHoldSec+=Number(o.holdSec);b.holdSamples++;}if(Number.isFinite(fees)){b.sumFeesUsd+=fees;b.feeSamples++;}}
function finish(b){b.winRate=b.trades?b.wins/b.trades:null;b.netWinRate=b.winRate;b.avgR=b.grossSamples?b.sumR/b.grossSamples:null;b.avgNetR=b.netSamples?b.sumNetR/b.netSamples:null;b.avgMfeR=b.mfeSamples?b.sumMfeR/b.mfeSamples:null;b.avgMaeR=b.maeSamples?b.sumMaeR/b.maeSamples:null;b.avgHoldSec=b.holdSamples?b.sumHoldSec/b.holdSamples:null;b.avgFeesUsd=b.feeSamples?b.sumFeesUsd/b.feeSamples:null;return b;}
function summarize(events=[]){
  const outcomes=events.filter(e=>e.outcome),closed=outcomes.filter(e=>Number.isFinite(effectiveNetR(e))),quarantined=outcomes.filter(e=>!Number.isFinite(effectiveNetR(e))),global=finish(closed.reduce((b,e)=>(addBucket(b,e),b),bucket()));
  const grossClosed=closed.filter(e=>Number.isFinite(grossR(e))),grossWins=grossClosed.filter(e=>sign(grossR(e))>0),grossWinRate=grossClosed.length?grossWins.length/grossClosed.length:null;
  const byStrategy={},bySymbol={},bySymbolStrategyRegime={};
  for(const e of closed){const sk=e.strategy||"UNKNOWN",sy=String(e.symbol||"UNKNOWN").toUpperCase(),rg=e.regime||parseRegimeFromStrategy(e.strategy)||"UNKNOWN",ek=edgeKey(sy,sk,rg);byStrategy[sk]??=bucket();bySymbol[sy]??=bucket();bySymbolStrategyRegime[ek]??=bucket();addBucket(byStrategy[sk],e);addBucket(bySymbol[sy],e);addBucket(bySymbolStrategyRegime[ek],e);}
  for(const m of [byStrategy,bySymbol,bySymbolStrategyRegime])for(const k of Object.keys(m))m[k]=finish(m[k]);
  const providers={};for(const p of PROVIDERS)providers[p]={samples:0,passOnWins:0,passOnLosses:0,rejectOnWins:0,rejectOnLosses:0,breakevens:0,blocked:0,unavailable:0};
  for(const e of closed){const outcomeSign=sign(effectiveNetR(e));for(const p of PROVIDERS){const v=String(e.ai?.verdicts?.[p]||"UNAVAILABLE").toUpperCase(),s=providers[p];s.samples++;if(outcomeSign===0){s.breakevens++;continue;}if(v==="PASS"){if(outcomeSign>0)s.passOnWins++;else s.passOnLosses++;}else if(v==="REJECT"){if(outcomeSign>0)s.rejectOnWins++;else s.rejectOnLosses++;}else if(v==="BLOCKED")s.blocked++;else s.unavailable++;}}
  for(const s of Object.values(providers)){const useful=s.passOnWins+s.rejectOnLosses,bad=s.passOnLosses+s.rejectOnWins,den=useful+bad;s.directionalAccuracy=den?useful/den:null;s.falsePassRate=(s.passOnWins+s.passOnLosses)?s.passOnLosses/(s.passOnWins+s.passOnLosses):null;s.falseRejectRate=(s.rejectOnWins+s.rejectOnLosses)?s.rejectOnWins/(s.rejectOnWins+s.rejectOnLosses):null;}
  const evidenceKinds={};for(const e of outcomes){const k=netEvidenceKind(e);evidenceKinds[k]=(evidenceKinds[k]||0)+1;}
  return {providerSet:PROVIDER_SET,dataIntegrityVersion:DATA_INTEGRITY_VERSION,learningPolicyVersion:LEARNING_POLICY_VERSION,outcomeAuthority:"NET_PNL_AFTER_FEES",sampleSize:global.trades,wins:global.wins,losses:global.losses,breakevens:global.breakevens,winRate:global.winRate,netWinRate:global.netWinRate,grossWinRate,avgR:global.avgR,avgNetR:global.avgNetR,sumNetR:global.sumNetR,avgMfeR:global.avgMfeR,avgMaeR:global.avgMaeR,quarantinedOutcomeCount:quarantined.length,evidenceKinds,byStrategy,bySymbol,bySymbolStrategyRegime,providers,adaptiveLearning:{perSymbol:true,regimeAware:true,netExpectancyAfterCosts:true,netWinClassification:true,idempotentOutcomes:true,minSampleGuard:true,strictNetOnly:true,grossOnlyQuarantined:true,autoPromote:false},updatedAt:now()};
}
export async function recordBybitLearningEvent(env,event){const store=await get(env,K.events,{events:[]}),e=boundedEvent(event),events=[...(store.events||[])],idx=events.findIndex(x=>String(x?.id||"")===e.id);if(idx>=0)events[idx]=e;else events.push(e);store.events=events.slice(-750);await put(env,K.events,store);const summary=summarize(store.events);await put(env,K.state,{providerSet:PROVIDER_SET,dataIntegrityVersion:DATA_INTEGRITY_VERSION,learningPolicyVersion:LEARNING_POLICY_VERSION,summary,lastEvent:e,updatedAt:now()});return e;}
export async function getBybitLearningState(env){const [state,champion,challenger,events,legacy]=await Promise.all([get(env,K.state,null),get(env,K.champion,{version:"BYBIT-AUTO-1.7.0",status:"ACTIVE",source:"LOCKED_RUNTIME"}),get(env,K.challenger,null),get(env,K.events,{events:[]}),get(env,"bybit:learning:v1:state",null)]);const summary=summarize(events.events||[]);return {mode:"BOUNDED_ADAPTIVE_LEARNING",autoPromote:false,providerSet:PROVIDER_SET,dataIntegrityVersion:DATA_INTEGRITY_VERSION,learningPolicyVersion:LEARNING_POLICY_VERSION,outcomeAuthority:"NET_PNL_AFTER_FEES",cleanNamespace:true,legacyV1Quarantined:!!legacy,champion,challenger,summary,lastEvent:state?.lastEvent||null,recentEvents:(events.events||[]).slice(-20)};}
export async function setShadowChallenger(env,challenger){const c={...(challenger||{}),status:"SHADOW_ONLY",autoPromote:false,providerSet:PROVIDER_SET,createdAt:now()};await put(env,K.challenger,c);return c;}
