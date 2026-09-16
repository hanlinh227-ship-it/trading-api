# Image Render Agent V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing FREE_ONLY image renderer so one typed request can execute 20–100 scenes with durable batch state, bounded parallelism, adaptive free-model routing, continuity locks, bounded QA/retry, and backward-compatible single-image endpoints.

**Architecture:** `GITHUB_BRAIN_V4` stays the only routing/reasoning authority. Brain converts natural-language render intent into `image_render_batch_request_v2`; the Worker validates that typed request, creates a manifest, and persists each logical batch in an `ImageRenderBatchState` Durable Object. Pure modules own prompt/continuity compilation, model ranking, state transitions, quality decisions, and export metadata; the Durable Object owns persistence, alarms, provider polling, bounded retry, and cancellation.

**Tech Stack:** JavaScript ES modules on Cloudflare Workers, Durable Objects with SQLite storage, Node.js `assert/strict` tests, AI Horde REST API, YAML Brain policy, Python `release.py` for GITHUB_BRAIN_V4 releases.

**Spec:** `docs/superpowers/specs/2026-09-16-image-render-agent-v2-design.md`

## Global Constraints

- `FREE_ONLY` is mandatory for every image-generation route.
- `paid_fallback=false`; `auto_purchase=false`.
- Trial/promo credit is never an acceptable paid fallback.
- `GITHUB_BRAIN_V4` remains routing/reasoning authority.
- `image_render_agent` remains a specialist executor with `routing_authority:false` and `reasoning_authority:false`.
- Existing V1 single-image routes stay backward compatible.
- AI Horde execution requires an explicit `dataClass` and accepts only `PUBLIC`.
- Reference images remain disabled by default in V2 core.
- Maximum logical scenes per batch: `100`.
- Default active provider jobs: `4`; adaptive ceiling: `8`.
- Maximum attempts per scene: `3`.
- Batch state uses `IMAGE_RENDER_BATCH`, never `TRADING_STATE`.
- STRICT mode never reports metadata-only QA as full visual verification.
- No persistent paid asset-storage dependency is added.
- No production render smoke occurs before unit/integration/regression gates pass.

---

## File Map

### New runtime modules

- `cloudflare-worker/image-render/render-manifest.js` — typed batch validation and canonical manifests.
- `cloudflare-worker/image-render/prompt-compiler.js` — merges explicit scene content with continuity locks.
- `cloudflare-worker/image-render/model-router.js` — deterministic ranking of live free image models.
- `cloudflare-worker/image-render/provider-registry.js` — provider-neutral adapter registry; AI Horde only at V2 launch.
- `cloudflare-worker/image-render/quality-policy.js` — STRUCTURAL/VISUAL/STRICT decisions.
- `cloudflare-worker/image-render/batch-engine.js` — pure batch/scene state machine.
- `cloudflare-worker/image-render/batch-state.js` — Durable Object orchestration and alarms.
- `cloudflare-worker/image-render/batch-client.js` — handler-to-Durable-Object client.
- `cloudflare-worker/image-render/export-contract.js` — render report and ZIP/export handoff metadata.

### Existing runtime files to modify

- `cloudflare-worker/image-render/ai-horde.js`
- `cloudflare-worker/image-render-handler.js`
- `cloudflare-worker/index.js`
- `cloudflare-worker/prepare-wrangler.mjs`
- `cloudflare-worker/wrangler.example.jsonc`
- `cloudflare-worker/package.json`
- `cloudflare-worker/test-deploy-safety.mjs`

### New tests

- `cloudflare-worker/test-image-render-v2-contracts.mjs`
- `cloudflare-worker/test-image-render-v2-provider.mjs`
- `cloudflare-worker/test-image-render-v2-model-router.mjs`
- `cloudflare-worker/test-image-render-v2-quality.mjs`
- `cloudflare-worker/test-image-render-v2-batch-engine.mjs`
- `cloudflare-worker/test-image-render-v2-batch-state.mjs`
- `cloudflare-worker/test-image-render-v2-handler.mjs`
- `cloudflare-worker/test-image-render-v2-export.mjs`

### Brain policy/release files

- `AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml`
- `AI_SKILL_LIBRARY/v4/legion/agents.yaml`
- `AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml`
- generated `AI_SKILL_LIBRARY/v4/releases/4.13.0/manifest.yaml`
- generated `AI_SKILL_LIBRARY/v4/releases/current.json`
- generated `AI_SKILL_LIBRARY/v4/releases/history.yaml`

---

### Task 1: Typed batch contract and prompt compiler

**Files:**
- Create: `cloudflare-worker/image-render/render-manifest.js`
- Create: `cloudflare-worker/image-render/prompt-compiler.js`
- Test: `cloudflare-worker/test-image-render-v2-contracts.mjs`

