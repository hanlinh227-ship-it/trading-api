export function normalizeQuotaState(value){return {state:String(value?.state||'AVAILABLE'),resetAt:value?.resetAt??null,retryAfterMs:Number(value?.retryAfterMs||0)};}
export function quotaAvailable(value,now=Date.now()){
  const q=normalizeQuotaState(value);
  if(q.state!=='COOLDOWN_QUOTA')return q.state!=='DISABLED';
  if(!q.resetAt)return false;
  return Date.parse(q.resetAt)<=now;
}
