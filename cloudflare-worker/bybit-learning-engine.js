const PREFIX="bybit:learning:v1";
const K={events:`${PREFIX}:events`,state:`${PREFIX}:state`,champion:`${PREFIX}:champion`,challenger:`${PREFIX}:challenger`};
const now=()=>Date.now();
async function get(env,key,def){try{return await env.TRADING_STATE?.get(key,{type:"json"})??def;}catch{return def;}}
async function put(env,key,val){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(val));}
const num=v=>Number.isFinite(Number(v))?Number(v):null;
function boundedEvent(x={}){return {
  id:String(x.id||crypto.randomUUID()).slice(0,80),
  at:Number(x.at||now()),
  stage:String(x.stage||"UNKNOWN").slice(0,40),
  mode:String(x.mode||"UNKNOWN").slice(0,20),
  symbol:String(x.symbol||"").slice(0,30),
  side:String(x.side||"").slice(0,10),
  strategy:String(x.strategy||"").slice(0,100),
  score:num(x.score),rr:num(x.rr),riskUsd:num(x.riskUsd),rewardUsd:num(x.rewardUsd),
  entry:num(x.entry),sl:num(x.sl),tp:num(x.tp),
  ai:x.ai&&typeof x.ai==="object"?{
    reason:String(x.ai.reason||"").slice(0,120),pass:num(x.ai.pass),reject:num(x.ai.reject),blocked:num(x.ai.blocked),unavailable:num(x.ai.unavailable),verdicts:x.ai.verdicts||{}
  }:null,
  postAi:x.postAi&&typeof x.postAi==="object"?{spreadBps:num(x.postAi.spreadBps),driftBps:num(x.postAi.driftBps),px:num(x.postAi.px)}:null,
  outcome:x.outcome&&typeof x.outcome==="object"?{status:String(x.outcome.status||"").slice(0,40),pnlUsd:num(x.outcome.pnlUsd),rMultiple:num(x.outcome.rMultiple),holdSec:num(x.outcome.holdSec),mfeR:num(x.outcome.mfeR),maeR:num(x.outcome.maeR)}:null,
  reason:String(x.reason||"").slice(0,160)
};}
function summarize(events=[]){
  const closed=events.filter(e=>e.outcome&&Number.isFinite(e.outcome.rMultiple)),wins=closed.filter(e=>e.outcome.rMultiple>0),losses=closed.filter(e=>e.outcome.rMultiple<0),sumR=closed.reduce((s,e)=>s+e.outcome.rMultiple,0),avgR=closed.length?sumR/closed.length:null,winRate=closed.length?wins.length/closed.length:null;
  const byStrategy={};for(const e of closed){const k=e.strategy||"UNKNOWN",b=byStrategy[k]||{trades:0,wins:0,sumR:0};b.trades++;if(e.outcome.rMultiple>0)b.wins++;b.sumR+=e.outcome.rMultiple;byStrategy[k]=b;}for(const b of Object.values(byStrategy)){b.winRate=b.trades?b.wins/b.trades:null;b.avgR=b.trades?b.sumR/b.trades:null;}
  return {sampleSize:closed.length,wins:wins.length,losses:losses.length,winRate,avgR,sumR,byStrategy,updatedAt:now()};
}
export async function recordBybitLearningEvent(env,event){
  const store=await get(env,K.events,{events:[]}),e=boundedEvent(event);store.events=[...(store.events||[]),e].slice(-500);await put(env,K.events,store);const summary=summarize(store.events);await put(env,K.state,{summary,lastEvent:e,updatedAt:now()});return e;
}
export async function getBybitLearningState(env){
  const [state,champion,challenger,events]=await Promise.all([get(env,K.state,{summary:summarize([])}),get(env,K.champion,{version:"BYBIT-AUTO-1.0.0",status:"ACTIVE",source:"LOCKED_RUNTIME"}),get(env,K.challenger,null),get(env,K.events,{events:[]})]);
  return {mode:"SHADOW_LEARNING",autoPromote:false,champion,challenger,summary:state.summary||summarize(events.events||[]),lastEvent:state.lastEvent||null,recentEvents:(events.events||[]).slice(-20)};
}
export async function setShadowChallenger(env,challenger){
  const c={...(challenger||{}),status:"SHADOW_ONLY",autoPromote:false,createdAt:now()};await put(env,K.challenger,c);return c;
}
