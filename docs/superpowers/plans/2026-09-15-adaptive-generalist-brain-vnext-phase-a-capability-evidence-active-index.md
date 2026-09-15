# Adaptive Generalist Brain vNext Phase A — Capability Evidence + Active Candidate Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a measured Capability Evidence Ledger and a bounded Canonical Active Candidate Index without changing current production selection behavior until verified capability coverage explicitly permits a hard gate.

**Architecture:** Keep `AI_SKILL_LIBRARY/v4/model_mesh/active.json` and the validated Model Mesh snapshot as canonical admitted-model inputs. Add a separate evidence ledger for measured capability facts, compile a derived exact-SHA Active Candidate Index from the validated snapshot + ledger + `domain_capabilities.yaml`, and load that index into the Worker as a generated build artifact. Runtime selection remains behavior-compatible by default because hard capability evidence gates are disabled until per-domain/per-capability coverage passes the approved threshold and a later config explicitly enables that gate.

**Tech Stack:** Python 3, `jsonschema`, PyYAML, Node.js ESM, Cloudflare Workers, existing Model Mesh compiler/validator pipeline, `unittest`, Node `assert`, GitHub Actions exact-SHA deploy gate.

**Spec:** `docs/superpowers/specs/2026-09-15-adaptive-generalist-brain-vnext-design.md`

## Global Constraints

- GitHub Brain remains the single routing/reasoning authority.
- `task_router` and exactly one primary skill + validated capsule remain upstream of model selection.
- No majority vote; same model family never counts as independent reasoning.
- `FAST` external workers remain exactly `0` and FAST adds no KV/provider/network routing RTT.
- `SECRET` external workers remain exactly `0`; unknown data class continues to fail closed to `SECRET`.
- Core remains `FREE_ONLY`; no paid fallback, auto-purchase, trial-credit promotion, or sponsored-credit assumption.
- Provider/model failure degrades to graceful zero and never becomes Brain failure.
- Cloud-first / zero-local remains mandatory.
- No permission widening; Trading execution authority is unchanged.
- Generated runtime artifacts remain build outputs and are not committed.
- Phase A must preserve current worker-selection behavior when the canonical evidence ledger has no `VERIFIED` record and hard gates are disabled.
- Hard capability gating is opt-in per domain/capability and must compile-fail if requested before coverage eligibility is proven.
- Production completion requires the existing exact-SHA deployment proof with `runtime_revision == main`.

---

## File Structure

### Create

- `AI_SKILL_LIBRARY/v4/schemas/capability_evidence_ledger.schema.json` — schema for immutable measured capability records.
- `AI_SKILL_LIBRARY/v4/schemas/model_mesh_active_candidate_index.schema.json` — schema for the exact-SHA derived bounded index.
- `AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json` — canonical ledger root; starts with an empty `records` array rather than fabricating verification evidence.
- `AI_SKILL_LIBRARY/v4/tools/capability_evidence.py` — ledger loading, indexing, freshness and evidence-state evaluation.
- `AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_active_index.py` — deterministic compiler from validated snapshot + ledger + domain capability policy.
- `AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_active_index.py` — schema, exact-SHA, boundedness and authority validator.
- `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_capability_evidence.py` — Python unit tests for `VERIFIED/PROVISIONAL/UNKNOWN/STALE` semantics.
- `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_active_index.py` — compiler/validator/coverage tests.
- `cloudflare-worker/model-mesh/capability-evidence.js` — runtime exact-key overlay and hard-gate lookup helper.
- `cloudflare-worker/test-model-mesh-active-index.mjs` — Worker parity, hard-gate, FAST/SECRET and source-SHA tests.

### Modify

