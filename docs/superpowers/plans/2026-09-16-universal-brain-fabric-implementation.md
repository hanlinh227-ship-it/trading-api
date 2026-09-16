# Universal Brain Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the already-partially-implemented Universal Brain Fabric so ChatGPT, Claude, Gemini, and future adapters share one canonical GITHUB_BRAIN_V4 entry contract, scoped authentication, shared promoted memory/context, continuous capability assimilation, and exact-SHA production verification without weakening FAST, Model Mesh, Trading, or permission invariants.

**Architecture:** Extend the existing Cloudflare Skill Gateway rather than creating a second gateway. Reuse `routeSkillRequest`, the exact-SHA Skill Gateway snapshot, the existing `universal-*` modules, `memory-candidate.js`, Stable/Evergreen policies, and the sole production deploy workflow. GitHub remains canonical; Cloudflare runtime state is derived and portable; FAST remains zero-network on adapters that possess the verified HOT snapshot, while STANDARD/DEEP call the cloud Brain.

**Tech Stack:** Python 3.12, Node.js 22 ESM, Cloudflare Workers/Wrangler 4.124.0, Cloudflare KV-compatible state, existing V4 YAML/JSON policies, GitHub Actions, Node `assert`, Python `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-16-universal-brain-fabric-design.md`

## Global Constraints

- `GITHUB_BRAIN_V4` remains the sole routing/reasoning authority; adapters, providers, models, upstream repositories, and plugins never become parallel authorities.
- FAST routing uses the last verified exact-SHA HOT snapshot with zero synchronous GitHub/provider/network routing calls, zero durable-memory preload, and zero synchronous telemetry persistence.
- STANDARD/DEEP/high-impact flows use the cloud Brain; safe degraded fallback is allowed only for non-high-impact requests using the last verified Stable snapshot.
- Live/trading/deploy/credential/financial/destructive/permission-change requests may not bypass the Brain and may not use stale cached state as current truth.
- Zero-cost Model Mesh remains unchanged: no paid fallback, no auto-purchase, no trial-credit-as-free, family dedupe remains mandatory.
- Self-learning never widens credential, financial, wallet-signing, destructive-production, or production-write permissions.
- Candidate memory and candidate upstreams have zero routing/reasoning authority until promoted through canonical gates.
- Raw private chat, prompts, chain-of-thought, hidden reasoning, credentials, secrets, private keys, auth tokens, and private provider/tool payloads are never persisted.
- Trading project authority and live execution controls are unchanged.
- There is one production deploy workflow: `.github/workflows/deploy-skill-mandatory-fast-gateway.yml`.
- Stable completion requires tests, validators, release tooling, CI, merge, canary, production health/security checks, and `FINAL_EXACT_SHA_GATE=PASS`.

---

## Existing Baseline To Preserve

The branch already contains a meaningful first slice and must be treated as existing code, not rebuilt:

- `cloudflare-worker/index.js` invokes `handleUniversalEntry()` and `createMemoryCandidateHandler()` before the legacy Brain/research/trading handlers.
- `cloudflare-worker/universal-entry-handler.js` exposes `/brain/universal/route`, `/brain/universal/health`, and `/brain/universal/capabilities` and routes through the current `routeSkillRequest` snapshot.
- `cloudflare-worker/universal-entry-contract.js` already provides normalization, safety/profile floors, and `degradedDecision()`.
- `cloudflare-worker/universal-auth.js` already has independent ChatGPT/Claude/Gemini token bindings and scopes.
- `cloudflare-worker/universal-state.js` already exposes portable KV/metadata/vector/object/queue/lock interfaces and safely falls back to namespaced `TRADING_STATE`.
- `cloudflare-worker/universal-telemetry.js` already sanitizes route telemetry.
- `cloudflare-worker/memory-candidate.js` already accepts candidate-only writes and rejects sensitive material.
- Tests already exist for auth, universal entry contract/handler, state, telemetry, and memory candidate, but are not yet part of `npm run check`.
- `AI_SKILL_LIBRARY/v4/tools/skill_forge.py` and `upstream_watch.py` already implement the core low-risk promotion and upstream-diff primitives.

The implementation below is therefore **gap-driven completion**.

---

### Task 1: Make the existing Universal Fabric slice part of canonical CI

**Files:**
- Modify: `cloudflare-worker/package.json`
- Modify: `cloudflare-worker/validate-worker.mjs`
- Test: `cloudflare-worker/test-universal-auth.mjs`
- Test: `cloudflare-worker/test-universal-entry-contract.mjs`
- Test: `cloudflare-worker/test-universal-entry-handler.mjs`
- Test: `cloudflare-worker/test-universal-state.mjs`
- Test: `cloudflare-worker/test-universal-telemetry.mjs`
- Test: `cloudflare-worker/test-memory-candidate.mjs`

**Interfaces:**
- Consumes: existing Universal Fabric modules.
- Produces: `npm run check` fails on any Universal Fabric regression; `validate-worker.mjs` asserts the Universal Entry and memory routes are wired before generic/trading handlers.

- [ ] **Step 1: Add a failing package-check assertion test**

Add to `validate-worker.mjs` assertions equivalent to:

