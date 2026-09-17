# Persistent Brain Entry / Always-On Chat Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make project continuity production-persistent so any authenticated connected ChatGPT/Claude/Gemini session can bootstrap the latest project handoff, resume canonical subsystem jobs, and update state without relying on the previous transcript.

**Architecture:** Extend the existing Universal Brain control plane with one `BrainProjectState` Durable Object per normalized `project_id`. Public bootstrap/project APIs authenticate through `universal-auth.js`; writes use optimistic concurrency (`expected_version`) and only store bounded continuity metadata plus canonical subsystem job pointers. Image execution remains on `/brain/image/v3/*`, and trading authority is unchanged.

**Tech Stack:** Cloudflare Workers JavaScript/ESM, Durable Objects, Node `assert` contract tests, existing Universal Fabric adapter compiler, Wrangler 4.124.0, GitHub Actions exact-main deployment/canary.

**Spec:** `docs/superpowers/specs/2026-09-17-persistent-brain-entry-always-on-chat-bridge-design.md`

## Global Constraints

- Backend Brain state, not chat history, is the source of truth for project continuity.
- `BrainProjectState` is state only: `routingAuthority=false`, `reasoningAuthority=false`, and it cannot widen trading authority.
- Do not store complete transcripts, credentials, raw Authorization values, private keys, provider tokens, or binary assets.
- Keep project state isolated by normalized `project_id`; never merge projects automatically.
- Writes require optimistic concurrency; stale `expected_version` returns HTTP 409 and never overwrites the newer snapshot.
- Image execution stays on `/brain/image/v3/*`; project state stores only job references.
- Preserve Image FREE_ONLY / paid-fallback=false behavior and all existing privacy/reference-safe rules.
- Do not introduce a new GitHub workflow; extend the existing Universal Fabric and exact-main gates.
- Production capability claims must remain evidence-based; route descriptors are not runtime-availability claims.
- No production code before its failing test (RED → GREEN → refactor).

---

### Task 1: Versioned project-state Durable Object

**Files:**
- Create: `cloudflare-worker/brain-project-state.js`
- Create: `cloudflare-worker/test-brain-project-state.mjs`

**Interfaces:**
- Produces: `normalizeProjectId(value) -> string`
- Produces: `createBrainProjectStateClass({now?}) -> DurableObject class`
- Produces: `BrainProjectState` default class export binding target.
- Internal DO routes: `GET /state`, `PUT /state`.

- [ ] **Step 1: Write the failing contract test**

Create `test-brain-project-state.mjs` with an in-memory `state.storage` implementation and assertions for:

```js
const ProjectState=createBrainProjectStateClass({now:()=>Date.parse('2026-09-17T04:00:00Z')});
const object=new ProjectState({storage:new MemoryStorage()},{});

let res=await object.fetch(new Request('https://internal/state'));
assert.equal(res.status,404);

res=await object.fetch(new Request('https://internal/state',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({
  project_id:'image-agent',expected_version:0,active_phase:'production-operation',status:'active',
  latest_handoff:{summary:'Image V3 is canonical',blockers:[],next_actions:['render scene 1'],refs:['spec:scene-1']},
  job_refs:[{subsystem:'image-v3',job_id:'logical-1',state:'running'}],runtime_revision:'a'.repeat(40),updated_by:'chatgpt'
})}));
assert.equal(res.status,200);
const created=await res.json();
assert.equal(created.state.version,1);
assert.equal(created.state.project_id,'image-agent');
assert.equal(created.state.updated_by,'chatgpt');

const stale=await object.fetch(new Request('https://internal/state',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({
  project_id:'image-agent',expected_version:0,active_phase:'wrong',status:'active',latest_handoff:{summary:'stale',blockers:[],next_actions:[],refs:[]},job_refs:[],runtime_revision:'b'.repeat(40),updated_by:'claude'
})}));
assert.equal(stale.status,409);
assert.equal((await stale.json()).currentVersion,1);

const fetched=await (await object.fetch(new Request('https://internal/state'))).json();
assert.equal(fetched.state.active_phase,'production-operation');
```

Also assert invalid traversal IDs, oversized lists/strings, unknown fields, raw `Bearer ...`/private-key material, and binary-like data are rejected with 400.

- [ ] **Step 2: Run RED**

Run in `cloudflare-worker/`:

```bash
node test-brain-project-state.mjs
```

Expected: FAIL because `brain-project-state.js` does not exist.

- [ ] **Step 3: Implement the minimal state contract**

