# Image Agent V3/V4 Multi-Model Image Intelligence Mesh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Image Render Agent V2 into a cloud-only, FREE_ONLY, multi-model image generation/editing mesh with reference-safe routing, large logical jobs, real visual critic integration, targeted repair, and continuous task-specific model benchmarking while preserving V1/V2 and trading boundaries.

**Architecture:** Keep the existing Cloudflare Worker + Durable Object V2 control plane and evolve it through versioned V3/V4 modules. Add an ImageIntent compiler, provider/model mesh registry, task-specific router, logical-job coordinator, reference-safe runtime contracts, critic/repair pipeline, benchmark/model-vault metadata, and versioned V3 APIs. AI Horde remains a PUBLIC-only fallback; no paid route or local runtime is introduced.

**Tech Stack:** Node.js 22, Cloudflare Workers, Durable Objects, existing image-render JavaScript modules/tests, YAML/JSON Brain policies, GitHub Actions CI, open-model provider adapters.

**Spec:** `docs/superpowers/specs/2026-09-17-image-agent-v3-v4-multimodel-mesh-design.md`

## Global Constraints

- Cloud-only / zero-local runtime for normal operation.
- User controls the system through ChatGPT/GITHUB_BRAIN_V4; no required local UI or ComfyUI.
- FREE_ONLY: `paid_fallback=false`, `auto_purchase=false`, no hidden paid credits.
- AI Horde remains PUBLIC-only and must never receive private/reference images.
- Reference/edit assets only route to providers with `reference_safe=true` and matching data-class policy.
- V1/V2 image APIs remain backward compatible.
- Image state never uses `TRADING_STATE`; image code must not change trading authority or execution semantics.
- No infinite retries; every retry/model-switch/repair loop is bounded.
- STRICT visual verification requires a real critic result; otherwise completion is explicitly unverified.
- New model/runtime registrations require code/weights license metadata and FREE_ONLY eligibility.
- Do not add a new active workflow unless workflow budget remains below repository policy; prefer extending existing CI.

---

## File Structure Map

New focused modules under `cloudflare-worker/image-render/`:

- `image-intent.js` — normalized ImageIntent compiler/validator.
- `provider-mesh.js` — provider/model metadata registry and policy filtering.
- `task-router.js` — task-specific model ranking.
- `logical-job-engine.js` — pure logical-job chunking/state transitions.
- `logical-job-state.js` — Durable Object coordinator for >100 scene jobs.
- `reference-profile.js` — non-biometric reference constraint profile.
- `critic.js` — normalized visual critic contract and decisions.
- `candidate-tournament.js` — candidate scoring/selection.
- `repair-planner.js` — targeted repair decision contract.
- `model-vault.js` — model/license/revision metadata validation.
- `benchmark-registry.js` — task-specific benchmark/promotion state.

Existing modules modified:

- `provider-registry.js` — backward-compatible facade over provider mesh.
- `image-render-handler.js` — add versioned V3 routes.
- `batch-state.js` / `batch-client.js` — interop with logical-job coordinator only, no semantic regressions.
- `index.js`, `prepare-wrangler.mjs`, `wrangler.toml.example` — bind new Durable Object.
- `package.json` — add V3/V4 tests to existing image test script.
- `AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml` — versioned V3/V4 policy fields.
- `AI_SKILL_LIBRARY/v4/legion/agents.yaml` and `AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml` — capability ownership only, no new routing authority.

Tests remain colocated as `cloudflare-worker/test-image-render-v3-*.mjs` and `test-image-render-v4-*.mjs`.

---

### Task 1: ImageIntent Compiler and V3 Contract

**Files:**
- Create: `cloudflare-worker/image-render/image-intent.js`
- Create: `cloudflare-worker/test-image-render-v3-intent.mjs`
- Modify: `cloudflare-worker/package.json`

**Interfaces:**
- Produces: `compileImageIntent(input) -> ImageIntent`, `validateImageIntent(intent) -> {ok, errors}`.
- `ImageIntent` includes `taskType`, `promptOriginal`, `promptCompiled`, `negativeConstraints`, `subjectCount`, `subjectIdentityConstraints`, `referenceAssets`, `preserveRegions`, `editableRegions`, `wardrobeConstraints`, `propConstraints`, `backgroundConstraints`, `styleConstraints`, `cameraConstraints`, `compositionConstraints`, `textRenderConstraints`, `continuityConstraints`, `target`, `privacyClass`, `qualityProfile`, `destructiveRedrawAllowed`.