```js
for (const required of [
  "handleUniversalEntry(req,env,ctx)",
  "handleMemoryCandidate(req,env,ctx)",
  "./universal-entry-active.js",
  "./memory-candidate.js",
]) {
  if (!source.includes(required)) throw new Error(`UNIVERSAL_FABRIC_WIRING_MISSING:${required}`);
}
```

Run:

```bash
cd cloudflare-worker
node validate-worker.mjs
```

Expected before all wiring/check-script changes: validator may pass current wiring, but `npm run check` still does not execute the Universal tests; record this as the RED coverage gap.

- [ ] **Step 2: Add the Universal tests to `package.json`**

Add a script:

```json
"test:universal-fabric": "node test-universal-auth.mjs && node test-universal-entry-contract.mjs && node test-universal-entry-handler.mjs && node test-universal-state.mjs && node test-universal-telemetry.mjs && node test-memory-candidate.mjs"
```

Append `npm run test:universal-fabric` to `check` before deploy-safety validation.

- [ ] **Step 3: Run the focused suite**

Run:

```bash
cd cloudflare-worker
npm run test:universal-fabric
```

Expected: all six tests print their `...=PASS` marker and exit 0.

- [ ] **Step 4: Run the canonical Worker suite**

Run:

```bash
cd cloudflare-worker
npm run check
```

Expected: exit 0 with Universal Fabric, Skill Gateway, Model Mesh, TinyFish, scheduler, secret-scan, and deploy-safety tests all passing.

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/package.json cloudflare-worker/validate-worker.mjs
git commit -m "test: gate Universal Brain Fabric in worker CI"
```

---

### Task 2: Canonicalize the adapter registry and Universal Fabric policy

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/adapters/registry.yaml`
- Create: `AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml`
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py`
- Create: `AI_SKILL_LIBRARY/tests/test_universal_fabric_policy.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`

**Interfaces:**
- Consumes: current V4 security/runtime/memory/observability policies.
- Produces: canonical non-secret adapter metadata and one validator that rejects parallel authority, unsafe scopes, FAST network dependencies, or permission widening.

- [ ] **Step 1: Write the failing policy tests**

Create `AI_SKILL_LIBRARY/tests/test_universal_fabric_policy.py` with tests that require:

```python
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return yaml.safe_load((ROOT / rel).read_text())


def test_three_initial_adapters_are_non_authoritative():
    rows = load("AI_SKILL_LIBRARY/v4/adapters/registry.yaml")["adapters"]
    assert {r["id"] for r in rows} == {"chatgpt", "claude", "gemini"}
    assert all(r["routing_authority"] is False for r in rows)
    assert all(r["reasoning_authority"] is False for r in rows)


def test_fast_is_zero_rtt_and_high_risk_never_degrades():
    policy = load("AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml")
    assert policy["routing"]["FAST"]["online_brain_required"] is False
    assert policy["routing"]["FAST"]["external_routing_calls"] == 0
    assert set(policy["degraded"]["fail_closed_classes"]) >= {
        "live_or_trading", "deployment_or_runtime_claim", "credential_sensitive",
        "financial", "destructive", "permission_change"
    }
```

Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_universal_fabric_policy -v
```

Expected: FAIL because the canonical files do not exist yet.

- [ ] **Step 2: Create the adapter registry**

Use exactly this shape:

```yaml
version: 1
authority: false
adapters:
  - id: chatgpt
    token_binding: BRAIN_CLIENT_CHATGPT_TOKEN
    scopes: [brain.route, brain.read_context, brain.submit_candidate_memory, brain.use_research_tools, brain.read_runtime_health]
    routing_authority: false
    reasoning_authority: false
  - id: claude
    token_binding: BRAIN_CLIENT_CLAUDE_TOKEN
    scopes: [brain.route, brain.read_context, brain.submit_candidate_memory, brain.use_research_tools, brain.read_runtime_health]
    routing_authority: false
    reasoning_authority: false
  - id: gemini
    token_binding: BRAIN_CLIENT_GEMINI_TOKEN
    scopes: [brain.route, brain.read_context, brain.submit_candidate_memory, brain.use_research_tools, brain.read_runtime_health]
    routing_authority: false
    reasoning_authority: false
future_adapter_contract:
  brain_core_change_required: false
  default_state: disabled
  default_scopes: [brain.route]
```

- [ ] **Step 3: Create the canonical Universal Fabric policy**

`AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml` must encode:

```yaml
version: 1
authority: GITHUB_BRAIN_V4
adapter_authority: false
routing:
  FAST: {online_brain_required: false, external_routing_calls: 0, hot_snapshot_required: true, synchronous_shared_state: false}
  STANDARD: {online_brain_required: true, external_routing_calls: bounded}
  DEEP: {online_brain_required: true, external_routing_calls: bounded}
degraded:
  safe_mode: last_verified_stable
  fail_closed_classes: [live_or_trading, deployment_or_runtime_claim, credential_sensitive, financial, destructive, permission_change]
shared_state:
  canonical_authority: github
  runtime_authority: false
  raw_chat_sync: false
  secrets_allowed: false
learning:
  candidate_first: true
  autonomous_promotion_classes: [A, B]
  approval_required_classes: [C, D]
  permission_widening: false
```

- [ ] **Step 4: Add `validate_universal_fabric.py`**

