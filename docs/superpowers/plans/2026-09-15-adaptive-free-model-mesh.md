# Adaptive Free Model Mesh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to execute this plan. Follow TDD and verification gates exactly.

**Goal:** Implement the approved Adaptive Free Model Mesh as a cloud-first, `FREE_ONLY`, multidisciplinary provider/model execution layer that discovers the broadest practical set of legitimately free/free-tier models, assigns only the smallest useful complementary worker set to routed STANDARD/DEEP subtasks, and automatically handles quota, health, cooldown, fallback, and conflict without creating a second Brain authority.

**Architecture:** Preserve `request -> task_router -> profile -> project authority -> exactly one primary skill + capsule`. Add a separate `AI_SKILL_LIBRARY/v4/model_mesh/` namespace and `/brain/mesh/*` Cloudflare runtime that only runs after canonical routing. Evergreen discovers/quarantines model candidates; Stable consumes a validated last-known-good model snapshot. `/brain/route` remains local, provider-free, and `externalRoutingCalls=0`.

**Tech Stack:** Python 3.12, PyYAML, jsonschema, Node.js 22, Cloudflare Workers/Wrangler, GitHub Actions, provider HTTPS APIs, generic OpenAI-compatible adapters plus native adapters only where protocol compatibility requires them.

**Specs:**
- `docs/superpowers/specs/2026-09-15-adaptive-free-model-mesh-design.md`
- `docs/superpowers/specs/2026-09-15-adaptive-free-model-mesh-multidomain-extension-design.md`

## Global Constraints

- Providers/models are execution/evidence resources only; they never gain routing, project, or reasoning authority.
- FAST gets zero mesh workers and no model/provider/network call. Existing Skill Gateway p95 and `externalRoutingCalls=0` must remain unchanged.
- STANDARD <= 2 independent workers; DEEP <= 4. This plan does not increase Brain hard limits.
- Initial mode is `FREE_ONLY`: `unknown`, paid, expired, or unverifiable billing state is excluded. No silent paid fallback, purchase, or top-up.
- No IP rotation, account cycling, key farming, proxy/region hopping, or other quota/rate-limit circumvention.
- Never commit secrets. `SECRET` data never goes to an external free endpoint. `INTERNAL`/`CONFIDENTIAL` require explicit provider privacy compatibility.
- No majority vote and no silent averaging. Material disagreement is resolved by current authority/evidence or explicit checker/verifier rules.
- Multiple providers hosting the same model family improve availability only; they do not count as independent reasoning diversity.
- Trading use remains read-only analysis/research; no order, wallet, leverage, transfer, account mutation, or credential capability is added.
- Stable continues working if model discovery, every free provider, or the entire mesh fails.
- Behavior changes follow `RED -> minimum GREEN -> regression -> canonical validators -> CI -> exact-SHA deploy verification`.
- Current approved baseline at plan creation is `4.8.1`. This explicitly human-authorized Class C architecture change targets `4.9.0` after all gates pass.

## Approved upstream references to absorb selectively

Add these as reference/capability inputs under the existing harmonization policy, with no parallel authority and no mandatory framework runtime:

- `anomalyco/models.dev` — MIT — model/provider catalog, capabilities, pricing metadata, family identity.
- `anomalyco/opencode` — MIT — provider discovery/plugin-order and OpenCode Zen adapter patterns.
- `Portkey-AI/models` — MIT — supplementary provider/model pricing/config metadata.
- `Portkey-AI/gateway` — MIT — retry/fallback/load-balancing/conditional routing patterns; reference-only initially.
- `vllm-project/semantic-router` — Apache-2.0 — capability/Mixture-of-Models selection and route-evaluation patterns.
- `microsoft/agent-framework` — MIT — bounded sequential/concurrent/handoff workflow patterns.
- Retain current approved LangGraph, Pydantic AI, OpenAI Agents, Google ADK, promptfoo, garak, and related references.
- Keep `BerriAI/litellm` design-reference-only under the existing license policy; no code reuse.
- Do not adopt `microsoft/autogen` as a new foundation; treat it as historical/maintenance reference only.

---

## Task 1 — Create the model-mesh policy namespace and register upstream patterns