- `AI_SKILL_LIBRARY/checkpoint.json` — add checkpoint-resolved ledger/index schema/compiler/validator pointers.
- `AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml` — add evidence freshness + hard-gate rollout policy; keep `weights_are_selection_metadata_only: true`.
- `AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_policy.py` — compile capability-evidence rollout policy into the runtime policy contract.
- `AI_SKILL_LIBRARY/v4/tools/ci_validate.py` — compile and validate the Active Candidate Index after the Model Mesh snapshot.
- `AI_SKILL_LIBRARY/v4/tools/release.py` — hash the new canonical schemas/policy/ledger/compiler/validator in capability releases.
- `cloudflare-worker/prepare-model-mesh.mjs` — require the derived index, enforce exact-SHA parity, and emit `generated/model-mesh-active-candidate-index.js`.
- `cloudflare-worker/model-mesh/contracts.js` — make the existing `capability` filter evidence-aware only when an enabled hard gate is supplied.
- `cloudflare-worker/model-mesh/selector.js` — score from provider metadata as today, but apply only compiler-approved hard capability gates.
- `cloudflare-worker/model-mesh/runtime-health.js` — preserve live-health overlay while retaining derived capability evidence metadata.
- `cloudflare-worker/model-mesh-runtime.js` — require snapshot/index source-SHA parity and apply the evidence overlay before selection.
- `cloudflare-worker/model-mesh-handler.js` — accept the index and expose sanitized coverage diagnostics.
- `cloudflare-worker/model-mesh-active.js` — import the generated Active Candidate Index and inject it into the handler.
- `cloudflare-worker/package.json` — add `test-model-mesh-active-index.mjs` to `test:model-mesh` and `check`.
- `cloudflare-worker/test-model-mesh-contracts.mjs` — cover evidence-aware capability filter behavior.
- `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_selection.py` — prove default parity and opt-in verified hard-gate behavior.
- `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_snapshot.py` — verify checkpoint/release/CI integration for the new paths.

### Generated only — never commit

- `AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-active-candidate-index.json`
- `cloudflare-worker/generated/model-mesh-active-candidate-index.js`

---

### Task 1: Define canonical Capability Evidence and Active Index contracts

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/schemas/capability_evidence_ledger.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/model_mesh_active_candidate_index.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_capability_evidence.py`
- Test: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_snapshot.py`

**Interfaces:**
- Consumes: existing canonical model identity `(provider_id, model_id, model_family)` and capability dimensions from `domain_capabilities.yaml`.
- Produces: `capability_evidence_ledger_v1` and `model_mesh_active_candidate_index_v1` contracts plus checkpoint paths.

- [ ] **Step 1: Write failing contract tests**

Add tests that require these checkpoint keys and files:

```python
expected = {
    "model_mesh_capability_evidence_path": "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json",
    "model_mesh_capability_evidence_schema_path": "AI_SKILL_LIBRARY/v4/schemas/capability_evidence_ledger.schema.json",
    "model_mesh_active_index_schema_path": "AI_SKILL_LIBRARY/v4/schemas/model_mesh_active_candidate_index.schema.json",
    "model_mesh_active_index_compiler_path": "AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_active_index.py",
    "model_mesh_active_index_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_active_index.py",
}
for key, rel in expected.items():
    self.assertEqual(checkpoint.get(key), rel)
    self.assertTrue((ROOT / rel).is_file(), rel)
```

Also assert the evidence policy remains non-authoritative and hard-gate-off by default:

```python
config = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml").read_text())
policy = config["capability_evidence"]
self.assertFalse(policy["hard_gate"]["default_enabled"])
self.assertEqual(policy["hard_gate"]["min_verified_candidates"], 2)
self.assertEqual(policy["hard_gate"]["min_coverage_ratio"], 0.80)
self.assertEqual(policy["default_freshness_hours"], 168)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python3 -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_capability_evidence AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_snapshot -v
```

Expected: FAIL because the new files/checkpoint keys and `capability_evidence` policy do not exist.

- [ ] **Step 3: Add the ledger schema and canonical empty ledger**

The ledger root must be exactly authority-free:

```json
{
  "version": 1,
  "routing_authority": false,
  "reasoning_authority": false,
  "records": []
}
```

Each future record schema must require:

```text
evidence_id
provider_id
model_id
model_family
capability
benchmark_id
benchmark_version
score
threshold
passed
measured_at
source_sha
environment
provenance
```

Require `score` and `threshold` in `[0,1]`, a 40-hex `source_sha`, non-empty immutable identifiers, and `additionalProperties:false`.

- [ ] **Step 4: Add the Active Candidate Index schema**

Require this root contract:

```text
schema_version = 1
source_sha = exact source revision
mode = FREE_ONLY
routing_authority = false
reasoning_authority = false
generated_at
hard_gate_policy
coverage
entries
```

Each entry is a bounded overlay, not a duplicate provider registry:

```json
{
  "candidate_key": "groq:openai/gpt-oss-120b",
  "provider_id": "groq",
  "model_id": "openai/gpt-oss-120b",
  "model_family": "gpt-oss-120b",
  "capability_evidence": {
    "text_reasoning": {
      "state": "PROVISIONAL",
      "score": 0.9,
      "evidence_ids": [],
      "measured_at": null
    }
  }
}
```

Allowed states are exactly `VERIFIED`, `PROVISIONAL`, `UNKNOWN`, `STALE`.

- [ ] **Step 5: Add rollout policy without enabling any hard gate**

Append to `domain_capabilities.yaml`:

```yaml
capability_evidence:
  routing_authority: false
  default_freshness_hours: 168
  hard_gate:
    default_enabled: false
    min_verified_candidates: 2
    min_coverage_ratio: 0.80
    overrides: {}
```

Do not change the existing domain weights or `weights_are_selection_metadata_only: true`.

- [ ] **Step 6: Register canonical paths in `checkpoint.json`**

Add the five keys from Step 1 adjacent to the existing Model Mesh pointers. Do not change the existing release, router, trading, or runtime pointers.

- [ ] **Step 7: Run tests and verify GREEN**

Run the same unittest command. Expected: PASS for path/policy/schema presence checks.

- [ ] **Step 8: Commit**

```bash
git add AI_SKILL_LIBRARY/checkpoint.json AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json AI_SKILL_LIBRARY/v4/schemas/capability_evidence_ledger.schema.json AI_SKILL_LIBRARY/v4/schemas/model_mesh_active_candidate_index.schema.json AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_capability_evidence.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_snapshot.py
git commit -m "feat(mesh): define capability evidence contracts"
```

---

### Task 2: Implement evidence normalization and freshness semantics

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/capability_evidence.py`
- Modify: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_capability_evidence.py`

**Interfaces:**
- Consumes: ledger root plus normalized model candidate.
- Produces:
  - `load_capability_ledger(root: Path, ledger_path: Path) -> dict`
  - `index_evidence_records(ledger: dict) -> dict[tuple[str, str, str], list[dict]]`
  - `capability_evidence_state(candidate: dict, capability: str, evidence_map: dict, *, now: str, freshness_hours: int) -> dict`

- [ ] **Step 1: Write failing state-machine tests**

Cover all four states with fixed timestamps:

```python
state = capability_evidence_state(candidate, "coding", evidence_map, now="2026-09-15T12:00:00Z", freshness_hours=168)
self.assertEqual(state["state"], "VERIFIED")
self.assertEqual(state["evidence_ids"], ["coding-bench-1"])
```

Also require:

```text
fresh passing measured record -> VERIFIED
fresh measured record below threshold -> PROVISIONAL
no measured record + provider declaration -> PROVISIONAL
no measured record + no declaration -> UNKNOWN
passing record older than freshness window -> STALE
record model_family mismatch -> ignored
record provider/model mismatch -> ignored
malformed timestamp -> never VERIFIED
```

- [ ] **Step 2: Run the test and verify RED**

```bash
python3 -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_capability_evidence -v
```

Expected: import failure for `capability_evidence.py`.

- [ ] **Step 3: Implement strict ledger loading**

Use `Draft202012Validator` against `capability_evidence_ledger.schema.json`. Reject invalid roots instead of skipping malformed measured records silently.

- [ ] **Step 4: Implement exact identity indexing**

Use exact tuple identity:

```python
key = (record["provider_id"], record["model_id"], record["capability"])
```

Before a record can verify a capability, additionally require `record["model_family"] == candidate["model_family"]`.

- [ ] **Step 5: Implement deterministic state evaluation**

Sort matching records by parsed `measured_at` descending, then by `evidence_id`. A record is `VERIFIED` only when:

```python
record["passed"] is True
and record["score"] >= record["threshold"]
and age_hours <= freshness_hours
and exact family/provider/model/capability identity matches
```

Provider metadata may only yield `PROVISIONAL`, never `VERIFIED`.

- [ ] **Step 6: Run tests and verify GREEN**