The validator must load the two files and fail if any adapter claims routing/reasoning authority, duplicate client IDs/token bindings exist, FAST has nonzero external routing calls, degraded mode permits a protected class, or C/D auto-promotion is enabled. It must print:

```text
UNIVERSAL_FABRIC_VALIDATE=PASS adapters=3
```

- [ ] **Step 5: Register checkpoint pointers and the validator**

Add to `checkpoint.json`:

```json
"universal_fabric_policy_path": "AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml",
"universal_adapter_registry_path": "AI_SKILL_LIBRARY/v4/adapters/registry.yaml",
"universal_fabric_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py"
```

Add `AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py` to `VALIDATORS` in `ci_validate.py`.

- [ ] **Step 6: Run focused and canonical validation**

Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_universal_fabric_policy -v
python AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py --root .
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)" --skip-tests
```

Expected: all exit 0.

- [ ] **Step 7: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/adapters AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py AI_SKILL_LIBRARY/tests/test_universal_fabric_policy.py AI_SKILL_LIBRARY/checkpoint.json AI_SKILL_LIBRARY/v4/tools/ci_validate.py
git commit -m "feat: canonicalize Universal Brain Fabric policy"
```

---

### Task 3: Compile adapter metadata into the Worker instead of hard-coding client policy

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/compile_universal_adapters.py`
- Create: `AI_SKILL_LIBRARY/v4/runtime/generated/universal-adapters.json` (generated)
- Create: `cloudflare-worker/prepare-universal-fabric.mjs`
- Modify: `cloudflare-worker/universal-auth.js`
- Modify: `cloudflare-worker/package.json`
- Modify: `cloudflare-worker/prepare-workers-build.mjs`
- Create: `AI_SKILL_LIBRARY/tests/test_compile_universal_adapters.py`
- Modify: `cloudflare-worker/test-universal-auth.mjs`

**Interfaces:**
- Produces JSON shape:

```json
{"schema_version":1,"source_sha":"<40 hex>","adapters":[{"id":"chatgpt","token_binding":"BRAIN_CLIENT_CHATGPT_TOKEN","scopes":["brain.route"],"routing_authority":false,"reasoning_authority":false}]}
```

- `universal-auth.js` consumes the generated adapter object; adding a future adapter requires registry + secret only, not Brain core edits.

- [ ] **Step 1: Write the failing compiler test**

Require deterministic ordering, exact source SHA, unique IDs/bindings, and rejection of any authority=true row.

Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_compile_universal_adapters -v
```

Expected: FAIL because compiler does not exist.

- [ ] **Step 2: Implement the compiler**

`compile_universal_adapters.py` accepts:

```text
--root <repo>
--source-sha <40 hex>
--output <json path>
```

It validates through the Task 2 policy rules and writes sorted/minified canonical JSON plus newline.

- [ ] **Step 3: Add Worker preparation**

`prepare-universal-fabric.mjs` must read `../AI_SKILL_LIBRARY/v4/runtime/generated/universal-adapters.json`, verify `source_sha === GITHUB_SHA`, and write `generated/universal-adapters.js`:

```js
export const UNIVERSAL_ADAPTERS = Object.freeze(/* frozen canonical object */);
```

Do not copy token values; only binding names/scopes are generated.

- [ ] **Step 4: Refactor `universal-auth.js` to use generated metadata**

Replace the hard-coded `CLIENTS` object with an object built from `UNIVERSAL_ADAPTERS.adapters`. Preserve constant-time token comparison and the same scope behavior.

- [ ] **Step 5: Wire preparation into build scripts**

Add `prepare:universal-fabric` and run it before `check`, `deploy`, `preview`, and `prepare:all`. Ensure `prepare-workers-build.mjs` verifies the generated module exists.

- [ ] **Step 6: Run tests**

```bash
python AI_SKILL_LIBRARY/v4/tools/compile_universal_adapters.py --root . --source-sha "$(git rev-parse HEAD)" --output AI_SKILL_LIBRARY/v4/runtime/generated/universal-adapters.json
cd cloudflare-worker
GITHUB_SHA="$(git -C .. rev-parse HEAD)" npm run prepare:universal-fabric
node test-universal-auth.mjs
npm run test:universal-fabric
```

Expected: PASS; ChatGPT/Claude/Gemini behavior unchanged.