**Files**
- Create `AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml`
- Create `AI_SKILL_LIBRARY/v4/model_mesh/upstreams.yaml`
- Modify `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml` under `upstream_pattern_map`
- Modify `AI_SKILL_LIBRARY/v4/index/workspace_map.yaml` under `groups`, `WARM`, `tools`, `tests`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_upstreams.py`

- [ ] Write RED tests asserting `mode=FREE_ONLY`, `routing_authority=false`, `reasoning_authority=false`, `FAST=0`, `STANDARD=2`, `DEEP=4`, provider voting forbidden, quota circumvention forbidden, and all six new upstreams registered with explicit license and zero authority.
- [ ] Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_upstreams -v
```

Expected: FAIL because the new namespace is absent.

- [ ] Implement `policy.yaml` with this minimum contract:

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

- [ ] Register upstream patterns with `code_reuse: false`, no mandatory runtime dependency, and no authority.
- [ ] Add `AI_SKILL_LIBRARY/v4/model_mesh` to WARM, never HOT.
- [ ] Re-run the test and commit:

```bash
git add AI_SKILL_LIBRARY/v4/model_mesh AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml AI_SKILL_LIBRARY/v4/index/workspace_map.yaml AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_upstreams.py
git commit -m "feat: define adaptive free model mesh policy"
```

---

## Task 2 — Add provider/model schemas, normalization, and family dedupe

**Files**
- Create `AI_SKILL_LIBRARY/v4/schemas/model_mesh_provider.schema.json`
- Create `AI_SKILL_LIBRARY/v4/schemas/model_mesh_snapshot.schema.json`
- Create `AI_SKILL_LIBRARY/v4/tools/model_mesh.py`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_registry.py`

- [ ] Write RED tests for required fields, fail-closed free status, privacy, deterministic normalization, and same-family dedupe.
- [ ] The module must expose these exact signatures:
  - `normalize_candidate(provider_id: str, raw: dict, *, observed_at: str) -> dict`
  - `classify_free_status(raw: dict) -> str`
  - `model_family_key(candidate: dict) -> str`
  - `dedupe_model_families(candidates: list[dict]) -> dict[str, list[dict]]`
  - `eligible_free_candidate(candidate: dict, *, data_class: str) -> bool`
- [ ] Tests must prove: `unknown` and `paid` are ineligible in `FREE_ONLY`; `SECRET` is always ineligible externally; two `gpt-oss-120b` hosts form one family group; unrelated names are never collapsed by substring heuristics.
- [ ] Run RED:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_registry -v
```

- [ ] Implement normalization to emit these fields: `provider_id`, `provider_class`, `model_id`, `model_family`, `model_variant`, `endpoint_family`, `free_status`, `free_verified_at`, `quota_scope`, `quota_dimensions`, `reset_semantics`, `capabilities`, `context_window`, `privacy_class`, `data_training_allowed_by_provider`, `retention_policy`, `usage_terms`, `health`, `latency_ema_ms`, `success_rate_ema`, `quality_scores`, `last_benchmark_at`, `source_evidence`.
- [ ] Validate every normalized object with jsonschema. Missing/unknown security-critical semantics fail closed.
- [ ] Run GREEN and neighboring regression tests:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_registry -v
python -m unittest AI_SKILL_LIBRARY.tests.test_brain_4_6_open_source_fusion AI_SKILL_LIBRARY.tests.test_brain_4_8_continuous_intelligence -v
```

- [ ] Commit:

```bash
git add AI_SKILL_LIBRARY/v4/schemas AI_SKILL_LIBRARY/v4/tools/model_mesh.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_registry.py
git commit -m "feat: add free model registry contracts"
```

---

## Task 3 — Build dynamic free-model discovery outside the request path

**Files**
- Create `AI_SKILL_LIBRARY/v4/model_mesh/providers.yaml`
- Create `AI_SKILL_LIBRARY/v4/model_mesh/discovery.yaml`
- Create `AI_SKILL_LIBRARY/v4/tools/discover_free_models.py`
- Create `AI_SKILL_LIBRARY/tests/fixtures/model_mesh/models_dev.json`
- Create `AI_SKILL_LIBRARY/tests/fixtures/model_mesh/opencode_zen.json`
- Create `AI_SKILL_LIBRARY/tests/fixtures/model_mesh/portkey_models.json`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_discovery.py`

- [ ] Write fixture-driven RED tests; unit tests must not use live network.
- [ ] Implement these exact call surfaces:
  - `parse_models_dev(payload: object, observed_at: str) -> list[dict]`
  - `parse_opencode_zen(payload: object, observed_at: str) -> list[dict]`
  - `parse_portkey_models(payload: object, observed_at: str) -> list[dict]`
  - `merge_candidates(*groups: list[dict]) -> list[dict]`
  - `discover(output: Path, fixture_dir: Path | None = None) -> dict`
