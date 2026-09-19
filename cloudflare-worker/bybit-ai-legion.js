import {collectBybitNewsContext} from './bybit-news-context.js';
import {MODEL_MESH_SNAPSHOT} from './generated/model-mesh-snapshot.js';
import {MODEL_MESH_ACTIVE_CANDIDATE_INDEX} from './generated/model-mesh-active-candidate-index.js';
import {applyCapabilityEvidence,enabledHardCapabilities} from './model-mesh/capability-evidence.js';
import {resolveLiveModels} from './model-mesh/runtime-health.js';
import {selectModelWorkers} from './model-mesh/selector.js';
import {executeSelectedModelWorker} from './model-mesh/provider-client.js';

export const BYBIT_AI_LEGION_VERSION='BYBIT_AI_LEGION_V3_ROLE_FEDERATION';
const STATE_KEY='bybit:ai-legion:v3:state';
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const on=v=>String(v||'').toLowerCase()==='true';
const off=v=>String(v||'').toLowerCase()==='false';
const nowIso=()=>new Date().toISOString();

export const BYBIT_AI_LEGION_ROLES=Object.freeze([
  Object.freeze({
    id:'macro_news_agent',
    required:true,
    purpose:'Economic-and-crypto intelligence desk: assess fresh macro policy/data, cross-asset risk and coin-specific news catalysts; never invent missing news.',
  }),
  Object.freeze({
    id:'market_structure_flow_agent',
    required:true,
    purpose:'Technical market-analysis desk: validate HTF/LTF structure, sweep/reclaim or break/retest, regime, executed flow, L2 liquidity, microprice, liquidation and volatility coherence.',
  }),
  Object.freeze({
    id:'order_risk_architect_agent',
    required:true,
    purpose:'Order-design and risk desk: design/audit the bounded order plan around deterministic structure, including entry quality, invalidation stop, target, fees/slippage, leverage and risk; it may only reduce risk.',
  }),
  Object.freeze({
    id:'independent_adversarial_checker',
    required:false,
    purpose:'Independent red-team desk: challenge every other desk for stale data, contradictory evidence, crowded traps, stop-hunt exposure, hidden execution risk and unsupported confidence.',
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
    participationMode:'ROTATING_ALL_HEALTHY_DISTINCT_MODEL_FAMILIES_MAX4_CONCURRENT',
    alwaysDecision:true,
    forcedTrade:false,
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
  // Cache a bounded AI verdict against the deterministic trade thesis rather than
  // every sub-second flow tick. StateFlow still re-evaluates live flow on every
  // event; this avoids turning model latency into an entry-frequency gate.
  return [
    String(market.symbol||'BTCUSDT'),
    String(setup.setup||''),
    String(setup.side||''),
    String(setup.entryTier||''),
    String(setup.strength||''),
    String(market.regime||''),
    bucket(setup.entry,25),
    bucket(setup.sl,25),
    bucket(setup.tp,25),
    String(market.microstructureSource||''),
  ].join('|');
}

function publicMarketPayload(market={},setup={},newsContext=null){
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
      stopAuthority:String(setup.stopAuthority||setup.evidence?.stopAuthority||''),
      targetAuthority:String(setup.targetAuthority||setup.evidence?.targetAuthority||''),
      structuralInvalidation:num(setup.structuralInvalidation||setup.evidence?.structuralInvalidation),
      noiseBuffer:num(setup.noiseBuffer||setup.evidence?.noiseBuffer),
      opposingLiquidity:num(setup.opposingLiquidity||setup.evidence?.opposingLiquidity),
      targetFrontRun:Boolean(setup.targetFrontRun||setup.evidence?.targetFrontRun),
      reason:String(setup.reason||'').slice(0,300),
    },
    newsContext:newsContext?{version:newsContext.version,at:newsContext.at,stale:newsContext.stale===true,sourceCount:num(newsContext.sourceCount),items:(newsContext.items||[]).slice(0,16),macroItems:(newsContext.items||[]).filter(x=>String(x.kind||'').startsWith('MACRO')).slice(0,8),cryptoItems:(newsContext.items||[]).filter(x=>String(x.kind||'').includes('CRYPTO')).slice(0,10),macroSummary:(newsContext.macroSummary||[]).slice(0,8),error:newsContext.error||null}:null,
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
        range5:market.range5||null,
        range15:market.range15||null,
        range60:market.range60||null,
      },
      executionCost:market.executionCost||null,
      quality:market.quality||null,
      pulse:market.marketPulse||null,
      source:String(market.microstructureSource||''),
    },
  };
}