**Interfaces:**
- Produces: `validateImageBatchRequest(body) -> {ok:true,request}|{ok:false,status,error}`
- Produces: `createRenderManifest(request,{batchId,createdAt}) -> manifest`
- Produces: `compileScenePrompt(scene,manifest) -> {prompt,negativePrompt,locks}`

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict';
import {validateImageBatchRequest,createRenderManifest} from './image-render/render-manifest.js';
import {compileScenePrompt} from './image-render/prompt-compiler.js';

const scenes=Array.from({length:20},(_,i)=>({sceneId:String(i+1),prompt:`Max scene ${i+1}`}));
assert.equal(validateImageBatchRequest({scenes}).error,'data_class_required');
assert.equal(validateImageBatchRequest({dataClass:'INTERNAL',scenes}).error,'ai_horde_public_data_only');
assert.equal(validateImageBatchRequest({dataClass:'PUBLIC',referenceImages:['x'],scenes}).error,'reference_images_not_enabled_for_volunteer_provider');
assert.equal(validateImageBatchRequest({dataClass:'PUBLIC',scenes:Array.from({length:101},()=>({prompt:'x'}))}).error,'batch_scene_limit_exceeded');
const valid=validateImageBatchRequest({dataClass:'PUBLIC',qualityMode:'STRICT',consistencyMode:'STRICT',scenes,globalConstraints:['16:9'],sharedCharacterState:{Max:['red-orange fur','blue shirt','yellow overalls']}});
assert.equal(valid.ok,true);
const manifest=createRenderManifest(valid.request,{batchId:'batch-test-001',createdAt:'2026-09-16T00:00:00.000Z'});
const compiled=compileScenePrompt(manifest.scenes[0],manifest);
assert.match(compiled.prompt,/Max scene 1/);
assert.match(compiled.prompt,/red-orange fur/);
assert.equal(compiled.locks.consistencyMode,'STRICT');
console.log('IMAGE_RENDER_V2_CONTRACTS_TEST=PASS');
```

- [ ] **Step 2: Run to prove RED**

```bash
cd cloudflare-worker
node test-image-render-v2-contracts.mjs
```

Expected: non-zero exit because the new modules do not exist.

- [ ] **Step 3: Implement minimal contract**

```js
export const IMAGE_BATCH_MAX_SCENES=100;
export const IMAGE_BATCH_DEFAULT_CONCURRENCY=4;
export const IMAGE_BATCH_MAX_CONCURRENCY=8;
export const IMAGE_BATCH_MAX_ATTEMPTS=3;

export function validateImageBatchRequest(body={}) {
  if (body?.dataClass===undefined || body?.dataClass===null || String(body.dataClass).trim()==='') return {ok:false,status:400,error:'data_class_required'};
  if (String(body.dataClass)!=='PUBLIC') return {ok:false,status:403,error:'ai_horde_public_data_only'};
  if (body.referenceImages!==undefined || body.sourceImage!==undefined) return {ok:false,status:409,error:'reference_images_not_enabled_for_volunteer_provider'};
  const scenes=Array.isArray(body.scenes)?body.scenes:[];
  if (!scenes.length) return {ok:false,status:400,error:'batch_scenes_required'};
  if (scenes.length>IMAGE_BATCH_MAX_SCENES) return {ok:false,status:413,error:'batch_scene_limit_exceeded'};
  if (scenes.some(x=>typeof x?.prompt!=='string'||!x.prompt.trim())) return {ok:false,status:400,error:'invalid_scene_prompt'};
  return {ok:true,request:{...body,dataClass:'PUBLIC',qualityMode:body.qualityMode==='STRUCTURAL'?'STRUCTURAL':'STRICT',consistencyMode:body.consistencyMode==='FLEXIBLE'?'FLEXIBLE':'STRICT',scenes:scenes.map((s,i)=>({...s,sceneId:String(s.sceneId||i+1)})),schedulerConfig:{concurrency:Math.min(8,Math.max(1,Number(body?.schedulerConfig?.concurrency)||4))},retryPolicy:{maxAttempts:Math.min(3,Math.max(1,Number(body?.retryPolicy?.maxAttempts)||3))}}};
}
```

`createRenderManifest()` preserves `original_prompt`, creates `attempts:[]`, and initializes each scene to `queued`. `compileScenePrompt()` appends explicit locks/global constraints without replacing subject/action/environment facts from `original_prompt`.

- [ ] **Step 4: Run GREEN**

Run: `node test-image-render-v2-contracts.mjs`

Expected: `IMAGE_RENDER_V2_CONTRACTS_TEST=PASS`.

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/image-render/render-manifest.js cloudflare-worker/image-render/prompt-compiler.js cloudflare-worker/test-image-render-v2-contracts.mjs
git commit -m "feat(image): add V2 batch manifest contracts"
```

