# Universal Brain Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend GITHUB_BRAIN_V4 into a multi-client Universal Brain Fabric with zero-RTT FAST routing, cloud-gated STANDARD/DEEP routing, portable shared runtime state, candidate-memory lifecycle, continuous capability assimilation, and bounded self-refinement without creating a second Brain or widening protected permissions.

**Architecture:** Reuse the current Skill-Mandatory Fast Gateway, Model Mesh, Evergreen, harmonization, learning, release, and exact-SHA deployment paths. Add a client-neutral entry envelope, scoped adapter auth, portable runtime-state interfaces, candidate-memory and telemetry APIs, then layer upstream watch and Skill Forge jobs into the existing Evergreen update plane. ChatGPT, Claude, and Gemini are the first adapters; all normalize into one canonical request contract.

**Tech Stack:** Python 3 validation/tooling, Node.js 22 ES modules, Cloudflare Workers, existing KV/Durable Object deployment pattern, JSON Schema/YAML release contracts, GitHub Actions, existing GITHUB_BRAIN_V4 release tooling.

**Spec:** `docs/superpowers/specs/2026-09-16-universal-brain-fabric-design.md`

## Global Constraints

- `GITHUB_BRAIN_V4` remains the sole routing/reasoning authority.
- FAST routing keeps zero synchronous external/GitHub/provider routing calls and p95 <= 25 ms.
- STANDARD/DEEP/high-impact requests use the cloud Brain path; live/trading/deploy/credential/financial/destructive actions may not bypass it.
- Safe degraded fallback may use only the last verified Stable snapshot for permitted informational work.
- GitHub is canonical; cloud state is derived/subordinate runtime state.
- Model Mesh remains zero-cost only: no paid fallback, auto-purchase, trial-credit-as-free, or quota circumvention.
- SECRET external = 0; unknown data classes fail closed.
- No hidden chain-of-thought, raw private chat, credentials, secrets, private keys, or raw sensitive provider/tool payloads are persisted.
- Learning cannot widen permissions; Class A/B may auto-promote only through existing gates; Class C/D require explicit authorization.
- Trading execution authority is unchanged.
- Production completion requires tests, canonical validators, release generation, CI, canary, post-merge runtime verification, and exact-SHA gate.

---

## File Structure

New canonical policy/contract files:
- `AI_SKILL_LIBRARY/v4/universal_entry/policy.yaml` — client-neutral routing/auth/fallback contract.
- `AI_SKILL_LIBRARY/v4/schemas/universal_entry_request.schema.json` — request envelope schema.
- `AI_SKILL_LIBRARY/v4/schemas/universal_entry_response.schema.json` — response envelope schema.
- `AI_SKILL_LIBRARY/v4/runtime/client_adapters.yaml` — adapter identities, capabilities, and non-secret scope declarations.
- `AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml` — portable storage interfaces and retention boundaries.
- `AI_SKILL_LIBRARY/v4/learning/memory_lifecycle.yaml` — candidate-memory state machine.
- `AI_SKILL_LIBRARY/v4/learning/upstream_watch.yaml` — source ledger and capability-diff policy.

New Python tooling:
- `AI_SKILL_LIBRARY/v4/tools/universal_entry.py` — pure normalization/classification/scoping helpers.
- `AI_SKILL_LIBRARY/v4/tools/memory_lifecycle.py` — candidate-memory state transitions and conflict/supersession logic.
- `AI_SKILL_LIBRARY/v4/tools/upstream_watch.py` — upstream ledger normalization and diff classification.
- `AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py` — repository-level invariant validator.

New Worker modules:
- `cloudflare-worker/universal-entry-contract.js` — runtime envelope validation, profile/risk escalation rules.
- `cloudflare-worker/universal-auth.js` — scoped client principal validation with no credential logging.
- `cloudflare-worker/universal-state.js` — `StateKV`, `MetadataStore`, `VectorIndex`, `ObjectStore`, `TaskQueue`, `LeaseLock` interfaces plus Cloudflare adapters/fail-safe stubs.
- `cloudflare-worker/universal-entry-handler.js` — `/brain/universal/*` HTTP endpoints.
- `cloudflare-worker/universal-telemetry.js` — sanitization and bounded event emission.
- `cloudflare-worker/memory-candidate.js` — candidate-memory submission/read path.