- [ ] **Step 1: Write failing contract tests** covering explicit-user-constraint preservation, subject-count preservation, task normalization, reference/private privacy requirement, target dimensions/aspect, and rejection of contradictory preserve/edit regions.
- [ ] **Step 2: Run `node test-image-render-v3-intent.mjs`** and confirm RED because `image-intent.js` does not exist.
- [ ] **Step 3: Implement `compileImageIntent` and `validateImageIntent`** with deterministic normalization and no silent subject add/remove.
- [ ] **Step 4: Re-run the test** and confirm PASS.
- [ ] **Step 5: Add the test to the existing image test script and commit** `feat(image): add v3 image intent compiler`.

### Task 2: Provider/Model Mesh + FREE_ONLY/Privacy Gate

**Files:**
- Create: `cloudflare-worker/image-render/provider-mesh.js`
- Create: `cloudflare-worker/test-image-render-v3-provider-mesh.mjs`
- Modify: `cloudflare-worker/image-render/provider-registry.js`

**Interfaces:**
- Consumes: `ImageIntent` from Task 1.
- Produces: `createImageProviderMesh({fetchImpl})`, `filterEligibleProviderModels(intent, registrations)`, normalized registration metadata.

- [ ] **Step 1: Write failing tests** proving AI Horde is `PUBLIC` only, private references are excluded, `monetaryCost !== 'zero'` is rejected, `paidFallback`/`autoPurchase` true is rejected, unknown cost fails closed, and a synthetic `reference_safe` free adapter can be selected.
- [ ] **Step 2: Run tests and confirm RED.**
- [ ] **Step 3: Implement provider/model registration and policy filtering.** Keep `createImageProviderRegistry()` working as a compatibility facade for V1/V2.
- [ ] **Step 4: Run V2 provider tests plus new V3 tests and confirm PASS.**
- [ ] **Step 5: Commit** `feat(image): add free-only provider model mesh`.

### Task 3: Task-Specific Model Router V3

**Files:**
- Create: `cloudflare-worker/image-render/task-router.js`
- Create: `cloudflare-worker/test-image-render-v3-task-router.mjs`

**Interfaces:**
- Consumes: eligible provider/model registrations and `ImageIntent`.
- Produces: `rankImageModels({intent, candidates, history}) -> ranked[]`.

- [ ] **Step 1: Write failing tests** for capability match, reference support, privacy, health, queue estimate, task-specific quality history, critic pass rate, latency, resolution, text-render score, and retry penalties.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement deterministic weighted ranking** with hard eligibility gates before scoring.
- [ ] **Step 4: Confirm PASS and verify the same model can rank differently for `TEXT_RENDER_EDIT` vs `CHARACTER_CONSISTENCY`.**
- [ ] **Step 5: Commit** `feat(image): add task-specific v3 model router`.

### Task 4: Model Vault + License Gate

**Files:**
- Create: `cloudflare-worker/image-render/model-vault.js`
- Create: `cloudflare-worker/image-render/model-vault.json`
- Create: `cloudflare-worker/test-image-render-v3-model-vault.mjs`

**Interfaces:**
- Produces: `validateModelVaultEntry(entry)`, `loadApprovedModelVault()`, registration fields for canonical source, exact revision, code/weights license, commercial eligibility, redistribution/mirroring eligibility, runtime compatibility, last verified date.

- [ ] **Step 1: Write failing tests** that reject missing weights license, ambiguous commercial use, absent revision, and non-zero-cost runtime registrations; accept explicitly approved Apache-2.0/MIT entries.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement the validator and seed metadata entries for the approved initial open-model families without claiming a runtime exists unless one is configured.**
- [ ] **Step 4: Confirm PASS.**
- [ ] **Step 5: Commit** `feat(image): add model vault and license gates`.

### Task 5: Unlimited Logical Job Engine

**Files:**
- Create: `cloudflare-worker/image-render/logical-job-engine.js`
- Create: `cloudflare-worker/test-image-render-v3-logical-job.mjs`

**Interfaces:**
- Produces: `createLogicalJob({scenes, chunkSize=100,...})`, `nextLogicalJobActions(state)`, `applyLogicalJobEvent(state,event)`, `cancelLogicalJob(state)`, `retryLogicalJobScenes(state,sceneIds)`.
- Physical chunk size maximum remains 100; logical scene count has no arbitrary 100-scene product ceiling.

- [ ] **Step 1: Write failing tests** for 1, 100, 101, 5,000 scenes; chunk boundaries; partial completion; cancel; resume; selective retry; provider-wait states; and bounded operational safeguards.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement the pure serializable state machine.**
- [ ] **Step 4: Confirm PASS.**
- [ ] **Step 5: Commit** `feat(image): add resumable logical image jobs`.

### Task 6: Logical Job Durable Object + V3 APIs

**Files:**
- Create: `cloudflare-worker/image-render/logical-job-state.js`
- Create: `cloudflare-worker/image-render/logical-job-client.js`
- Create: `cloudflare-worker/test-image-render-v3-logical-job-state.mjs`
- Modify: `cloudflare-worker/image-render-handler.js`
- Modify: `cloudflare-worker/index.js`
- Modify: `cloudflare-worker/prepare-wrangler.mjs`
- Modify: `cloudflare-worker/wrangler.toml.example`

