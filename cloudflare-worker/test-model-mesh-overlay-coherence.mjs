// Regression suite for the exact-main deploy failure
// `overlay_missing_expected_provider:openrouter`.
//
// What happened: the deploy canary probed, openrouter answered, the probe
// persisted LIVE_HEALTHY - and `/brain/mesh/health` kept reporting openrouter
// inactive for the entire 60-second retry window. Re-reading could never fix
// it, because the problem was not propagation. A SECOND probe (the Worker's own
// 20-minute cron, started before the deploy and still in flight) finished
// afterwards and overwrote the record: under a last-writer-wins store the
// SLOWEST probe wins rather than the LATEST one, and its evidence belonged to
// the previous source revision, which the reader then correctly refused.
//
// Two structural changes close it, and this file damages both:
//   1. evidence is keyed per source revision, so revisions cannot share a slot
//   2. the Durable Object refuses a write whose observation is older than the
//      stored one, and tells the writer it lost rather than letting it report
//      its own losing record as the truth
//
// These tests drive the REAL ModelMeshHealthState against an in-memory storage,
// not a stand-in for it, because the guard being tested lives inside it.

import assert from 'node:assert/strict';
import {ModelMeshHealthState,resolveModelHealthStore} from './model-mesh/health-state.js';
import {writeProbeHealth,readModelHealth} from './model-mesh/health-store.js';
import {providerRuntimeStatus} from './model-mesh/runtime-health.js';
import {validateLiveOverlay,validateProbeCanary} from './model-mesh/canary-policy.js';

const REVISION_A='a'.repeat(40);
const REVISION_B='b'.repeat(40);
const noDelay=async()=>{};

class MemoryStorage{
  constructor(){this.rows=new Map();}
  async get(key){return this.rows.get(key);}
  async put(key,value){this.rows.set(key,value);}
  async delete(keys){for(const key of (Array.isArray(keys)?keys:[keys]))this.rows.delete(key);}
  async list({prefix='',limit=1000}={}){
    const out=new Map();
    for(const [key,value] of this.rows){
      if(!key.startsWith(prefix))continue;
      out.set(key,value);
      if(out.size>=limit)break;
    }
    return out;
  }
}

function strongEnv(extra={}){
  const storage=new MemoryStorage();
  const object=new ModelMeshHealthState({storage});
  const namespace={idFromName:name=>`id:${name}`,get:()=>({fetch:request=>object.fetch(request)})};
  return {env:{MODEL_MESH_HEALTH:namespace,...extra},storage};
}

const freeModel=(providerId,modelId)=>({
  provider_id:providerId,
  model_id:modelId,
  model_family:modelId,
  free_status:'account_specific',
  free_verified_at:'2026-09-16T00:00:00Z',
  usage_terms:'production_allowed',
  context_window:131072,
  health:'degraded',
  privacy_class:'public_safe',
  capabilities:{text_reasoning:{supported:true,score:0.8}},
  quality_scores:{},
});

const openrouter=freeModel('openrouter','deepseek/deepseek-chat-v3.1:free');
const groq=freeModel('groq','openai/gpt-oss-120b');
const snapshot=(sourceSha,models)=>({schema_version:1,source_sha:sourceSha,mode:'FREE_ONLY',models});
const credentials={OPENROUTER_API_KEY:'configured',GROQ_API_KEY:'configured'};
const activeIds=async(env,snap,nowMs)=>
  (await providerRuntimeStatus(snap,env,{nowMs})).filter(row=>row.active===true).map(row=>row.providerId);

// ---------------------------------------------------------------------------
// 1. A live probe at the current revision makes the provider active.
// ---------------------------------------------------------------------------
{
  const {env}=strongEnv(credentials);
  const nowMs=Date.parse('2026-09-18T16:41:20Z');
  const store=resolveModelHealthStore(env);
  const written=await writeProbeHealth(store,openrouter,{ok:true,latencyMs:12},{sourceSha:REVISION_A,nowMs,delay:noDelay});
  assert.equal(written.state,'LIVE_HEALTHY');
  assert.equal(written.persisted,true);
  assert.equal(written.superseded,false);
  assert.equal(written.writeGuard,'ENFORCED');
  assert.deepEqual(
    await activeIds(env,snapshot(REVISION_A,[openrouter]),nowMs+1000),
    ['openrouter'],
    'evidence persisted at this revision must make the provider active');
}