Run the Task 2 unittest command. Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/capability_evidence.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_capability_evidence.py
git commit -m "feat(mesh): evaluate measured capability evidence"
```

---

### Task 3: Compile and validate the bounded Active Candidate Index

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_active_index.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_active_index.py`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_active_index.py`

**Interfaces:**
- Consumes: validated `model-mesh-snapshot.json`, canonical ledger, `domain_capabilities.yaml`, exact source SHA.
- Produces: `compile_active_index(...) -> dict` and `validate_active_index(...) -> list[str]`.

- [ ] **Step 1: Write failing deterministic-index tests**

Required test shape:

```python
first = compile_active_index(
    ROOT,
    source_sha=SOURCE_SHA,
    snapshot_path=snapshot_path,
    ledger_path=ledger_path,
    capabilities_path=ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml",
    output=output_a,
    generated_at=GENERATED_AT,
)
second = compile_active_index(..., output=output_b, generated_at=GENERATED_AT)
self.assertEqual(first, second)
self.assertEqual(output_a.read_text(), output_b.read_text())
```

Assert the compiler emits entries only for models already present in the validated snapshot. A ledger record for an unadmitted model must never create a new index entry.

- [ ] **Step 2: Write failing coverage tests**

For each domain capability with weight at or above the existing `hard_capability_weight_threshold`, compute:

```text
eligible_candidates
verified_candidates
coverage_ratio = verified_candidates / eligible_candidates
requested_enabled
gate_eligible
enabled
```

Require `gate_eligible` only when both:

```text
verified_candidates >= 2
coverage_ratio >= 0.80
```

Require `enabled = requested_enabled and gate_eligible`.

- [ ] **Step 3: Write the fail-closed hard-gate test**

Create a temporary capabilities config with an override requesting a gate before coverage is eligible. The compiler must fail with a stable error containing:

```text
CAPABILITY_HARD_GATE_COVERAGE_INSUFFICIENT
```

- [ ] **Step 4: Run tests and verify RED**

```bash
python3 -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_active_index -v
```

Expected: compiler/validator imports missing.

- [ ] **Step 5: Implement `compile_active_index`**

Build `candidate_key` exactly as the current Python selector does:

```python
candidate_key = f"{candidate['provider_id']}:{candidate['model_id']}"
```

Sort entries by `(provider_id, model_id, model_family)`. Sort capability names and coverage keys. Never copy credentials, arbitrary discovery payload fields, or provider secrets into the index.

- [ ] **Step 6: Implement validation**

Validator must check:

```text
schema validity
source_sha exact match
FREE_ONLY mode
routing_authority=false
reasoning_authority=false
unique candidate_key
entry identity matches an admitted snapshot model
no index-only model creation
hard gate enabled only if gate_eligible=true
no unknown capability dimension
no credential-shaped field names or values
```

- [ ] **Step 7: Run tests and verify GREEN**

Run Task 3 unittest command. Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_active_index.py AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_active_index.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_active_index.py
git commit -m "feat(mesh): compile bounded active candidate index"
```

---

### Task 4: Integrate the index into canonical policy, CI and release hashing

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_policy.py`
- Modify: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`
- Modify: `AI_SKILL_LIBRARY/v4/tools/release.py`
- Modify: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_snapshot.py`
- Modify: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_active_index.py`

**Interfaces:**
- Consumes: Task 1 policy and Task 3 compiler/validator.
- Produces: runtime policy field `capability_evidence`, generated exact-SHA Active Candidate Index, and release-hashed canonical inputs.

- [ ] **Step 1: Write failing policy compiler assertions**

Require the compiled policy to include:

```python
self.assertEqual(contract["capability_evidence"]["default_freshness_hours"], 168)
self.assertFalse(contract["capability_evidence"]["hard_gate"]["default_enabled"])
self.assertEqual(contract["capability_evidence"]["hard_gate"]["min_verified_candidates"], 2)
self.assertEqual(contract["capability_evidence"]["hard_gate"]["min_coverage_ratio"], 0.80)
```

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
python3 -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_active_index AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_snapshot -v
```

Expected: compiled policy/CI/release assertions fail.

- [ ] **Step 3: Compile evidence rollout policy in `compile_model_mesh_policy.py`**

Validate bounds:

```text
default_freshness_hours: integer 1..8760
min_verified_candidates: integer >= 1
min_coverage_ratio: float 0..1
default_enabled: boolean and must remain false in this Phase A release
```

Emit the normalized block under `contract["capability_evidence"]`.

- [ ] **Step 4: Extend `_compile_model_snapshot` in `ci_validate.py`**

After snapshot validation succeeds, run:

```bash
python3 AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_active_index.py \
  --root . \
  --source-sha "$SOURCE_SHA" \
  --snapshot "$MODEL_SNAPSHOT" \
  --ledger AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json \
  --output AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-active-candidate-index.json

