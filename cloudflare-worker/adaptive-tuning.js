const KEY="v10:signal:adaptive:tuning";
export const DEFAULT_TUNING={
  version:"V10",
  signal:{
    locationTrendFit:46,
    locationRelativeFit:46,
    triggerTrendFit:48,
    triggerRelativeFit:48,
    conditionalFit:50,
    fallbackFit:40,
    forexMinRR:1.15,
    cryptoMinRR:1.20,
    metalMinRR:1.22,
    indexMinRR:1.30,
    marketChaseAtr:.75,
    baseQualityMin:68,
    directionalAiConfidenceMin:64
  }
};
const RANGE={signal:{locationTrendFit:[45,52],locationRelativeFit:[45,52],triggerTrendFit:[47,54],triggerRelativeFit:[47,54],conditionalFit:[49,56],fallbackFit:[39,46],forexMinRR:[1.12,1.25],cryptoMinRR:[1.16,1.32],metalMinRR:[1.18,1.32],indexMinRR:[1.26,1.42],marketChaseAtr:[.65,.82],baseQualityMin:[66,76],directionalAiConfidenceMin:[62,72]}};
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null;};
const clamp=(v,[lo,hi],fallback)=>{const n=num(v);return n==null?fallback:Math.max(lo,Math.min(hi,n));};
function sanitize(proposed={}){const out=structuredClone(DEFAULT_TUNING);for(const [k,r] of Object.entries(RANGE.signal))out.signal[k]=clamp(proposed?.signal?.[k],r,DEFAULT_TUNING.signal[k]);out.version="V10";return out;}
async function readState(env){try{return await env.TRADING_STATE?.get(KEY,"json")||null;}catch{return null;}}
export async function loadAdaptiveTuning(env){const x=await readState(env);return x?.values?sanitize(x.values):structuredClone(DEFAULT_TUNING);}
export async function applyAdaptiveTuning(env,proposed,{source="V10_BOUNDED_LEARNING",reviewId=null}={}){const values=sanitize(proposed),state={version:"V10",source,reviewId,values,updatedAt:Date.now(),guardrails:{freshness:true,structuralSL:true,closedOutcomeLearningOnly:true,tradeAuthority:false,deployAuthority:false,noAutonomousSourceRewrite:true}};if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(state));return state;}
export async function getAdaptiveTuningState(env){const x=await readState(env);return x?{...x,values:sanitize(x.values||x),version:"V10"}:{version:"V10",source:"DEFAULT",values:structuredClone(DEFAULT_TUNING),updatedAt:null};}
export const ADAPTIVE_TUNING_KEY=KEY;