Implement bounded schema validation with exact allowed fields. Normalize project IDs to lowercase slug form (`[a-z0-9][a-z0-9._-]{0,79}` after trimming/lowercasing); reject traversal/control characters instead of silently rewriting them. Store one snapshot under a constant storage key.

Required persisted shape:

```js
{
  project_id,
  schema_version:1,
  version:currentVersion+1,
  active_phase,
  status,
  latest_handoff:{summary,blockers,next_actions,refs},
  job_refs:[{subsystem,job_id,state}],
  runtime_revision,
  updated_at:new Date(now()).toISOString(),
  updated_by
}
```

Use conservative bounds: summary <= 4000 chars; phase/status/updated_by <= 160; each blocker/action/ref <= 500; each list <= 32; job refs <= 32 with each field <= 160. Reject unknown top-level/nested fields. Reject obvious credential material (`Authorization:`, `Bearer <value>`, private-key PEM markers, `sk-...`) before persistence.

`PUT /state` must compare `expected_version` against the current stored version (0 when absent) and return:

```js
{ok:false,error:'project_state_conflict',currentVersion}
```

with 409 on mismatch.

- [ ] **Step 4: Run GREEN**

```bash
node test-brain-project-state.mjs
```

Expected: `BRAIN_PROJECT_STATE_TESTS=PASS`.

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/brain-project-state.js cloudflare-worker/test-brain-project-state.mjs
git commit -m "feat(brain): add versioned project continuity state"
```

---

### Task 2: Authenticated bootstrap and project-state API

**Files:**
- Create: `cloudflare-worker/project-continuity-handler.js`
- Create: `cloudflare-worker/project-continuity-active.js`
- Create: `cloudflare-worker/test-project-continuity-handler.mjs`
- Modify: `cloudflare-worker/universal-auth.js`
- Modify: `cloudflare-worker/test-universal-auth.mjs`
- Modify: `AI_SKILL_LIBRARY/v4/adapters/registry.yaml`

**Interfaces:**
- Consumes: `normalizeProjectId()` and `env.BRAIN_PROJECT_STATE`.
- Produces: `createProjectContinuityHandler({snapshot})`.
- Produces: `handleProjectContinuity` active handler.
- Public routes: `GET /brain/bootstrap?project_id=...`, `GET /brain/project/state?project_id=...`, `PUT /brain/project/state`.

- [ ] **Step 1: Extend auth tests first**

Add failing assertions:

```js
assert.equal(requiredScopeForPath('/brain/bootstrap','GET'),'brain.bootstrap');
assert.equal(requiredScopeForPath('/brain/project/state','GET'),'brain.read_project_state');
assert.equal(requiredScopeForPath('/brain/project/state','PUT'),'brain.write_project_state');
for(const id of ['chatgpt','claude','gemini']){
  const token=`${id}-token`;
  for(const scope of ['brain.bootstrap','brain.read_project_state','brain.write_project_state']){
    const out=await authenticateAdapter(req(id,token,'/brain/bootstrap','GET'),env,scope);
    assert.equal(out.ok,true);
  }
}
```

Update canonical adapter registry rows for ChatGPT/Claude/Gemini with those three scopes; do not add them to Evergreen.

- [ ] **Step 2: Write failing bootstrap/continuity handler test**

Use a fake Durable Object namespace whose `idFromName(projectId)` records the normalized ID and whose stub delegates to isolated in-memory `BrainProjectState` instances. Assert:

- ChatGPT PUT initializes `image-agent` at version 1.
- Fresh Claude GET `/brain/bootstrap?project_id=image-agent` receives exactly that handoff/version/job ref without prior transcript state.
- Bootstrap response includes `sourceSha`, `releaseId`, `clientId`, canonical Image V3 route descriptors, `runtimeAvailability:'unknown_until_called'`, and `nextAction` equal only to stored `next_actions[0]`.
- A second project has independent version/state.
- Missing project GET state returns 404; missing project bootstrap returns 200 with `project.initialized=false` and no invented next action.
- Auth token/header values do not appear in response or stored state.
- Missing DO binding returns 503 `project_state_unavailable`.

- [ ] **Step 3: Run RED**

```bash
npm run prepare:universal-fabric
node test-universal-auth.mjs
node test-project-continuity-handler.mjs
```

Expected: auth-scope and missing-handler failures.

- [ ] **Step 4: Implement handler + active wrapper**

`project-continuity-handler.js` must:

```js
export function createProjectContinuityHandler({snapshot}={}) { /* ... */ }
```

Authenticate every supported route through `authenticateAdapter()` and `requiredScopeForPath()`. Resolve exactly one DO by `env.BRAIN_PROJECT_STATE.idFromName(normalizedProjectId)`. Never fall back to `TRADING_STATE` or KV.

Bootstrap response contract:

```js
{
  ok:true,
  brainAuthority:'GITHUB_BRAIN_V4',
  clientId,
  sourceSha:snapshot.source_sha,
  releaseId:snapshot.release_id||null,
  runtimeRevision:String(env.RUNTIME_REVISION||snapshot.source_sha),
  project:{initialized:boolean,state:null|snapshot},
  jobRefs:[],
  nextAction:null|string,
  capabilities:{
    projectContinuity:{versioned:true,conflictSafe:true},
    imageV3:{canonical:true,runtimeAvailability:'unknown_until_called'}
  },
  routes:{
    universalRoute:'/brain/universal/route',
    imageJobs:'/brain/image/v3/jobs',
    imageStatus:'/brain/image/v3/jobs/status',
    imageRetry:'/brain/image/v3/jobs/retry',
    imageAssets:'/brain/image/v3/jobs/assets'
  }
}
```

Do not claim Image V3 runtime availability from route existence.

- [ ] **Step 5: Run GREEN**

```bash
npm run prepare:universal-fabric
node test-universal-auth.mjs
node test-project-continuity-handler.mjs
```

Expected: both pass.

- [ ] **Step 6: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/adapters/registry.yaml cloudflare-worker/universal-auth.js cloudflare-worker/test-universal-auth.mjs cloudflare-worker/project-continuity-handler.js cloudflare-worker/project-continuity-active.js cloudflare-worker/test-project-continuity-handler.mjs
git commit -m "feat(brain): add authenticated bootstrap continuity API"
```