// ---------------------------------------------------------------------------
// 2. Evidence from revision A can never make revision B active.
// ---------------------------------------------------------------------------
{
  const {env}=strongEnv(credentials);
  const nowMs=Date.parse('2026-09-18T16:41:20Z');
  const store=resolveModelHealthStore(env);
  await writeProbeHealth(store,openrouter,{ok:true,latencyMs:12},{sourceSha:REVISION_A,nowMs,delay:noDelay});
  assert.deepEqual(
    await activeIds(env,snapshot(REVISION_B,[openrouter]),nowMs+1000),
    [],
    'a provider probed under another revision must not appear active here');
  // ...and it is still active for the revision that actually observed it.
  assert.deepEqual(await activeIds(env,snapshot(REVISION_A,[openrouter]),nowMs+1000),['openrouter']);
}

// ---------------------------------------------------------------------------
// 3. THE PRODUCTION FAILURE. A probe that began under the previous revision
//    finishes after the deploy. Its write must not destroy the new revision's
//    evidence, and the overlay must still see the provider as active.
// ---------------------------------------------------------------------------
{
  const {env}=strongEnv(credentials);
  const deployAt=Date.parse('2026-09-18T16:41:03Z');
  const store=resolveModelHealthStore(env);

  // The deploy canary probes the newly live revision and openrouter answers.
  const canaryProbe=await writeProbeHealth(store,openrouter,{ok:true,latencyMs:12},
    {sourceSha:REVISION_B,nowMs:deployAt+17_000,delay:noDelay});
  assert.equal(canaryProbe.state,'LIVE_HEALTHY');

  // The cron probe, started 63 seconds BEFORE the deploy under the previous
  // revision, now finishes and writes a rate-limited result - later in time,
  // older in revision. This is the write that used to win.
  const lateCron=await writeProbeHealth(store,openrouter,{ok:false,category:'RATE_LIMITED'},
    {sourceSha:REVISION_A,nowMs:deployAt+47_000,delay:noDelay});
  assert.equal(lateCron.state,'COOLDOWN');

  const live=await readModelHealth(store,openrouter,{sourceSha:REVISION_B,nowMs:deployAt+50_000});
  assert.equal(live.state,'LIVE_HEALTHY','the previous revision must not overwrite this revision\'s evidence');
  assert.deepEqual(await activeIds(env,snapshot(REVISION_B,[openrouter]),deployAt+50_000),['openrouter']);

  // And the canary comparison - the thing that actually failed - converges.
  const envelope={ok:true,mode:'FREE_ONLY',routingAuthority:false,reasoningAuthority:false,
    probedProviderCount:1,successfulProviderCount:1,liveHealthyProviderCount:1,
    results:[{providerId:'openrouter',modelId:openrouter.model_id,configured:true,ok:true,
      status:200,latencyMs:12,category:null,state:'LIVE_HEALTHY',evidencePersisted:true}]};
  const health={providers:await providerRuntimeStatus(snapshot(REVISION_B,[openrouter]),env,{nowMs:deployAt+50_000})};
  const overlay=validateLiveOverlay(envelope,health);
  assert.deepEqual(overlay.expectedProviderIds,['openrouter']);
  assert.deepEqual(overlay.extraActiveProviderIds,[]);
}

// ---------------------------------------------------------------------------
// 4. Healthy then degraded, within one revision: the LATEST observation is
//    authoritative whichever write lands last, and the loser is told it lost
//    instead of reporting its own record as the truth.
// ---------------------------------------------------------------------------
{
  const {env}=strongEnv(credentials);
  const t0=Date.parse('2026-09-18T16:41:00Z');
  const store=resolveModelHealthStore(env);

  // A newer observation says the provider has degraded.
  await writeProbeHealth(store,openrouter,{ok:false,category:'RATE_LIMITED'},
    {sourceSha:REVISION_B,nowMs:t0+30_000,delay:noDelay});
  // An older, slower probe that saw it healthy now completes.
  const loser=await writeProbeHealth(store,openrouter,{ok:true,latencyMs:9},
    {sourceSha:REVISION_B,nowMs:t0+10_000,delay:noDelay});

  assert.equal(loser.superseded,true,'a stale observation must be refused, not silently applied');
  assert.equal(loser.state,'COOLDOWN','the loser must report the winning state, not its own');
  assert.equal(loser.persisted,true,'evidence IS persisted - just not this probe\'s');
  assert.equal(loser.supersededReason,'superseded_by_newer_observation');
  assert.deepEqual(await activeIds(env,snapshot(REVISION_B,[openrouter]),t0+31_000),[]);

  // The canary must accept the decoupled row without ever letting a superseded
  // unavailable provider into the expected-active set.
  const envelope={ok:true,mode:'FREE_ONLY',routingAuthority:false,reasoningAuthority:false,
    probedProviderCount:1,successfulProviderCount:1,liveHealthyProviderCount:0,
    results:[{providerId:'openrouter',modelId:openrouter.model_id,configured:true,ok:true,
      status:200,latencyMs:9,category:null,state:'COOLDOWN',evidencePersisted:true,superseded:true}]};
  const summary=validateProbeCanary(envelope);
  assert.equal(summary.healthyCount,0);
  assert.equal(summary.succeededCount,1);
  assert.equal(summary.supersededCount,1);
  assert.deepEqual(validateLiveOverlay(envelope,{providers:[]}).expectedProviderIds,[],
    'a superseded-unavailable provider must never be expected active');
  // requireHealthy must still refuse: a successful call is not live evidence.
  assert.throws(()=>validateProbeCanary(envelope,{requireHealthy:true}),/no_live_healthy_provider/);

  // Decoupled is not unconstrained. `superseded` frees a row from the ok/state
  // coupling; it must not become a hole through which any string passes as a
  // health state.
  const bogus={...envelope,results:[{...envelope.results[0],state:'TOTALLY_FINE'}]};
  assert.throws(()=>validateProbeCanary(bogus),/probe_state_unknown:openrouter/);
}