- [ ] Explicitly test that catalog presence alone leaves `free_status=unknown`; catalog metadata is discovery evidence, not account entitlement.
- [ ] Run RED:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_discovery -v
```

- [ ] Implement HTTP discovery with Python stdlib `urllib.request`; no new package is required. `providers.yaml` must include first-party evidence metadata for Groq, Gemini Developer API, Cloudflare Workers AI, OpenRouter, Mistral, Cohere, Hugging Face Inference Providers, NVIDIA NIM, Cerebras, SambaNova, Alibaba Model Studio, OpenCode Zen, Models.dev, and future provider entries admitted by Evergreen.
- [ ] Implement CLI:

```bash
python AI_SKILL_LIBRARY/v4/tools/discover_free_models.py --root . --output /tmp/v4-free-model-mesh-candidates.json
```

The output is quarantine-only with `routing_authority=false` and `stable_mutation=false`.
- [ ] Run GREEN and commit:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_discovery -v
git add AI_SKILL_LIBRARY/v4/model_mesh AI_SKILL_LIBRARY/v4/tools/discover_free_models.py AI_SKILL_LIBRARY/tests/fixtures/model_mesh AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_discovery.py
git commit -m "feat: add evergreen free model discovery"
```

---

## Task 4 — Add multidisciplinary capability mapping and bounded selection

**Files**
- Create `AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml`
- Modify `AI_SKILL_LIBRARY/v4/tools/model_mesh.py`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_multidomain.py`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_selection.py`

- [ ] Write RED tests covering all canonical domains: `core`, `engineering`, `trading`, `game`, `design_2d`, `design_3d`, `adobe`, `prompt_media`, `writing`, `academic`, `data_docs`, `business`.
- [ ] Capability dimensions are exactly: `text_reasoning`, `coding`, `math_quant`, `long_context`, `multilingual`, `vision`, `structured_output`, `tool_calling`, `planning`, `creative_writing`, `prompt_media`, `research_synthesis`, `data_analysis`, `low_latency`.
- [ ] Implement exact signatures:
  - `required_capabilities(domain: str, primary_skill: str, *, has_image: bool = False) -> dict[str, float]`
  - `score_candidate(candidate: dict, requirements: dict[str, float], *, quota_headroom: float, reputation: float) -> float`
  - `select_workers(task: dict, candidates: list[dict], *, max_workers: int) -> list[dict]`
- [ ] Tests must prove FAST returns zero workers; STANDARD never exceeds 2; DEEP never exceeds 4; same-family alternate hosts remain fallback capacity; different qualified families are preferred when diversity materially helps; weak free models do not win solely on quota; Trading selections carry `research_only=true`.
- [ ] Run RED:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_multidomain AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_selection -v
```

- [ ] Implement filter-before-score order: capability -> permission ceiling -> privacy/data class -> health -> verified free entitlement -> quota -> context fit -> usage terms -> score.
- [ ] Support role labels `maker`, `researcher`, `specialist`, `critic`, `checker`, `grader`, `summarizer` as execution metadata only.
- [ ] Run GREEN and commit:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_multidomain AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_selection -v
git add AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml AI_SKILL_LIBRARY/v4/tools/model_mesh.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_multidomain.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_selection.py
git commit -m "feat: route multidisciplinary model mesh workers"
```

---

## Task 5 — Implement quota, cooldown, circuit breaker, and provider-path reputation

**Files**
- Modify `AI_SKILL_LIBRARY/v4/tools/model_mesh.py`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_quota.py`
- Modify `AI_SKILL_LIBRARY/v4/stable/reliability.yaml`
- Modify `AI_SKILL_LIBRARY/v4/stable/reputation.yaml`

- [ ] Write RED tests for exact state transitions: `AVAILABLE -> LOW_HEADROOM -> COOLDOWN_QUOTA -> PROBE_READY -> AVAILABLE` and `AVAILABLE -> DEGRADED -> CIRCUIT_OPEN -> HALF_OPEN -> AVAILABLE`.
- [ ] Implement exact signatures:
  - `apply_quota_event(state: dict, event: dict, *, now: str) -> dict`
  - `provider_available(state: dict, *, now: str) -> bool`
  - `next_probe_at(state: dict) -> str | None`
- [ ] Tests must prove 429 honors provider reset/retry metadata; invalid credentials never retry; three transient failures open the circuit in line with Stable reliability; no transition emits any IP/account/key rotation or bypass action.
- [ ] Run RED:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_quota -v
```