Tests:
- `AI_SKILL_LIBRARY/tests/test_universal_entry.py`
- `AI_SKILL_LIBRARY/tests/test_memory_lifecycle.py`
- `AI_SKILL_LIBRARY/tests/test_upstream_watch.py`
- `cloudflare-worker/test-universal-entry-contract.mjs`
- `cloudflare-worker/test-universal-auth.mjs`
- `cloudflare-worker/test-universal-state.mjs`
- `cloudflare-worker/test-universal-entry-handler.mjs`
- `cloudflare-worker/test-memory-candidate.mjs`
- `cloudflare-worker/test-universal-telemetry.mjs`

Existing files modified only where they are canonical owners:
- `AI_SKILL_LIBRARY/checkpoint.json`
- `AI_SKILL_LIBRARY/validate_v4.py`
- `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`
- `AI_SKILL_LIBRARY/v4/tools/release.py`
- `cloudflare-worker/index.js`
- `cloudflare-worker/package.json`
- `cloudflare-worker/prepare-wrangler.mjs`
- `cloudflare-worker/wrangler.example.jsonc`
- `cloudflare-worker/test-deploy-safety.mjs`

---

### Task 1: Canonical Universal Entry policy and schemas

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/universal_entry/policy.yaml`
- Create: `AI_SKILL_LIBRARY/v4/schemas/universal_entry_request.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/universal_entry_response.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/runtime/client_adapters.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_universal_entry.py`

**Interfaces:**
- Produces Python API: `normalize_request(payload: dict, adapter_id: str) -> dict`, `classify_entry(normalized: dict) -> dict`, `scope_allows(adapter: dict, required_scope: str) -> bool`.
- Canonical normalized request keys: `client_id`, `adapter_version`, `session_id`, `request_id`, `text`, `project_hint`, `freshness`, `declared_capabilities`, `tool_classes`, `data_class`, `requested_action_class`.
- Classification output keys: `profile`, `high_impact`, `requires_online_brain`, `safe_degraded_allowed`, `reason`.

- [ ] **Step 1: Write failing tests for request normalization and escalation**

```python
from AI_SKILL_LIBRARY.v4.tools.universal_entry import normalize_request, classify_entry


def test_fast_text_stays_zero_rtt_eligible():
    req = normalize_request({"text": "giải thích khái niệm API", "request_id": "r1", "session_id": "s1"}, "chatgpt")
    out = classify_entry(req)
    assert out["profile"] == "FAST"
    assert out["requires_online_brain"] is False


def test_live_trading_escalates_and_disallows_degraded():
    req = normalize_request({"text": "quét giá BTC live", "request_id": "r2", "session_id": "s1", "freshness": "live"}, "chatgpt")
    out = classify_entry(req)
    assert out["profile"] == "DEEP"
    assert out["requires_online_brain"] is True
    assert out["safe_degraded_allowed"] is False
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_universal_entry -v`
Expected: import/module failure because `universal_entry.py` does not exist.

- [ ] **Step 3: Add schemas and policy with exact escalation classes**

`policy.yaml` must declare `routing_authority: false`, `reasoning_authority: false`, `brain_authority: GITHUB_BRAIN_V4`, FAST zero-RTT, STANDARD/DEEP online Brain, and mandatory DEEP escalation for `live_or_trading`, `deployment_or_runtime_claim`, `credential_sensitive`, `financial`, `destructive`, `permission_change`.

- [ ] **Step 4: Implement minimal pure normalization/classification helpers**

Implement `AI_SKILL_LIBRARY/v4/tools/universal_entry.py` with deterministic validation only; no network calls, provider calls, model calls, or alternate router.

- [ ] **Step 5: Run tests GREEN and commit**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_universal_entry -v`
Commit: `feat: add universal entry contracts`