python3 AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_active_index.py \
  AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-active-candidate-index.json \
  --root . \
  --snapshot "$MODEL_SNAPSHOT" \
  --source-sha "$SOURCE_SHA"
```

The helper must run both in the initial compile and in the existing `finalize_exact_sha` pass.

- [ ] **Step 5: Add canonical inputs to `release.py`**

Hash at least:

```text
AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json
AI_SKILL_LIBRARY/v4/schemas/capability_evidence_ledger.schema.json
AI_SKILL_LIBRARY/v4/schemas/model_mesh_active_candidate_index.schema.json
AI_SKILL_LIBRARY/v4/tools/capability_evidence.py
AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_active_index.py
AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_active_index.py
```

Do not add runtime-generated JSON/JS outputs to the immutable source list.

- [ ] **Step 6: Run focused validation**

```bash
python3 AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)" --skip-tests
```

Expected: `CI_VALIDATE=PASS failures=0`.

- [ ] **Step 7: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_policy.py AI_SKILL_LIBRARY/v4/tools/ci_validate.py AI_SKILL_LIBRARY/v4/tools/release.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_snapshot.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_active_index.py
git commit -m "feat(mesh): integrate active index into validation pipeline"
```

---

### Task 5: Generate and inject the Active Candidate Index into the Worker

**Files:**
- Create: `cloudflare-worker/model-mesh/capability-evidence.js`
- Create: `cloudflare-worker/test-model-mesh-active-index.mjs`
- Modify: `cloudflare-worker/prepare-model-mesh.mjs`
- Modify: `cloudflare-worker/model-mesh-active.js`
- Modify: `cloudflare-worker/model-mesh-runtime.js`
- Modify: `cloudflare-worker/model-mesh-handler.js`
- Modify: `cloudflare-worker/package.json`

**Interfaces:**
- Consumes: `MODEL_MESH_SNAPSHOT` and generated `MODEL_MESH_ACTIVE_CANDIDATE_INDEX` with identical `source_sha`.
- Produces:
  - `applyCapabilityEvidence(models, activeIndex) -> enrichedModels`
  - `enabledHardCapabilities(activeIndex, domain) -> string[]`
  - handler config `{skillSnapshot, modelSnapshot, activeCandidateIndex, ...}`.

- [ ] **Step 1: Write failing Worker artifact tests**

In `test-model-mesh-active-index.mjs`, assert:

```js
assert.equal(index.schema_version,1);
assert.equal(index.mode,'FREE_ONLY');
assert.equal(index.routing_authority,false);
assert.equal(index.reasoning_authority,false);
assert.equal(index.source_sha,MODEL_MESH_SNAPSHOT.source_sha);
```

Also assert an empty canonical ledger does not remove any current snapshot model from eligibility solely because capability evidence is not yet VERIFIED.

- [ ] **Step 2: Run prepare + test and verify RED**

```bash
cd cloudflare-worker
npm run prepare:all
node test-model-mesh-active-index.mjs
```

Expected: missing generated Active Candidate Index module/test import.

- [ ] **Step 3: Extend `prepare-model-mesh.mjs`**

Read:

```text
../AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-active-candidate-index.json
```

Reject unless:

```js
activeIndex?.schema_version===1
activeIndex?.mode==='FREE_ONLY'
activeIndex?.routing_authority===false
activeIndex?.reasoning_authority===false
activeIndex?.source_sha===snapshot.source_sha
```

Emit:

```js
export const MODEL_MESH_ACTIVE_CANDIDATE_INDEX=Object.freeze(...)
```

into `cloudflare-worker/generated/model-mesh-active-candidate-index.js`.

- [ ] **Step 4: Implement exact-key evidence overlay**

`applyCapabilityEvidence()` must join only by exact `candidate_key = provider_id + ':' + model_id` and verify the entry family equals `model.model_family` before attaching `capability_evidence`.

If an index entry is absent or mismatched, attach no verified evidence; never guess by substring/model family alone.

- [ ] **Step 5: Inject index through active runtime**

Update `model-mesh-active.js`:

```js
import {MODEL_MESH_ACTIVE_CANDIDATE_INDEX} from './generated/model-mesh-active-candidate-index.js';
```

Pass it to `createModelMeshHandler` as `activeCandidateIndex`.

`buildModelMeshPlan` must reject configuration drift when:

```js
modelSnapshot.source_sha!==activeCandidateIndex.source_sha
```

with `MODEL_MESH_ACTIVE_INDEX_SOURCE_SHA_MISMATCH`.

- [ ] **Step 6: Add sanitized health diagnostics**

`/brain/mesh/health` may expose only aggregate evidence metadata:

```json
{
  "capabilityEvidence": {
    "indexLoaded": true,
    "verifiedRecords": 0,
    "enabledHardGates": 0
  }
}
```

Do not expose raw benchmark payloads, prompts, secrets, or private provider responses.

- [ ] **Step 7: Add the test to package scripts**

Append `node test-model-mesh-active-index.mjs` to both `test:model-mesh` and `check`.

- [ ] **Step 8: Run focused Worker tests**

```bash
npm run prepare:all
node test-model-mesh-active-index.mjs
node test-model-mesh-handler.mjs
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add cloudflare-worker/prepare-model-mesh.mjs cloudflare-worker/model-mesh/capability-evidence.js cloudflare-worker/model-mesh-active.js cloudflare-worker/model-mesh-runtime.js cloudflare-worker/model-mesh-handler.js cloudflare-worker/test-model-mesh-active-index.mjs cloudflare-worker/package.json
git commit -m "feat(mesh): load capability evidence index at runtime"
```

---

### Task 6: Make capability filtering evidence-aware without changing default selection

**Files:**
- Modify: `cloudflare-worker/model-mesh/contracts.js`
- Modify: `cloudflare-worker/model-mesh/selector.js`
- Modify: `cloudflare-worker/model-mesh/runtime-health.js`
- Modify: `cloudflare-worker/test-model-mesh-contracts.mjs`
- Modify: `cloudflare-worker/test-model-mesh-active-index.mjs`
- Modify: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_selection.py`

**Interfaces:**
- Consumes: enriched model `capability_evidence` and compiler-approved enabled gate list.
- Produces: existing rejection name `capability`; no new parallel selection authority.

- [ ] **Step 1: Write failing default-parity test**

A model with declared `supported:true` but `capability_evidence.text_reasoning.state === 'PROVISIONAL'` must remain eligible when no hard gate is enabled:

```js
assert.equal(selectionRejection(model,{
  requiredCapability:'text_reasoning',
  hardCapabilityGate:false,
} ),null);
```

- [ ] **Step 2: Write failing enabled-gate tests**

Require:

```js
assert.equal(selectionRejection(provisionalModel,{
  requiredCapability:'text_reasoning',
  hardCapabilityGate:true,
}),'capability');

assert.equal(selectionRejection(verifiedModel,{
  requiredCapability:'text_reasoning',
  hardCapabilityGate:true,
}),null);
```

A `STALE` or `UNKNOWN` state must also reject when the gate is enabled.

- [ ] **Step 3: Run JS tests and verify RED**

```bash
cd cloudflare-worker
npm run prepare:all
node test-model-mesh-contracts.mjs
node test-model-mesh-active-index.mjs
```

Expected: new assertions fail because `hardCapabilityGate` is ignored.

- [ ] **Step 4: Extend only the existing `capability` filter**

Keep the existing filter chain name. Implement:

```js
if(!capability||capability.supported!==true)return 'capability';
if(hardCapabilityGate&&model?.capability_evidence?.[requiredCapability]?.state!=='VERIFIED')return 'capability';
```

Do not add a second routing/filter authority.

- [ ] **Step 5: Apply only compiler-approved hard gates in `selector.js`**

Resolve the enabled list from the Active Candidate Index. With the Phase A canonical config, this list is empty, so current production behavior is preserved.

For a future enabled gate, require every enabled hard capability for the routed domain to be `VERIFIED`; scoring continues to use declared/measured capability scores as ranking metadata.

- [ ] **Step 6: Preserve health semantics**

`resolveLiveModels` must carry `capability_evidence` through health overlay merges without allowing evidence state to mint `LIVE_HEALTHY`; health and capability verification remain independent gates.

- [ ] **Step 7: Run Python and JS parity tests**

```bash
cd ..
python3 -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_selection -v
cd cloudflare-worker
npm run prepare:all
node test-model-mesh-contracts.mjs
node test-model-mesh-active-index.mjs
node test-model-mesh-resilience.mjs
```

Expected: PASS, including existing family dedupe, FAST zero, privacy, quota, health and graceful-zero tests.

- [ ] **Step 8: Commit**

```bash
git add cloudflare-worker/model-mesh/contracts.js cloudflare-worker/model-mesh/selector.js cloudflare-worker/model-mesh/runtime-health.js cloudflare-worker/test-model-mesh-contracts.mjs cloudflare-worker/test-model-mesh-active-index.mjs AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_selection.py
git commit -m "feat(mesh): gate capabilities on verified evidence when enabled"
```

---

### Task 7: Add security, boundedness and regression coverage

**Files:**
- Modify: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_active_index.py`
- Modify: `cloudflare-worker/test-model-mesh-active-index.mjs`
- Modify: `cloudflare-worker/test-secret-scan.mjs`
- Modify: `cloudflare-worker/test-model-mesh-resilience.mjs`