---

### Task 2: AI Horde live-model adapter and provider registry

**Files:**
- Modify: `cloudflare-worker/image-render/ai-horde.js`
- Create: `cloudflare-worker/image-render/provider-registry.js`
- Test: `cloudflare-worker/test-image-render-v2-provider.mjs`

**Interfaces:**
- Produces: `listAiHordeModels({fetchImpl}) -> {ok,status,provider,models[]}`
- Produces: `createImageProviderRegistry({fetchImpl}) -> {get(id,env),list()}`
- Adapter methods: `health()`, `listModels()`, `submit(input)`, `check(jobId)`, `status(jobId)`, `cancel(jobId)`.

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict';
import {listAiHordeModels} from './image-render/ai-horde.js';
import {createImageProviderRegistry} from './image-render/provider-registry.js';
const fetchImpl=async url=>new Response(JSON.stringify([{name:'Model A',count:4,performance:25.5,eta:2,queued:1}]),{status:200,headers:{'content-type':'application/json'}});
const listed=await listAiHordeModels({fetchImpl});
assert.deepEqual(listed.models[0],{name:'Model A',workerCount:4,performance:25.5,eta:2,queued:1});
const registry=createImageProviderRegistry({fetchImpl});
assert.deepEqual(registry.list(),['ai_horde']);
assert.equal(registry.get('unknown',{}),null);
console.log('IMAGE_RENDER_V2_PROVIDER_TEST=PASS');
```

- [ ] **Step 2: Run RED**

Run: `node test-image-render-v2-provider.mjs`

- [ ] **Step 3: Implement model listing**

Add to `ai-horde.js`:

```js
export async function listAiHordeModels({fetchImpl=fetch}={}) {
  let response;
  try { response=await fetchImpl(`${AI_HORDE_BASE}/status/models?type=image`,{headers:{accept:'application/json','Client-Agent':CLIENT_AGENT}}); }
  catch { return {ok:false,status:0,provider:'ai_horde',error:'provider_unreachable',models:[]}; }
  const body=await readJson(response);
  if (!response.ok || !Array.isArray(body)) return {ok:false,status:Number(response.status||0),provider:'ai_horde',error:'provider_rejected',models:[]};
  return {ok:true,status:Number(response.status||200),provider:'ai_horde',models:body.map(x=>({name:String(x?.name||''),workerCount:Number(x?.count||0),performance:Number(x?.performance||0),eta:Number(x?.eta||0),queued:Number(x?.queued||0)})).filter(x=>x.name)};
}
```

`provider-registry.js` wraps existing AI Horde auth/submit/check/status/cancel so orchestration code has no provider-specific credential branches.

- [ ] **Step 4: Run GREEN + V1 regression**

```bash
node test-image-render-v2-provider.mjs
npm run test:image-render
```

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/image-render/ai-horde.js cloudflare-worker/image-render/provider-registry.js cloudflare-worker/test-image-render-v2-provider.mjs
git commit -m "feat(image): add live free image provider registry"
```

---

### Task 3: Adaptive free-model router

**Files:**
- Create: `cloudflare-worker/image-render/model-router.js`
- Test: `cloudflare-worker/test-image-render-v2-model-router.mjs`

**Interfaces:**
- Produces: `rankImageModels({models,preferredModels,history,limit}) -> ranked[]`.

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict';
import {rankImageModels} from './image-render/model-router.js';
const ranked=rankImageModels({models:[{name:'Fast',workerCount:8,performance:20,eta:1,queued:0},{name:'Preferred',workerCount:2,performance:15,eta:8,queued:1},{name:'Failing',workerCount:8,performance:30,eta:0,queued:0}],preferredModels:['Preferred'],history:{Failing:{failures:5,successes:0}},limit:3});
assert.equal(ranked[0].name,'Preferred');
assert.ok(ranked.find(x=>x.name==='Failing').score<ranked.find(x=>x.name==='Fast').score);
console.log('IMAGE_RENDER_V2_MODEL_ROUTER_TEST=PASS');
```

- [ ] **Step 2: Run RED**

Run: `node test-image-render-v2-model-router.mjs`

- [ ] **Step 3: Implement deterministic scoring**

```js
const clamp=(v,min,max)=>Math.min(max,Math.max(min,Number(v)||0));
export function rankImageModels({models=[],preferredModels=[],history={},limit=4}={}) {
  const preferred=new Set(preferredModels.map(String));
  return models.map(model=>{
    const h=history?.[model.name]||{};let score=0;const reasons=[];
    if (preferred.has(model.name)) {score+=50;reasons.push('preferred_model');}
    score+=clamp(model.workerCount,0,8)*4;
    score+=clamp(model.performance,0,200)/10;
    score-=clamp(model.eta,0,300)/10;
    score-=clamp(model.queued,0,50);
    score+=Math.min(Number(h.successes||0),5)*3;
    score-=Math.min(Number(h.failures||0),5)*12;
    if (Number(model.workerCount||0)<=0) score-=1000;
    return {...model,score,reasons};
  }).sort((a,b)=>b.score-a.score||a.name.localeCompare(b.name)).slice(0,Math.max(1,Math.min(8,Number(limit)||4)));
}
```

Do not infer model family/baseline from arbitrary model-name text.

- [ ] **Step 4: Run GREEN**

Run: `node test-image-render-v2-model-router.mjs`

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/image-render/model-router.js cloudflare-worker/test-image-render-v2-model-router.mjs
git commit -m "feat(image): rank live free render models"
```