- [ ] Implement immutable/sanitized state updates. Persist only provider/model identity, status, timestamps, latency, failure class, headroom, reset/probe metadata. Never raw prompts, Authorization values, or secrets.
- [ ] Preserve existing retry max=3 and bounded reputation 0..1; model reputation can only rank equally authorized candidates.
- [ ] Run GREEN and commit:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_quota -v
git add AI_SKILL_LIBRARY/v4/tools/model_mesh.py AI_SKILL_LIBRARY/v4/stable/reliability.yaml AI_SKILL_LIBRARY/v4/stable/reputation.yaml AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_quota.py
git commit -m "feat: add quota aware model mesh recovery"
```

---

## Task 6 — Add promoted active registry, snapshot compiler, and canonical validation

**Files**
- Create `AI_SKILL_LIBRARY/v4/model_mesh/active.yaml`
- Create `AI_SKILL_LIBRARY/v4/tools/promote_model_mesh_candidate.py`
- Create `AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_snapshot.py`
- Create `AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_snapshot.py`
- Create `AI_SKILL_LIBRARY/v4/tools/validate_model_mesh.py`
- Modify `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`
- Modify `AI_SKILL_LIBRARY/checkpoint.json`
- Modify `AI_SKILL_LIBRARY/v4/tools/release.py`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_snapshot.py`

- [ ] Write RED tests for checkpoint paths, `active.yaml`, promotion gates, deterministic ordering, schema validity, no secrets, and release inclusion.
- [ ] Add these exact checkpoint keys:

```json
"model_mesh_policy_path": "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml",
"model_mesh_provider_registry_path": "AI_SKILL_LIBRARY/v4/model_mesh/providers.yaml",
"model_mesh_active_registry_path": "AI_SKILL_LIBRARY/v4/model_mesh/active.yaml",
"model_mesh_domain_capabilities_path": "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml",
"model_mesh_snapshot_schema_path": "AI_SKILL_LIBRARY/v4/schemas/model_mesh_snapshot.schema.json",
"model_mesh_snapshot_compiler_path": "AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_snapshot.py",
"model_mesh_snapshot_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_snapshot.py"
```

- [ ] Run RED:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_snapshot -v
```

- [ ] `active.yaml` starts with an empty `models` array unless a candidate has verified current free entitlement, privacy/terms, benchmark, and health evidence. An integrated provider may exist in `providers.yaml` without becoming execution-eligible.
- [ ] `promote_model_mesh_candidate.py` may copy a sanitized candidate into `active.yaml` only after required gates are true. It cannot copy credentials, raw provider payloads, or hidden reasoning.
- [ ] `compile_model_mesh_snapshot.py` compiles from `active.yaml` by default, not from an ephemeral `/tmp` discovery report. Exact CLI:

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
python AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_snapshot.py --root . --source-sha "$SOURCE_SHA" --registry AI_SKILL_LIBRARY/v4/model_mesh/active.yaml --output AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json
```

- [ ] Add `validate_model_mesh.py` to `ci_validate.py`; compile and validate the model snapshot after the Skill Gateway snapshot. Add stable model-mesh contract files to `release.py` `RELEASE_FILES`; do not hand-edit hashes.
- [ ] Run GREEN:

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_snapshot -v
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$SOURCE_SHA" --skip-tests
```

- [ ] Commit:

```bash
git add AI_SKILL_LIBRARY/checkpoint.json AI_SKILL_LIBRARY/v4/model_mesh AI_SKILL_LIBRARY/v4/tools AI_SKILL_LIBRARY/v4/schemas AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_snapshot.py
git commit -m "feat: compile validated model mesh snapshots"
```

---

## Task 7 — Integrate model discovery with Continuous Intelligence / Evergreen

**Files**
- Modify `AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml`
- Modify `AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml`
- Modify `.github/workflows/ai-brain-evergreen-scan.yml`
- Modify `AI_SKILL_LIBRARY/tests/test_brain_4_8_continuous_intelligence.py`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_evergreen.py`