**Interfaces:**
- Consumes: completed Phase A compiler/runtime path.
- Produces: regression evidence for protected dimensions.

- [ ] **Step 1: Add adversarial ledger tests**

Inject ledger records containing extra fields such as `api_key`, `authorization`, or `prompt`. Schema/loader must reject the record/root; the compiler must never copy those fields into the generated index.

- [ ] **Step 2: Add stale and source-drift tests**

Require:

```text
stale measured evidence -> STALE, never VERIFIED
active-index source_sha != snapshot source_sha -> validator failure
runtime index SHA != snapshot SHA -> runtime configuration failure
```

- [ ] **Step 3: Add boundedness test**

Create 100 unrelated ledger records plus 3 admitted snapshot models. Assert the index contains exactly 3 entries and no request-time path iterates the unrelated ledger records.

- [ ] **Step 4: Add protected behavior tests**

Reassert:

```text
FAST -> workers=[]
SECRET -> external denied
unknown data class -> SECRET
same family -> one independent worker
all providers unavailable -> graceful zero
hard gates disabled -> prior worker set unchanged
capability evidence cannot create LIVE_HEALTHY
```

- [ ] **Step 5: Run complete Model Mesh tests**

```bash
cd cloudflare-worker
npm run prepare:all
npm run test:model-mesh
```

Expected: all tests PASS.

- [ ] **Step 6: Run Python Model Mesh suite**

```bash
cd ..
python3 -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_adaptive_free_model_mesh_*.py'
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_active_index.py cloudflare-worker/test-model-mesh-active-index.mjs cloudflare-worker/test-secret-scan.mjs cloudflare-worker/test-model-mesh-resilience.mjs
git commit -m "test(mesh): prove capability index safety and parity"
```

---

### Task 8: Full validation, release promotion and exact-SHA production proof

**Files:**
- Modify only if generated by canonical tooling: release manifests/history/current pointer according to `release.py`.
- Do not manually edit generated release hashes or runtime generated artifacts.

**Interfaces:**
- Consumes: all Phase A tasks green.
- Produces: one exact-SHA verified production revision or a blocked/rolled-back promotion with the previous known-good release preserved.

- [ ] **Step 1: Run the complete Worker suite**

```bash
cd cloudflare-worker
npm run prepare:all
npm run check
```

Expected: all Worker checks PASS.

- [ ] **Step 2: Run canonical repository validation**

```bash
cd ..
python3 AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
```

Expected: `CI_VALIDATE=PASS failures=0`.

- [ ] **Step 3: Verify release state before building a new patch**

```bash
python3 AI_SKILL_LIBRARY/v4/tools/release.py verify
python3 AI_SKILL_LIBRARY/v4/tools/release.py check
```

Expected: zero verification errors and current release check PASS.

- [ ] **Step 4: Compute the next patch version from the current pointer**

```bash
NEXT_VERSION="$(python3 - <<'PY'
import json
from pathlib import Path
v=json.loads(Path('AI_SKILL_LIBRARY/v4/releases/current.json').read_text())['version']
major,minor,patch=map(int,v.split('.'))
print(f'{major}.{minor}.{patch+1}')
PY
)"
echo "$NEXT_VERSION"
```