function roleGuide(roleId){
  if(roleId==='macro_news_agent')return [
    'Use only supplied newsContext. Do not browse, invent headlines, dates, policy decisions or economic releases.',
    'Separate direct symbol/crypto catalysts from broad macro context. A fresh high-impact conflict may VETO or reduce risk; ordinary headlines should not force a trade.',
    'If newsContext is unavailable or stale, state that explicitly and return NEUTRAL unless the supplied context itself shows a material hazard.'
  ];
  if(roleId==='market_structure_flow_agent')return [
    'Use 5/15/60 structure, sweep/reclaim and break/retest together with persistent 3s/5s/15s executed flow.',
    'Use near-touch L2 imbalance, microprice, spread, fragility and liquidation evidence together. Displayed size alone is not sufficient.',
    'VETO when the candidate conflicts with higher-timeframe structure, lacks follow-through after a sweep/break, or execution liquidity is materially unsafe.'
  ];
  if(roleId==='order_risk_architect_agent')return [
    'Audit OI, funding, premium/basis, crowding, volatility, fee/slippage and the supplied deterministic entry/stop/target geometry.',
    'Design a bounded order-plan suggestion around the existing thesis: entry quality, invalidation stop, target logic and risk reduction. Never move a stop inside structural invalidation or claim it cannot be swept.',
    'You may only reduce risk. Do not propose leverage above the deterministic limit, do not widen authority, and VETO if expected cost or stop/target geometry is incoherent.'
  ];
  return [
    'Act as an adversarial red-team checker. Search for stale inputs, source conflict, crowded traps, stop-hunt exposure, target beyond opposing liquidity, fee mismatch or overconfidence.',
    'Do not invent a new trade thesis. VETO when a material contradiction remains unresolved; otherwise SUPPORT or NEUTRAL based on supplied evidence.'
  ];
}

