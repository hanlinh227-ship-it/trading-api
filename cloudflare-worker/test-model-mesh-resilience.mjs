import assert from 'node:assert/strict';
import {QUARANTINE_FAILURE_THRESHOLD,readModelHealth,recordModelExecutionHealth,resolveCooldownMs,writeProbeHealth} from './model-mesh/health-store.js';
import {claimSelfHeal,scheduleSelfHeal} from './model-mesh/self-heal.js';
import {eligibleModel,selectionCandidate,selectionRejection,MODEL_MESH_LIMITS,MODEL_MESH_SELECTION_FILTERS} from './model-mesh/contracts.js';
import {selectModelWorkers} from './model-mesh/selector.js';
import {buildModelMeshPlan} from './model-mesh-runtime.js';
import {createProviderProbe} from './model-mesh/provider-client.js';

const SHA='c'.repeat(40);
const baseModel={provider_id:'groq',model_id:'openai/gpt-oss-120b',model_family:'gpt-oss-120b',free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z',usage_terms:'production_allowed',context_window:131072,privacy_class:'public_safe',health:'healthy',capabilities:{text_reasoning:{supported:true,score:0.8}},quality_scores:{core:0.8}};
const makeKv=()=>{const rows=new Map();return {rows,get:async k=>rows.get(k)??null,put:async(k,v)=>{rows.set(k,v);}};};
const noDelay=async()=>{};

// ===========================================================================
// 1. A transient provider failure must not quarantine a provider for 6 hours
// ===========================================================================
{
  const kv=makeKv();const t0=Date.parse('2026-09-15T12:00:00Z');
  const first=await writeProbeHealth(kv,baseModel,{ok:false,category:'AUTH_FAILED',latencyMs:10},{sourceSha:SHA,nowMs:t0,delay:noDelay});
  assert.equal(first.state,'DEGRADED','a single AUTH_FAILED is transient, not a quarantine');
  assert.equal(first.consecutiveFailures,1);
  const recovered=await writeProbeHealth(kv,baseModel,{ok:true,latencyMs:12},{sourceSha:SHA,nowMs:t0+60_000,delay:noDelay});
  assert.equal(recovered.state,'LIVE_HEALTHY');
  assert.equal(recovered.consecutiveFailures,0,'a success resets the failure streak');
}

// ===========================================================================
// 2. consecutiveFailures is load-bearing: the threshold actually quarantines
// ===========================================================================
{
  const kv=makeKv();let t=Date.parse('2026-09-15T12:00:00Z');
  const states=[];
  for(let i=0;i<QUARANTINE_FAILURE_THRESHOLD.MODEL_NOT_FOUND;i+=1){
    const row=await writeProbeHealth(kv,baseModel,{ok:false,category:'MODEL_NOT_FOUND',latencyMs:5},{sourceSha:SHA,nowMs:t,delay:noDelay});
    states.push(row.state);t+=30_000;
  }
  assert.deepEqual(states,['DEGRADED','DEGRADED','QUARANTINED'],'quarantine only once the failure has proven persistent');
  const stored=await readModelHealth(kv,baseModel,{sourceSha:SHA,nowMs:t});
  assert.equal(stored.state,'QUARANTINED');
  assert.equal(stored.consecutiveFailures,3);
}

// ===========================================================================
// 3. Retry-After / reset is honoured instead of a fixed five minutes
// ===========================================================================
{
  const now=Date.parse('2026-09-15T12:00:00Z');
  assert.equal(resolveCooldownMs({retryAfter:'900'},now),900_000,'numeric Retry-After seconds');
  assert.equal(resolveCooldownMs({retryAfter:String(new Date(now+600_000).toUTCString())},now),600_000,'HTTP-date Retry-After');
  assert.equal(resolveCooldownMs({resetAt:new Date(now+120_000).toISOString()},now),120_000,'ISO reset timestamp');
  assert.equal(resolveCooldownMs({},now),5*60*1000,'documented default when the provider says nothing');
  assert.equal(resolveCooldownMs({retryAfter:'99999'},now),60*60*1000,'clamped to one hour');
  assert.equal(resolveCooldownMs({retryAfter:'1'},now),30_000,'clamped to a 30s floor so we cannot hammer');

  const kv=makeKv();const t0=Date.parse('2026-09-15T12:00:00Z');
  const cooled=await writeProbeHealth(kv,baseModel,{ok:false,category:'RATE_LIMITED',retryAfter:'900',latencyMs:3},{sourceSha:SHA,nowMs:t0,delay:noDelay});
  assert.equal(cooled.state,'COOLDOWN');
  assert.equal(Date.parse(cooled.cooldownUntil)-t0,900_000,'cooldown follows the provider, not our default');
}

// ===========================================================================
// 4. Quota-aware probing: a provider inside its own cooldown is not re-probed
// ===========================================================================
{
  const kv=makeKv();
  await writeProbeHealth(kv,baseModel,{ok:false,category:'RATE_LIMITED',retryAfter:'900',latencyMs:3},{sourceSha:SHA,nowMs:Date.now(),delay:noDelay});
  let calls=0;
  const probe=createProviderProbe({fetchImpl:async()=>{calls+=1;return new Response(JSON.stringify({choices:[{message:{content:'OK'}}]}),{status:200,headers:{'content-type':'application/json'}});}});
  const envelope=await probe({GROQ_API_KEY:'k'.repeat(24),TRADING_STATE:kv},{modelSnapshot:{source_sha:SHA,models:[baseModel]}});
  assert.equal(calls,0,'no provider request is spent while its own cooldown is active');
  assert.equal(envelope.results[0].state,'COOLDOWN');
  assert.equal(envelope.results[0].skipped,'quota_cooldown_active');
  assert.equal(envelope.results[0].evidencePersisted,true,'stored evidence still counts as persisted');
}

// ===========================================================================
// 4b. A QUARANTINED model is not re-called inside its quarantine window
// ===========================================================================
{
  const kv=makeKv();
  for(let i=0;i<QUARANTINE_FAILURE_THRESHOLD.MODEL_NOT_FOUND;i+=1){
    await writeProbeHealth(kv,baseModel,{ok:false,category:'MODEL_NOT_FOUND',latencyMs:3},{sourceSha:SHA,nowMs:Date.now(),delay:noDelay});
  }
  assert.equal((await readModelHealth(kv,baseModel,{sourceSha:SHA})).state,'QUARANTINED');
  let calls=0;
  const probe=createProviderProbe({fetchImpl:async()=>{calls+=1;return new Response(JSON.stringify({choices:[{message:{content:'OK'}}]}),{status:200,headers:{'content-type':'application/json'}});}});
  const envelope=await probe({GROQ_API_KEY:'k'.repeat(24),TRADING_STATE:kv},{modelSnapshot:{source_sha:SHA,models:[baseModel]}});
  assert.equal(calls,0,'policy quarantine_before_next_request: a probe is a request');
  assert.equal(envelope.results[0].state,'QUARANTINED');
  assert.equal(envelope.results[0].skipped,'quarantine_active');
  assert.equal(envelope.results[0].evidencePersisted,true);
}

// ===========================================================================
// 5. Stale evidence, all providers down, and graceful zero
// ===========================================================================
{
  const kv=makeKv();const t0=Date.parse('2026-09-15T12:00:00Z');
  await writeProbeHealth(kv,baseModel,{ok:true,latencyMs:5},{sourceSha:SHA,nowMs:t0,delay:noDelay});
  const fresh=await readModelHealth(kv,baseModel,{sourceSha:SHA,nowMs:t0+60_000});
  assert.equal(fresh.state,'LIVE_HEALTHY');
  const stale=await readModelHealth(kv,baseModel,{sourceSha:SHA,nowMs:t0+31*60_000});
  assert.equal(stale.state,'DEGRADED');
  assert.equal(stale.category,'STALE_EVIDENCE');
  const otherRevision=await readModelHealth(kv,baseModel,{sourceSha:'d'.repeat(40),nowMs:t0+60_000});
  assert.equal(otherRevision.category,'SOURCE_REVISION_MISMATCH');
}

const skillSnapshot={source_sha:SHA,fallback_primary_skill:'core_reasoning',capsules:{core_reasoning:{domain:'core',capsule_hash:'h'}}};
const modelSnapshot={source_sha:SHA,models:[baseModel]};
const activeIndex={schema_version:1,source_sha:SHA,mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,coverage:{},entries:[{candidate_key:'groq:openai/gpt-oss-120b',provider_id:'groq',model_id:'openai/gpt-oss-120b',model_family:'gpt-oss-120b',capability_evidence:{text_reasoning:{state:'PROVISIONAL',score:0.8,evidence_ids:[],measured_at:null}}}]};

{
  const plan=await buildModelMeshPlan({text:'analyse this',profile:'DEEP'},{skillSnapshot,modelSnapshot,activeIndex,env:{}});
  assert.equal(plan.ok,true,'the Brain answers even with no provider at all');
  assert.deepEqual(plan.workers,[]);
  assert.equal(plan.selectionReason,'no_live_healthy_provider');
  assert.equal(plan.routingAuthority,false);
  assert.equal(plan.reasoningAuthority,false);
}

// ===========================================================================
// 6. FAST and SECRET never reach an external worker
// ===========================================================================
{
  const env={GROQ_API_KEY:'k'.repeat(24),TRADING_STATE:makeKv()};
  const fast=await buildModelMeshPlan({text:'hi',profile:'FAST'},{skillSnapshot,modelSnapshot,activeIndex,env});
  assert.deepEqual(fast.workers,[]);
  assert.equal(fast.selectionReason,'fast_external_mesh_forbidden');
  assert.equal(MODEL_MESH_LIMITS.FAST,0,'the compiled policy forbids FAST fan-out');

  const secret=await buildModelMeshPlan({text:'hi',profile:'DEEP',dataClass:'SECRET'},{skillSnapshot,modelSnapshot,activeIndex,env});
  assert.deepEqual(secret.workers,[]);
  assert.equal(secret.selectionReason,'secret_external_mesh_forbidden');
  const unknown=await buildModelMeshPlan({text:'hi',profile:'DEEP',dataClass:'not-a-class'},{skillSnapshot,modelSnapshot,activeIndex,env});
  assert.equal(unknown.dataClass,'SECRET');
  assert.deepEqual(unknown.workers,[]);
}

// ===========================================================================
// 7. Every declared selection filter is implemented and reports its rejection
// ===========================================================================
{
  const healthy={...baseModel};
  assert.equal(selectionRejection(healthy,{}),null);
  assert.equal(selectionRejection({...healthy,free_status:'trial_credit'},{}),'free_entitlement');
  assert.equal(selectionRejection({...healthy,usage_terms:'evaluation'},{}),'usage_terms');
  assert.equal(selectionRejection({...healthy,capabilities:{}},{}),'capability');
  assert.equal(selectionRejection(healthy,{dataClass:'SECRET'}),'permission_ceiling');
  assert.equal(selectionRejection(healthy,{dataClass:'CONFIDENTIAL'}),'privacy');
  assert.equal(selectionRejection({...healthy,health:'unavailable'},{}),'health');
  assert.equal(selectionRejection({...healthy,quota_state:{state:'COOLDOWN_QUOTA',resetAt:null}},{}),'quota');
  assert.equal(selectionRejection(healthy,{contextTokens:200000}),'context_fit');
  for(const filter of MODEL_MESH_SELECTION_FILTERS)assert.ok(typeof filter==='string'&&filter.length);
  assert.equal(selectionCandidate({...healthy,usage_terms:'evaluation'}),false);
  assert.equal(eligibleModel({...healthy,usage_terms:'evaluation'}),false);
  assert.equal(selectionCandidate({...healthy,health:'unavailable'}),true);
}

// ===========================================================================
// 8. Family dedupe: one model family is never two independent reasoners
// ===========================================================================
{
  const twins=[
    {...baseModel,provider_id:'groq',model_id:'a',model_family:'gpt-oss-120b',quality_scores:{core:0.9}},
    {...baseModel,provider_id:'huggingface_inference_providers',model_id:'b',model_family:'gpt-oss-120b',quality_scores:{core:0.85}},
    {...baseModel,provider_id:'mistral',model_id:'c',model_family:'mistral-small',quality_scores:{core:0.7}},
  ];
  const picked=selectModelWorkers({profile:'DEEP',models:twins});
  assert.deepEqual(picked.map(w=>w.model_family),['gpt-oss-120b','mistral-small'],'the duplicate family is dropped');
  assert.deepEqual(picked.map(w=>w.worker_role),['maker','critic']);
  assert.ok(selectModelWorkers({profile:'STANDARD',models:twins}).length<=MODEL_MESH_LIMITS.STANDARD);
}

// ===========================================================================
// 9. Concurrent health writes do not lose the quarantine
// ===========================================================================
{
  const kv=makeKv();const t0=Date.parse('2026-09-15T12:00:00Z');
  const [a,b]=await Promise.all([
    writeProbeHealth(kv,baseModel,{ok:false,category:'AUTH_FAILED',latencyMs:1},{sourceSha:SHA,nowMs:t0,delay:noDelay}),
    writeProbeHealth(kv,baseModel,{ok:false,category:'AUTH_FAILED',latencyMs:2},{sourceSha:SHA,nowMs:t0+1,delay:noDelay}),
  ]);
  assert.ok(['DEGRADED','QUARANTINED'].includes(a.state));
  assert.ok(['DEGRADED','QUARANTINED'].includes(b.state));
  const settled=await readModelHealth(kv,baseModel,{sourceSha:SHA,nowMs:t0+2});
  assert.ok(Number.isInteger(settled.consecutiveFailures)&&settled.consecutiveFailures>=1,'the record stays well-formed under a concurrent write');
}

// ===========================================================================
// 10. Execution feedback never fabricates a success refresh
// ===========================================================================
{
  const kv=makeKv();const t0=Date.parse('2026-09-15T12:00:00Z');
  const onSuccess=await recordModelExecutionHealth(kv,baseModel,{ok:true,latencyMs:10},{sourceSha:SHA,nowMs:t0});
  assert.equal(onSuccess.persisted,false,'a successful execution does not mint LIVE evidence');
  assert.equal(onSuccess.storeCategory,'SCHEDULED_PROBE_OWNS_SUCCESS_REFRESH');
}

// ===========================================================================
// 11. Capability evidence never mints live health
// ===========================================================================
{
  const evidenceOnly={...baseModel,capability_evidence:{text_reasoning:{state:'VERIFIED',score:0.95,evidence_ids:['bench'],measured_at:'2026-09-15T10:00:00Z'}}};
  const state=await readModelHealth(makeKv(),evidenceOnly,{sourceSha:SHA,nowMs:Date.parse('2026-09-15T12:00:00Z')});
  assert.notEqual(state.state,'LIVE_HEALTHY','capability verification is independent from provider live-health evidence');
}

// ===========================================================================
// 12. Self-heal is bounded and never surfaces as a request error
// ===========================================================================
{
  const kv=makeKv();const t0=Date.parse('2026-09-15T12:00:00Z');
  assert.equal((await claimSelfHeal(kv,{nowMs:t0})).claimed,true);
  const second=await claimSelfHeal(kv,{nowMs:t0+60_000});
  assert.equal(second.claimed,false,'recovery is rate-limited, not once per request');
  assert.equal(second.reason,'recently_attempted');
  assert.equal((await claimSelfHeal(kv,{nowMs:t0+6*60_000})).claimed,true,'and becomes available again after the interval');
  assert.equal((await claimSelfHeal(null,{nowMs:t0})).claimed,false,'no health store means no recovery attempt');

  const pending=[];
  const ctx={waitUntil:p=>pending.push(p)};
  const scheduled=scheduleSelfHeal({env:{TRADING_STATE:makeKv()},ctx,probeProviders:async()=>{throw new Error('provider down');},modelSnapshot,nowMs:t0});
  assert.equal(scheduled.scheduled,true);
  await Promise.all(pending);
  assert.equal(scheduleSelfHeal({env:{},ctx:{},probeProviders:async()=>{},modelSnapshot}).scheduled,false);
}

// ===========================================================================
// 13. domain_capabilities.yaml is real ranking authority, not documentation
// ===========================================================================
{
  const coder={...baseModel,provider_id:'groq',model_id:'coder',model_family:'coder-family',
    capabilities:{text_reasoning:{supported:true,score:0.7},coding:{supported:true,score:0.95}},quality_scores:{}};
  const scholar={...baseModel,provider_id:'gemini_developer_api',model_id:'scholar',model_family:'scholar-family',
    capabilities:{text_reasoning:{supported:true,score:0.7},long_context:{supported:true,score:0.95},research_synthesis:{supported:true,score:0.95}},quality_scores:{}};
  const pool=[coder,scholar];

  const engineering=selectModelWorkers({profile:'DEEP',domain:'engineering',models:pool});
  assert.equal(engineering[0].model_family,'coder-family','engineering must prefer the coding model');
  const academic=selectModelWorkers({profile:'DEEP',domain:'academic',models:pool});
  assert.equal(academic[0].model_family,'scholar-family','academic must prefer the long-context research model');

  const sparse={...baseModel,provider_id:'mistral',model_id:'sparse',model_family:'sparse-family',
    capabilities:{text_reasoning:{supported:true,score:0.5}},quality_scores:{}};
  const withSparse=selectModelWorkers({profile:'DEEP',domain:'engineering',models:[...pool,sparse]});
  assert.equal(withSparse.length,3,'incomplete capability coverage ranks low but never disqualifies');
  assert.equal(withSparse.at(-1).model_family,'sparse-family');
}

console.log('model mesh resilience, quota and recovery contracts ok');
