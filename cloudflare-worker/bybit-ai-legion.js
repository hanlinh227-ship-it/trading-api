import {MODEL_MESH_SNAPSHOT} from './generated/model-mesh-snapshot.js';
import {MODEL_MESH_ACTIVE_CANDIDATE_INDEX} from './generated/model-mesh-active-candidate-index.js';
import {applyCapabilityEvidence,enabledHardCapabilities} from './model-mesh/capability-evidence.js';
import {resolveLiveModels} from './model-mesh/runtime-health.js';
import {selectModelWorkers} from './model-mesh/selector.js';
import {executeSelectedModelWorker} from './model-mesh/provider-client.js';

export const BYBIT_AI_LEGION_VERSION='BYBIT_AI_LEGION_V1';
const STATE_KEY='bybit:btc:ai-legion:v1:state';
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const on=v=>String(v||'').toLowerCase()==='true';
const off=v=>String(v||'').toLowerCase()==='false';
const nowIso=()=>new Date().toISOString();

export const BYBIT_AI_LEGION_ROLES=Object.freeze([
  Object.freeze({
    id:'structure_regime_agent',
    required:true,
    purpose:'Validate market structure, sweep/reclaim, break/retest, regime and side coherence.',
  }),
  Object.freeze({
    id:'flow_liquidity_agent',
    required:true,
    purpose:'Validate executed flow, L2 near-touch liquidity, microprice and liquidation evidence.',
  }),
  Object.freeze({
    id:'derivatives_risk_agent',
    required:true,
    purpose:'Validate OI/funding/premium/crowding, cost, stale-data and execution-risk context. May only reduce risk.',
  }),
  Object.freeze({
    id:'independent_checker',
    required:false,
    purpose:'Look only for contradiction, stale evidence or unsupported conclusions in the other evidence lanes.',
  }),
]);

function policy(env={},mode='PAPER'){
  const globallyEnabled=!off(env.BYBIT_AI_LEGION_ENABLED);
  const demoEnabled=!off(env.BYBIT_AI_LEGION_DEMO_ENABLED);
  const liveEnabled=on(env.BYBIT_AI_LEGION_LIVE_ENABLED);
  const modelMeshEnabled=String(env.MODEL_MESH_EXECUTION_ENABLED||'0')==='1';
  const m=String(mode||'PAPER').toUpperCase();
  const modeEnabled=m==='DEMO'?demoEnabled:m==='LIVE'?liveEnabled:globallyEnabled;
  return {
    enabled:globallyEnabled&&modeEnabled,
    requiredForNewRisk:m==='DEMO'||m==='LIVE',
    liveActivationRequired:m==='LIVE',
    liveActivationPresent:liveEnabled,
    modelMeshEnabled,
    freshnessMs:Math.max(5000,Math.min(120000,num(env.BYBIT_AI_LEGION_FRESHNESS_MS)||30000)),
    refreshMinGapMs:Math.max(1000,Math.min(30000,num(env.BYBIT_AI_LEGION_REFRESH_MIN_GAP_MS)||5000)),
    minimumRequiredWorkers:3,
    maxWorkers:4,
  };
}

export function bybitAiLegionPolicy(env={},mode='PAPER'){return policy(env,mode);}

async function kvGet(env){
  try{return await env.TRADING_STATE?.get(STATE_KEY,{type:'json'})||{};}catch{return {};}
}
async function kvPut(env,value){
  try{if(env.TRADING_STATE)await env.TRADING_STATE.put(STATE_KEY,JSON.stringify(value));}catch{}
}
export async function getBybitAiLegionState(env){return kvGet(env);}

function bucket(v,step){const n=num(v);return step>0?Math.round(n/step):Math.round(n);}
function setupFingerprint(market={},setup={}){
  return [
    String(market.symbol||'BTCUSDT'),
    String(setup.setup||''),
    String(setup.side||''),
    String(setup.entryTier||''),
    String(setup.strength||''),
    String(market.regime||''),
    bucket(setup.entry,10),
    bucket(setup.sl,10),
    bucket(setup.tp,10),
    bucket(market.marketPulse?.score,.05),
    bucket(market.trades?.window15s?.imbalance,.05),
    bucket(market.book?.imbalance5,.05),
    bucket(market.book?.micropriceEdgeBps,.05),
    bucket(market.derivatives?.oiDeltaPct,.05),
    bucket(market.derivatives?.fundingRate,.00005),
    String(market.microstructureSource||''),
  ].join('|');
}