// ---------------------------------------------------------------------------
// 5. Stale evidence cannot satisfy the production canary.
// ---------------------------------------------------------------------------
{
  const {env}=strongEnv(credentials);
  const t0=Date.parse('2026-09-18T16:00:00Z');
  const store=resolveModelHealthStore(env);
  await writeProbeHealth(store,openrouter,{ok:true,latencyMs:12},{sourceSha:REVISION_B,nowMs:t0,delay:noDelay});
  const afterTtl=t0+31*60_000;
  assert.equal((await readModelHealth(store,openrouter,{sourceSha:REVISION_B,nowMs:afterTtl})).category,'STALE_EVIDENCE');
  assert.deepEqual(await activeIds(env,snapshot(REVISION_B,[openrouter]),afterTtl),[]);

  const envelope={ok:true,mode:'FREE_ONLY',routingAuthority:false,reasoningAuthority:false,
    probedProviderCount:1,successfulProviderCount:1,liveHealthyProviderCount:1,
    results:[{providerId:'openrouter',modelId:openrouter.model_id,configured:true,ok:true,
      status:200,latencyMs:12,category:null,state:'LIVE_HEALTHY',evidencePersisted:true}]};
  const health={providers:await providerRuntimeStatus(snapshot(REVISION_B,[openrouter]),env,{nowMs:afterTtl})};
  assert.throws(()=>validateLiveOverlay(envelope,health),/overlay_missing_expected_provider:openrouter/,
    'stale evidence must fail the canary rather than be accepted as live');
}

// ---------------------------------------------------------------------------
// 6. Nothing here can make a non-free or uncredentialed provider active.
// ---------------------------------------------------------------------------
{
  const paid={...openrouter,free_status:'trial_credit'};
  const {env}=strongEnv(credentials);
  const nowMs=Date.parse('2026-09-18T16:41:20Z');
  const store=resolveModelHealthStore(env);
  const written=await writeProbeHealth(store,paid,{ok:true,latencyMs:12},{sourceSha:REVISION_B,nowMs,delay:noDelay});
  assert.equal(written.state,'NOT_ELIGIBLE');
  assert.equal(written.category,'FREE_ONLY_POLICY');
  assert.deepEqual(await activeIds(env,snapshot(REVISION_B,[paid]),nowMs+1000),[],
    'the zero-cost guard is not negotiable by a health write');

  // No credential: configured is false, so no probe result can activate it.
  const {env:bare}=strongEnv({});
  const bareStore=resolveModelHealthStore(bare);
  await writeProbeHealth(bareStore,groq,{ok:true,latencyMs:5},{sourceSha:REVISION_B,nowMs,delay:noDelay});
  assert.deepEqual(await activeIds(bare,snapshot(REVISION_B,[groq]),nowMs+1000),[]);
}

// ---------------------------------------------------------------------------
// 7. Expired rows are swept, so per-revision keying cannot grow without bound.
// ---------------------------------------------------------------------------
{
  const {env,storage}=strongEnv(credentials);
  const store=resolveModelHealthStore(env);
  // A row left behind by a retired revision, whose TTL has already passed.
  // Nothing will ever read it again - its revision is gone - so the lazy
  // delete on read can never reach it. Storage TTL is wall-clock, so this is
  // planted with a real past expiry rather than an injected clock.
  storage.rows.set(`brain:model-mesh:health:v1:openrouter:${REVISION_A}:deadbeef`,
    {value:'{}',expiresAt:Date.now()-1000,observedAt:Date.now()-60_000});
  assert.equal(storage.rows.size,1);
  await writeProbeHealth(store,openrouter,{ok:true,latencyMs:12},{sourceSha:REVISION_B,nowMs:Date.now(),delay:noDelay});
  assert.equal(storage.rows.size,1,'expired evidence from a retired revision must not accumulate');
  assert.ok([...storage.rows.keys()][0].includes(REVISION_B));
}

console.log('model mesh provider overlay coherence contracts ok');