- [ ] Write RED tests requiring model-catalog discovery to be Evergreen-only, hourly, quarantine-output, no Stable request dependency, and no permission expansion.
- [ ] Add:

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

- [ ] Run RED:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_evergreen -v
```

- [ ] Extend existing hourly workflow with:

```bash
python AI_SKILL_LIBRARY/v4/tools/discover_free_models.py --root . --output /tmp/v4-free-model-mesh-candidates.json
```

Upload the candidate report in the existing artifact; workflow remains `contents: read` and never pushes Stable changes.
- [ ] Run GREEN and regression:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_evergreen AI_SKILL_LIBRARY.tests.test_brain_4_8_continuous_intelligence -v
```

- [ ] Commit:

```bash
git add AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml .github/workflows/ai-brain-evergreen-scan.yml AI_SKILL_LIBRARY/tests
git commit -m "feat: discover free models in evergreen plane"
```

---

## Task 8 — Add a Cloudflare model-mesh planner while preserving FAST routing

**Files**
- Create `cloudflare-worker/model-mesh/contracts.js`
- Create `cloudflare-worker/model-mesh/selector.js`
- Create `cloudflare-worker/model-mesh/task-graph.js`
- Create `cloudflare-worker/model-mesh/quota-state.js`
- Create `cloudflare-worker/model-mesh/conflict.js`
- Create `cloudflare-worker/model-mesh-handler.js`
- Create `cloudflare-worker/model-mesh-runtime.js`
- Create `cloudflare-worker/prepare-model-mesh.mjs`
- Create `cloudflare-worker/test-model-mesh.mjs`
- Create `cloudflare-worker/test-model-mesh-handler.mjs`
- Modify `cloudflare-worker/index.js`
- Modify `cloudflare-worker/package.json`

- [ ] Write RED JS tests for `GET /brain/mesh/health` and `POST /brain/mesh/plan`.
- [ ] `/brain/mesh/plan` receives `{text, dataClass, hasImage}` with defaults `PUBLIC,false`, routes through the existing local Skill Gateway snapshot, rejects FAST/ineligible high-risk execution, and returns a bounded plan from the compiled model snapshot without external model calls.
- [ ] Tests must include:

```js
assert.equal(plan.route.externalRoutingCalls, 0);
if (plan.route.profile === 'FAST') assert.equal(plan.workers.length, 0);
assert.ok(plan.workers.length <= 4);
assert.equal(externalFetchCount, 0);
```

- [ ] Run RED:

```bash
cd cloudflare-worker
node test-model-mesh.mjs
node test-model-mesh-handler.mjs
```

- [ ] Implement planner using `ACTIVE_SKILL_GATEWAY_SNAPSHOT`; never add provider lookup to `/brain/route` or `skill-gateway-handler.js`. Wire `handleModelMesh` in `index.js` after `handleSkillGateway` and before unrelated domain handlers.
- [ ] `prepare-model-mesh.mjs` converts only the validated sanitized JSON snapshot into `cloudflare-worker/generated/model-mesh-snapshot.js` and fails when source SHA differs from `GITHUB_SHA`.
- [ ] Add package scripts:

```json
"test:model-mesh": "node test-model-mesh.mjs && node test-model-mesh-handler.mjs",
"prepare:model-mesh": "node prepare-model-mesh.mjs"
```

Extend `check` to include model-mesh tests.
- [ ] Run GREEN and FAST regression:

```bash
npm run prepare:skill-gateway
npm run prepare:model-mesh
npm run check
node benchmark-skill-gateway.mjs
```

Expected: current FAST p95 threshold and `externalRoutingCalls=0` remain intact.
- [ ] Commit:

```bash
git add cloudflare-worker
git commit -m "feat: add bounded model mesh planner runtime"
```

---

## Task 9 — Add disabled-by-default FREE_ONLY execution adapters

**Files**
- Create `cloudflare-worker/model-mesh/provider-client.js`
- Create `cloudflare-worker/model-mesh/providers/openai-compatible.js`
- Create `cloudflare-worker/model-mesh/providers/gemini.js`
- Create `cloudflare-worker/model-mesh/providers/cloudflare-ai.js`
- Modify `cloudflare-worker/model-mesh-handler.js`
- Create `cloudflare-worker/test-model-mesh-execute.mjs`
- Modify `cloudflare-worker/package.json`