function rolePrompt(role,payload){
  return [
    'You are one bounded specialist inside BYBIT_AI_LEGION_V2_MARKET_INTELLIGENCE.',
    'You are advisory evidence only. You cannot place orders, change leverage, increase risk, override StateFlow, or invent missing market data.',
    'Never reveal chain-of-thought. Return strict JSON only.',
    `ROLE_ID: ${role.id}`,
    `ROLE_PURPOSE: ${role.purpose}`,
    ...roleGuide(role.id).map(x=>`ROLE_RULE: ${x}`),
    'Evaluate only the supplied PUBLIC market state, news context and the already-selected candidate for this symbol.',
    'Required JSON schema:',
    '{"verdict":"SUPPORT|NEUTRAL|VETO","side":"BUY|SELL|NEUTRAL","confidence":0.0,"risk_multiplier":1.0,"reasons":["short reason"],"freshness_ok":true,"order_plan":{"entry_quality":"GOOD|MARGINAL|REJECT","stop_buffer_mult":1.0,"target_r_mult":1.0,"notes":"short"}}',
    'Rules:',
    '- confidence must be 0..1 and must reflect evidence quality, not optimism.',
    '- risk_multiplier must be 0.50..1.00 and can only reduce risk.',
    '- If required market evidence is stale, contradictory, malformed or insufficient: VETO. For optional news context, explicit unavailability may be NEUTRAL rather than fabricated.',
    '- SUPPORT means this role finds the candidate internally coherent; it is not a profit prediction.',
    '- Never claim a stop cannot be swept. Judge whether it is outside the thesis invalidation/noise zone.',
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
  const op=parsed.order_plan&&typeof parsed.order_plan==='object'?parsed.order_plan:null;
  const orderPlan=role.id==='order_risk_architect_agent'&&op?{entryQuality:['GOOD','MARGINAL','REJECT'].includes(String(op.entry_quality||'').toUpperCase())?String(op.entry_quality).toUpperCase():'MARGINAL',stopBufferMult:clamp(num(op.stop_buffer_mult)||1,1,1.5),targetRMult:clamp(num(op.target_r_mult)||1,.8,1.2),notes:String(op.notes||'').replace(/\s+/g,' ').slice(0,160)}:null;
  return {
    roleId:role.id,required:role.required,ok:freshnessOk&&!sideConflict,verdict:sideConflict?'VETO':verdict,side,
    confidence,riskMultiplier,reasons:sideConflict?['SIDE_CONFLICT_WITH_STATEFLOW_CANDIDATE',...reasons].slice(0,3):reasons,
    freshnessOk,orderPlan,providerId:worker?.provider_id||null,modelId:worker?.model_id||null,modelFamily:worker?.model_family||null,
    latencyMs:num(result?.latency_ms),
  };
}

export function evaluateBybitAiLegionAgents(agents=[]){
  const byRole=Object.fromEntries(agents.map(x=>[x.roleId,x]));
  const macro=byRole.macro_news_agent;
  const market=byRole.market_structure_flow_agent;
  const order=byRole.order_risk_architect_agent;
  const checker=byRole.independent_adversarial_checker;
  const required=[macro,market,order];
  if(required.some(x=>!x))return {approved:false,reason:'AI_LEGION_REQUIRED_ROLE_MISSING',riskMultiplier:.5,confidenceFloor:0};
  for(const x of required)if(!x.ok||x.verdict==='VETO')return {approved:false,reason:`AI_LEGION_${x.roleId.toUpperCase()}_VETO`,riskMultiplier:.5,confidenceFloor:Math.min(...required.map(z=>num(z.confidence)))};
  if(market.verdict!=='SUPPORT')return {approved:false,reason:'AI_LEGION_MARKET_STRUCTURE_FLOW_SUPPORT_REQUIRED',riskMultiplier:.5,confidenceFloor:num(market.confidence)};
  if(order.verdict!=='SUPPORT')return {approved:false,reason:'AI_LEGION_ORDER_RISK_SUPPORT_REQUIRED',riskMultiplier:.5,confidenceFloor:num(order.confidence)};
  if(checker&&(!checker.ok||checker.verdict==='VETO'))return {approved:false,reason:'AI_LEGION_ADVERSARIAL_CHECKER_VETO',riskMultiplier:.5,confidenceFloor:Math.min(...[...required,checker].map(z=>num(z.confidence)))};
  const riskMultiplier=Math.min(1,...agents.map(x=>clamp(num(x.riskMultiplier)||1,.5,1)));
  const confidenceFloor=Math.min(...required.map(x=>clamp(num(x.confidence),0,1)));
  return {approved:true,reason:'AI_LEGION_ROLE_CONTRACTS_PASS',riskMultiplier,confidenceFloor};
}

async function selectWorkers(env,offset=0){
  const evidenceSnapshot={...MODEL_MESH_SNAPSHOT,models:applyCapabilityEvidence(MODEL_MESH_SNAPSHOT?.models,MODEL_MESH_ACTIVE_CANDIDATE_INDEX)};
  const liveModels=await resolveLiveModels(evidenceSnapshot,env);
  const hardCapabilities=enabledHardCapabilities(MODEL_MESH_ACTIVE_CANDIDATE_INDEX,'trading');
  const selectAt=off=>selectModelWorkers({profile:'DEEP',domain:'trading',dataClass:'PUBLIC',models:liveModels,hardCapabilities,requiredCapability:'text_reasoning',offset:off});
  const pool=new Map();
  for(let i=0;i<Math.max(8,liveModels.length*2);i++)for(const worker of selectAt(i)){const key=String(worker.model_family||worker.model_id||worker.provider_id);if(!pool.has(key))pool.set(key,worker);}
  const selected=selectAt(offset).slice(0,BYBIT_AI_LEGION_ROLES.length);
  return {evidenceSnapshot,selected,poolSize:pool.size,pool:[...pool.values()].map(x=>({providerId:x.provider_id,modelId:x.model_id,modelFamily:x.model_family}))};
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

  const priorState=await kvGet(env),rotationCursor=Math.max(0,Math.floor(num(priorState?.workerRotationCursor)));
  let selectedInfo;
  try{selectedInfo=await selectWorkers(env,rotationCursor);}catch(error){
    const state={version:BYBIT_AI_LEGION_VERSION,status:'BLOCKED',mode,fingerprint,approved:false,reason:'AI_LEGION_WORKER_SELECTION_FAILED',error:String(error?.message||error).slice(0,180),riskMultiplier:.5,updatedAt:nowIso(),updatedAtMs:Date.now(),agents:[]};
    await kvPut(env,state);return state;
  }
  const workers=selectedInfo.selected||[];
  if(workers.length<p.minimumRequiredWorkers){
    const state={version:BYBIT_AI_LEGION_VERSION,status:'BLOCKED',mode,fingerprint,approved:false,reason:'AI_LEGION_INSUFFICIENT_DISTINCT_WORKERS',workerCount:workers.length,minimumRequiredWorkers:p.minimumRequiredWorkers,riskMultiplier:.5,updatedAt:nowIso(),updatedAtMs:Date.now(),agents:[]};
    await kvPut(env,state);return state;
  }
  let newsContext=null;try{newsContext=await collectBybitNewsContext(env,String(market.symbol||setup.symbol||'BTCUSDT'));}catch(error){newsContext={version:'BYBIT_NEWS_CONTEXT_V1',at:Date.now(),symbol:String(market.symbol||setup.symbol||'BTCUSDT'),stale:true,sourceCount:0,items:[],macroSummary:[],error:String(error?.message||error).slice(0,160)}}
  const payload=publicMarketPayload(market,setup,newsContext);
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
    confidenceFloor:decision.confidenceFloor,workerCount:workers.length,requiredWorkers:p.minimumRequiredWorkers,newsContext:{sourceCount:num(newsContext?.sourceCount),stale:newsContext?.stale===true,at:newsContext?.at||null,error:newsContext?.error||null},
    noMajorityVote:true,authority:'ADVISORY_EVIDENCE_ONLY',executionAuthority:'BYBIT-TOP100-STATEFLOW-3.0',decisionPolicy:'ALWAYS_DECIDE_NEVER_FORCE_TRADE',forcedTrade:false,
    workerPoolSize:num(selectedInfo.poolSize),workerPool:selectedInfo.pool||[],participationMode:p.participationMode,
    agents,orderPlanSuggestion:agents.find(x=>x.roleId==='order_risk_architect_agent')?.orderPlan||null,workerRotationCursor:rotationCursor+Math.max(1,workers.length),workerRotationEnabled:true,startedAtMs:startedAt,updatedAt:nowIso(),updatedAtMs:Date.now(),expiresAtMs:Date.now()+p.freshnessMs,
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
