# Adaptive Free Model Mesh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to execute this plan. Do not skip TDD, verification, or exact-SHA release checks.

**Goal:** Implement the approved Adaptive Free Model Mesh as a cloud-first, FREE_ONLY, multidisciplinary provider/model execution layer that discovers as many legitimately free/free-tier models as practical, assigns only the smallest useful complementary worker set to routed STANDARD/DEEP subtasks, handles quota/health/fallback automatically, and never creates a second reasoning authority.

**Architecture:** Keep the existing `task_router -> primary skill -> capsule` path unchanged. Add a separate `model_mesh` namespace for provider/model metadata, discovery, scoring, quota state, task decomposition, conflict handling, and Cloudflare execution after canonical routing. Evergreen discovers and quarantines model/provider candidates; Stable consumes only a last-known-good compiled model-mesh snapshot. `/brain/route` remains zero-network and never calls a provider. External model execution lives only under separate `/brain/mesh/*` endpoints and is disabled by default until an approved cloud secret/entitlement exists.

**Tech Stack:** Python 3.12, PyYAML, jsonschema, Node.js 22, Cloudflare Workers/Wrangler, GitHub Actions, provider HTTPS APIs, OpenAI-compatible provider adapters where possible, native Gemini/Cloudflare adapters where required.

**Spec:**
- `docs/superpowers/specs/2026-09-15-adaptive-free-model-mesh-design.md`
- `docs/superpowers/specs/2026-09-15-adaptive-free-model-mesh-multidomain-extension-design.md`

## Global Constraints

- Preserve one canonical Brain authority: providers/models are execution/evidence resources only.
- Preserve exactly one `task_router`, one primary domain, one primary skill, and one validated capsule per routed request.
- Preserve FAST invariants: no model-mesh execution, no provider/network call for routing, `externalRoutingCalls=0`, current p95 benchmark contract unchanged.
- Preserve current concurrency ceiling: STANDARD <= 2 independent nodes; DEEP <= 4; do not increase hard limits in this implementation.
- Initial operating mode is `FREE_ONLY`: unknown billing/free state is excluded; no silent paid fallback; no auto-purchase/top-up.
- Do not implement IP rotation, account cycling, key farming, proxy/region hopping, or any quota/rate-limit circumvention.
- Never commit API keys, bearer tokens, credentials, private keys, wallet material, or raw private prompts.
- `SECRET` data never leaves to an external free endpoint. `INTERNAL`/`CONFIDENTIAL` require an explicitly compatible provider privacy classification.
- No provider/model output may majority-vote truth. Conflicts resolve through current authority/evidence or an explicit checker/verifier.
- Model-family deduplication is mandatory: multiple providers hosting the same underlying model increase availability, not epistemic independence.
- Trading mesh use remains read-only analysis/research and must not add order/wallet/leverage/account mutation capability.
- Stable must work when the entire model mesh or Evergreen discovery is unavailable.
- All behavior changes follow RED -> minimum GREEN -> regression -> canonical validators -> CI -> exact-SHA deployment verification.
- Current approved baseline at plan creation is release `4.8.1`; this human-authorized Class C architecture change targets `4.9.0` only after all release gates pass.

## Upstream patterns to absorb, not install as parallel authority

Register these as reference/capability sources under existing harmonization rules:

- `anomalyco/models.dev` (MIT): provider/model catalog, capability/pricing metadata, model-family identity.
- `anomalyco/opencode` (MIT): provider discovery/plugin-order patterns, OpenCode Zen adapter patterns, broad provider compatibility.
- `Portkey-AI/models` (MIT): supplementary model/provider pricing/config metadata.
- `Portkey-AI/gateway` (MIT): retry/fallback/load-balancing/conditional-routing patterns; start reference-only, no wholesale gateway replacement.
- `vllm-project/semantic-router` (Apache-2.0): Mixture-of-Models capability selection, policy signals, route evaluation patterns.
- `microsoft/agent-framework` (MIT): bounded sequential/concurrent/handoff workflow patterns.
- Keep existing `langchain-ai/langgraph`, `pydantic/pydantic-ai`, `openai/openai-agents-python`, `google/adk-python`, `promptfoo/promptfoo`, `NVIDIA/garak`, and related approved references.
- Keep `BerriAI/litellm` design-reference-only under the current license policy; do not copy code.
- Do not adopt `microsoft/autogen` as a new foundation because it is in maintenance mode; Microsoft Agent Framework is the successor reference.