---

### Task 4: Quality policy and STRICT fail-safe

**Files:**
- Create: `cloudflare-worker/image-render/quality-policy.js`
- Test: `cloudflare-worker/test-image-render-v2-quality.mjs`

**Interfaces:**
- Produces: `evaluateImageQuality({scene,generation,qualityMode,visualCritic})`.
- Decisions: `PASS`, `PASS_UNVERIFIED`, `RETRY_PROMPT`, `RETRY_MODEL`, `RETRY_SEED`, `FAIL_TERMINAL`.

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict';
import {evaluateImageQuality} from './image-render/quality-policy.js';
const scene={scene_id:'01',compiled_prompt:'one Max',expected_subject_count:1};
const good={imageUrl:'https://example.invalid/a.webp',censored:false,model:'m',state:'ok'};
assert.equal((await evaluateImageQuality({scene,generation:good,qualityMode:'STRICT'})).decision,'PASS_UNVERIFIED');
assert.equal((await evaluateImageQuality({scene,generation:{...good,censored:true},qualityMode:'STRICT'})).decision,'RETRY_MODEL');
assert.equal((await evaluateImageQuality({scene,generation:good,qualityMode:'STRICT',visualCritic:async()=>({ok:true,pass:false,confidence:.97,reasons:['duplicate_subject']})})).decision,'RETRY_PROMPT');
assert.equal((await evaluateImageQuality({scene,generation:good,qualityMode:'STRICT',visualCritic:async()=>({ok:true,pass:true,confidence:.94,reasons:[]})})).decision,'PASS');
console.log('IMAGE_RENDER_V2_QUALITY_TEST=PASS');
```

- [ ] **Step 2: Run RED**

Run: `node test-image-render-v2-quality.mjs`

- [ ] **Step 3: Implement structural + optional visual policy**

Reject non-HTTPS URLs, censored output, missing model/state, and malformed generation records. STRICT without a usable `visualCritic` returns `PASS_UNVERIFIED` and scene state `complete_unverified`.

```js
const PROMPT_REPAIR_REASONS=new Set(['duplicate_subject','wrong_subject_count','wardrobe_mismatch','identity_mismatch','background_mismatch','camera_mismatch','text_or_watermark']);
const MODEL_RETRY_REASONS=new Set(['severe_anatomy','deformation','provider_censored','model_mismatch']);
```

- [ ] **Step 4: Run GREEN**

Run: `node test-image-render-v2-quality.mjs`

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/image-render/quality-policy.js cloudflare-worker/test-image-render-v2-quality.mjs
git commit -m "feat(image): add strict bounded quality policy"
```

---

### Task 5: Pure batch state machine and retry engine

**Files:**
- Create: `cloudflare-worker/image-render/batch-engine.js`
- Test: `cloudflare-worker/test-image-render-v2-batch-engine.mjs`

