import {V11_CONFIG,V11_GROUPS} from './config.js';
import {evaluateMarketCandidate} from './market-policies.js';
import {reviewV11,decide} from './ai-gateway.js';
const state=new Map();
export function dueMarkets(ts=Date.now()){return V11_GROUPS.filter(m=>ts-Number(state.get(m)||0)>=V11_CONFIG.scanCadenceSec[m]*1000);}
export async function processCandidate(env,market,candidate,evidence){const gate=evaluateMarketCandidate(market,candidate);if(!gate.pass)return {status:'REJECTED',market,symbol:candidate.symbol,gate};const ai=await reviewV11(env,evidence),decision=decide(candidate,ai);if(!decision.pass)return {status:'WAIT',market,symbol:candidate.symbol,gate,decision};return {status:'APPROVED_SIGNAL',version:'V11',market,symbol:candidate.symbol,candidate,gate,decision,approvedAt:Date.now(),expiresAt:Date.now()+V11_CONFIG.markets[market].horizonMin*60000};}
export async function scheduledV11(env,handlers={},ts=Date.now()){const due=dueMarkets(ts),results=[];for(const market of due){try{const r=await handlers.scan?.(market,env);results.push({market,ok:true,result:r});state.set(market,ts);}catch(e){results.push({market,ok:false,error:String(e?.message||e)});}}return {version:'V11',authority:'CLOUDFLARE_SINGLE_SCHEDULER',due,results};}
