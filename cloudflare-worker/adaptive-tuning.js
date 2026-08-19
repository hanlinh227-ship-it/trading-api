const KEY="v771824:adaptive:tuning",LEGACY_KEY="v771823:adaptive:tuning";
export const DEFAULT_TUNING={
  version:"V77.18.37",
  signal:{locationTrendFit:46,locationRelativeFit:46,triggerTrendFit:48,triggerRelativeFit:48,conditionalFit:50,fallbackFit:40,forexMinRR:1.15,metalMinRR:1.22,indexMinRR:1.30,marketChaseAtr:.75},
  hyro:{maxDeep:16,minTurnover:5000000,bMicroMin:.50,bDistMult:1.45,bMinRR:1.35}
};
const RANGE={
  signal:{locationTrendFit:[45,52],locationRelativeFit:[45,52],triggerTrendFit:[47,54],triggerRelativeFit:[47,54],conditionalFit:[49,56],fallbackFit:[39,46],forexMinRR:[1.12,1.25],metalMinRR:[1.18,1.32],indexMinRR:[1.26,1.42],marketChaseAtr:[.65,.82]},
  hyro:{maxDeep:[10,18],minTurnover:[4000000,12000000],bMicroMin:[.48,.58],bDistMult:[1.25,1.55],bMinRR:[1.30,1.45]}
};
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null;};
const clamp=(v,[lo,hi],fallback)=>{const n=num(v);return n==null?fallback:Math.max(lo,Math.min(hi,n));};
function sanitize(proposed={}){const out=structuredClone(DEFAULT_TUNING);for(const group of ["signal","hyro"]){for(const [k,r] of Object.entries(RANGE[group]))out[group][k]=clamp(proposed?.[group]?.[k],r,DEFAULT_TUNING[group][k]);}out.version="V77.18.37";return out;}
async function readState(env){try{return await env.TRADING_STATE?.get(KEY,"json")||await env.TRADING_STATE?.get(LEGACY_KEY,"json")||null;}catch{return null;}}
export async function loadAdaptiveTuning(env){const x=await readState(env);return x?.values?sanitize(x.values):structuredClone(DEFAULT_TUNING);}
export async function applyAdaptiveTuning(env,proposed,{source="AI_ARBITER",reviewId=null}={}){const values=sanitize(proposed),state={version:"V77.18.37",source,reviewId,values,updatedAt:Date.now(),guardrails:{hardNews:true,freshness:true,executionAuthority:true,structuralSL:true,hyroRiskUntouched:true,tradeAuthority:false,deployAuthority:false,marketEntryBalanced:true}};if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(state));return state;}
export async function getAdaptiveTuningState(env){const x=await readState(env);return x?{...x,values:sanitize(x.values||x),version:"V77.18.37"}:{version:"V77.18.37",source:"DEFAULT",values:structuredClone(DEFAULT_TUNING),updatedAt:null};}
export const ADAPTIVE_TUNING_KEY=KEY;