---

### Task 2: Scoped client authentication contract

**Files:**
- Create: `cloudflare-worker/universal-auth.js`
- Test: `cloudflare-worker/test-universal-auth.mjs`
- Modify: `AI_SKILL_LIBRARY/v4/runtime/client_adapters.yaml`

**Interfaces:**
- `authenticateAdapter(request, env) -> {ok:boolean, principal?:{clientId:string, scopes:string[]}, status:number, error?:string}`
- Secrets are resolved from per-adapter environment bindings; repository stores only binding names and non-secret scope metadata.

- [ ] **Step 1: Add RED tests for isolated credentials and scope denial**

```js
assert.equal(authFor('chatgpt-token','brain.route').principal.clientId,'chatgpt');
assert.equal(authFor('claude-token','brain.route').principal.clientId,'claude');
assert.equal(authFor('chatgpt-token','brain.request_deploy_action').ok,false);
assert.equal(JSON.stringify(authFor('bad','brain.route')).includes('chatgpt-token'),false);
```

- [ ] **Step 2: Implement constant-time token comparison and fail-closed scope checks**

Supported initial principals: `chatgpt`, `claude`, `gemini`; each has independent secret binding and explicit scopes. Unknown client/scope returns 401/403 without echoing tokens.

- [ ] **Step 3: Run GREEN and commit**

Run: `node cloudflare-worker/test-universal-auth.mjs`
Commit: `feat: add scoped universal adapter auth`

---

### Task 3: Portable Shared Brain State interfaces

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml`
- Create: `cloudflare-worker/universal-state.js`
- Test: `cloudflare-worker/test-universal-state.mjs`

**Interfaces:**
- `createStateStores(env) -> {kv, metadata, vector, objects, queue, locks}`
- Each store exposes bounded methods only: `get`, `put`, `delete` as applicable; vector exposes `query`; queue exposes `enqueue`; locks expose `withLease`.
- Backend unavailability returns typed `UNAVAILABLE` results; it never invents authority or blocks FAST routing.

- [ ] **Step 1: RED tests using in-memory fake bindings**
- [ ] **Step 2: Implement interface adapters with Cloudflare-first binding resolution and safe unavailable stubs**
- [ ] **Step 3: Prove FAST route code has no import-time state reads**
- [ ] **Step 4: GREEN tests and commit**

Run: `node cloudflare-worker/test-universal-state.mjs`
Commit: `feat: add portable shared brain state interfaces`

---

### Task 4: Universal Entry runtime handler

**Files:**
- Create: `cloudflare-worker/universal-entry-contract.js`
- Create: `cloudflare-worker/universal-entry-handler.js`
- Test: `cloudflare-worker/test-universal-entry-contract.mjs`
- Test: `cloudflare-worker/test-universal-entry-handler.mjs`
- Modify: `cloudflare-worker/index.js`

**Interfaces:**
- `POST /brain/universal/route`
- `GET /brain/universal/health`
- `GET /brain/universal/capabilities`
- Request normalization must feed the existing `routeSkillRequest`; it may not select a primary skill itself.
- FAST response includes the existing route/capsule and `onlineBrainRequired:false` without shared-state/provider reads.
- STANDARD/DEEP response is marked `onlineBrainRequired:true` and may proceed to bounded context/tool execution only through existing Brain/Model Mesh paths.

- [ ] **Step 1: RED tests proving all three initial client envelopes normalize identically**
- [ ] **Step 2: Implement contract validation and high-impact escalation**
- [ ] **Step 3: Wire handler before Model Mesh/research/trading routes in `index.js`**
- [ ] **Step 4: Assert no route changes for existing `/brain/route` tests**
- [ ] **Step 5: GREEN tests and commit**

Run: `node cloudflare-worker/test-universal-entry-contract.mjs && node cloudflare-worker/test-universal-entry-handler.mjs && node cloudflare-worker/test-skill-gateway-handler.mjs`
Commit: `feat: add universal brain entry endpoint`

---

### Task 5: Candidate Memory lifecycle

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/learning/memory_lifecycle.yaml`
- Create: `AI_SKILL_LIBRARY/v4/tools/memory_lifecycle.py`
- Create: `cloudflare-worker/memory-candidate.js`
- Test: `AI_SKILL_LIBRARY/tests/test_memory_lifecycle.py`
- Test: `cloudflare-worker/test-memory-candidate.mjs`