- [ ] **Step 7: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/compile_universal_adapters.py AI_SKILL_LIBRARY/tests/test_compile_universal_adapters.py AI_SKILL_LIBRARY/v4/runtime/generated/universal-adapters.json cloudflare-worker/prepare-universal-fabric.mjs cloudflare-worker/universal-auth.js cloudflare-worker/package.json cloudflare-worker/prepare-workers-build.mjs cloudflare-worker/generated/universal-adapters.js
git commit -m "feat: compile universal adapter registry"
```

---

### Task 4: Complete portable Shared Brain State with a production-safe KV baseline

**Files:**
- Modify: `cloudflare-worker/universal-state.js`
- Modify: `cloudflare-worker/test-universal-state.mjs`
- Modify: `cloudflare-worker/prepare-wrangler.mjs`
- Modify: `cloudflare-worker/test-deploy-safety.mjs`

**Interfaces:**
- `StateKV`: `get`, `put`, `delete`, `list(prefix, limit)`.
- `MetadataStore`: same interface with metadata namespace.
- Optional `VectorIndex`, `ObjectStore`, `TaskQueue`, `LeaseLock` remain non-authoritative and fail soft.
- Production baseline uses `BRAIN_STATE` when a dedicated namespace ID is configured; otherwise it uses namespaced existing `TRADING_STATE` without changing trading keys.

- [ ] **Step 1: Add failing state tests for prefix listing and namespace isolation**

Extend `test-universal-state.mjs` to require:

```js
assert.equal(typeof stores.metadata.list, 'function');
const rows = await stores.metadata.list('candidate:', 20);
assert.deepEqual(rows.items.map(x=>x.key), ['candidate:a']);
```

Also assert all Universal state keys are prefixed `brain:v1:` or `brain:v1:meta:` and cannot overwrite an unprefixed trading key.

Run:

```bash
cd cloudflare-worker
node test-universal-state.mjs
```

Expected: FAIL because `list` is not implemented.

- [ ] **Step 2: Implement bounded `list`**

Implement `list(prefix, limit=50)` with `1 <= limit <= 100`, returning:

```js
{unavailable:false, items:[{key, value}], cursor:null}
```

Strip only the Universal namespace prefix from returned keys. Any binding failure returns `{unavailable:true,items:[]}`.

- [ ] **Step 3: Add optional dedicated BRAIN_STATE binding generation**

In `prepare-wrangler.mjs`, accept `BRAIN_KV_NAMESPACE_ID`. If it matches the existing 32-hex namespace rule, add:

```js
{binding:'BRAIN_STATE', id:brainKvId}
```

alongside existing `TRADING_STATE`. If absent, do not fail deploy; runtime deliberately falls back to the namespaced trading KV.

Never generate Vectorize/R2/Queue bindings without explicit configured resource identifiers.

- [ ] **Step 4: Add deploy-safety assertions**

Require that `BRAIN_STATE`, when present, has a valid namespace ID and is never aliased by name to a secret/var. Verify removal of `BRAIN_KV_NAMESPACE_ID` yields a valid config that still contains `TRADING_STATE`.

- [ ] **Step 5: Run tests**

```bash
cd cloudflare-worker
node test-universal-state.mjs
node test-deploy-safety.mjs
npm run check
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add cloudflare-worker/universal-state.js cloudflare-worker/test-universal-state.mjs cloudflare-worker/prepare-wrangler.mjs cloudflare-worker/test-deploy-safety.mjs
git commit -m "feat: complete portable shared Brain state baseline"
```

---

### Task 5: Implement the candidate-memory review, promotion, supersession, and retrieval lifecycle

**Files:**
- Create: `cloudflare-worker/memory-lifecycle.js`
- Create: `cloudflare-worker/memory-context-handler.js`
- Create: `cloudflare-worker/test-memory-lifecycle.mjs`
- Create: `cloudflare-worker/test-memory-context-handler.mjs`
- Modify: `cloudflare-worker/index.js`
- Modify: `cloudflare-worker/universal-auth.js`
- Modify: `cloudflare-worker/package.json`
- Modify: `AI_SKILL_LIBRARY/v4/stable/memory.yaml`

**Interfaces:**
- Candidate stays `state:'candidate', active:false` until review gates pass.
- `reviewMemoryCandidate(candidate, evidence)` returns one of `confirmed`, `rejected`, `needs_reverify`.
- `promoteMemoryCandidate(candidate, review)` returns active normalized memory only when reusable, verified, non-sensitive, evidence-backed, non-conflicted, and confidence >= 0.55.
- `supersedeMemory(active, replacement)` preserves provenance and sets `active:false`, `state:'superseded'`, `superseded_by`.
- `POST /brain/memory/review` is **not** a normal client route; it requires `BRAIN_EVERGREEN_TOKEN` via a dedicated `x-brain-client: evergreen` principal with scope `brain.review_candidate_memory`.
- `POST /brain/context/query` requires `brain.read_context`, rejects FAST profile, and returns only active promoted memory within domain/scope/freshness bounds.

- [ ] **Step 1: Write failing lifecycle tests**

Cover at least:

```js
assert.equal(reviewMemoryCandidate(candidate,{evidence_count:2,conflict:false,current:true}).decision,'confirmed');
assert.throws(()=>promoteMemoryCandidate({...candidate,non_sensitive:false},review));
assert.equal(supersedeMemory(active,replacement).state,'superseded');
```

Also prove a raw-chat/secret-like content candidate cannot be promoted even if submitted by Evergreen.

Run:

```bash
cd cloudflare-worker
node test-memory-lifecycle.mjs
```

Expected: FAIL because module does not exist.

- [ ] **Step 2: Implement deterministic lifecycle gates**

The confirmation rule is:

```text
reusable == true
verified == true
non_sensitive == true
confidence >= 0.55
evidence_refs.length >= 1
conflicts_with.length == 0
review.evidence_count >= 1
review.current == true
review.conflict == false
```

No model vote or majority rule may appear in the implementation.

- [ ] **Step 3: Add Evergreen-only review authentication**

Extend the generated adapter registry with a non-user internal adapter:

```yaml
  - id: evergreen
    token_binding: BRAIN_EVERGREEN_TOKEN
    scopes: [brain.review_candidate_memory, brain.read_context]
    routing_authority: false
    reasoning_authority: false
