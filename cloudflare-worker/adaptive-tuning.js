const KEY="v771823:adaptive:tuning";
export const DEFAULT_TUNING={
  version:"V77.18.23",
  signal:{locationTrendFit:47,locationRelativeFit:47,triggerTrendFit:49,triggerRelativeFit:49,conditionalFit:51,fallbackFit:41,forexMinRR:1.18,metalMinRR:1.26,futureMinRR:1.43,marketChaseAtr:.72},
  hyro:{maxDeep:14,minTurnover:6000000,bMicroMin:.52,bDistMult:1.40,bMinRR:1.38}
};
const RANGE={
  signal:{locationTrendFit:[46,52],locationRelativeFit:[46,52],triggerTrendFit:[48,54],triggerRelativeFit:[48,54],conditionalFit:[50,56],fallbackFit:[40,46],forexMinRR:[1.15,1.25],metalMinRR:[1.22,1.32],futureMinRR:[1.40,1.50],marketChaseAtr:[.65,.75]},
  hyro:{maxDeep:[10,16],minTurnover:[5000000,12000000],bMicroMin:[.50,.58],bDistMult:[1.25,1.45],bMinRR:[1.35,1.45]}
};
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null;};
const clamp=(v,[lo,hi],fallback)=>{const n=num(v);return n==null?fallback:Math.max(lo,Math.min(hi,n));};
function sanitize(proposed={}){const out=structuredClone(DEFAULT_TUNING);for(const group of ["signal","hyro"]){for(const [k,r] of Object.entries(RANGE[group])){out[group][k]=clamp(proposed?.[group]?.[k],r,DEFAULT_TUNING[group][k]);}}out.version="V77.18.23";return out;}
export async function loadAdaptiveTuning(env){try{const x=await env.TRADING_STATE?.get(KEY,"json");return x?.values?sanitize(x.values):structuredClone(DEFAULT_TUNING);}catch{return structuredClone(DEFAULT_TUNING);}}
export async function applyAdaptiveTuning(env,proposed,{source="CHATGPT_PRIMARY",reviewId=null}={}){const values=sanitize(proposed),state={version:"V77.18.23",source,reviewId,values,updatedAt:Date.now(),guardrails:{hardNews:true,freshness:true,executionAuthority:true,structuralSL:true,hyroRiskUntouched:true,tradeAuthority:false}};if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(state));return state;}
export async function getAdaptiveTuningState(env){try{return await env.TRADING_STATE?.get(KEY,"json")||{version:"V77.18.23",source:"DEFAULT",values:structuredClone(DEFAULT_TUNING),updatedAt:null};}catch{return {version:"V77.18.23",source:"DEFAULT",values:structuredClone(DEFAULT_TUNING),updatedAt:null};}}
export const ADAPTIVE_TUNING_KEY=KEY;
