// Bounded in-worker recovery for stale provider health evidence.
//
// Live evidence expires after 30 minutes. The only refresher is an external
// GitHub Actions schedule, which is explicitly best-effort: if it slips past
// the TTL every model reads STALE_EVIDENCE, the planner selects zero workers,
// and nothing inside the Worker can restore the mesh. This adds a recovery
// path that does not introduce a cron trigger and does not touch Brain
// authority -- it only refreshes evidence the scheduled probe would refresh.

const LOCK_KEY='brain:model-mesh:self-heal:v1:lock';
const DEFAULT_MIN_INTERVAL_MS=5*60*1000;

/**
 * Claim the right to run one opportunistic probe.
 * The lock is advisory: Workers KV has no compare-and-set, so a rare double
 * probe is possible. That is bounded and acceptable -- the failure it prevents
 * (an unbounded probe per request) is the one that matters.
 */
export async function claimSelfHeal(kv,{nowMs=Date.now(),minIntervalMs=DEFAULT_MIN_INTERVAL_MS}={}){
  if(!kv||typeof kv.get!=='function'||typeof kv.put!=='function')return {claimed:false,reason:'no_health_store'};
  let last=0;
  try{const raw=await kv.get(LOCK_KEY);if(raw)last=Number(JSON.parse(raw)?.at)||0;}catch{return {claimed:false,reason:'health_store_unavailable'};}
  if(last&&nowMs-last<minIntervalMs)return {claimed:false,reason:'recently_attempted',nextEligibleAt:new Date(last+minIntervalMs).toISOString()};
  try{await kv.put(LOCK_KEY,JSON.stringify({at:nowMs}),{expirationTtl:Math.max(60,Math.ceil(minIntervalMs*2/1000))});}
  catch{return {claimed:false,reason:'health_store_unavailable'};}
  return {claimed:true};
}

/**
 * Record that a probe is running now, without gating on the claim.
 * Used by the authenticated manual probe (deploy canary, refresh job): it must
 * always run, but the cron and self-heal paths must then yield to it, so the
 * three probe paths never overlap and never re-spend free quota back-to-back.
 */
export async function markSelfHealAttempt(kv,{nowMs=Date.now(),minIntervalMs=DEFAULT_MIN_INTERVAL_MS}={}){
  if(!kv||typeof kv.put!=='function')return {marked:false,reason:'no_health_store'};
  try{await kv.put(LOCK_KEY,JSON.stringify({at:nowMs}),{expirationTtl:Math.max(60,Math.ceil(minIntervalMs*2/1000))});}
  catch{return {marked:false,reason:'health_store_unavailable'};}
  return {marked:true};
}

/**
 * Schedule an opportunistic re-probe when the planner found no live provider.
 * Runs after the response via ctx.waitUntil, so it never adds request latency
 * and never changes the answer the caller already received.
 */
export function scheduleSelfHeal({env,ctx,probeProviders,modelSnapshot,minIntervalMs=DEFAULT_MIN_INTERVAL_MS,nowMs=Date.now()}={}){
  if(typeof probeProviders!=='function')return {scheduled:false,reason:'probe_not_configured'};
  if(typeof ctx?.waitUntil!=='function')return {scheduled:false,reason:'no_wait_until'};
  ctx.waitUntil((async()=>{
    const claim=await claimSelfHeal(env?.TRADING_STATE,{nowMs,minIntervalMs});
    if(!claim.claimed)return;
    // A failed recovery probe must never surface as a request error; the
    // caller already has a correct graceful-zero plan.
    try{await probeProviders(env,{modelSnapshot});}catch{}
  })());
  return {scheduled:true};
}