- [ ] Write RED security/execution tests for `POST /brain/mesh/execute`.
- [ ] Required behavior: execution flag not `1` -> 503; missing/invalid execution token -> 401; FAST -> 409; `SECRET` -> 403; unknown/paid free status excluded; 429 -> cooldown with reset metadata; errors never echo key/token/Authorization values.
- [ ] Run RED:

```bash
cd cloudflare-worker
node test-model-mesh-execute.mjs
```

- [ ] Implement exact generic adapter signature `callOpenAICompatible({baseUrl, apiKey, model, messages, timeoutMs, fetchImpl=fetch})`. Use it for compatible providers such as Groq, OpenRouter, OpenCode Zen, Mistral, Cerebras, SambaNova, and future compatible endpoints. Add native Gemini and Cloudflare Workers AI adapters only where required.
- [ ] Provider config stores only endpoint metadata and the **name** of the Worker secret variable. Secret values are read only from `env` and never serialized.
- [ ] Use `Promise.allSettled()` only for independent task-graph nodes admitted within profile limits. If orchestration fails, use bounded serial fallback per Stable reliability.
- [ ] Normalize every worker result to: `task_id`, `subtask_id`, `input_hash`, `authority_revision`, `primary_skill_id`, `capsule_hash`, `domain_label`, `worker_role`, `provider_id`, `model_id`, `model_family`, `started_at`, `completed_at`, `latency_ms`, `quota_state`, `source_refs`, `verification_status`. Never return hidden reasoning.
- [ ] Run GREEN:

```bash
node test-model-mesh-execute.mjs
npm run check
```

- [ ] Commit:

```bash
git add cloudflare-worker/model-mesh cloudflare-worker/model-mesh-handler.js cloudflare-worker/test-model-mesh-execute.mjs cloudflare-worker/package.json
git commit -m "feat: execute free model mesh workers safely"
```

**Activation boundary:** code integration does not make a provider ACTIVE. Runtime activation requires a separately configured Cloudflare secret/account, verified current free entitlement, privacy compatibility, health probe, and canary. Never ask the user to paste secrets into chat or commit them.

---

## Task 10 — Add multidisciplinary benchmark/eval and conflict gates

**Files**
- Create `AI_SKILL_LIBRARY/v4/model_mesh/benchmarks.yaml`
- Create `AI_SKILL_LIBRARY/v4/tools/evaluate_model_mesh.py`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_evals.py`
- Create `AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_conflicts.py`

- [ ] Write RED tests requiring representative cases for all 12 canonical domains plus adversarial cases: unsupported facts, fake live trading state, schema-invalid output, duplicate family hosts, privacy mismatch, same-resource mutation conflict, and contradictory worker outputs.
- [ ] Run RED:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_evals AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_conflicts -v
```

- [ ] Implement offline selector/contract evaluator. Live model canary scores are optional additional evidence only after credentials exist.
- [ ] Protected dimensions with zero regression: `correctness`, `authority`, `security`, `verification`, `project_isolation`, `no_secret_leakage`, `FAST_latency_contract`.
- [ ] Run GREEN and commit:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_evals AI_SKILL_LIBRARY.tests.test_adaptive_free_model_mesh_conflicts -v
git add AI_SKILL_LIBRARY/v4/model_mesh/benchmarks.yaml AI_SKILL_LIBRARY/v4/tools/evaluate_model_mesh.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_evals.py AI_SKILL_LIBRARY/tests/test_adaptive_free_model_mesh_conflicts.py
git commit -m "test: add multidisciplinary model mesh evals"
```

---

## Task 11 — Build the human-authorized 4.9.0 release and run full validation

**Files**
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/4.9.0/manifest.yaml`
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Generated by canonical tools: `AI_SKILL_LIBRARY/v4/releases/history.yaml`
- Modify `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md`
- Generated by canonical tool: `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml`

- [ ] Run all tests before creating the release:

```bash
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p 'test_*.py' -v
python -m unittest discover -s tests -p 'test_*.py' -v
cd cloudflare-worker && npm run check && cd ..
```

- [ ] Rebuild retrieval index only with the canonical builder:

```bash
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --root .
```

- [ ] Build unmarked 4.9.0 release:

```bash
python AI_SKILL_LIBRARY/v4/tools/release.py build --version 4.9.0 --source human_authorized_adaptive_free_model_mesh --class C --validated --root .
```

