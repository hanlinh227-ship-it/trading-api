const STATE_KEY="v771824:ai:governance";
const LOCK_KEY="v771824:ai:lease";
const PROPOSAL_KEY="v771824:ai:proposals";
const now=()=>Date.now();
async function get(env,k,f=null){try{return await env.TRADING_STATE?.get(k,"json")??f;}catch{return f;}}
async function put(env,k,v,ttl){try{if(env.TRADING_STATE)await env.TRADING_STATE.put(k,JSON.stringify(v),ttl?{expirationTtl:ttl}:undefined);}catch{}}
export const AI_GOVERNANCE={version:"V77.18.24",mode:"CO_ENGINEER_ARBITRATED",actors:{CHATGPT:{role:"CO_ENGINEER",readRepo:true,readRuntime:true,proposeSource:true,softTuning:true,directTrade:false,directDeploy:false},CLAUDE:{role:"CO_ENGINEER",readRepo:true,readRuntime:true,proposeSource:true,softTuning:true,directTrade:false,directDeploy:false}},arbiter:{singleWriter:true,hardRiskImmutable:true,secretsImmutable:true,tradeAuthority:false,deployAuthority:false}};
export async function acquireAiLease(env,{actor="UNKNOWN",scope="SOFT_TUNING",ttlMs=120000}={}){const old=await get(env,LOCK_KEY,null),t=now();if(old?.expiresAt>t&&old?.actor!==actor)return {ok:false,reason:"LEASE_BUSY",lease:old};const lease={actor,scope,acquiredAt:t,expiresAt:t+Math.max(15000,Math.min(300000,ttlMs)),nonce:`${actor}:${t}:${Math.random().toString(36).slice(2,9)}`};await put(env,LOCK_KEY,lease,600);return {ok:true,lease};}
export async function releaseAiLease(env,lease){const cur=await get(env,LOCK_KEY,null);if(cur?.nonce&&lease?.nonce&&cur.nonce===lease.nonce)await put(env,LOCK_KEY,{releasedAt:now(),actor:lease.actor,scope:lease.scope},60);return true;}
export async function recordAiProposal(env,{actor,area="SYSTEM",summary="",proposal=null,status="PROPOSED",reviewId=null}={}){const old=await get(env,PROPOSAL_KEY,{items:[]}),item={id:`${String(actor||"AI")}:${now()}`,actor,area,summary:String(summary||"").slice(0,900),proposal,reviewId,status,at:now()},items=[item,...(old?.items||[])].slice(0,20);await put(env,PROPOSAL_KEY,{version:"V77.18.24",items},2592000);return item;}
export async function getAiGovernanceState(env){return {policy:AI_GOVERNANCE,lease:await get(env,LOCK_KEY,null),proposals:await get(env,PROPOSAL_KEY,{items:[]}),state:await get(env,STATE_KEY,null)};}
export async function markAiGovernanceState(env,state){const v={version:"V77.18.24",...state,updatedAt:now()};await put(env,STATE_KEY,v,2592000);return v;}