---

## Task 1: Add model-mesh policy namespace and upstream intake

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml`
- Create: `AI_SKILL_LIBRARY/v4/model_mesh/upstreams.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml` under `upstream_pattern_map`
- Modify: `AI_SKILL_LIBRARY/v4/index/workspace_map.yaml` under `groups`, `WARM`, `tools`, and `tests`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_upstreams.py`

- [ ] **Step 1: Write the failing upstream/policy tests.**

Test exact invariants:

```python
class AdaptiveFreeModelMeshUpstreamTests(unittest.TestCase):
    def test_policy_is_free_only_and_not_routing_authority(self):
        p = self._yaml("AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml")
        self.assertEqual(p["mode"], "FREE_ONLY")
        self.assertFalse(p["routing_authority"])
        self.assertFalse(p["reasoning_authority"])
        self.assertEqual(p["max_parallel"]["DEEP"], 4)
        self.assertEqual(p["max_parallel"]["STANDARD"], 2)
        self.assertEqual(p["max_parallel"]["FAST"], 0)
        self.assertTrue(p["quota"]["circumvention_forbidden"])

    def test_reference_sources_are_registered_without_authority(self):
        rows = self._yaml("AI_SKILL_LIBRARY/v4/model_mesh/upstreams.yaml")["sources"]
        by_id = {row["id"]: row for row in rows}
        for source_id in (
            "anomalyco/models.dev",
            "anomalyco/opencode",
            "Portkey-AI/models",
            "Portkey-AI/gateway",
            "vllm-project/semantic-router",
            "microsoft/agent-framework",
        ):
            self.assertIn(source_id, by_id)
            self.assertFalse(by_id[source_id]["routing_authority"])
            self.assertFalse(by_id[source_id]["reasoning_authority"])
```

