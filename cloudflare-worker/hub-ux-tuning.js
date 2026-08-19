const KEY="v771826:hub:ux";
const PRESETS=new Set(["COMPACT","ACTION_FIRST","STATUS_FIRST"]);
const DENSITY=new Set(["MINIMAL","NORMAL"]);
const DEFAULT={preset:"COMPACT",density:"MINIMAL",showVersion:true,showHealthBadge:true,showAutoState:true,notificationButtons:true,source:"DEFAULT",updatedAt:0};
const now=()=>Date.now();
async function get(env,k,f=null){try{return await env.TRADING_STATE?.get(k,"json")??f;}catch{return f;}}
async function put(env,k,v){try{if(env.TRADING_STATE)await env.TRADING_STATE.put(k,JSON.stringify(v),{expirationTtl:2592000});}catch{}}
export async function loadHubUxTuning(env){const x=await get(env,KEY,null);return {...DEFAULT,...(x||{})};}
export async function applyHubUxTuning(env,input={},meta={}){const x=input&&typeof input==="object"?input:{};const v={preset:PRESETS.has(String(x.preset||"").toUpperCase())?String(x.preset).toUpperCase():DEFAULT.preset,density:DENSITY.has(String(x.density||"").toUpperCase())?String(x.density).toUpperCase():DEFAULT.density,showVersion:x.showVersion!==false,showHealthBadge:x.showHealthBadge!==false,showAutoState:x.showAutoState!==false,notificationButtons:x.notificationButtons!==false,source:String(meta.source||"CLAUDE_HUB_UX").slice(0,80),reviewId:meta.reviewId||null,updatedAt:now()};await put(env,KEY,v);return v;}
export async function getHubUxState(env){return loadHubUxTuning(env);}