```

Update Task 2 tests to expect three user adapters plus one internal Evergreen adapter, while `/brain/universal/capabilities` reports `userAdapters: [chatgpt, claude, gemini]` separately from internal principals.

- [ ] **Step 4: Implement `/brain/memory/review`**

Request body:

```json
{"candidate_id":"m-123","evidence_count":2,"current":true,"conflict":false,"reviewed_at":"2026-09-16T00:00:00Z"}
```

Load `candidate:<id>`, run lifecycle gate, write `memory:<domain>:<scope>:<candidate_id>` only on confirmation, and update candidate state. Return sanitized status only.

- [ ] **Step 5: Implement `/brain/context/query`**

Request body:

```json
{"domain":"coding","scope":"project:trading-api","profile":"STANDARD","query":"universal brain gateway","limit":4}
```

Behavior:

- reject profile FAST with 400 `fast_memory_preload_forbidden`;
- enforce limit <= Stable policy (`STANDARD=4`, `DEEP=8`);
- exact scope/domain filter first;
- lexical token overlap ranking over active memory content;
- optional vector lookup only after exact/lexical miss and only when `stores.vector.available`;
- never return candidate/superseded/tombstoned memory;
- return provenance metadata and no raw private chat.

- [ ] **Step 6: Wire handlers and tests into `index.js` and package checks**

Place memory review/context handling before generic Skill Gateway, but after authentication-specific Universal Entry dispatch. Add both tests to `test:universal-fabric`.

- [ ] **Step 7: Run tests**

```bash
cd cloudflare-worker
npm run test:universal-fabric
npm run check
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add cloudflare-worker/memory-lifecycle.js cloudflare-worker/memory-context-handler.js cloudflare-worker/test-memory-lifecycle.mjs cloudflare-worker/test-memory-context-handler.mjs cloudflare-worker/index.js cloudflare-worker/universal-auth.js cloudflare-worker/package.json AI_SKILL_LIBRARY/v4/stable/memory.yaml AI_SKILL_LIBRARY/v4/adapters/registry.yaml
git commit -m "feat: add shared Brain memory lifecycle and retrieval"
```

---

### Task 6: Implement a reusable hybrid adapter SDK and concrete ChatGPT/Claude/Gemini manifests

**Files:**
- Create: `clients/universal-brain-adapter/package.json`
- Create: `clients/universal-brain-adapter/index.mjs`
- Create: `clients/universal-brain-adapter/test-adapter.mjs`
- Create: `clients/universal-brain-adapter/openapi.yaml`
- Create: `clients/universal-brain-adapter/adapters/chatgpt.json`
- Create: `clients/universal-brain-adapter/adapters/claude.json`
- Create: `clients/universal-brain-adapter/adapters/gemini.json`
- Create: `clients/universal-brain-adapter/README.md`

**Interfaces:**
- `createBrainAdapter({clientId, token, endpoint, hotSnapshot, fetchImpl})`
- `adapter.route(request)` returns local FAST route when safe and provable from `hotSnapshot`; otherwise calls `/brain/universal/route`.
- `adapter.queryContext(request)` calls `/brain/context/query` only for STANDARD/DEEP.
- `adapter.submitMemoryCandidate(candidate)` calls `/brain/memory/candidates`.
- Cloud failure invokes `degradedDecision`; high-impact fails closed.

- [ ] **Step 1: Write failing adapter tests**

Prove:

```js
let calls=0;
const adapter=createBrainAdapter({...,fetchImpl:async()=>{calls++;throw new Error('network');}});
const fast=await adapter.route({text:'explain recursion',request_id:'r1',session_id:'s1',data_class:'PUBLIC'});
assert.equal(fast.profile,'FAST');
assert.equal(calls,0);
```

Then prove a live trading request attempts online Brain and fails closed if unreachable, while a safe STANDARD request may return `degraded:true` only with an explicitly supplied verified Stable snapshot.

- [ ] **Step 2: Implement local FAST routing using the existing Skill Gateway code contract**

Do not duplicate routing logic. Package/copy the generated HOT snapshot and reuse the canonical deterministic route algorithm artifact produced by `prepare-skill-gateway.mjs`. The adapter SDK must verify snapshot `source_sha`, `release_id`, and capsule presence before local FAST use.

- [ ] **Step 3: Implement cloud STANDARD/DEEP route and degraded behavior**

All calls send:

```http
x-brain-client: <clientId>
Authorization: Bearer <token>
Content-Type: application/json
```

Never log token values or full request bodies.

- [ ] **Step 4: Add platform manifests**

Each JSON manifest contains only public metadata:

```json
{"client_id":"chatgpt","entry":"/brain/universal/route","health":"/brain/universal/health","context":"/brain/context/query","memory_candidate":"/brain/memory/candidates","auth":"bearer+client-header","brain_authority":"GITHUB_BRAIN_V4"}
```

`openapi.yaml` documents the cloud endpoints and required headers but contains no credential values.

- [ ] **Step 5: Document the unavoidable platform boundary**

`README.md` must explicitly state: the repository and cloud endpoint cannot force third-party ChatGPT/Claude/Gemini consumer apps to call the Brain globally; each platform must connect/install its adapter or custom connector/system integration once. After that connection, the same endpoint/contract applies. Do not claim account-wide interception without a platform-supported hook.

- [ ] **Step 6: Run tests**

```bash
cd clients/universal-brain-adapter
npm test
```

Expected: local FAST test proves `fetchImpl` call count 0; protected cloud-failure test proves fail-closed.

- [ ] **Step 7: Commit**

```bash
git add clients/universal-brain-adapter
git commit -m "feat: add hybrid Universal Brain client adapter SDK"
```

---

### Task 7: Operationalize Upstream Watch and Skill Forge inside the existing Evergreen plane

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/run_upstream_watch.py`
- Create: `AI_SKILL_LIBRARY/v4/learning/upstream_sources.yaml`
- Create: `AI_SKILL_LIBRARY/v4/learning/upstream_ledger.json`
- Create: `AI_SKILL_LIBRARY/tests/test_run_upstream_watch.py`
- Modify: `.github/workflows/ai-brain-evergreen-scan.yml`
- Modify: `.github/workflows/ai-brain-evergreen-candidate.yml`
- Modify: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`

**Interfaces:**
- Reuses `normalize_source()` and `capability_diff()` from `upstream_watch.py`.
- Writes candidate/active/blocked/stale ledger only; never Stable skill registry directly.
- Candidate gaps are fed to `skill_forge.triage_gap()` and promotion classes A/B/C/D remain unchanged.

- [ ] **Step 1: Write failing runner tests**

Fixtures must prove:

- MIT + maintained + approved source → `active`;
- unknown license → `blocked`;
- critical security risk → `blocked`;
- equivalent capability → `strengthen_existing`;
- distinct capability → `distinct_candidate`;
- no output row has routing/reasoning authority.

- [ ] **Step 2: Implement `run_upstream_watch.py`**

CLI:

```text
--root .
--sources AI_SKILL_LIBRARY/v4/learning/upstream_sources.yaml
--output AI_SKILL_LIBRARY/v4/learning/upstream_ledger.json
--check
```

`--check` recomputes and fails if committed ledger differs, enabling CI freshness checks.

- [ ] **Step 3: Seed only already-approved upstreams**

Populate `upstream_sources.yaml` from currently approved repository/source records already present in the Brain source registries. Do not add an Internet source merely because it is popular. Every code source must have pinned revision, license, maintenance status, and capability list.

- [ ] **Step 4: Connect existing Evergreen workflows**

In `ai-brain-evergreen-scan.yml`, run source refresh + `run_upstream_watch.py` and upload/report the quarantine ledger. In `ai-brain-evergreen-candidate.yml`, feed `distinct_candidate`/`strengthen_existing` rows into candidate evaluation only; do not directly mutate Stable.

- [ ] **Step 5: Add CI freshness validation**

Add a validator/check call in `ci_validate.py` after existing V4 validators but before release checks:

```bash
python AI_SKILL_LIBRARY/v4/tools/run_upstream_watch.py --root . --check
```

- [ ] **Step 6: Run tests and validator**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_run_upstream_watch -v
python AI_SKILL_LIBRARY/v4/tools/run_upstream_watch.py --root . --check
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)" --skip-tests
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/run_upstream_watch.py AI_SKILL_LIBRARY/v4/learning/upstream_sources.yaml AI_SKILL_LIBRARY/v4/learning/upstream_ledger.json AI_SKILL_LIBRARY/tests/test_run_upstream_watch.py .github/workflows/ai-brain-evergreen-scan.yml .github/workflows/ai-brain-evergreen-candidate.yml AI_SKILL_LIBRARY/v4/tools/ci_validate.py
git commit -m "feat: operationalize upstream capability assimilation"
```