- [ ] **Step 2: Run RED.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_upstreams -v
```

Expected: FAIL because `v4/model_mesh/*` does not exist.

- [ ] **Step 3: Add the minimum policy.**

`policy.yaml` must include this contract:

```yaml
version: 1
mode: FREE_ONLY
routing_authority: false
reasoning_authority: false
stable_request_dependency: false
discovery_plane: evergreen_only
stable_snapshot_only: true
free_status_unknown_action: exclude
paid_fallback: disabled
auto_purchase: false
max_parallel: {FAST: 0, STANDARD: 2, DEEP: 4}
provider_voting: forbidden
same_family_counts_as_independent_reasoning: false
quota:
  respect_provider_reset: true
  use_runtime_headers_first: true
  cooldown_on_exhaustion: true
  circumvention_forbidden: true
privacy:
  SECRET: deny_external_free
  CONFIDENTIAL: verified_provider_only
  INTERNAL: verified_provider_only
  PUBLIC: eligible_free_pool
```

- [ ] **Step 4: Register the six new upstream references in `upstreams.yaml` and mirror their approved-reference patterns in `stable/capability_fusion.yaml`.**

Use explicit licenses and `code_reuse: false` initially for all six. Absorb only metadata/routing/workflow patterns; do not make any external framework mandatory.

- [ ] **Step 5: Add `AI_SKILL_LIBRARY/v4/model_mesh` to the WARM workspace map. Do not add it to HOT.**

- [ ] **Step 6: Run GREEN.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_upstreams -v
```

- [ ] **Step 7: Commit.**

```bash
git add AI_SKILL_LIBRARY/v4/model_mesh AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml AI_SKILL_LIBRARY/v4/index/workspace_map.yaml AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_upstreams.py
git commit -m "feat: define adaptive free model mesh policy"
```

---

## Task 2: Define provider/model schemas, normalization, and model-family dedupe

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/schemas/model_mesh_provider.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/model_mesh_snapshot.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/tools/model_mesh.py`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_registry.py`

- [ ] **Step 1: Write failing registry tests covering required fields, `FREE_ONLY`, privacy, and family dedupe.**

The Python public surface must be:

```python
def normalize_candidate(provider_id: str, raw: dict, *, observed_at: str) -> dict: ...
def classify_free_status(raw: dict) -> str: ...
def model_family_key(candidate: dict) -> str: ...
def dedupe_model_families(candidates: list[dict]) -> dict[str, list[dict]]: ...
def eligible_free_candidate(candidate: dict, *, data_class: str) -> bool: ...
```

Tests must prove:

```python
self.assertFalse(eligible_free_candidate(dict(base, free_status="unknown"), data_class="PUBLIC"))
self.assertFalse(eligible_free_candidate(dict(base, free_status="paid"), data_class="PUBLIC"))
self.assertFalse(eligible_free_candidate(base, data_class="SECRET"))
self.assertEqual(len(dedupe_model_families([groq_gpt_oss, cerebras_gpt_oss])), 1)
```

- [ ] **Step 2: Run RED.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_registry -v
```

- [ ] **Step 3: Implement deterministic normalization.**

Normalized entries must include at least:

```text
provider_id, provider_class, model_id, model_family, model_variant,
endpoint_family, free_status, free_verified_at, quota_scope,
quota_dimensions, reset_semantics, capabilities, context_window,
privacy_class, data_training_allowed_by_provider, retention_policy,
usage_terms, health, latency_ema_ms, success_rate_ema,
quality_scores, last_benchmark_at, source_evidence
```

`model_family_key()` must lowercase, trim provider-only suffixes when a canonical family is supplied by source metadata, and never infer two unrelated model names are identical merely by substring.

- [ ] **Step 4: Validate normalized objects with `jsonschema`; unknown required semantics fail closed.**

- [ ] **Step 5: Run GREEN and full neighboring tests.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_registry -v
python -m unittest AI_SKILL_LIBRARY.tests.test_brain_4_6_open_source_fusion AI_SKILL_LIBRARY.tests.test_brain_4_8_continuous_intelligence -v
```

- [ ] **Step 6: Commit.**

```bash
git add AI_SKILL_LIBRARY/v4/schemas AI_SKILL_LIBRARY/v4/tools/model_mesh.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_registry.py
git commit -m "feat: add free model registry contracts"
```

---

## Task 3: Build dynamic free-model discovery outside the request path

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/model_mesh/providers.yaml`
- Create: `AI_SKILL_LIBRARY/v4/model_mesh/discovery.yaml`
- Create: `AI_SKILL_LIBRARY/v4/tools/discover_free_models.py`
- Create: `AI_SKILL_LIBRARY/tests/fixtures/model_mesh/models_dev.json`
- Create: `AI_SKILL_LIBRARY/tests/fixtures/model_mesh/opencode_zen.json`
- Create: `AI_SKILL_LIBRARY/tests/fixtures/model_mesh/portkey_models.json`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_discovery.py`

- [ ] **Step 1: Write fixture-driven RED tests; tests must never depend on live network.**

Public parser surface:

```python
def parse_models_dev(payload: object, observed_at: str) -> list[dict]: ...
def parse_opencode_zen(payload: object, observed_at: str) -> list[dict]: ...
def parse_portkey_models(payload: object, observed_at: str) -> list[dict]: ...
def merge_candidates(*groups: list[dict]) -> list[dict]: ...
def discover(*, output: Path, fixture_dir: Path | None = None) -> dict: ...
```

Prove that appearing in an aggregator catalog does **not** make a model free automatically:

```python
self.assertEqual(candidate["free_status"], "unknown")
self.assertFalse(eligible_free_candidate(candidate, data_class="PUBLIC"))
```

- [ ] **Step 2: Run RED.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_discovery -v
```

- [ ] **Step 3: Implement source adapters using Python stdlib `urllib.request`; no new dependency is needed.**

Use Models.dev/OpenCode/Portkey metadata as discovery evidence, then keep provider/account free entitlement as a separate verification field. `providers.yaml` must also register first-party evidence URLs for Groq, Gemini, Cloudflare Workers AI, OpenRouter, Mistral, Cohere, Hugging Face Inference Providers, NVIDIA NIM, Cerebras, SambaNova, and Alibaba Model Studio.

- [ ] **Step 4: Implement CLI.**

```bash
python AI_SKILL_LIBRARY/v4/tools/discover_free_models.py \
  --root . \
  --output /tmp/v4-free-model-mesh-candidates.json
```

The report must be quarantine-only:

```json
{
  "state": "quarantine",
  "routing_authority": false,
  "stable_mutation": false,
  "candidates": []
}
```

- [ ] **Step 5: Run GREEN.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_discovery -v
```

- [ ] **Step 6: Commit.**

```bash
git add AI_SKILL_LIBRARY/v4/model_mesh AI_SKILL_LIBRARY/v4/tools/discover_free_models.py AI_SKILL_LIBRARY/tests/fixtures/model_mesh AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_discovery.py
git commit -m "feat: add evergreen free model discovery"
```

---

## Task 4: Add multidomain capability matching and bounded worker selection

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/tools/model_mesh.py`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_multidomain.py`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_selection.py`

- [ ] **Step 1: Write RED tests for every canonical domain in `v4/mesh/graph.yaml`.**

Required capability dimensions:

```text
text_reasoning, coding, math_quant, long_context, multilingual,
vision, structured_output, tool_calling, planning, creative_writing,
prompt_media, research_synthesis, data_analysis, low_latency
```

Public selection surface:

```python
def required_capabilities(domain: str, primary_skill: str, *, has_image: bool = False) -> dict[str, float]: ...
def score_candidate(candidate: dict, requirements: dict[str, float], *, quota_headroom: float, reputation: float) -> float: ...
def select_workers(task: dict, candidates: list[dict], *, max_workers: int) -> list[dict]: ...
```

Tests must prove:

- all 12 canonical domains resolve to capability requirements;
- `FAST` returns zero workers;
- STANDARD cannot select >2;
- DEEP cannot select >4;
- a same-family second provider is fallback capacity and does not consume a diversity slot while a comparably qualified different family exists;
- a weak free model is not preferred solely because it has more quota;
- trading selections retain `research_only=true`.

- [ ] **Step 2: Run RED.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_multidomain AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_selection -v
```

- [ ] **Step 3: Implement filter-before-score selection.**

Candidate filtering order must be:

```text
capability -> permission ceiling -> privacy/data class -> health -> free entitlement -> quota -> context fit -> usage terms -> score
```

Use bounded weights configured in `policy.yaml`; do not let model reputation override any gate.

- [ ] **Step 4: Implement complementary roles.**

Allowed role labels: `maker`, `researcher`, `specialist`, `critic`, `checker`, `grader`, `summarizer`. Role selection is execution metadata, not a second router.

- [ ] **Step 5: Run GREEN.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_multidomain AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_selection -v
```

- [ ] **Step 6: Commit.**

```bash
git add AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml AI_SKILL_LIBRARY/v4/tools/model_mesh.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_multidomain.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_selection.py
git commit -m "feat: route multidomain model mesh workers"
```

---

## Task 5: Implement quota, cooldown, circuit-breaker, and reputation state

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/model_mesh.py`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_quota.py`
- Modify: `AI_SKILL_LIBRARY/v4/stable/reliability.yaml` only to reference the model-mesh quota contract; do not weaken existing retry ceilings
- Modify: `AI_SKILL_LIBRARY/v4/stable/reputation.yaml` only to add provider/model-path task-class signals; preserve bounded 0..1 semantics

- [ ] **Step 1: Write RED state-machine tests.**

Public surface:

```python
def apply_quota_event(state: dict, event: dict, *, now: str) -> dict: ...
def provider_available(state: dict, *, now: str) -> bool: ...
def next_probe_at(state: dict) -> str | None: ...
```

State machine:

```text
AVAILABLE -> LOW_HEADROOM -> COOLDOWN_QUOTA -> PROBE_READY -> AVAILABLE
AVAILABLE -> DEGRADED -> CIRCUIT_OPEN -> HALF_OPEN -> AVAILABLE
```

Tests must prove 429 honors provider reset/retry metadata, invalid credentials never retry, three transient failures open the circuit, and no event produces any `rotate_ip`, `new_account`, `new_key`, or bypass action.

- [ ] **Step 2: Run RED.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_quota -v
```

- [ ] **Step 3: Implement immutable state transitions and sanitized reputation updates.**

Prefer runtime headers/API reset metadata over static schedules. Persist operational fields only: provider/model id, status, timestamps, latency, success/failure class, quota headroom; never raw prompts or tokens.

- [ ] **Step 4: Run GREEN plus current reliability/reputation tests.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_quota -v
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_*reputation*.py' -v
```

- [ ] **Step 5: Commit.**

```bash
git add AI_SKILL_LIBRARY/v4/tools/model_mesh.py AI_SKILL_LIBRARY/v4/stable/reliability.yaml AI_SKILL_LIBRARY/v4/stable/reputation.yaml AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_quota.py
git commit -m "feat: add quota aware model mesh recovery"
```

---

## Task 6: Compile and validate a last-known-good model-mesh snapshot

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_snapshot.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_snapshot.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_model_mesh.py`
- Modify: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/v4/tools/release.py`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_snapshot.py`

- [ ] **Step 1: Write RED tests for checkpoint paths, snapshot schema, deterministic ordering, no secrets, and release inclusion.**

Checkpoint additions must be exactly:

```json
"model_mesh_policy_path": "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml",
"model_mesh_provider_registry_path": "AI_SKILL_LIBRARY/v4/model_mesh/providers.yaml",
"model_mesh_domain_capabilities_path": "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml",
"model_mesh_snapshot_schema_path": "AI_SKILL_LIBRARY/v4/schemas/model_mesh_snapshot.schema.json",
"model_mesh_snapshot_compiler_path": "AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_snapshot.py",
"model_mesh_snapshot_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_snapshot.py"
```

- [ ] **Step 2: Run RED.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_snapshot -v
```

- [ ] **Step 3: Implement deterministic snapshot compile.**

Command:

```bash
python AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_snapshot.py \
  --root . \
  --source-sha "$SOURCE_SHA" \
  --candidates /tmp/v4-free-model-mesh-candidates.json \
  --output AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json
```

The compiler may include only candidates that passed the configured free-status, privacy, capability, health, provenance, and benchmark gates. It must never copy credentials or raw provider payloads into the snapshot.

- [ ] **Step 4: Add `validate_model_mesh.py` to `VALIDATORS` in `ci_validate.py`, compile/validate the model snapshot after the skill snapshot, and add stable model-mesh policy files to `release.py` `RELEASE_FILES`.**

Do not manually edit release hashes.

- [ ] **Step 5: Run GREEN.**

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_snapshot -v
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$SOURCE_SHA" --skip-tests
```

- [ ] **Step 6: Commit.**

```bash
git add AI_SKILL_LIBRARY/checkpoint.json AI_SKILL_LIBRARY/v4/tools AI_SKILL_LIBRARY/v4/schemas AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_snapshot.py
git commit -m "feat: compile validated model mesh snapshots"
```

---

## Task 7: Extend Continuous Intelligence and Evergreen discovery

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml`
- Modify: `.github/workflows/ai-brain-evergreen-scan.yml`
- Modify: `AI_SKILL_LIBRARY/tests/test_brain_4_8_continuous_intelligence.py`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_evergreen.py`

- [ ] **Step 1: Write RED tests that require model-catalog discovery to be Evergreen-only and hourly, with Stable request dependency false.**

Required contract addition:

```yaml
model_mesh_discovery:
  plane: evergreen_only
  cadence: hourly
  stable_request_dependency: false
  output_state: quarantine
  free_status_revalidation: true
  privacy_terms_revalidation: true
  model_family_dedupe: true
  auto_permission_expansion: false
```

- [ ] **Step 2: Run RED.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_evergreen -v
```

- [ ] **Step 3: Extend the existing hourly GitHub Actions scan.**

After the existing GitHub skill scan, add:

```bash
python AI_SKILL_LIBRARY/v4/tools/discover_free_models.py \
  --root . \
  --output /tmp/v4-free-model-mesh-candidates.json
```

Upload it in the existing `v4-evergreen-source-refresh` artifact. The workflow remains `contents: read` and must not push to `main`.

- [ ] **Step 4: Run GREEN and Continuous Intelligence regression tests.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_evergreen AI_SKILL_LIBRARY.tests.test_brain_4_8_continuous_intelligence -v
```

- [ ] **Step 5: Commit.**

```bash
git add AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml .github/workflows/ai-brain-evergreen-scan.yml AI_SKILL_LIBRARY/tests
git commit -m "feat: discover free models in evergreen plane"
```

---

## Task 8: Add Cloudflare model-mesh planner without touching FAST routing behavior

**Files:**
- Create: `cloudflare-worker/model-mesh/contracts.js`
- Create: `cloudflare-worker/model-mesh/selector.js`
- Create: `cloudflare-worker/model-mesh/task-graph.js`
- Create: `cloudflare-worker/model-mesh/quota-state.js`
- Create: `cloudflare-worker/model-mesh/conflict.js`
- Create: `cloudflare-worker/model-mesh-handler.js`
- Create: `cloudflare-worker/model-mesh-runtime.js`
- Create: `cloudflare-worker/prepare-model-mesh.mjs`
- Create: `cloudflare-worker/test-model-mesh.mjs`
- Create: `cloudflare-worker/test-model-mesh-handler.mjs`
- Modify: `cloudflare-worker/index.js`
- Modify: `cloudflare-worker/package.json`

- [ ] **Step 1: Write RED JS tests first.**

Required endpoints:

```text
GET  /brain/mesh/health
POST /brain/mesh/plan
```

`/brain/mesh/plan` is selection-only and must not call an external model. It receives `{text, dataClass?, hasImage?}`, routes through the existing local Skill Gateway snapshot, rejects FAST/high-risk ineligible routes, and returns a bounded task/worker plan from the compiled model snapshot.

Tests must assert:

```js
assert.equal(plan.route.externalRoutingCalls, 0);
assert.equal(plan.profile === 'FAST' ? plan.workers.length : true, true);
assert.ok(plan.workers.length <= 4);
assert.equal(externalFetchCount, 0);
```

- [ ] **Step 2: Run RED.**

```bash
cd cloudflare-worker
node test-model-mesh.mjs
node test-model-mesh-handler.mjs
```

- [ ] **Step 3: Implement the minimum planner.**

Use the existing `ACTIVE_SKILL_GATEWAY_SNAPSHOT`; do not add provider lookup to `skill-gateway-handler.js` or `/brain/route`. Wire `handleModelMesh` in `index.js` **after** `handleSkillGateway` and before unrelated domain handlers.

- [ ] **Step 4: Generate a JS snapshot module from the validated JSON snapshot.**

`prepare-model-mesh.mjs` must write only `cloudflare-worker/generated/model-mesh-snapshot.js` from the compiled sanitized snapshot and fail if source SHA does not match `GITHUB_SHA`.

- [ ] **Step 5: Add package scripts.**

```json
"test:model-mesh": "node test-model-mesh.mjs && node test-model-mesh-handler.mjs",
"prepare:model-mesh": "node prepare-model-mesh.mjs"
```

Extend `check` so both existing Skill Gateway tests and model-mesh tests run.

- [ ] **Step 6: Run GREEN and FAST regressions.**

```bash
npm run prepare:skill-gateway
npm run prepare:model-mesh
npm run check
node benchmark-skill-gateway.mjs
```

Expected: existing FAST p95 limit and `externalRoutingCalls=0` remain unchanged.

- [ ] **Step 7: Commit.**

```bash
git add cloudflare-worker
git commit -m "feat: add bounded model mesh planner runtime"
```

---

## Task 9: Add disabled-by-default FREE_ONLY provider execution adapters

**Files:**
- Create: `cloudflare-worker/model-mesh/provider-client.js`
- Create: `cloudflare-worker/model-mesh/providers/openai-compatible.js`
- Create: `cloudflare-worker/model-mesh/providers/gemini.js`
- Create: `cloudflare-worker/model-mesh/providers/cloudflare-ai.js`
- Modify: `cloudflare-worker/model-mesh-handler.js`
- Create: `cloudflare-worker/test-model-mesh-execute.mjs`
- Modify: `cloudflare-worker/package.json`

- [ ] **Step 1: Write RED execution-security tests.**

Add endpoint:

```text
POST /brain/mesh/execute
```

Required default behavior:

```js
MODEL_MESH_EXECUTION_ENABLED !== '1'  -> 503 mesh_execution_disabled
missing/invalid MODEL_MESH_EXECUTION_TOKEN -> 401 unauthorized
FAST route -> 409 mesh_ineligible_fast
SECRET dataClass -> 403 data_class_forbidden
unknown/paid free_status -> provider excluded
```

Tests must also prove sanitized error output never contains API keys or Authorization headers and 429 produces a cooldown result with reset metadata rather than repeated hammering.

- [ ] **Step 2: Run RED.**

```bash
cd cloudflare-worker
node test-model-mesh-execute.mjs
```

- [ ] **Step 3: Implement one generic OpenAI-compatible adapter.**

Use it for configured compatible providers such as Groq, OpenRouter, OpenCode Zen, Mistral, Cerebras, SambaNova, and future compatible endpoints. Provider URL/model/key-env-name come from the sanitized snapshot/config; the secret value comes only from Worker `env`.

Public adapter signature:

```js
export async function callOpenAICompatible({baseUrl, apiKey, model, messages, timeoutMs, fetchImpl=fetch}) { ... }
```

- [ ] **Step 4: Implement native Gemini and Cloudflare Workers AI adapters only where protocol compatibility requires it.**

Do not add a separate adapter per brand when the generic adapter is sufficient.

- [ ] **Step 5: Implement bounded parallel execution.**

Use `Promise.allSettled()` only for independent worker nodes already admitted by the task graph. Enforce current profile limits before network calls. On orchestrator failure, fall back serially per the existing reliability policy.

- [ ] **Step 6: Normalize worker output before merge.**

Required returned metadata:

```text
task_id, subtask_id, input_hash, authority_revision, primary_skill_id,
capsule_hash, domain_label, worker_role, provider_id, model_id,
model_family, started_at, completed_at, latency_ms, quota_state,
source_refs, verification_status
```

Never return or persist hidden reasoning.

- [ ] **Step 7: Run GREEN.**

```bash
node test-model-mesh-execute.mjs
npm run check
```

- [ ] **Step 8: Commit.**

```bash
git add cloudflare-worker/model-mesh cloudflare-worker/model-mesh-handler.js cloudflare-worker/test-model-mesh-execute.mjs cloudflare-worker/package.json
git commit -m "feat: execute free model mesh workers safely"
```

**Credential activation note:** code integration can be completed without provider keys. Real provider execution may only be marked ACTIVE after the corresponding Cloudflare secret/account entitlement is configured and runtime smoke-tested. Do not ask the user to paste secrets into chat or commit them to GitHub.

---

## Task 10: Add multidisciplinary benchmark/eval gates and conflict tests

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/model_mesh/benchmarks.yaml`
- Create: `AI_SKILL_LIBRARY/v4/tools/evaluate_model_mesh.py`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_evals.py`
- Create: `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_conflicts.py`

- [ ] **Step 1: Write RED tests requiring at least one representative case for every canonical Brain domain.**

Benchmark cases must cover:

```text
core, engineering, trading, game, design_2d, design_3d, adobe,
prompt_media, writing, academic, data_docs, business
```

Include adversarial cases for unsupported factual claims, fake live trading state, schema-invalid output, same-family duplicate providers, privacy mismatch, same-resource write conflict, and contradictory worker outputs.

- [ ] **Step 2: Run RED.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_evals AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_conflicts -v
```

- [ ] **Step 3: Implement offline evaluator.**

The evaluator scores selection/contract correctness without requiring paid or credentialed live model calls. Live canary quality metrics are a separate optional evidence input after credentials exist.

Protected dimensions stay zero-regression:

```text
correctness, authority, security, verification, project_isolation, no_secret_leakage, FAST_latency_contract
```

- [ ] **Step 4: Run GREEN.**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_evals AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_conflicts -v
```

- [ ] **Step 5: Commit.**

```bash
git add AI_SKILL_LIBRARY/v4/model_mesh/benchmarks.yaml AI_SKILL_LIBRARY/v4/tools/evaluate_model_mesh.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_evals.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_conflicts.py
git commit -m "test: add multidisciplinary model mesh evals"
```

---

## Task 11: Build the human-authorized 4.9.0 release and run complete validation

**Files:**
- Modify/generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/4.9.0/manifest.yaml`
- Modify/generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Modify/generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/history.yaml`
- Modify: `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md`
- Modify: `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml` through its builder only

- [ ] **Step 1: Run the entire unit suite before building the release.**

```bash
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_*.py' -v
python -m unittest discover -s tests -p 'test_*.py' -v
cd cloudflare-worker && npm run check && cd ..
```

Expected: PASS. If any test fails, fix the causal defect before release creation.

- [ ] **Step 2: Rebuild the retrieval index with the canonical tool.**

```bash
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --root .
```

- [ ] **Step 3: Build release 4.9.0 with generated hashes/pointer/history; never edit hashes manually.**

```bash
python AI_SKILL_LIBRARY/v4/tools/release.py build \
  --version 4.9.0 \
  --source human_authorized_adaptive_free_model_mesh \
  --class C \
  --validated \
  --root .
```

Do **not** pass `--known-good` until post-deploy verification succeeds.

- [ ] **Step 4: Update `AI_GLOBAL_CHECKPOINT.md` to point to the new capability release and describe model-mesh boundaries without changing Trading authority. Rebuild release if this file becomes part of the immutable release contract through a separate policy change; otherwise keep it checkpoint documentation only.**

- [ ] **Step 5: Run the canonical single validation entrypoint.**

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$SOURCE_SHA"
```

Expected: `CI_VALIDATE=PASS failures=0`.

- [ ] **Step 6: Commit generated release/index/checkpoint changes.**

```bash
git add AI_SKILL_LIBRARY

git commit -m "release: prepare Brain 4.9 adaptive free model mesh"
```

---

## Task 12: Verify CI, deploy exact SHA, and separate integrated vs ACTIVE providers

**Files:**
- Modify: `.github/workflows/deploy-skill-mandatory-fast-gateway.yml`
- Modify only if needed for non-secret defaults: `cloudflare-worker/prepare-wrangler.mjs`

- [ ] **Step 1: Extend deployment preflight to run `npm run prepare:model-mesh`, model-mesh tests, and a Wrangler dry-run without generating any provider secret.**

Do not put `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `OPENCODE_ZEN_API_KEY`, `MISTRAL_API_KEY`, `GEMINI_API_KEY`, `MODEL_MESH_EXECUTION_TOKEN`, or any other provider credential into repo files or generated `wrangler.jsonc` vars.

- [ ] **Step 2: Add post-deploy health verification.**

After existing `/runtime/contract` and `/brain/health` exact-SHA checks, require:

```bash
curl -fsS "$WORKER_BASE_URL/brain/mesh/health"
```

Validate at minimum:

```text
ok=true
mode=FREE_ONLY
routingAuthority=false
reasoningAuthority=false
sourceSha=<exact deployed main SHA>
maxParallelDeep=4
executionEnabled=<actual runtime switch>
```

Existing `/brain/health` must still report `externalRoutingCalls=0`.

- [ ] **Step 3: Verify planner behavior in production without external provider execution.**

Use `/brain/mesh/plan` on one STANDARD and one DEEP public test prompt and assert worker count bounds and canonical route/capsule identity.

- [ ] **Step 4: Provider activation is separate and evidence-based.**

For each configured provider secret/account:

```text
INTEGRATED -> credential present -> entitlement probe -> current FREE verified -> privacy/terms compatible -> health probe -> canary -> ACTIVE
```

If no secret/account entitlement exists, report that provider/model family as `INTEGRATED_NOT_ACTIVE`, not broken and not LIVE.

- [ ] **Step 5: Only after exact-SHA deployment and post-deploy smoke succeed, mark release 4.9.0 known-good using the canonical release tool/history mechanism and commit that state.**

- [ ] **Step 6: Final verification report must distinguish:**

```text
SOURCE_INTEGRATED
DISCOVERY_VERIFIED
SNAPSHOT_ELIGIBLE
RUNTIME_CONFIGURED
PROVIDER_ACTIVE
PRODUCTION_VERIFIED
```

Never collapse those states into a single “done” claim.

---

## Completion Definition

Implementation is complete only when all of the following are verified:

- Dynamic discovery can ingest new free-model candidates without changing `task_router`.
- Models.dev/OpenCode/Portkey catalog evidence is normalized but never treated as account entitlement by itself.
- At least three independently hosted recurring free-capacity providers are supported end-to-end in code; actual ACTIVE status depends on verified account secrets/entitlement.
- Every canonical Brain domain maps to measured capability requirements.
- `FREE_ONLY` cannot incur paid usage.
- Quota exhaustion enters cooldown/fallback and returns only after legitimate reset/probe.
- Same-family duplicate hosts do not count as independent reasoning votes.
- STANDARD/DEEP use bounded parallelism only for independent subtasks; max remains 2/4.
- FAST remains provider-free and preserves `externalRoutingCalls=0` and existing latency contract.
- Secrets/private keys/raw private prompts are absent from snapshots, telemetry, commits, and provider fan-out.
- Material conflicts are handled by authority/evidence/checker rules, never silent averaging or majority vote.
- Stable remains functional if discovery/model providers fail.
- Python tests, Worker tests, canonical validators, release check, retrieval-index check, Wrangler dry-run, exact-SHA deploy verification, `/brain/health`, `/brain/mesh/health`, and route/planner smoke checks all pass.
- No provider/model is called ACTIVE merely because source code or configuration exists.