This avoids hard-coding a version if `main` advances before execution.

- [ ] **Step 5: Build the validated candidate release using the canonical tool**

```bash
python3 AI_SKILL_LIBRARY/v4/tools/release.py build --version "$NEXT_VERSION" --validated
python3 AI_SKILL_LIBRARY/v4/tools/release.py verify
python3 AI_SKILL_LIBRARY/v4/tools/release.py check
```

Expected: release manifest/hashes are generated by tooling and verification passes. Do not set `known_good` before production proof.

- [ ] **Step 6: Commit release-tool outputs**

```bash
git status --short
git add AI_SKILL_LIBRARY/v4/releases AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml AI_SKILL_LIBRARY/checkpoint.json
git commit -m "release: prepare capability evidence phase A"
```

Only add files actually generated/required by canonical tooling; generated Model Mesh runtime JSON/JS remains uncommitted.

- [ ] **Step 7: Push the implementation branch and open/review the PR**

Require PR checks to include the full Worker suite, canonical validators, release checks and deploy-safety tests. Do not merge a failing or skipped protected check.

- [ ] **Step 8: Merge only after review and let the sole gated deploy workflow run**

The deployment authority remains `.github/workflows/deploy-skill-mandatory-fast-gateway.yml`. Do not add or invoke a second Worker deploy authority.

- [ ] **Step 9: Verify exact-SHA production invariants**

From the gated deployment evidence require all of:

```text
runtime_revision == current main SHA
FINAL_EXACT_SHA_GATE=PASS
FAST_EXTERNAL_BOUNDARY=PASS external_workers=0 externalRoutingCalls=0
SECRET_EXTERNAL_BOUNDARY=PASS
DATACLASS_FAIL_CLOSED=PASS
MODEL_MESH_MODE=FREE_ONLY
Active Candidate Index source_sha == model snapshot source_sha == current main SHA
hard capability gates enabled = 0 for the initial Phase A release
provider failure still degrades gracefully
```

- [ ] **Step 10: Mark known-good only after exact-SHA production proof**

Run the canonical release tool for the same `$NEXT_VERSION` with the repository's existing known-good promotion path, then verify `current.json`, `history.yaml`, and production deployment record agree. If the exact-SHA gate fails, do not mark known-good; preserve/restore the previous verified production target.

- [ ] **Step 11: Record Phase A completion evidence**

Add a bounded checkpoint/report under `CHECKPOINTS/` containing the exact main SHA, release version, CI result, production exact-SHA result, enabled hard-gate count (`0` initially), and any unresolved non-blocking items. Do not claim any capability `VERIFIED` unless a ledger record supports it.

---

## Self-Review Checklist Applied to This Plan

- Spec §5 Capability Evidence Ledger: Tasks 1–3.
- Spec §5.3 hard-gate rollout: Tasks 1, 3, 6.
- Spec §6 bounded Canonical Active Candidate Index: Tasks 3–5, 7.
- Spec §7 discovery does not auto-promote: preserved because Phase A consumes only the already-admitted snapshot; unrelated ledger/discovery rows cannot create entries.
- Spec §10 FAST/DEEP boundaries: Tasks 6–8 preserve existing compiled limits; no adaptive fan-out is introduced in Phase A.
- Spec §11 family dedupe/no majority vote: regression-covered in Tasks 6–7.
- Spec §12 KV/runtime scaling: the new index is build-time derived; request-time code does not scan an unbounded discovered-model universe.
- Spec §16 security/privacy: ledger schema is fail-closed; raw prompts/secrets/provider payloads are excluded; SECRET remains external-zero.
- Spec §17 existing promotion/release model: Tasks 4 and 8 reuse `ci_validate.py`, `release.py`, and sole exact-SHA deploy authority.
- Spec §18 Phase A decomposition: this plan implements only Capability Evidence + Active Candidate Index. Agent Skills, Graphify, Ponytail, OmniRoute, Dynamic Discovery, Legion runtime and Adaptive Parallel Execution each require their own subsequent plan.
- Placeholder scan: no `TBD`, `TODO`, "implement later", or undefined cross-task interface remains.
- Type/interface consistency: exact candidate identity is `provider_id:model_id`; family equality is a separate mandatory check; generated index source SHA is required to equal snapshot source SHA at compiler, validator, build and runtime boundaries.