---

### Task 8: Add failure-driven learning and bounded autonomous A/B promotion evidence

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/learning/failure_ledger.json`
- Create: `AI_SKILL_LIBRARY/v4/tools/intake_failure.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/evaluate_skill_candidate.py`
- Create: `AI_SKILL_LIBRARY/tests/test_failure_driven_learning.py`
- Modify: `AI_SKILL_LIBRARY/v4/learning/skill_evo.yaml`
- Modify: `.github/workflows/ai-brain-evergreen-candidate.yml`

**Interfaces:**
- Failure record keys: `failure_id`, `domain`, `failure_class`, `observable_symptom`, `expected_outcome`, `evidence_ref`, `timestamp`, optional release/client/skill identifiers.
- Forbidden keys: raw prompt/private chat/secret/credential/hidden reasoning/private tool payload.
- `evaluate_skill_candidate.py` calls existing `promotion_decision()` and may mark A/B `automatic=true` only when all existing gates pass, frozen replay is true, protected regressions=0, critical conflicts=0, permission unchanged=true.
- It never writes Stable directly; it emits a promotion candidate consumed by existing release/promotion tooling.

- [ ] **Step 1: Write failing tests**

Require rejection of forbidden fields and prove:

```python
assert result_A["automatic"] is True
assert result_B["automatic"] is True
assert result_C["automatic"] is False and result_C["explicit_authorization_required"] is True
assert result_D["automatic"] is False and result_D["explicit_authorization_required"] is True
```

- [ ] **Step 2: Implement sanitized failure intake**

`intake_failure.py` validates one JSON input or JSONL batch and appends deterministically by `failure_id`, rejecting duplicates with conflicting content.

- [ ] **Step 3: Implement candidate evaluation wrapper**

The wrapper consumes a candidate JSON and eval-result JSON, delegates to `skill_forge.promotion_decision`, and adds provenance/immutable replay reference. It must not redefine A/B/C/D rules.

- [ ] **Step 4: Wire event-driven failures into Evergreen candidate workflow**

Workflow dispatch inputs reference ledger/evidence paths only; never put raw private prompts or secrets in GitHub Actions inputs/logs.

- [ ] **Step 5: Run tests**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_failure_driven_learning -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/learning/failure_ledger.json AI_SKILL_LIBRARY/v4/tools/intake_failure.py AI_SKILL_LIBRARY/v4/tools/evaluate_skill_candidate.py AI_SKILL_LIBRARY/tests/test_failure_driven_learning.py AI_SKILL_LIBRARY/v4/learning/skill_evo.yaml .github/workflows/ai-brain-evergreen-candidate.yml
git commit -m "feat: add failure-driven bounded skill refinement"
```

