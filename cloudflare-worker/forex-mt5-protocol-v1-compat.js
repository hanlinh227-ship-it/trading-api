import {handleForexAutonomousMt5Bridge} from "./forex-autonomous-mt5-bridge.js";

function n(v,d=0){return Number.isFinite(Number(v))?Number(v):d;}
function normalizeBar(r={}){
  return {time:r.time??r.t??null,open:n(r.open??r.o),high:n(r.high??r.h),low:n(r.low??r.l),close:n(r.close??r.c),volume:n(r.volume??r.v)};
}
function normalizeBars(rows){return Array.isArray(rows)?rows.map(normalizeBar):[];}
function normalizeSnapshot(s={}){const bars=s?.bars&&typeof s.bars==="object"?s.bars:{};return {...s,bars:{M5:normalizeBars(bars.M5),M15:normalizeBars(bars.M15),H1:normalizeBars(bars.H1),H4:normalizeBars(bars.H4)}};}
function compactJson(body,status=200,headers={}){const h=new Headers(headers);h.set("content-type","application/json; charset=utf-8");h.set("cache-control","no-store");return new Response(JSON.stringify(body),{status,headers:h});}
const store=env=>env.FOREX_STATE||env.TRADING_STATE||null;
const lockKey=id=>`forex:ai:inflight:${String(id||"default").slice(0,80)}`;
const heartbeatKey=id=>`forex:mt5:heartbeat:${String(id||"default").slice(0,80)}`;
const HEARTBEAT_LAST_KEY="forex:mt5:heartbeat:last";
async function getKv(env,k){try{return await store(env)?.get(k,{type:"json"})||null}catch{return null}}
async function putKv(env,k,v,ttl){try{if(store(env))await store(env).put(k,JSON.stringify(v),ttl?{expirationTtl:ttl}:undefined)}catch{}}
async function lockState(env,id){return getKv(env,lockKey(id));}
async function setLock(env,id){await putKv(env,lockKey(id),{startedAt:Date.now()},90);}
async function clearLock(env,id){try{await store(env)?.delete(lockKey(id))}catch{}}
function isCanonicalEa(raw={}){const mt5=raw?.mt5||{},a=raw?.account||{};return Number(raw?.protocolVersion||1)===1&&mt5.pureAiEa===true&&mt5.directHub===true&&String(mt5.eaVersion||"").startsWith("1.")&&n(a.balance)>0&&n(a.equity)>0;}
async function recordHeartbeat(env,raw,terminalId){if(!isCanonicalEa(raw))return null;const a=raw.account||{},m=raw.mt5||{},hb={terminalId,receivedAt:new Date().toISOString(),protocolVersion:1,canonicalEa:true,eaVersion:String(m.eaVersion||""),connected:m.connected===true,tradeAllowed:a.tradeAllowed===true,balance:n(a.balance),equity:n(a.equity),freeMargin:n(a.freeMargin),marginLevelPct:n(a.marginLevelPct),openPositions:n(a.openPositions),server:String(a.server||""),login:String(a.login||"")};await putKv(env,heartbeatKey(terminalId),hb,86400);await putKv(env,HEARTBEAT_LAST_KEY,hb,86400);return hb;}
async function currentDecision(req,env,terminalId){const u=new URL(req.url),headers=new Headers(req.headers);const r=new Request(`${u.origin}/forex/mt5/decision?terminal_id=${encodeURIComponent(terminalId)}`,{method:"GET",headers});const res=await handleForexAutonomousMt5Bridge(r,env);if(!res||!res.ok)return null;try{return await res.json()}catch{return null}}
function safeImmediate(body,started){const d=body?.decision&&typeof body.decision==="object"?body.decision:null;if(!d)return {ok:true,asyncAi:true,aiInFlight:started,decision:{action:"WAIT",reason:started?"AI_EVALUATION_STARTED":"AI_EVALUATION_IN_PROGRESS"}};if(Number(d.expiresAt||0)>0&&Number(d.expiresAt)<Date.now())return {ok:true,asyncAi:true,aiInFlight:started,decision:{action:"WAIT",reason:"LAST_AI_DECISION_EXPIRED"},manageDecision:body?.manageDecision||null,dailyObjective:body?.dailyObjective||null,target:body?.target||null,requiredSide:body?.requiredSide||null};return {...body,asyncAi:true,aiInFlight:started};}
function heartbeatStatus(hb){const age=hb?.receivedAt?Math.max(0,(Date.now()-Date.parse(hb.receivedAt))/1000):Infinity;return {heartbeat:hb||null,ageSec:Number.isFinite(age)?age:null,connected:!!hb?.canonicalEa&&hb?.connected===true&&age<=30,status:!hb?"NO_CANONICAL_HEARTBEAT":age>30?"STALE_HEARTBEAT":hb.connected===true?"CONNECTED":"BROKER_DISCONNECTED"};}

export async function handleForexMt5ProtocolV1(req,env,ctx){
  const u=new URL(req.url);if(!u.pathname.startsWith("/forex/"))return null;
  if(u.pathname==="/forex/health"&&req.method==="GET"){
    const base=await handleForexAutonomousMt5Bridge(req,env);if(!base)return null;let body;try{body=await base.clone().json()}catch{return base;}return compactJson({...body,mt5Canonical:heartbeatStatus(await getKv(env,HEARTBEAT_LAST_KEY))},base.status,base.headers);
  }
  if(u.pathname!=="/forex/mt5/pulse"||req.method!=="POST")return handleForexAutonomousMt5Bridge(req,env);
  let raw;try{raw=await req.clone().json();}catch{return compactJson({ok:false,error:"INVALID_JSON"},400);}
  const terminalId=String(raw?.terminalId||"").slice(0,80);if(!terminalId)return compactJson({ok:false,error:"TERMINAL_ID_REQUIRED"},400);
  const protocol=Number(raw?.protocolVersion||req.headers.get("x-forex-protocol")||1);const normalized={...raw,protocolVersion:protocol,snapshots:Array.isArray(raw?.snapshots)?raw.snapshots.map(normalizeSnapshot):[]};
  const heartbeat=await recordHeartbeat(env,normalized,terminalId);
  const headers=new Headers(req.headers);headers.set("content-type","application/json");const forwarded=new Request(req.url,{method:"POST",headers,body:JSON.stringify(normalized)});
  if(ctx&&typeof ctx.waitUntil==="function"&&store(env)){
    const l=await lockState(env,terminalId),active=Number(l?.startedAt||0)>0&&Date.now()-Number(l.startedAt)<70000;let started=false;
    if(!active){started=true;await setLock(env,terminalId);ctx.waitUntil((async()=>{try{await handleForexAutonomousMt5Bridge(forwarded,env)}finally{await clearLock(env,terminalId)}})());}
    const latest=await currentDecision(req,env,terminalId);return compactJson({...safeImmediate(latest,started),mt5HeartbeatAccepted:!!heartbeat});
  }
  const res=await handleForexAutonomousMt5Bridge(forwarded,env);if(!res)return null;let body;try{body=await res.clone().json();}catch{return res;}return compactJson({...body,mt5HeartbeatAccepted:!!heartbeat},res.status,res.headers);
}