**Interfaces:**
- `createBatchState(manifest)`
- `nextSubmissionSceneIds(state)`
- `markSceneSubmitted(state,input)`
- `markSceneProviderResult(state,input)`
- `applySceneQualityDecision(state,input)`
- `cancelBatchState(state)`
- `resetFailedScenesForRetry(state,sceneIds)`
- `summarizeBatch(state)`

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict';
import {createBatchState,nextSubmissionSceneIds,markSceneSubmitted,applySceneQualityDecision,summarizeBatch} from './image-render/batch-engine.js';
const manifest={batch_id:'b1',scheduler_config:{concurrency:4},retry_policy:{maxAttempts:3},scenes:Array.from({length:20},(_,i)=>({scene_id:String(i+1),status:'queued',attempts:[]}))};
let state=createBatchState(manifest);
assert.equal(nextSubmissionSceneIds(state).length,4);
for (const id of nextSubmissionSceneIds(state)) state=markSceneSubmitted(state,{sceneId:id,provider:'ai_horde',model:'M',jobId:`job-${id}`,seed:id,submittedAt:'t1'});
assert.equal(nextSubmissionSceneIds(state).length,0);
state=applySceneQualityDecision(state,{sceneId:'1',quality:{decision:'RETRY_PROMPT',reasons:['duplicate_subject']},completedAt:'t2'});
assert.equal(state.scenes.find(x=>x.scene_id==='1').status,'retry_pending');
assert.equal(nextSubmissionSceneIds(state).length,1);
assert.equal(summarizeBatch(state).activeScenes,3);
console.log('IMAGE_RENDER_V2_BATCH_ENGINE_TEST=PASS');
```

Add a second test that drives one scene through three failed attempts and proves it becomes `failed_quality` while another scene reaches `complete`.

- [ ] **Step 2: Run RED**

Run: `node test-image-render-v2-batch-engine.mjs`

- [ ] **Step 3: Implement state transitions**

Active states are `submitting`, `provider_wait`, `provider_processing`, `qa_pending`. Free slots are:

```js
const free=Math.max(0,Math.min(8,state.scheduler.concurrency)-state.scenes.filter(s=>active.has(s.status)).length);
```

Retries increment attempts and stop at `state.retry.maxAttempts`. One failed scene never forces the whole batch to `failed` while other scenes remain runnable.

- [ ] **Step 4: Run GREEN**

Run: `node test-image-render-v2-batch-engine.mjs`

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/image-render/batch-engine.js cloudflare-worker/test-image-render-v2-batch-engine.mjs
git commit -m "feat(image): add V2 batch state machine"
```

---

### Task 6: Durable Object coordinator, alarms, resume, cancellation

**Files:**
- Create: `cloudflare-worker/image-render/batch-state.js`
- Create: `cloudflare-worker/image-render/batch-client.js`
- Test: `cloudflare-worker/test-image-render-v2-batch-state.mjs`

**Interfaces:**
- Durable Object: `ImageRenderBatchState`.
- Test factory: `createImageRenderBatchClass({registryFactory,qualityEvaluator,now})`.
- Client: `createImageBatch`, `getImageBatchStatus`, `cancelImageBatch`, `retryImageBatchScenes`.

- [ ] **Step 1: Write memory-storage lifecycle tests**

```js
class MemoryStorage {
  constructor(){this.map=new Map();this.alarm=null;}
  async get(k){return this.map.get(k);}
  async put(k,v){this.map.set(k,structuredClone(v));}
  async delete(k){this.map.delete(k);}
  async setAlarm(v){this.alarm=v;}
  async getAlarm(){return this.alarm;}
}
```

Use a fake provider that returns deterministic job IDs/status. Create 20 scenes, call `/create`, invoke `alarm()`, assert progress, reconstruct the Durable Object with the same storage, invoke `alarm()` again, and assert already completed scene IDs were not resubmitted. Add cancellation and selected-scene retry tests.

- [ ] **Step 2: Run RED**

Run: `node test-image-render-v2-batch-state.mjs`

- [ ] **Step 3: Implement Durable Object routes**

Persistent key: `image-render-batch-state-v2`.

Internal routes:
- `POST /create`
- `GET /status`
- `DELETE /cancel`
- `POST /retry`
- `POST /tick` for deterministic tests/internal lifecycle only

`alarm()` calls the same private cycle used by `/tick`. Cycle order: poll active jobs -> fetch completed generation -> quality decision -> rank models if submissions are needed -> submit up to free slots -> persist once -> schedule next alarm if non-terminal.

Bound alarm delay:

```js
const nextDelayMs=Math.min(30_000,Math.max(2_000,Number(nearestProviderWaitSeconds||2)*1000));
await this.storage.setAlarm(this.now()+nextDelayMs);
```

- [ ] **Step 4: Implement client binding**

`batch-client.js` must use `env.IMAGE_RENDER_BATCH.idFromName(batchId)` and `env.IMAGE_RENDER_BATCH.get(id)`. Missing binding fails with `image_render_batch_binding_unavailable`; there is no `TRADING_STATE` fallback.

- [ ] **Step 5: Run GREEN**

```bash
node test-image-render-v2-batch-engine.mjs
node test-image-render-v2-batch-state.mjs
```

- [ ] **Step 6: Commit**

```bash
git add cloudflare-worker/image-render/batch-state.js cloudflare-worker/image-render/batch-client.js cloudflare-worker/test-image-render-v2-batch-state.mjs
git commit -m "feat(image): persist V2 batches in Durable Objects"
```

---

### Task 7: V2 HTTP endpoints while preserving V1

**Files:**
- Modify: `cloudflare-worker/image-render-handler.js`
- Test: `cloudflare-worker/test-image-render-v2-handler.mjs`