function publicMarketPayload(market={},setup={}){
  return {
    symbol:String(market.symbol||'BTCUSDT'),
    observedAt:num(market.at)||Date.now(),
    candidate:{
      setup:String(setup.setup||''),
      side:String(setup.side||''),
      entryTier:String(setup.entryTier||''),
      strength:String(setup.strength||''),
      entry:num(setup.entry),
      stop:num(setup.sl),
      target:num(setup.tp),
      rr:num(setup.rr),
      executionIntent:String(setup.executionIntent||''),
      reason:String(setup.reason||'').slice(0,300),
    },
    state:{
      regime:String(market.regime||''),
      price:num(market.price),
      mark:num(market.mark),
      structure5:market.structure5||null,
      structure15:market.structure15||null,
      structure60:market.structure60||null,
      sweep5:market.sweep5||null,
      sweep15:market.sweep15||null,
      flow:{
        window1s:market.trades?.window1s||null,
        window3s:market.trades?.window3s||null,
        window5s:market.trades?.window5s||null,
        window15s:market.trades?.window15s||null,
        window60s:market.trades?.window60s||null,
        pressure:num(market.ultraFast?.pressureScore),
        impulse:num(market.ultraFast?.impulseScore),
        acceleration:num(market.ultraFast?.flowAcceleration),
      },
      liquidity:{
        spreadBps:num(market.book?.spreadBps),
        imbalance2:num(market.book?.imbalance2),
        imbalance5:num(market.book?.imbalance5),
        imbalance10:num(market.book?.imbalance10),
        micropriceEdgeBps:num(market.book?.micropriceEdgeBps),
        fragility:num(market.book?.fragility),
      },
      derivatives:market.derivatives||null,
      crowding:market.crowding||null,
      liquidations:market.liquidations||null,
      volatility:{
        volRatio:num(market.volRatio),
        realizedVol5:num(market.realizedVol5),
        realizedVolBase:num(market.realizedVolBase),
      },
      executionCost:market.executionCost||null,
      quality:market.quality||null,
      pulse:market.marketPulse||null,
      source:String(market.microstructureSource||''),
    },
  };
}

function rolePrompt(role,payload){
  return [
    'You are one bounded specialist inside BYBIT_AI_LEGION_V1.',
    'You are advisory evidence only. You cannot place orders, change leverage, increase risk, override StateFlow, or invent missing market data.',
    'Never reveal chain-of-thought. Return strict JSON only.',
    `ROLE_ID: ${role.id}`,
    `ROLE_PURPOSE: ${role.purpose}`,
    'Evaluate only the supplied PUBLIC BTCUSDT market state and the already-selected candidate.',
    'Required JSON schema:',
    '{"verdict":"SUPPORT|NEUTRAL|VETO","side":"BUY|SELL|NEUTRAL","confidence":0.0,"risk_multiplier":1.0,"reasons":["short reason"],"freshness_ok":true}',
    'Rules:',
    '- confidence must be 0..1.',
    '- risk_multiplier must be 0.50..1.00 and can only reduce risk.',
    '- If evidence is stale, contradictory, malformed or insufficient: VETO.',
    '- SUPPORT means this role finds the candidate internally coherent; it is not a profit prediction.',
    '- Use max 3 concise reasons, each under 120 chars.',
    `INPUT: ${JSON.stringify(payload)}`,
  ].join('\n');
}