Do not pass `--known-good` before production verification.
- [ ] Update `AI_GLOBAL_CHECKPOINT.md` to describe 4.9 model-mesh boundaries while preserving Trading/Railway authority separation.
- [ ] Because Stable release files/checkpoint docs may have changed after the first build, run the release builder again with the same version/source to regenerate hashes and pointer deterministically before validation.
- [ ] Run canonical validation:

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$SOURCE_SHA"
```

Expected: `CI_VALIDATE=PASS failures=0`.
- [ ] Commit generated release/index/checkpoint state:

```bash
git add AI_SKILL_LIBRARY
git commit -m "release: prepare Brain 4.9 adaptive free model mesh"
```

---

## Task 12 — Verify CI/deployment and distinguish integrated from ACTIVE providers

**Files**
- Modify `.github/workflows/deploy-skill-mandatory-fast-gateway.yml`
- Modify `cloudflare-worker/prepare-wrangler.mjs` only if a non-secret mesh default is required

- [ ] Extend deployment preflight with `npm run prepare:model-mesh`, model-mesh tests, and Wrangler dry-run. Never generate provider secret values into `wrangler.jsonc`.
- [ ] After existing `/runtime/contract` and `/brain/health` exact-SHA checks, verify `/brain/mesh/health` returns `ok=true`, `mode=FREE_ONLY`, `routingAuthority=false`, `reasoningAuthority=false`, exact `sourceSha`, `maxParallelDeep=4`, and the actual execution-enabled flag. Existing `/brain/health` must still report `externalRoutingCalls=0`.
- [ ] Verify `/brain/mesh/plan` with one STANDARD and one DEEP public prompt: canonical route/capsule identity is preserved and worker counts stay <=2/<=4.
- [ ] If any deploy/smoke fails, roll the release pointer back to the prior known-good release using the canonical rollback mechanism, commit, and redeploy; do not mark 4.9 known-good.
- [ ] For each provider, activation state progresses only as:

```text
SOURCE_INTEGRATED -> DISCOVERY_VERIFIED -> SNAPSHOT_ELIGIBLE -> RUNTIME_CONFIGURED -> PROVIDER_ACTIVE
```

A provider without the required cloud secret/account entitlement is `INTEGRATED_NOT_ACTIVE`, never LIVE.
- [ ] After the first exact-SHA deployment passes, mark 4.9.0 known-good with the canonical release tool:

```bash
python AI_SKILL_LIBRARY/v4/tools/release.py build --version 4.9.0 --source post_deploy_verified_adaptive_free_model_mesh --class C --validated --known-good --root .
git add AI_SKILL_LIBRARY/v4/releases
git commit -m "release: mark Brain 4.9 model mesh known good"
```

This commit changes the exact source SHA, so allow the normal exact-main deployment workflow to deploy it again and re-run `/runtime/contract`, `/brain/health`, `/brain/mesh/health`, and route/planner smoke checks. Only that second exact-SHA verification is the final `PRODUCTION_VERIFIED` state.

## Completion Definition

Implementation is complete only when:

- dynamic discovery can ingest new free-model candidates without changing `task_router`;
- Models.dev/OpenCode/Portkey catalog data is discovery evidence, not entitlement proof;
- at least three independently hosted recurring-free provider paths are supported end-to-end in code, while actual ACTIVE status remains entitlement-dependent;
- every canonical domain maps to measured model capabilities;
- `FREE_ONLY` cannot incur paid usage;
- quota exhaustion uses legitimate cooldown/reset/fallback only;
- same-family hosts do not become independent truth votes;
- STANDARD/DEEP parallelism stays bounded to 2/4 and only independent subtasks run concurrently;
- FAST stays provider-free with unchanged zero-external-routing-call and latency contracts;
- snapshots, telemetry, commits, and worker outputs contain no secrets/private keys/raw private prompts/hidden reasoning;
- material conflicts use authority/evidence/checker rules;
- Stable survives complete mesh/discovery/provider outage;
- Python tests, Worker tests, canonical validators, release check, retrieval-index check, Wrangler dry-run, exact-SHA deploy, `/brain/health`, `/brain/mesh/health`, and route/planner smoke checks pass;
- provider/runtime status is reported precisely as `SOURCE_INTEGRATED`, `DISCOVERY_VERIFIED`, `SNAPSHOT_ELIGIBLE`, `RUNTIME_CONFIGURED`, `PROVIDER_ACTIVE`, or `PRODUCTION_VERIFIED`, never collapsed into an unverified “done”.