**Interfaces:**
- Adds: `POST /brain/image/v3/jobs`, `GET /brain/image/v3/jobs/status?id=`, `DELETE /brain/image/v3/jobs?id=`, `POST /brain/image/v3/jobs/retry`, `GET /brain/image/v3/models`, `GET /brain/image/v3/capabilities`.
- New binding/class: `IMAGE_LOGICAL_JOB` / `ImageLogicalJobState`.

- [ ] **Step 1: Write failing Durable Object/API tests** for create/status/cancel/retry and >100-scene chunk orchestration.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement Durable Object coordinator and versioned handlers.** Do not change existing V1/V2 route behavior.
- [ ] **Step 4: Add Wrangler binding/migration wiring and verify no `TRADING_STATE` fallback exists.**
- [ ] **Step 5: Run V1/V2/V3 handler/state tests and confirm PASS.**
- [ ] **Step 6: Commit** `feat(image): add v3 logical job api and durable state`.

### Task 7: ReferenceProfile + Reference-Safe Edit Routing

**Files:**
- Create: `cloudflare-worker/image-render/reference-profile.js`
- Create: `cloudflare-worker/test-image-render-v3-reference.mjs`
- Modify: `cloudflare-worker/image-render/provider-mesh.js`
- Modify: `cloudflare-worker/image-render-handler.js`

**Interfaces:**
- Produces: `createReferenceProfile({references,constraints})`, `validateReferenceRoute({intent,providerModel})`.
- Adds `POST /brain/image/v3/edit` contract without enabling unsafe volunteer upload.

- [ ] **Step 1: Write failing tests** proving reference metadata can describe stylized character traits, private refs never route to AI Horde, missing safe runtime returns `WAITING_FOR_SAFE_FREE_RUNTIME`, and direct references are only passed to explicitly safe adapters.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement non-biometric ReferenceProfile and reference-safe routing contract.**
- [ ] **Step 4: Confirm PASS.**
- [ ] **Step 5: Commit** `feat(image): add reference-safe generation and edit contracts`.

### Task 8: Real Visual Critic Contract + Candidate Tournament

**Files:**
- Create: `cloudflare-worker/image-render/critic.js`
- Create: `cloudflare-worker/image-render/candidate-tournament.js`
- Create: `cloudflare-worker/test-image-render-v4-critic.mjs`
- Create: `cloudflare-worker/test-image-render-v4-tournament.mjs`
- Modify: `cloudflare-worker/image-render/quality-policy.js`

**Interfaces:**
- Produces: `normalizeCriticResult(result)`, `decideQualityAction(result,policy)`, `selectBestCandidate({candidates,criticResults,thresholds})`.

- [ ] **Step 1: Write failing tests** for real critic PASS, critic unavailable => `PASS_UNVERIFIED`, local/global repair, retry seed/model/prompt, terminal fail, and ranking 1/2/4 candidates.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement normalized critic decisions and candidate tournament.**
- [ ] **Step 4: Wire V2 quality policy to preserve existing behavior while adding `STRICT_VISUAL`.**
- [ ] **Step 5: Confirm PASS across V2 and V4 quality tests.**
- [ ] **Step 6: Commit** `feat(image): add visual critic and candidate tournament`.

### Task 9: Targeted Repair Planner

**Files:**
- Create: `cloudflare-worker/image-render/repair-planner.js`
- Create: `cloudflare-worker/test-image-render-v4-repair.mjs`

**Interfaces:**
- Produces: `planRepair({intent,criticResult,capabilities,attempts})` returning `NONE | LOCAL_MASKED_EDIT | GLOBAL_EDIT | RETRY_SEED | RETRY_MODEL | FAIL_TERMINAL` plus target descriptors.

- [ ] **Step 1: Write failing tests** for hand/anatomy local repair, wardrobe/object repair, background repair, identity mismatch model switch, unavailable segmentation fallback, preserve-region protection, and repair-attempt limits.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement planner contracts for GroundingDINO/SAM2-compatible localization and editor adapters without pretending those runtimes exist when unavailable.**
- [ ] **Step 4: Confirm PASS.**
- [ ] **Step 5: Commit** `feat(image): add critic-driven targeted repair planner`.

### Task 10: Benchmark Registry + Model Promotion/Demotion

**Files:**
- Create: `cloudflare-worker/image-render/benchmark-registry.js`
- Create: `cloudflare-worker/test-image-render-v4-benchmark.mjs`

**Interfaces:**
- Produces: `recordBenchmarkResult`, `evaluateModelPromotion`, `evaluateModelRegression`, task-class specific statuses `CANDIDATE|ACTIVE|DEGRADED|DISABLED`.