function parseObject(text=''){
  let raw=String(text||'').trim();
  raw=raw.replace(/^\`\`\`(?:json)?\s*/i,'').replace(/\s*\`\`\`$/,'').trim();
  const a=raw.indexOf('{'),b=raw.lastIndexOf('}');
  if(a>=0&&b>a)raw=raw.slice(a,b+1);
  try{const x=JSON.parse(raw);return x&&typeof x==='object'&&!Array.isArray(x)?x:null;}catch{return null;}
}

function normalizeAgent(role,worker,result,setup){
  const parsed=parseObject(result?.text);
  if(!parsed)return {
    roleId:role.id,required:role.required,ok:false,verdict:'VETO',side:'NEUTRAL',confidence:0,
    riskMultiplier:.5,reasons:['MODEL_OUTPUT_INVALID_JSON'],freshnessOk:false,
    providerId:worker?.provider_id||null,modelId:worker?.model_id||null,modelFamily:worker?.model_family||null,
    latencyMs:num(result?.latency_ms),
  };
  const verdict=['SUPPORT','NEUTRAL','VETO'].includes(String(parsed.verdict||'').toUpperCase())?String(parsed.verdict).toUpperCase():'VETO';
  const sideRaw=String(parsed.side||'NEUTRAL').toUpperCase();
  const side=['BUY','SELL','NEUTRAL'].includes(sideRaw)?sideRaw:'NEUTRAL';
  const reasons=(Array.isArray(parsed.reasons)?parsed.reasons:[]).slice(0,3).map(x=>String(x).replace(/\s+/g,' ').slice(0,120));
  const freshnessOk=parsed.freshness_ok===true;
  const confidence=clamp(num(parsed.confidence),0,1);
  const riskMultiplier=clamp(num(parsed.risk_multiplier)||1,.5,1);
  const candidateSide=String(setup.side||'').toUpperCase()==='BUY'?'BUY':String(setup.side||'').toUpperCase()==='SELL'?'SELL':'NEUTRAL';
  const sideConflict=side!=='NEUTRAL'&&candidateSide!=='NEUTRAL'&&side!==candidateSide;
  return {
    roleId:role.id,required:role.required,ok:freshnessOk&&!sideConflict,verdict:sideConflict?'VETO':verdict,side,
    confidence,riskMultiplier,reasons:sideConflict?['SIDE_CONFLICT_WITH_STATEFLOW_CANDIDATE',...reasons].slice(0,3):reasons,
    freshnessOk,providerId:worker?.provider_id||null,modelId:worker?.model_id||null,modelFamily:worker?.model_family||null,
    latencyMs:num(result?.latency_ms),
  };
}

export function evaluateBybitAiLegionAgents(agents=[]){
  const byRole=Object.fromEntries(agents.map(x=>[x.roleId,x]));
  const structure=byRole.structure_regime_agent;
  const flow=byRole.flow_liquidity_agent;
  const risk=byRole.derivatives_risk_agent;
  const checker=byRole.independent_checker;
  const missing=[structure,flow,risk].filter(x=>!x).length;
  if(missing)return {approved:false,reason:'AI_LEGION_REQUIRED_ROLE_MISSING',riskMultiplier:.5,confidenceFloor:0};
  for(const x of [structure,flow,risk])if(!x.ok||x.verdict==='VETO')return {approved:false,reason:`AI_LEGION_${x.roleId.toUpperCase()}_VETO`,riskMultiplier:.5,confidenceFloor:Math.min(...[structure,flow,risk].map(z=>num(z.confidence)))};
  if(structure.verdict!=='SUPPORT')return {approved:false,reason:'AI_LEGION_STRUCTURE_SUPPORT_REQUIRED',riskMultiplier:.5,confidenceFloor:num(structure.confidence)};
  if(flow.verdict!=='SUPPORT')return {approved:false,reason:'AI_LEGION_FLOW_SUPPORT_REQUIRED',riskMultiplier:.5,confidenceFloor:num(flow.confidence)};
  if(checker&&(!checker.ok||checker.verdict==='VETO'))return {approved:false,reason:'AI_LEGION_INDEPENDENT_CHECKER_VETO',riskMultiplier:.5,confidenceFloor:Math.min(...[structure,flow,risk,checker].map(z=>num(z.confidence)))};
  const riskMultiplier=Math.min(1,...agents.map(x=>clamp(num(x.riskMultiplier)||1,.5,1)));
  const confidenceFloor=Math.min(...[structure,flow,risk].map(x=>clamp(num(x.confidence),0,1)));
  return {approved:true,reason:'AI_LEGION_ROLE_CONTRACTS_PASS',riskMultiplier,confidenceFloor};
}

async function selectWorkers(env){
  const evidenceSnapshot={...MODEL_MESH_SNAPSHOT,models:applyCapabilityEvidence(MODEL_MESH_SNAPSHOT?.models,MODEL_MESH_ACTIVE_CANDIDATE_INDEX)};
  const liveModels=await resolveLiveModels(evidenceSnapshot,env);
  const hardCapabilities=enabledHardCapabilities(MODEL_MESH_ACTIVE_CANDIDATE_INDEX,'trading');
  const selected=selectModelWorkers({
    profile:'DEEP',domain:'trading',dataClass:'PUBLIC',models:liveModels,hardCapabilities,
    requiredCapability:'text_reasoning',
  });
  return {evidenceSnapshot,selected:selected.slice(0,BYBIT_AI_LEGION_ROLES.length)};
}

export async function refreshBybitAiLegion({env={},market={},setup={}}={}){
  const mode=String(env.BYBIT_AUTO_DEMO||'').toLowerCase()==='true'?'DEMO':(on(env.BYBIT_AUTO_LIVE)&&on(env.BYBIT_BTC_LIVE_ACK)?'LIVE':'PAPER');
  const p=policy(env,mode),fingerprint=setupFingerprint(market,setup),startedAt=Date.now();
  if(!p.enabled){
    const state={version:BYBIT_AI_LEGION_VERSION,status:'DISABLED',mode,fingerprint,approved:false,reason:'AI_LEGION_DISABLED',riskMultiplier:1,updatedAt:nowIso(),updatedAtMs:Date.now(),agents:[]};
    await kvPut(env,state);return state;
  }
  if(p.liveActivationRequired&&!p.liveActivationPresent){
    const state={version:BYBIT_AI_LEGION_VERSION,status:'BLOCKED',mode,fingerprint,approved:false,reason:'AI_LEGION_LIVE_ACK_REQUIRED',riskMultiplier:.5,updatedAt:nowIso(),updatedAtMs:Date.now(),agents:[]};
    await kvPut(env,state);return state;
  }
  if(!p.modelMeshEnabled){
    const state={version:BYBIT_AI_LEGION_VERSION,status:'BLOCKED',mode,fingerprint,approved:false,reason:'MODEL_MESH_EXECUTION_DISABLED',riskMultiplier:.5,updatedAt:nowIso(),updatedAtMs:Date.now(),agents:[]};
    await kvPut(env,state);return state;
  }

  let selectedInfo;
  try{selectedInfo=await selectWorkers(env);}catch(error){
    const state={version:BYBIT_AI_LEGION_VERSION,status:'BLOCKED',mode,fingerprint,approved:false,reason:'AI_LEGION_WORKER_SELECTION_FAILED',error:String(error?.message||error).slice(0,180),riskMultiplier:.5,updatedAt:nowIso(),updatedAtMs:Date.now(),agents:[]};
    await kvPut(env,state);return state;
  }
  const workers=selectedInfo.selected||[];
  if(workers.length<p.minimumRequiredWorkers){
    const state={version:BYBIT_AI_LEGION_VERSION,status:'BLOCKED',mode,fingerprint,approved:false,reason:'AI_LEGION_INSUFFICIENT_DISTINCT_WORKERS',workerCount:workers.length,minimumRequiredWorkers:p.minimumRequiredWorkers,riskMultiplier:.5,updatedAt:nowIso(),updatedAtMs:Date.now(),agents:[]};
    await kvPut(env,state);return state;
  }
  const payload=publicMarketPayload(market,setup);
  const assignments=BYBIT_AI_LEGION_ROLES.slice(0,workers.length).map((role,index)=>({role,worker:workers[index]}));
  const route={primarySkill:'crypto',domain:'trading',sourceSha:selectedInfo.evidenceSnapshot?.source_sha||null,capsuleHash:null};
  const settled=await Promise.allSettled(assignments.map(({role,worker})=>executeSelectedModelWorker({
    selectedWorker:worker,env,text:rolePrompt(role,payload),route,modelSnapshot:selectedInfo.evidenceSnapshot,
  })));
  const agents=settled.map((item,index)=>{
    const {role,worker}=assignments[index];
    if(item.status!=='fulfilled')return {roleId:role.id,required:role.required,ok:false,verdict:'VETO',side:'NEUTRAL',confidence:0,riskMultiplier:.5,reasons:['MODEL_WORKER_FAILURE'],freshnessOk:false,providerId:worker.provider_id,modelId:worker.model_id,modelFamily:worker.model_family,latencyMs:0};
    return normalizeAgent(role,worker,item.value,setup);
  });
  const decision=evaluateBybitAiLegionAgents(agents);
  const state={
    version:BYBIT_AI_LEGION_VERSION,status:decision.approved?'READY':'BLOCKED',mode,fingerprint,
    approved:decision.approved,reason:decision.reason,riskMultiplier:decision.riskMultiplier,
    confidenceFloor:decision.confidenceFloor,workerCount:workers.length,requiredWorkers:p.minimumRequiredWorkers,
    noMajorityVote:true,authority:'ADVISORY_EVIDENCE_ONLY',executionAuthority:'BYBIT-BTC-STATEFLOW-2.1',
    agents,startedAtMs:startedAt,updatedAt:nowIso(),updatedAtMs:Date.now(),expiresAtMs:Date.now()+p.freshnessMs,
  };
  await kvPut(env,state);
  return state;
}

export async function resolveBybitAiLegionDecision({env={},mode='PAPER',market={},setup={},ctx=null}={}){
  const p=policy(env,mode);
  if(!p.enabled){
    return {ready:!p.requiredForNewRisk,approved:!p.requiredForNewRisk,reason:'AI_LEGION_DISABLED',riskMultiplier:1,status:'DISABLED',state:null};
  }
  if(p.liveActivationRequired&&!p.liveActivationPresent){
    return {ready:false,approved:false,reason:'AI_LEGION_LIVE_ACK_REQUIRED',riskMultiplier:.5,status:'BLOCKED',state:null};
  }
  const fingerprint=setupFingerprint(market,setup),state=await kvGet(env),ageMs=state?.updatedAtMs?Math.max(0,Date.now()-num(state.updatedAtMs)):Infinity;
  const fresh=state?.fingerprint===fingerprint&&ageMs<=p.freshnessMs&&num(state?.expiresAtMs)>=Date.now();
  if(fresh){
    return {ready:true,approved:state.approved===true,reason:String(state.reason||'AI_LEGION_DECISION'),riskMultiplier:clamp(num(state.riskMultiplier)||1,.5,1),status:String(state.status||'UNKNOWN'),state};
  }
  const lastRequestMs=num(state?.refreshRequestedAtMs),tooSoon=lastRequestMs>0&&Date.now()-lastRequestMs<p.refreshMinGapMs;
  if(ctx&&typeof ctx.waitUntil==='function'){
    if(!tooSoon){
      const pending={...state,version:BYBIT_AI_LEGION_VERSION,status:'REFRESH_PENDING',mode,fingerprint,approved:false,reason:'AI_LEGION_REFRESH_PENDING',riskMultiplier:.5,refreshRequestedAt:nowIso(),refreshRequestedAtMs:Date.now()};
      await kvPut(env,pending);
      ctx.waitUntil(refreshBybitAiLegion({env,market,setup}));
    }
    return {ready:false,approved:false,reason:'AI_LEGION_REFRESH_PENDING',riskMultiplier:.5,status:'REFRESH_PENDING',state};
  }
  const refreshed=await refreshBybitAiLegion({env,market,setup});
  return {ready:true,approved:refreshed.approved===true,reason:String(refreshed.reason||'AI_LEGION_DECISION'),riskMultiplier:clamp(num(refreshed.riskMultiplier)||1,.5,1),status:String(refreshed.status||'UNKNOWN'),state:refreshed};
}