**Interfaces:**
- `POST /brain/image/batch`
- `GET /brain/image/batch/status?id=<batch_id>`
- `DELETE /brain/image/batch?id=<batch_id>`
- `POST /brain/image/retry`
- `GET /brain/image/models`

- [ ] **Step 1: Write failing endpoint tests**

Prove unauthenticated access is `401`, missing data class is `400 data_class_required`, non-PUBLIC is `403`, reference image is `409`, 101 scenes is `413`, and a valid 20-scene request returns `202`, `mode:'FREE_ONLY'`, `paidFallback:false`, `sceneCount:20`, and a server-generated `batchId`.

- [ ] **Step 2: Run RED and confirm V1 remains green**

```bash
node test-image-render-v2-handler.mjs
npm run test:image-render
```

- [ ] **Step 3: Implement routes**

Batch IDs are generated server-side:

```js
const batchId=`img-${crypto.randomUUID()}`;
```

`GET /brain/image/models` only lists/ranks model metadata and never submits an image.

- [ ] **Step 4: Extend health without deleting V1 fields**

```js
batch:{enabled:Boolean(env?.IMAGE_RENDER_BATCH),maxScenes:100,defaultConcurrency:4,maxConcurrency:8,maxAttemptsPerScene:3},
quality:{strictVisualVerificationRequired:true,metadataOnlyMayReportVerified:false},
```

- [ ] **Step 5: Run GREEN + V1 regression**

```bash
node test-image-render-v2-handler.mjs
npm run test:image-render
```

- [ ] **Step 6: Commit**

```bash
git add cloudflare-worker/image-render-handler.js cloudflare-worker/test-image-render-v2-handler.mjs
git commit -m "feat(image): expose V2 batch render API"
```

---

### Task 8: Export/report contract

**Files:**
- Create: `cloudflare-worker/image-render/export-contract.js`
- Test: `cloudflare-worker/test-image-render-v2-export.mjs`
- Modify: `cloudflare-worker/image-render-handler.js`

**Interfaces:**
- `buildRenderReport(state)`
- `buildExportManifest(state)`

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict';
import {buildRenderReport,buildExportManifest} from './image-render/export-contract.js';
const state={batch_id:'b1',status:'complete_with_failures',scenes:[{scene_id:'01',status:'complete_unverified',attempts:[{model:'A',seed:'1',generation:{imageUrl:'https://example.invalid/1.webp'},qa:{qaLevel:'STRUCTURAL'}}]},{scene_id:'02',status:'failed_quality',attempts:[{model:'B',seed:'2',qa:{reasons:['deformation']}}]}]};
assert.equal(buildRenderReport(state).monetaryImageProviderCost,0);
assert.deepEqual(buildRenderReport(state).failedScenes,['02']);
assert.deepEqual(buildExportManifest(state).assets,[{sceneId:'01',fileName:'Scene_01.webp',url:'https://example.invalid/1.webp'}]);
console.log('IMAGE_RENDER_V2_EXPORT_TEST=PASS');
```

- [ ] **Step 2: Run RED**

Run: `node test-image-render-v2-export.mjs`

- [ ] **Step 3: Implement metadata-only export**

Accept only `https:` generation URLs. Report includes total/passed/failed scenes, model usage, seeds, attempts, QA, failure reasons, `freeOnly:true`, `paidFallback:false`, and `monetaryImageProviderCost:0`. Do not fetch/store binary assets in Worker storage.

- [ ] **Step 4: Expose export metadata from batch status**

Only include `exportManifest` when at least one completed scene has a validated generation URL.

- [ ] **Step 5: Run GREEN**

```bash
node test-image-render-v2-export.mjs
node test-image-render-v2-handler.mjs
```

- [ ] **Step 6: Commit**

```bash
git add cloudflare-worker/image-render/export-contract.js cloudflare-worker/test-image-render-v2-export.mjs cloudflare-worker/image-render-handler.js
git commit -m "feat(image): add batch render export contract"
```

---

### Task 9: Durable Object deployment wiring

**Files:**
- Modify: `cloudflare-worker/index.js`
- Modify: `cloudflare-worker/prepare-wrangler.mjs`
- Modify: `cloudflare-worker/wrangler.example.jsonc`
- Modify: `cloudflare-worker/test-deploy-safety.mjs`

**Interfaces:**
- Export `ImageRenderBatchState`.
- Binding `IMAGE_RENDER_BATCH` -> `ImageRenderBatchState`.
- Migration `image-render-batch-v1` with `new_sqlite_classes:['ImageRenderBatchState']`.

- [ ] **Step 1: Add failing deploy-safety assertions**

```js
assert.match(wranglerPrep,/IMAGE_RENDER_BATCH/);
assert.match(wranglerPrep,/ImageRenderBatchState/);
assert.match(wranglerPrep,/image-render-batch-v1/);
assert.match(wranglerExample,/IMAGE_RENDER_BATCH/);
assert.match(fs.readFileSync('index.js','utf8'),/export \{ImageRenderBatchState\} from '\.\/image-render\/batch-state\.js'/);
assert.doesNotMatch(fs.readFileSync('image-render/batch-state.js','utf8'),/TRADING_STATE/);
```

- [ ] **Step 2: Run RED**

Run: `node test-deploy-safety.mjs`

- [ ] **Step 3: Wire Worker config**

Add to `index.js`:

```js
export {ImageRenderBatchState} from './image-render/batch-state.js';
```

Add binding and migration to both generated config source and example:

```js
{name:'IMAGE_RENDER_BATCH',class_name:'ImageRenderBatchState'}
{tag:'image-render-batch-v1',new_sqlite_classes:['ImageRenderBatchState']}
```

- [ ] **Step 4: Run GREEN + image regression**

```bash
node test-deploy-safety.mjs
npm run test:image-render
node test-image-render-v2-batch-state.mjs
```

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/index.js cloudflare-worker/prepare-wrangler.mjs cloudflare-worker/wrangler.example.jsonc cloudflare-worker/test-deploy-safety.mjs
git commit -m "feat(image): wire render batch Durable Object"
```