- [ ] **Step 1: Write failing tests** for task-specific promotion, regression demotion, no universal default from upstream claims, and minimum sample/quality requirements.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement benchmark registry and deterministic policy.**
- [ ] **Step 4: Confirm PASS.**
- [ ] **Step 5: Commit** `feat(image): add task-specific image model evolution`.

### Task 11: Brain Policy/Agent Integration

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/legion/agents.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml`
- Add/modify Brain validation tests under `AI_SKILL_LIBRARY/tests/`.

**Interfaces:**
- Policy version becomes V3/V4-aware while preserving V2 endpoints and authority constraints.

- [ ] **Step 1: Write failing Brain tests** for FREE_ONLY, no trading authority, AI Horde PUBLIC-only, reference-safe routing, logical jobs >100, real critic requirement, and new capability ownership.
- [ ] **Step 2: Confirm RED in Brain validation.**
- [ ] **Step 3: Update policy/agent/stable fusion metadata.**
- [ ] **Step 4: Run Brain validators and tests, confirm PASS.**
- [ ] **Step 5: Commit** `feat(brain): integrate image agent v3 v4 mesh policy`.

### Task 12: Deployment Wiring, Production Smoke Contract, and Full Regression

**Files:**
- Modify existing image CI/smoke workflow only if needed; do not add an active workflow if it would violate the active workflow budget.
- Create/modify: `cloudflare-worker/test-image-render-v3-deploy-wiring.mjs`
- Create/modify: `cloudflare-worker/test-image-render-v3-production-smoke.mjs`
- Modify: `cloudflare-worker/package.json`

**Interfaces:**
- Production smoke verifies exact SHA, FREE_ONLY, V3 capabilities, logical-job create/cancel/status, no private ref, no trading-state binding; external provider outages are classified appropriately.

- [ ] **Step 1: Write failing deployment/smoke contract tests.**
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Wire new Durable Object and V3 health/capability metadata into existing deployment/smoke structure.**
- [ ] **Step 4: Run all image V1/V2/V3/V4 tests, Worker tests, Brain validators, workflow-budget tests, and exact deployment contract tests.**
- [ ] **Step 5: Commit** `test(image): gate v3 v4 mesh deployment`.

### Task 13: Release/Checkpoint + Claude Code Handoff Prompt

**Files:**
- Update release/checkpoint files according to existing Brain release tooling.
- Create: `docs/handoffs/2026-09-17-claude-code-image-agent-v3-v4.md`

**Interfaces:**
- Handoff prompt tells Claude Code to load exact current main, GITHUB_BRAIN_V4, spec, plan, V3/V4 policy, and only contribute inside approved subsystem boundaries.

- [ ] **Step 1: Run release tooling/tests to determine the correct next release version; do not hard-code a version before the repository tooling validates it.**
- [ ] **Step 2: Update release/checkpoint metadata and verify exact pointers.**
- [ ] **Step 3: Write the Claude Code prompt with explicit prohibitions: no duplicate Brain/router/provider mesh, no trading changes, no paid fallbacks, no local-runtime requirement, no private refs to AI Horde, RED→GREEN mandatory, exact-head CI mandatory.**
- [ ] **Step 4: Run final full regression and release validators.**
- [ ] **Step 5: Commit** `docs(image): finalize v3 v4 release and claude handoff`.

### Task 14: PR, CI, Review, Merge, Exact-Main Deploy Verification

**Files:** none beyond fixes required by review/CI.

- [ ] **Step 1: Open PR from implementation branch to `main` with spec/plan links and exact scope.**
- [ ] **Step 2: Inspect changed-file list and patches for accidental trading/shared-authority modifications.**
- [ ] **Step 3: Require all repository CI gates green; investigate any failure before changing code.**
- [ ] **Step 4: Merge only after CI and review are green.**
- [ ] **Step 5: Verify main HEAD equals merge SHA and exact-main deployment succeeds.**
- [ ] **Step 6: Verify production image smoke on exact main.**
- [ ] **Step 7: Report exact SHA, deployed release, enabled capabilities, unavailable external runtimes, and any remaining quality limitations without claiming unsupported frontier parity.**

---

## Self-Review Result

- Spec coverage: all design sections map to Tasks 1–14, including privacy, unlimited logical jobs, V1/V2 compatibility, critic/repair, model vault, benchmarking, deployment, and Claude Code handoff.
- Placeholder scan: no TBD/TODO/"implement later" placeholders are used as implementation instructions.
- Type consistency: `ImageIntent`, provider/model registrations, task router, logical jobs, critic results, repair plans, benchmark states, and API routes are named consistently across tasks.
- Scope: implementation is phased but remains one coherent image subsystem; every phase produces independently testable software and preserves V2.