**Interfaces:**
- Python: `evaluate_candidate(candidate: dict, active_records: list[dict]) -> dict` and `transition(record: dict, target_state: str, evidence: dict) -> dict`.
- States: `candidate`, `pending`, `confirmed`, `active`, `superseded`, `archived`, `tombstoned`.
- Runtime endpoint: `POST /brain/memory/candidates` requires `brain.submit_candidate_memory` and rejects forbidden fields/content categories.

- [ ] **Step 1: RED tests for no immediate promotion, conflict blocking, verified-newer supersession, and secret/raw-chat rejection**
- [ ] **Step 2: Implement lifecycle as authority-subordinate to `stable/memory.yaml`**
- [ ] **Step 3: Implement runtime candidate submission to MetadataStore/queue only; no direct Stable writes**
- [ ] **Step 4: GREEN tests and commit**

Commit: `feat: add candidate memory lifecycle`

---

### Task 6: Sanitized telemetry and per-client audit

**Files:**
- Create: `cloudflare-worker/universal-telemetry.js`
- Test: `cloudflare-worker/test-universal-telemetry.mjs`
- Modify: `AI_SKILL_LIBRARY/v4/stable/observability.yaml`

**Interfaces:**
- `sanitizeEvent(event) -> event`
- `recordUniversalEvent(stores, event) -> Promise<{ok:boolean}>`
- Allowed fields are bounded to client ID, request/profile/domain/skill/capsule/release hashes, latency, tool/provider/model-family identifiers, cache/retrieval outcome, fallback state, memory/promotion/recovery event type, and status.

- [ ] **Step 1: RED tests proving raw text, prompts, secrets, account data, credentials and chain-of-thought keys are removed**
- [ ] **Step 2: Implement field allowlist + character/event bounds matching Stable observability limits**
- [ ] **Step 3: Ensure telemetry failure never blocks Stable answer path**
- [ ] **Step 4: GREEN tests and commit**

Commit: `feat: add sanitized universal telemetry`

---

### Task 7: Safe degraded fallback contract

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/universal_entry/policy.yaml`
- Modify: `cloudflare-worker/universal-entry-contract.js`
- Modify: `cloudflare-worker/universal-entry-handler.js`
- Test: `cloudflare-worker/test-universal-entry-handler.mjs`

**Interfaces:**
- `degradedDecision({classification, stableSnapshotAvailable}) -> {allowed:boolean, mode:string, disclosureRequired:boolean}`

- [ ] **Step 1: RED tests: safe informational STANDARD can use last verified Stable; live/trading/deploy/credential/financial/destructive cannot**
- [ ] **Step 2: Implement fallback without candidate cache promotion or freshness fabrication**
- [ ] **Step 3: GREEN tests and commit**

Commit: `feat: enforce safe degraded universal fallback`

---

### Task 8: Upstream Watch and capability-diff ledger

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/learning/upstream_watch.yaml`
- Create: `AI_SKILL_LIBRARY/v4/tools/upstream_watch.py`
- Test: `AI_SKILL_LIBRARY/tests/test_upstream_watch.py`
- Modify: `AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml`

**Interfaces:**
- `normalize_source(row: dict) -> dict`
- `capability_diff(active: dict, upstream: dict) -> dict`
- Output categories: `already_assimilated`, `strengthen_existing`, `distinct_candidate`, `conflict`, `blocked_license`, `blocked_security`, `stale`.

