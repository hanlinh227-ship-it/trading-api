import baseEngine from '../engine-v77168.js';
import {V11_GROUPS} from './config.js';
import {buildEntryPlan} from './entry-plan.js';
import {evaluateMarketCandidate} from './market-policies.js';
import {reviewV11} from './ai-gateway.js';
const ACTIONABLE=new Set(['MARKET_SIGNAL','MARKET','MARKET_PLAN','LIMIT','LIMIT_PLAN']);
async function engine(path,env){const r=await baseEngine.fetch(new Request(`https://v11.hunter${path}`),env);try{return await r.json()}catch{return null}}
async function fresh(symbol,env){const a=await engine(`/analyze?symbol=${encodeURIComponent(symbol)}`,env),q=a?.analysisQuote||a?.quote;if(!(Number(q?.price)>0)||q?.fresh!==true)throw new Error('QUOTE_NOT_VERIFIED_FRESH');return {a,q:{...q,price:Number(q.price)}};}
const finite=v=>{const x=Number(v);return Number.isFinite(x)?x:null};

function normalize(raw,a,q){
 const planned=a?.planned||raw?.planned||{};
 const canonical=a?.canonical||raw?.canonical||{};
 const mg=canonical.marketGeometry||{};
 const lg=canonical.limitGeometry||{};
 const m15=canonical.m15Location||{};
 const m5=canonical.m5Trigger||{};

 const atrCandidates=[
  a?.atr,
  raw?.atr,
  a?.atr14,
  raw?.atr14,
  a?.indicators?.atr,
  raw?.indicators?.atr,
  a?.indicators?.atr14,
  raw?.indicators?.atr14,
  a?.M5?.atr14,
  raw?.M5?.atr14,
  a?.M15?.atr14,
  raw?.M15?.atr14,
  a?.H1?.atr14,
  raw?.H1?.atr14,
  a?.timeframes?.M5?.atr14,
  raw?.timeframes?.M5?.atr14,
  a?.timeframes?.M15?.atr14,
  raw?.timeframes?.M15?.atr14,
  a?.timeframes?.H1?.atr14,
  raw?.timeframes?.H1?.atr14,
  planned?.atr,
  planned?.atr14,
  mg?.atr,
  lg?.atr
 ].map(finite).filter(x=>x>0);

 const entry=finite(
  a?.entry ??
  raw?.entry ??
  planned?.entry ??
  mg?.entry ??
  lg?.entry ??
  q?.price
 );

 const structureLevels=[
  a?.swingLow,a?.swingHigh,a?.support,a?.resistance,
  raw?.swingLow,raw?.swingHigh,raw?.support,raw?.resistance,
  a?.structureInvalidation,raw?.structureInvalidation,
  a?.swingInvalidation,raw?.swingInvalidation,
  m15?.level,m5?.level
 ].map(finite).filter(Number.isFinite);

 const liquidityLevels=[
  a?.liquidityLow,a?.liquidityHigh,
  raw?.liquidityLow,raw?.liquidityHigh,
  a?.target1,a?.target2,a?.tp,a?.tp1,a?.tp2,
  raw?.target1,raw?.target2,raw?.tp,raw?.tp1,raw?.tp2,
  planned?.tp,planned?.tp1,planned?.tp2
 ].map(finite).filter(Number.isFinite);

 return {
  ...raw,
  ...a,
  symbol:raw.symbol,
  entry,
  price:finite(q?.price),
  quote:q,
  atr:atrCandidates[0]??null,
  qualityScore:Number(
   a?.qualityScore ??
   raw?.qualityScore ??
   a?.quality ??
   raw?.quality ??
   a?.score ??
   raw?.score ??
   0
  ),
  structureLevels,
  liquidityLevels
 };
}
function score(x){return Number(x.gate?.score||x.candidate?.qualityScore||0)+Math.min(20,Number(x.plan?.rr||0)*8);}
async function marketCandidates(env,market){const scan=await engine(`/run-now?group=${market}`,env);if(!scan?.ok)return [];const out=[];for(const raw of scan.analyses||[]){if(!raw?.symbol||!ACTIONABLE.has(String(raw.status||'').toUpperCase()))continue;try{const {a,q}=await fresh(raw.symbol,env),c=normalize(raw,a,q),plan=buildEntryPlan(market,c);if(!plan.ok||!plan.executable)continue;const candidate={...c,symbol:plan.symbol,entry:q.price,sl:plan.sl,tp:plan.tp,rr:plan.rr,setup:plan.setup,orderType:'MARKET'};const gate=evaluateMarketCandidate(market,candidate);if(gate.pass)out.push({market,candidate,plan,gate,quote:q,score:score({candidate,plan,gate})});}catch{}}return out.sort((a,b)=>b.score-a.score).slice(0,3);}
async function bridge(env,evidence){const secret=String(env.V11_AI_BRIDGE_SECRET||'');if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')return {ok:false,error:'V11_AI_BRIDGE_VPC_BINDING_MISSING',providers:{}};if(!secret)return {ok:false,error:'V11_AI_BRIDGE_SECRET_MISSING',providers:{}};try{const request=new Request('http://127.0.0.1:8789/review',{method:'POST',headers:{'content-type':'application/json','authorization':'Bearer '+secret},body:JSON.stringify({evidence}),signal:AbortSignal.timeout(125000)});const r=await env.AI_BRIDGE.fetch(request);let j={};try{j=await r.json();}catch{return {ok:false,error:'BRIDGE_INVALID_JSON',providers:{}};}return r.ok?j:{ok:false,error:'BRIDGE_HTTP_'+r.status,providers:j?.providers||{}};}catch(e){return {ok:false,error:'BRIDGE_VPC_FETCH_FAILED:'+String(e?.message||e),providers:{}};}}
function good(r,side){return r?.status==='OK'&&r.review&&r.review.direction===side&&!r.review.hardRisk?.length;}
export async function huntWholeMarket(env){const groups=await Promise.all(V11_GROUPS.map(m=>marketCandidates(env,m)));const candidates=groups.flat().sort((a,b)=>b.score-a.score).slice(0,5);if(!candidates.length)return {status:'NO_MARKET_ENTRY',reason:'NO_FRESH_MARKET_CANDIDATE',candidates:[]};const reviewed=[];for(const x of candidates){const evidence={mode:'MANUAL_WHOLE_MARKET_MARKET_HUNTER',market:x.market,candidate:x.candidate,entryPlan:x.plan,quote:x.quote,instruction:'Independent second opinion for an immediate MARKET entry. Never invent missing evidence.'};const [deep,vps]=await Promise.all([reviewV11(env,evidence),bridge(env,evidence)]);const ds=deep.reviews?.find(r=>r.status==='OK')?.review||null,claude=vps.providers?.claude||{status:'UNAVAILABLE'},codex=vps.providers?.codex||{status:'UNAVAILABLE'};const side=String(x.candidate.side).toUpperCase(),consensus=Boolean(ds&&ds.direction===side&&!ds.hardRisk?.length&&good(claude,side)&&good(codex,side));reviewed.push({...x,ai:{deepseek:ds,claude,codex},consensus});}
 const aligned=reviewed.filter(x=>x.consensus).sort((a,b)=>(Number(b.ai.deepseek?.confidence||0)+Number(b.ai.claude?.review?.confidence||0)+Number(b.ai.codex?.review?.confidence||0)+b.score)-(Number(a.ai.deepseek?.confidence||0)+Number(a.ai.claude?.review?.confidence||0)+Number(a.ai.codex?.review?.confidence||0)+a.score));const best=aligned[0]||reviewed.sort((a,b)=>b.score-a.score)[0];return {status:aligned.length?'MARKET_ENTRY_FOUND':'NO_3AI_CONSENSUS',best,shortlist:reviewed,reviewMode:'ON_DEMAND_VPC_BRIDGE',automaticSignalAuthority:false,allThreeRequired:true};}