---

### Task 10: Brain policy and creative canonical bindings

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/legion/agents.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml`

- [ ] **Step 1: Promote image policy to V2**

Set `version: 2` and add:

```yaml
batch:
  enabled: true
  max_scenes: 100
  default_concurrency: 4
  max_concurrency: 8
  max_attempts_per_scene: 3
  state_binding: IMAGE_RENDER_BATCH
  state_class: ImageRenderBatchState
  trading_state_forbidden: true
quality:
  modes: [STRUCTURAL, STRICT]
  strict_requires_visual_verification_for_verified_label: true
  visual_critic_unavailable_state: complete_unverified
runtime:
  batch_submit_path: /brain/image/batch
  batch_status_path: /brain/image/batch/status
  models_path: /brain/image/models
  retry_path: /brain/image/retry
```

Preserve PUBLIC-only privacy, reference-image disabled, `paid_fallback:false`, and `auto_purchase:false`.

- [ ] **Step 2: Update `image_render_agent.runtime`**

Add V2 paths and exact limits (`100`, `4`, `8`, `3`) without changing authority flags.

- [ ] **Step 3: Bind execution to existing canonical creative modules**

Add:

```yaml
image_execution_bindings:
  prompt_compiler_owner: visual_prompt_compiler
  consistency_owner: continuity_engine
  quality_owner: render_quality_critic
  execution_agent: image_render_agent
  duplicate_creative_reasoning_forbidden: true
  preserve_user_constraints: true