- [ ] **Step 1: RED tests for whitelist source refresh, candidate source quarantine, license/security blocking, and strengthen-existing preference**
- [ ] **Step 2: Implement ledger/diff tool with no routing authority and no direct Stable write**
- [ ] **Step 3: Add upstream-watch job class to existing Evergreen discovery policy, not a new scheduler**
- [ ] **Step 4: GREEN tests and commit**

Commit: `feat: add upstream capability watch`

---

### Task 9: Skill Forge / failure-driven self-refinement orchestration

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/skill_forge.py`
- Test: `AI_SKILL_LIBRARY/tests/test_skill_forge.py`
- Modify: `AI_SKILL_LIBRARY/v4/learning/skill_factory.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/learning/skill_evo.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/learning/idle.yaml`

**Interfaces:**
- `triage_gap(gap, existing_skills) -> {action: discard|improve|merge|create, target_skill_id, promotion_class}`
- `promotion_decision(candidate, eval_result) -> {eligible, automatic, reason}`
- A/B may be automatic only when every Evergreen gate passes; C/D return `automatic:false`.

- [ ] **Step 1: RED tests for strengthen-first, frozen replay requirement, protected regression zero tolerance, and C/D manual gate**
- [ ] **Step 2: Implement pure orchestration over existing admission/harmonization/promotion contracts**
- [ ] **Step 3: Add only bounded idle job metadata; never add financial/destructive/credential jobs**
- [ ] **Step 4: GREEN tests and commit**

Commit: `feat: add bounded skill forge orchestration`

---

### Task 10: Repository validator and release/checkpoint integration

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py`
- Modify: `AI_SKILL_LIBRARY/validate_v4.py`
- Modify: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`
- Modify: `AI_SKILL_LIBRARY/v4/tools/release.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`

**Interfaces:**
- Validator checks one Brain authority, no parallel router, FAST zero-RTT constraints, adapter scope isolation, storage subordination, memory privacy, learning permission ceiling, and required schema/policy paths.

- [ ] **Step 1: Add failing unit assertions that checkpoint pointers are missing**
- [ ] **Step 2: Add checkpoint paths for universal policy, request/response schemas, client adapter registry, shared-state contract, memory lifecycle, upstream watch, and validator**
- [ ] **Step 3: Add validator to `ci_validate.py` and release files to `release.py`**
- [ ] **Step 4: Run `python3 AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha <HEAD>` after implementation checkout has a real HEAD SHA**
- [ ] **Step 5: Commit**

Commit: `build: integrate universal fabric validation and release`

---

### Task 11: Worker build/deploy bindings without weakening trading/runtime safety

**Files:**
- Modify: `cloudflare-worker/prepare-wrangler.mjs`
- Modify: `cloudflare-worker/wrangler.example.jsonc`
- Modify: `cloudflare-worker/test-deploy-safety.mjs`
- Modify: `cloudflare-worker/package.json`

**Interfaces:**
- Reuse existing `TRADING_STATE` KV only for explicitly namespaced universal lightweight runtime records where policy permits; do not replace trading keys.
- Optional future D1/Vectorize/R2 bindings must be fail-safe/optional until account resources are explicitly configured and verified; missing optional backends cannot break FAST or Stable routing.
- Adapter secrets remain environment secrets and are never emitted into generated config/logs.

- [ ] **Step 1: RED deploy-safety tests for no shared master key, no secret logging, no new financial/autonomous cron, and no second deploy authority**
- [ ] **Step 2: Extend package `check` with all universal JS tests**
- [ ] **Step 3: Add only safe bindings/config generation and preserve the single health-only cron invariant**
- [ ] **Step 4: Run `npm --prefix cloudflare-worker run check` GREEN**
- [ ] **Step 5: Commit**

Commit: `build: wire universal fabric worker checks`

---

### Task 12: Adapter contract fixtures for ChatGPT, Claude, Gemini, future clients

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/runtime/adapters/chatgpt.yaml`
- Create: `AI_SKILL_LIBRARY/v4/runtime/adapters/claude.yaml`
- Create: `AI_SKILL_LIBRARY/v4/runtime/adapters/gemini.yaml`
- Create: `AI_SKILL_LIBRARY/v4/runtime/adapters/template.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_universal_entry.py`

