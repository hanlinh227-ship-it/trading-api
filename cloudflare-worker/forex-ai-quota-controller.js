export const FOREX_AI_QUOTA_VERSION="FOREX_AI_QUOTA_0.1";
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,n(v,a)));
const STORE_KEY="forex:ai:quota";
const store=env=>env.FOREX_STATE||env.TRADING_STATE||null;
async function get(env){try{return await store(env)?.get(STORE_KEY,{type:"json"})||{}}catch{return {}}}
async function put(env,v){if(store(env))await store(env).put(STORE_KEY,JSON.stringify(v));}
export function forexAiQuotaConfig(env={}){return {cooldownMs:Math.max(60*60*1000,n(env.FOREX_AI_QUOTA_COOLDOWN_HOURS,5)*60*60*1000),openAiMaxOutputTokens:clamp(env.FOREX_OPENAI_MAX_OUTPUT_TOKENS||12000,1000,32000),claudeMaxOutputTokens:clamp(env.FOREX_CLAUDE_MAX_OUTPUT_TOKENS||12000,1000,32000),quotaStatusCodes:[429],quotaErrorTokens:["rate_limit","rate limit","quota","usage limit","insufficient_quota","overloaded"]};}
export async function providerQuotaState(env,provider){const s=await get(env),p=s?.[provider]||{};const now=Date.now(),blockedUntil=n(p.blockedUntil);return {blocked:blockedUntil>now,blockedUntil,remainingMs:Math.max(0,blockedUntil-now),reason:p.reason||null,lastQuotaAt:p.lastQuotaAt||null};}
export async function markProviderQuotaExhausted(env,provider,reason="QUOTA_EXHAUSTED"){const c=forexAiQuotaConfig(env),s=await get(env),now=Date.now();s[provider]={...(s[provider]||{}),blockedUntil:now+c.cooldownMs,lastQuotaAt:new Date(now).toISOString(),reason:String(reason).slice(0,240)};await put(env,s);return s[provider];}
export async function clearExpiredProviderQuota(env,provider){const s=await get(env),p=s?.[provider];if(p&&n(p.blockedUntil)<=Date.now()){delete s[provider];await put(env,s);}return providerQuotaState(env,provider);}
export function looksLikeQuotaExhausted(status,payload){const c=forexAiQuotaConfig({});if(c.quotaStatusCodes.includes(Number(status)))return true;const t=JSON.stringify(payload||{}).toLowerCase();return c.quotaErrorTokens.some(x=>t.includes(x));}
