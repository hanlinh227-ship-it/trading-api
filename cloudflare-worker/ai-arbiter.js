const STATE_KEY="v10:ai:governance";
const LOCK_KEY="v10:ai:lease";
const PROPOSAL_KEY="v10:ai:proposals";
const now=()=>Date.now();
async function get(env,k,f=null){try{return await env.TRADING_STATE?.get(k,"json")??f;}catch{return f;}}
async function put(env,k,v,ttl){try{if(env.TRADING_STATE)await env.TRADING_STATE.put(k,JSON.stringify(v),ttl?{expirationTtl:ttl}:undefined);}catch{}}

export const AI_GOVERNANCE={
  version:"V10",
  mode:"SIGNAL_ONLY_THREE_AI_BOUNDED_COORDINATION",
  actors:{
    CLAUDE:{role:"CONTEXT_REGIME",signalReview:true,sourceAuthority:false,tradeAuthority:false,secrets:false},
    DEEPSEEK:{role:"ADVERSARIAL_EDGE_RISK",signalReview:true,sourceAuthority:false,tradeAuthority:false,secrets:false},
    CODEX:{role:"QUANT_LOGIC_EXECUTION",signalReview:true,sourceAuthority:false,tradeAuthority:false,secrets:false}
  },
  council:{allThreeResponsesRequired:true,promotionRule:"2_OF_3_SAME_DIRECTION_NO_OPPOSITION",directionalConfidenceMin:64,realDisagreementMustRemainVisible:true},
  learning:{perMarket:true,perSymbol:true,perStrategy:true,closedOutcomeOnly:true,noAutonomousSourceRewrite:true},
  authority:{signalOnly:true,directTrade:false,directDeploy:false,secretsImmutable:true}
};

export async function acquireAiLease(env,{actor="UNKNOWN",scope="SIGNAL_REVIEW",ttlMs=120000}={}){const old=await get(env,LOCK_KEY,null),t=now();if(old?.expiresAt>t&&old?.actor!==actor)return {ok:false,reason:"LEASE_BUSY",lease:old};const lease={actor,scope,acquiredAt:t,expiresAt:t+Math.max(15000,Math.min(300000,ttlMs)),nonce:`${actor}:${t}:${Math.random().toString(36).slice(2,9)}`};await put(env,LOCK_KEY,lease,600);return {ok:true,lease};}
export async function releaseAiLease(env,lease){const cur=await get(env,LOCK_KEY,null);if(cur?.nonce&&lease?.nonce&&cur.nonce===lease.nonce)await put(env,LOCK_KEY,{releasedAt:now(),actor:lease.actor,scope:lease.scope},60);return true;}
export async function recordAiProposal(env,{actor,area="SIGNAL_V10",summary="",proposal=null,status="PROPOSED",reviewId=null}={}){const old=await get(env,PROPOSAL_KEY,{items:[]}),item={id:`${String(actor||"AI")}:${now()}`,actor,area,summary:String(summary||"").slice(0,900),proposal,reviewId,status,at:now()},items=[item,...(old?.items||[])].slice(0,50);await put(env,PROPOSAL_KEY,{version:"V10",items},2592000);return item;}
export async function getAiGovernanceState(env){return {policy:AI_GOVERNANCE,lease:await get(env,LOCK_KEY,null),proposals:await get(env,PROPOSAL_KEY,{items:[]}),state:await get(env,STATE_KEY,null)};}
export async function markAiGovernanceState(env,state){const v={version:"V10",...state,updatedAt:now()};await put(env,STATE_KEY,v,2592000);return v;}