**Interfaces:**
- Every adapter maps to the same canonical request/response schemas.
- Adapter fixtures declare only capabilities/tool classes/scopes and secret binding names; they contain no credentials and no client-specific reasoning authority.

- [ ] **Step 1: RED test that all three initial fixtures validate to the same normalized envelope and template requires no Brain-core change**
- [ ] **Step 2: Add fixtures and validation loader**
- [ ] **Step 3: GREEN tests and commit**

Commit: `feat: add universal client adapter fixtures`

---

### Task 13: Full regression, FAST benchmark, security boundaries

**Files:**
- Modify only tests/validators if a verified regression exposes a defect.

- [ ] **Step 1: Run Python suite**

Run: `python3 -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_*.py'`
Expected: PASS.

- [ ] **Step 2: Run Worker suite**

Run: `npm --prefix cloudflare-worker run check`
Expected: PASS.

- [ ] **Step 3: Build exact-SHA snapshots through canonical CI validator**

Run: `python3 AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"`
Expected: `failures=0`.

- [ ] **Step 4: Run FAST benchmark**

Run from `cloudflare-worker`: `node benchmark-skill-gateway.mjs`
Expected: `FAST_EXTERNAL_CALLS=0` and `FAST_ROUTE_P95_MS <= 25`.

- [ ] **Step 5: Verify security invariants**

Confirm tests prove: unknown data class fails closed; SECRET external workers = 0; adapter scopes isolated; telemetry/memory reject sensitive fields; high-impact degraded fallback blocked; no paid Model Mesh fallback.

- [ ] **Step 6: Commit regression fixes only if required**

---

### Task 14: Release, canary, and production closure

**Files:**
- Generated through existing release tooling; update release/checkpoint closure records only after verification.

- [ ] **Step 1: Generate next patch release through `AI_SKILL_LIBRARY/v4/tools/release.py`, never hand-edit hashes**
- [ ] **Step 2: Open PR from implementation branch and require CI green**
- [ ] **Step 3: Merge only the reviewed exact head SHA**
- [ ] **Step 4: Run the single production deployment authority `.github/workflows/deploy-skill-mandatory-fast-gateway.yml`**
- [ ] **Step 5: Canary `/brain/health`, `/brain/route`, `/brain/universal/health`, `/brain/universal/route`, Model Mesh probe/overlay, and existing trading/runtime health**
- [ ] **Step 6: Require `FREE_ONLY_ZERO_COST_GUARD=PASS`, `SECRET_EXTERNAL_BOUNDARY=PASS`, `FAST_EXTERNAL_BOUNDARY=PASS`, and `FINAL_EXACT_SHA_GATE=PASS`**
- [ ] **Step 7: Confirm rollback behavior is still deterministic**
- [ ] **Step 8: Only then mark the release known-good and update closure checkpoint**

---

## Plan Self-Review

- Spec coverage: Universal Entry, Hybrid FAST/STANDARD/DEEP, scoped auth, Shared Brain State, portable backend, candidate memory, RAG-ready state interface, upstream watch, Skill Forge, failure-driven learning, Model Mesh invariants, telemetry, recovery/degraded behavior, privacy, adapter extensibility, staged rollout, release/canary/exact-SHA closure are all mapped to tasks.
- No parallel Brain/router/skill registry/scheduler is introduced.
- No task grants financial, credential, destructive, or broader write permission.
- FAST never gains a synchronous state/network dependency.
- All mutable learning outputs remain candidate/quarantine state until existing promotion gates pass.
- Exact runtime/cloud resources such as optional D1/Vectorize/R2 are deliberately adapter-bound and fail-safe; the plan does not fabricate resource IDs or silently require new paid services.