---

### Task 9: Add per-client production secret wiring and Universal Fabric canary gates to the sole deploy workflow

**Files:**
- Modify: `.github/workflows/deploy-skill-mandatory-fast-gateway.yml`
- Create: `cloudflare-worker/validate-universal-canary.mjs`
- Create: `cloudflare-worker/test-universal-canary.mjs`
- Modify: `cloudflare-worker/package.json`
- Modify: `cloudflare-worker/test-deploy-safety.mjs`

**Interfaces:**
- GitHub secret names: `BRAIN_CLIENT_CHATGPT_TOKEN`, `BRAIN_CLIENT_CLAUDE_TOKEN`, `BRAIN_CLIENT_GEMINI_TOKEN`, `BRAIN_EVERGREEN_TOKEN`.
- These are Cloudflare Worker secrets, never vars/config/repo content.
- Production canary verifies health/capabilities plus one authenticated route per configured user adapter and protected-class fail-closed behavior.

- [ ] **Step 1: Write failing deploy-safety tests**

Require that generated `wrangler.jsonc` never contains any `BRAIN_*_TOKEN` value/key in `vars` and that deploy workflow syncs them only via `wrangler secret put`.

- [ ] **Step 2: Extend deploy credential environment without exposing values**

Add secret env mappings:

```yaml
BRAIN_CLIENT_CHATGPT_TOKEN: ${{ secrets.BRAIN_CLIENT_CHATGPT_TOKEN }}
BRAIN_CLIENT_CLAUDE_TOKEN: ${{ secrets.BRAIN_CLIENT_CLAUDE_TOKEN }}
BRAIN_CLIENT_GEMINI_TOKEN: ${{ secrets.BRAIN_CLIENT_GEMINI_TOKEN }}
BRAIN_EVERGREEN_TOKEN: ${{ secrets.BRAIN_EVERGREEN_TOKEN }}
```

Sync each nonempty secret with `wrangler secret put`. Do not print values. For the release that claims all three adapters operational, require all three user adapter secrets; Evergreen token is required before memory-review automation is marked operational.

- [ ] **Step 3: Implement the canary validator**

`validate-universal-canary.mjs` accepts `WORKER_BASE_URL` and secrets via env. It must verify:

1. `/brain/universal/health` returns `brainAuthority=GITHUB_BRAIN_V4` and current source SHA;
2. `/brain/universal/capabilities` lists ChatGPT/Claude/Gemini;
3. each configured adapter can route a safe informational request;
4. a live/trading request returns DEEP + `safeDegradedAllowed=false`;
5. no response contains `chainOfThought`, `hidden_reasoning`, token value, or raw private payload.

- [ ] **Step 4: Add production gate after deploy and before known-good closure**

Run the Universal canary alongside existing Model Mesh, FAST, SECRET, and exact-SHA gates. Any Universal canary failure triggers the existing deterministic rollback path; do not create a second rollback implementation.

- [ ] **Step 5: Run local tests**

```bash
cd cloudflare-worker
node test-universal-canary.mjs
node test-deploy-safety.mjs
npm run check
```