```

- [ ] **Step 4: Run policy validators**

```bash
python3 AI_SKILL_LIBRARY/v4/tools/validate_legion.py
python3 AI_SKILL_LIBRARY/v4/tools/validate_consolidation.py
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml AI_SKILL_LIBRARY/v4/legion/agents.yaml AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml
git commit -m "feat(brain): register Image Render Agent V2"
```

---

### Task 11: Test script integration, release 4.13.0, regression, and production smoke

**Files:**
- Modify: `cloudflare-worker/package.json`
- Generated by release tool: `AI_SKILL_LIBRARY/v4/releases/4.13.0/manifest.yaml`
- Generated by release tool: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Generated by release tool: `AI_SKILL_LIBRARY/v4/releases/history.yaml`
- Modify `.github/workflows/deploy-skill-mandatory-fast-gateway.yml` only if V2 smoke assertions cannot be expressed with existing post-deploy hooks.

- [ ] **Step 1: Add V2 test script**

```json
"test:image-render-v2": "node test-image-render-v2-contracts.mjs && node test-image-render-v2-provider.mjs && node test-image-render-v2-model-router.mjs && node test-image-render-v2-quality.mjs && node test-image-render-v2-batch-engine.mjs && node test-image-render-v2-batch-state.mjs && node test-image-render-v2-handler.mjs && node test-image-render-v2-export.mjs"
```

Append `&& npm run test:image-render-v2` immediately after `npm run test:image-render` inside `scripts.check`.

- [ ] **Step 2: Run focused image regression**

```bash
cd cloudflare-worker
npm run test:image-render
npm run test:image-render-v2
```

Expected: exit 0.

- [ ] **Step 3: Run full Worker regression before release promotion**

```bash
npm run check
```

Expected: exit 0.

- [ ] **Step 4: Run Brain validators that do not require a fresh release pointer**

From repository root:

```bash
python3 AI_SKILL_LIBRARY/v4/tools/validate_legion.py
python3 AI_SKILL_LIBRARY/v4/tools/validate_consolidation.py
```

Expected: exit 0.

Do **not** run `ci_validate.py` against the old 4.12.0 pointer after changing release-tracked policy files; that validator is allowed to reject stale hashes. Build the new release first.

- [ ] **Step 5: Build and verify release 4.13.0**

```bash
python3 AI_SKILL_LIBRARY/v4/tools/release.py build --version 4.13.0 --source image_render_agent_v2 --class feature --validated --known-good
python3 AI_SKILL_LIBRARY/v4/tools/release.py verify
python3 AI_SKILL_LIBRARY/v4/tools/release.py check
```

Expected:

```text
RELEASE_BUILD=PASS version=4.13.0
Release verification summary: 0 error(s), 0 warning(s)
RELEASE_CHECK=PASS version=4.13.0
```

- [ ] **Step 6: Run canonical CI validation against the new pointer**

```bash
python3 AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
```

Expected: exit 0.

- [ ] **Step 7: Re-run full Worker regression**

```bash
cd cloudflare-worker
npm run check
```

Expected: exit 0.

- [ ] **Step 8: Commit release/test integration**

```bash
git add cloudflare-worker/package.json AI_SKILL_LIBRARY/v4/releases/4.13.0/manifest.yaml AI_SKILL_LIBRARY/v4/releases/current.json AI_SKILL_LIBRARY/v4/releases/history.yaml
git commit -m "release: promote Image Render Agent V2"
```

- [ ] **Step 9: Run Wrangler dry-run**

```bash
cd cloudflare-worker
npm run deploy
```

Expected: dry-run succeeds; generated config contains `IMAGE_RENDER_BATCH`/`ImageRenderBatchState`, keeps `keep_vars:true`, and preserves the single Model Mesh health cron.

- [ ] **Step 10: Production smoke only after gated exact-main deployment**

Run authenticated probes in this order using PUBLIC test prompts only:

```text
1. GET /brain/image/health
   Require mode=FREE_ONLY, paidFallback=false, batch.enabled=true, maxScenes=100.
2. GET /brain/image/models
   Require HTTP 200; when AI Horde is available, at least one normalized live model.
3. POST /brain/image/render with one small PUBLIC prompt
   Require existing V1 202 response contract.
4. POST /brain/image/batch with two small PUBLIC scenes and qualityMode=STRUCTURAL
   Require 202, one batchId, sceneCount=2.
5. Poll /brain/image/batch/status?id=<batchId>
   Require terminal state; submitted scenes record provider/model/job/attempt metadata; no paid route.
6. Create a separate small batch and DELETE /brain/image/batch?id=<batchId>
   Require cancelled state and no later submissions.
```

No user reference asset is used for smoke tests.

- [ ] **Step 11: Record fresh verification evidence**

PR/deployment evidence must include exact outputs for:

```text
npm run test:image-render
npm run test:image-render-v2
npm run check
release.py verify
release.py check
ci_validate.py
Wrangler dry-run
production health/model/single/batch/cancel smoke gates
```

Any failed core gate blocks runtime promotion.

---

## Self-Review Checklist

- Spec coverage: contract, 20–100 scenes, 4–8 concurrency, durable state, live model ranking, consistency locks, QA/retry, status/cancel/retry API, export metadata, backward compatibility, FREE_ONLY/privacy, release and smoke gates are all assigned to tasks above.
- Placeholder scan: no `TODO`, `TBD`, or “similar to Task N” instructions are permitted in this plan.
- Type consistency: downstream tasks use the exact interfaces `validateImageBatchRequest`, `createRenderManifest`, `compileScenePrompt`, `createImageProviderRegistry`, `rankImageModels`, `evaluateImageQuality`, `ImageRenderBatchState`, `createImageBatch`, `getImageBatchStatus`, `cancelImageBatch`, and `retryImageBatchScenes`.
- Visual QA boundary: this plan does not fabricate a multimodal critic. STRICT mode exposes `complete_unverified` until an approved FREE_ONLY visual critic is actually wired through the `visualCritic` interface.
- Release order: runtime/policy tests -> release build -> release verification -> `ci_validate.py` -> full regression -> dry-run -> gated deployment -> PUBLIC smoke.

## Execution Order

Tasks 1–4 create independent pure/provider foundations. Tasks 5–9 add durable orchestration and API/deployment wiring. Task 10 updates Brain policy only after runtime contracts are testable. Task 11 alone advances the stable release pointer and performs production smoke.

Every task ends in an independently reviewable commit. Production deployment is not part of any earlier task.