---

### Task 3: Worker routing and Durable Object deployment wiring

**Files:**
- Modify: `cloudflare-worker/index.js`
- Modify: `cloudflare-worker/prepare-wrangler.mjs`
- Modify: `cloudflare-worker/wrangler.example.jsonc`
- Create: `cloudflare-worker/test-project-continuity-deploy-wiring.mjs`
- Modify: `cloudflare-worker/package.json`

**Interfaces:**
- Consumes: `handleProjectContinuity`.
- Exports: `BrainProjectState` as the class named by Wrangler binding.
- Adds binding `BRAIN_PROJECT_STATE -> BrainProjectState` and migration `brain-project-state-v1`.

- [ ] **Step 1: Write failing deploy-wiring test**

Assertions must require, in both `prepare-wrangler.mjs` and `wrangler.example.jsonc`:

```js
assert.match(source,/BRAIN_PROJECT_STATE/);
assert.match(source,/BrainProjectState/);
assert.match(source,/brain-project-state-v1/);
```

Also require:

```js
assert.match(index,/export \{BrainProjectState\} from '\.\/brain-project-state\.js';/);
assert.match(index,/handleProjectContinuity/);
assert.doesNotMatch(projectStateSource,/TRADING_STATE|BRAIN_STATE/);
```

and ensure `project-continuity-handler.js` appears before generic Skill Gateway handling in `index.js`.

- [ ] **Step 2: Run RED**

```bash
node test-project-continuity-deploy-wiring.mjs
```

Expected: FAIL for missing binding/export/router.

- [ ] **Step 3: Wire runtime minimally**

In `index.js`, call continuity after Universal Entry and before memory/Skill Gateway generic routes:

```js
const continuity=await handleProjectContinuity(req,env,ctx);
if(continuity)return continuity;
```

Add the Durable Object binding/migration to generated Wrangler config and the checked-in example. Do not alter existing cron, trading switches, AI binding, or image bindings.

Add new project-state tests to `test:universal-fabric` so `npm run check` covers them.

- [ ] **Step 4: Run GREEN**

```bash
npm run test:universal-fabric
node test-project-continuity-deploy-wiring.mjs
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/index.js cloudflare-worker/prepare-wrangler.mjs cloudflare-worker/wrangler.example.jsonc cloudflare-worker/package.json cloudflare-worker/test-project-continuity-deploy-wiring.mjs
git commit -m "feat(brain): wire persistent project continuity runtime"
```

---

### Task 4: Production canary proves cross-session continuity

**Files:**
- Modify: `cloudflare-worker/validate-universal-canary.mjs`
- Modify: `cloudflare-worker/test-universal-canary.mjs`
- Modify: `cloudflare-worker/test-universal-deploy-safety.mjs`

**Interfaces:**
- Extends `runUniversalCanary()` to prove one writer + independent reader on a dedicated canary project ID.
- Uses ChatGPT token to write and Claude token to bootstrap/read.