Expected: PASS with network calls stubbed in the unit test.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/deploy-skill-mandatory-fast-gateway.yml cloudflare-worker/validate-universal-canary.mjs cloudflare-worker/test-universal-canary.mjs cloudflare-worker/package.json cloudflare-worker/test-deploy-safety.mjs
git commit -m "feat: gate Universal Brain Fabric production deployment"
```

**Operator prerequisite:** if the four GitHub secrets do not yet exist, repository code can be fully merged but the all-adapter production canary cannot honestly pass. Creating secret values is an account operation and must be completed through GitHub/Cloudflare secret management; values must never be committed or pasted into logs.

---

### Task 10: Refresh generated indexes/releases and run the complete pre-PR verification

**Files:**
- Modify generated release/index artifacts only through canonical tools.
- Modify: `CHECKPOINTS/MAXIMUM_INTEGRATION_ACTIVATION_2026-09-16.md` or create a new Universal Fabric checkpoint if the release tooling/checkpoint convention requires a new dated file.

**Interfaces:**
- One canonical CI validator.
- One generated release bundle.
- No manual hash edits.

- [ ] **Step 1: Run all Python tests**

```bash
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_*.py'
python -m unittest discover -s tests -p 'test_*.py'
```

Expected: `OK`.

- [ ] **Step 2: Run all Worker tests**

```bash
cd cloudflare-worker
npm ci --ignore-scripts --no-audit --no-fund
npm run check
cd ..
```

Expected: exit 0.

- [ ] **Step 3: Run canonical exact-SHA Brain validation**

```bash
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
```

Expected: `CI_VALIDATE=PASS failures=0` (or the repository's exact current PASS marker) with Universal Fabric validator included.

- [ ] **Step 4: Rebuild retrieval index through canonical tooling**

```bash
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --root .
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --check --root .
```

Expected: fresh index check PASS.

- [ ] **Step 5: Generate the release only through `release.py`**

Use the next semver selected by current release tooling; do not hand-edit manifests/hashes. Run its `build`/`promote` command according to `release.py --help`, then:

```bash
python AI_SKILL_LIBRARY/v4/tools/release.py check --root .
```

Expected: release check PASS, initially not marked known-good until post-merge production verification.

- [ ] **Step 6: Update closure checkpoint**

Record implemented features, known platform connection boundary, secret prerequisites, test evidence, target release, and the rule that supported clients require one-time platform adapter connection before their chats can invoke the Brain.

- [ ] **Step 7: Commit generated artifacts**

```bash
git add AI_SKILL_LIBRARY CHECKPOINTS cloudflare-worker clients .github/workflows docs/superpowers
git commit -m "release: prepare Universal Brain Fabric candidate"
```

---

### Task 11: Open PR, review, merge, deploy, and prove exact production state

**Files:**
- No hand-edited runtime files after exact-SHA build except review fixes that repeat Task 10 validation.

**Interfaces:**
- PR head SHA is immutable input to review.
- Production known-good is only the merged `main` SHA verified live.

- [ ] **Step 1: Open PR from the implementation branch to `main`**

PR body must summarize:

- existing Universal slice completed rather than rewritten;
- adapters and auth isolation;
- FAST zero-RTT contract;
- Shared Brain memory/context lifecycle;
- Upstream Watch/Skill Forge integration;
- no permission widening / no Trading changes / no paid fallback;
- required secrets and platform-connection boundary;
- test/validator results.

- [ ] **Step 2: Perform code review against the spec**

Review specifically for duplicate authority, secret leakage, FAST synchronous calls, unsafe degraded behavior, Stable direct writes from learning, Model Mesh paid fallback changes, Trading authority drift, and unbounded context/runtime growth.

- [ ] **Step 3: Merge only the reviewed head SHA**

Use `expected_head_sha` so the merge fails if the branch moved after review.

- [ ] **Step 4: Let the sole production workflow deploy exact `main`**

Do not invoke or create another production deployment workflow.

- [ ] **Step 5: Verify production gates**

Required PASS evidence:

```text
UNIVERSAL_BRAIN_HEALTH=PASS
UNIVERSAL_ADAPTER_CANARY=PASS chatgpt claude gemini
UNIVERSAL_HIGH_RISK_FAIL_CLOSED=PASS
FAST_EXTERNAL_BOUNDARY=PASS
SECRET_EXTERNAL_BOUNDARY=PASS
FREE_ONLY_ZERO_COST_GUARD=PASS
MODEL_MESH_PROBE=PASS
FINAL_EXACT_SHA_GATE=PASS
```

The actual deployed runtime revision must equal merged `main` SHA.

- [ ] **Step 6: Mark release known-good only after live proof**

Use canonical release tooling/history conventions. Record rollback predecessor and live verification run ID.

- [ ] **Step 7: Final post-merge check**

Verify `/brain/universal/health`, `/brain/health`, Model Mesh health, runtime revision, and release pointer all agree on the same known-good release/SHA.

---

## Completion Criteria

This implementation plan is complete when:

1. Universal Fabric tests are first-class canonical CI, not orphan tests.
2. Adapter registry/policy is canonical, validated, and compiled from GitHub authority.
3. ChatGPT/Claude/Gemini use isolated credentials/scopes and future adapters do not require Brain-core modification.
4. FAST-capable adapters can route verified safe FAST requests locally with zero network calls.
5. STANDARD/DEEP/high-impact requests route to cloud Brain and protected requests fail closed during cloud failure.
6. Shared state is namespace-isolated and works on Cloudflare KV baseline, while vector/object/queue backends remain optional portable extensions.
7. Memory is candidate-first, promotion-gated, supersedable, provenance-preserving, and retrievable only by bounded STANDARD/DEEP context queries.
8. Upstream Watch and Skill Forge operate under the existing Evergreen plane, with A/B bounded auto-promotion and C/D explicit approval.
9. No learning path writes Stable directly or widens permissions.
10. Sole production deploy workflow securely syncs adapter secrets and runs Universal canary gates.
11. Model Mesh zero-cost, Trading authority, SECRET external=0, FAST boundary, and exact-SHA invariants remain green.
12. Third-party client integration is stated precisely: the Brain endpoint/adapter is production-ready, but each external product must support and receive a one-time connector/adapter installation before its chats can automatically invoke it.