- [ ] **Step 1: Write failing canary test**

Extend fake fetch to support `PUT /brain/project/state`, `GET /brain/bootstrap`, and cleanup-by-overwrite is not required. Use a unique canary project ID derived from source SHA, e.g. `canary-${expected.slice(0,12)}`.

Assert canary sequence:

```text
ChatGPT GET project state (404 allowed on first deploy)
ChatGPT PUT project state using current version or 0
Claude GET /brain/bootstrap?project_id=<same-id>
Claude sees exact new version, summary sentinel, and one image-v3 job ref
```

The summary sentinel must contain no credentials. Assert response sanitization still rejects token echo/private reasoning fields.

- [ ] **Step 2: Run RED**

```bash
node test-universal-canary.mjs
```

Expected: FAIL because production canary does not yet exercise continuity.

- [ ] **Step 3: Implement canary continuity proof**

Generalize `requestJson` to accept explicit method while preserving existing GET/POST behavior. Read current version first, PUT a bounded canary snapshot using `expected_version`, then bootstrap as Claude and verify exact version/sentinel/job pointer.

Return `projectContinuity:true` and emit:

```text
UNIVERSAL_PROJECT_CONTINUITY=PASS
```

Extend deploy-safety test to require that marker. Do not add a new workflow.

- [ ] **Step 4: Run GREEN**

```bash
node test-universal-canary.mjs
node test-universal-deploy-safety.mjs
```

Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/validate-universal-canary.mjs cloudflare-worker/test-universal-canary.mjs cloudflare-worker/test-universal-deploy-safety.mjs
git commit -m "test(brain): canary cross-session project continuity"
```

---

### Task 5: Full regression, exact-main rollout, and production acceptance

**Files:**
- No new production files expected.
- PR contains the approved spec + plan + Tasks 1-4.

**Interfaces:**
- Acceptance artifact is CI + exact-main deploy/canary evidence, not a verbal claim.

- [ ] **Step 1: Run full focused suites**

```bash
cd cloudflare-worker
npm run test:universal-fabric
npm run test:image-render
```

Expected: all green.

- [ ] **Step 2: Run full Worker gate**

```bash
npm run check
```

Expected: exit 0 with no trading-authority, secret-scan, image, model-mesh, or deploy-safety regression.

- [ ] **Step 3: Run repository Brain validation**

```bash
cd ..
python3 AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)" --skip-tests
```

Expected: PASS.

- [ ] **Step 4: Open PR and wait for exact-head CI**

PR title:

```text
feat(brain): persist project continuity across chat sessions
```

PR body must explicitly state:

- new Durable Object is project-state only, not routing/reasoning authority;
- no trading authority change;
- Image V3 remains canonical;
- no paid fallback or privacy widening;
- stale writes fail with 409;
- production canary proves ChatGPT-write → Claude-bootstrap continuity.

- [ ] **Step 5: Merge only after required CI is green**

Use normal merge policy. Record merged SHA.

- [ ] **Step 6: Verify exact-main deployment/canary**

Require existing exact-main Cloudflare deployment workflow to deploy the merged SHA and the Universal canary to emit all prior PASS markers plus:

```text
UNIVERSAL_PROJECT_CONTINUITY=PASS
```

If production canary fails, rely on the existing deterministic rollback; do not claim done.

- [ ] **Step 7: Production acceptance**

After exact-main is live, verify:

1. ChatGPT-authenticated request writes a dedicated acceptance project snapshot.
2. Separately authenticated Claude request bootstraps the same project without transcript context.
3. Version, handoff summary, and image job pointer match exactly.
4. A stale write returns 409.
5. A different project ID does not expose the acceptance project's state.

Only after these pass may the backend be described as end-to-end persistent. The final product boundary remains explicit: an arbitrary new ChatGPT conversation still requires the account/client Brain connector/action to be installed and authorized once; repository code cannot force-install that integration.

---

## Self-Review

- Spec coverage: project persistence, isolation, concurrency, auth scopes, bootstrap, Image V3 pointers, capability honesty, failure behavior, exact-main deploy/canary, and platform boundary are each mapped to a task.
- Placeholder scan: no TBD/TODO/"implement later" steps remain.
- Type consistency: `project_id`, `expected_version`, `latest_handoff`, `job_refs`, `runtime_revision`, `updated_by`, `version`, and the three new auth scopes use the same names across state, handler, tests, and canary.
- Authority check: no task changes trading execution authority, Image V3 authority, paid fallback, or provider privacy policy.
