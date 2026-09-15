# AI Legion Integration and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Peer Tri-Layer Intelligence, AI Legion/OpenCode, Skill Evolution, Idle Autonomy and the Adaptive Free Model Mesh into one validated GITHUB_BRAIN_V4 release and roll it out in bounded stages with exact-SHA production verification.

**Architecture:** Treat the existing Adaptive Free Model Mesh implementation plan as a prerequisite execution layer. Add checkpoint paths, release-manifest files, CI snapshot compilation/validation and end-to-end protected evals for Legion. Roll out shadow/read-only first, then bounded coding/evolution/autonomy features; do not change live-price or high-risk execution authority. Stable must retain last-known-good fallback through every stage.

**Tech Stack:** Python 3.12, unittest, PyYAML/jsonschema, Node.js 22, Fastify, Cloudflare Workers/Wrangler, Railway, GitHub Actions, existing release/retrieval-index tools.

**Spec:** `docs/superpowers/specs/2026-09-15-peer-tri-layer-ai-legion-design.md`

## Global Constraints

- Current branch baseline is `github-brain-v4-afmm-implementation2`; current Stable pointer observed during planning is `4.8.1`.
- Existing `docs/superpowers/plans/2026-09-15-adaptive-free-model-mesh.md` must finish its remaining tasks and produce a known-good AFMM release before Legion is production-activated.
- The AFMM plan's intended minor release is `4.9.0`; after `4.9.0` is known-good, this plan targets `4.10.0`. If the canonical pointer has advanced for another approved release, use `release.py` to select the next unused V4 minor version rather than overwriting history.
- No manual manifest hashes or hand-edited release pointer.
- FAST p95 <=25 ms and `externalRoutingCalls=0` remain protected.
- No new primary Brain router or second authority.
- High-risk financial, credential, destructive and permission-widening actions remain blocked/gated exactly as Stable security requires.
- Deployment success is not inferred from source code; exact deployed SHA + health/smoke verification is required.
- OpenCode/Legion/Autonomy failure may degrade capability but must not disable Stable routing or live-price research.

## Plan dependency order

```text
AFMM completion / known-good 4.9.0
        |
        +--> Peer Tri-Layer Intelligence plan
        +--> AI Legion + OpenCode Runtime plan
        +--> Skill Evolution + Idle Learning plan
                     |
                     v
              This integration plan
                     |
                 4.10.0
```

---

### Task 1: Add checkpoint discovery roots for all Legion subsystems

**Files:**
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/v4/index/workspace_map.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_ai_legion_checkpoint.py`

**Interfaces:**
- Produces exact paths for policy, catalogs, schemas, compilers and validators.

- [ ] **Step 1: Write RED checkpoint test**

```python
EXPECTED = {
  "legion_policy_path": "AI_SKILL_LIBRARY/v4/legion/policy.yaml",
  "legion_agents_path": "AI_SKILL_LIBRARY/v4/legion/agents.yaml",
  "legion_learning_path": "AI_SKILL_LIBRARY/v4/legion/learning.yaml",
  "legion_evolution_path": "AI_SKILL_LIBRARY/v4/legion/evolution.yaml",
  "legion_autonomy_path": "AI_SKILL_LIBRARY/v4/legion/autonomy.yaml",
  "legion_snapshot_compiler_path": "AI_SKILL_LIBRARY/v4/tools/compile_legion_snapshot.py",
  "legion_snapshot_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_legion_snapshot.py",
  "legion_intelligence_snapshot_compiler_path": "AI_SKILL_LIBRARY/v4/tools/compile_legion_intelligence_snapshot.py",
  "legion_intelligence_snapshot_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_legion_intelligence_snapshot.py"
}
```

Assert every referenced path exists and `v4/legion` is WARM, not HOT.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_checkpoint -v
```

- [ ] **Step 3: Add checkpoint keys and workspace mapping**

Do not replace existing model-mesh/skill-gateway pointers. Add Legion as a separate capability namespace only.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_checkpoint -v
git add AI_SKILL_LIBRARY/checkpoint.json AI_SKILL_LIBRARY/v4/index/workspace_map.yaml AI_SKILL_LIBRARY/tests/test_ai_legion_checkpoint.py
git commit -m "feat: register AI Legion checkpoint paths"
```

---

### Task 2: Extend the single CI entrypoint with Legion snapshot validation

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_legion.py`
- Test: `AI_SKILL_LIBRARY/tests/test_ai_legion_ci.py`

**Interfaces:**
- `validate_legion.py --root <repo>` validates canonical policy/catalog/schema relationships.
- `ci_validate.run_validators()` compiles and validates Skill Gateway, Model Mesh, Legion Runtime and Peer Intelligence snapshots against the same exact source SHA.

- [ ] **Step 1: Write RED CI test**

Assert `VALIDATORS` contains `validate_legion.py`; generated paths include `legion-runtime-snapshot.json` and `legion-intelligence-snapshot.json`; source SHA mismatch fails validation; empty/quarantine learning state is safe and valid.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_ci -v
```

- [ ] **Step 3: Implement validator and CI stages**

CI order must remain deterministic:

```text
legacy/V4 validators
-> Skill Gateway compile/validate
-> Model Mesh compile/validate
-> Legion Runtime compile/validate
-> Peer Intelligence compile/validate
-> release check
-> retrieval-index freshness
-> consolidation invariants
-> unit tests
```

A Legion failure is a release failure; it does not rewrite existing snapshots.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_ci -v
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)" --skip-tests
git add AI_SKILL_LIBRARY/v4/tools/ci_validate.py AI_SKILL_LIBRARY/v4/tools/validate_legion.py AI_SKILL_LIBRARY/tests/test_ai_legion_ci.py
git commit -m "feat: validate AI Legion in canonical CI"
```

---

### Task 3: Add Legion canonical files to immutable release manifests

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/release.py`
- Test: `AI_SKILL_LIBRARY/tests/test_ai_legion_release_manifest.py`

**Interfaces:**
- Existing `build_manifest()` must hash Legion canonical files.

- [ ] **Step 1: Write RED manifest test**

Require release rows for:

```text
AI_SKILL_LIBRARY/v4/legion/policy.yaml
AI_SKILL_LIBRARY/v4/legion/learning.yaml
AI_SKILL_LIBRARY/v4/legion/agents.yaml
AI_SKILL_LIBRARY/v4/legion/orchestration.yaml
AI_SKILL_LIBRARY/v4/legion/upstreams.yaml
AI_SKILL_LIBRARY/v4/legion/evolution.yaml
AI_SKILL_LIBRARY/v4/legion/autonomy.yaml
```

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_release_manifest -v
```

- [ ] **Step 3: Extend `RELEASE_FILES`**

Do not add generated runtime snapshots to the immutable source manifest unless the current release contract already treats generated artifacts as canonical source files; snapshots remain exact-SHA build artifacts.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_release_manifest -v
git add AI_SKILL_LIBRARY/v4/tools/release.py AI_SKILL_LIBRARY/tests/test_ai_legion_release_manifest.py
git commit -m "feat: include AI Legion in release manifests"
```

---

### Task 4: Add protected end-to-end AI Legion evals

**Files:**
- Modify: `AI_SKILL_LIBRARY/evals.yaml`
- Create: `AI_SKILL_LIBRARY/tests/test_ai_legion_protected_evals.py`
- Create: `crypto-research-gateway/test/legion-integration.test.ts`
- Create: `opencode-worker/test/integration.test.ts`

**Interfaces:**
- End-to-end fixtures cover route -> task graph -> worker selection -> output normalization -> conflict/checker -> verified result.

- [ ] **Step 1: Add RED protected scenarios**

Required scenarios:
1. A/B/C branch neutrality.
2. Two weak claims cannot outvote one reproducible stronger claim.
3. Prompt-injected open source cannot override authority/security.
4. Same model family on two providers is not diversity.
5. Provider quota exhaustion triggers compliant cooldown/fallback.
6. OpenCode review cannot edit; patch cannot escape allowed paths; `git push` denied.
7. Worker crash/retry remains idempotent.
8. Generated skill cannot expand permission ceiling.
9. Mutation cannot win by judge preference without protected eval evidence.
10. Idle scheduler rejects financial/credential/destructive jobs.
11. Trading Legion remains research-only.
12. Stable works when Legion, OpenCode, Autonomy and model mesh are all unavailable.
13. FAST route latency/external-call invariants remain unchanged.

- [ ] **Step 2: Run RED suites**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_legion_protected_evals -v
cd crypto-research-gateway && npm test -- --test-name-pattern="legion"
cd ../opencode-worker && npm test
```

- [ ] **Step 3: Implement only fixes required for protected scenarios**

Do not broaden scope while making GREEN. Any newly discovered architecture conflict goes back through spec/change review rather than silent workaround.

- [ ] **Step 4: Run GREEN plus full canonical CI**

```bash
cd ..
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
cd crypto-research-gateway && npm test && npm run typecheck
cd ../opencode-worker && npm test && npm run typecheck
cd ..
node --test cloudflare-worker/test-brain-autonomy.mjs
```

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/evals.yaml AI_SKILL_LIBRARY/tests/test_ai_legion_protected_evals.py crypto-research-gateway/test opencode-worker/test
git commit -m "test: protect AI Legion authority and safety invariants"
```

---

### Task 5: Build the next immutable V4 release

**Files:**
- Generated by tools: `AI_SKILL_LIBRARY/v4/releases/<version>/manifest.yaml`
- Generated/updated by tools: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Generated/updated by tools: `AI_SKILL_LIBRARY/v4/releases/history.yaml`
- Generated by tools: `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml`

**Interfaces:**
- Target version rule: use `4.10.0` only if `4.9.0` is the current known-good AFMM release; otherwise compute next unused approved V4 minor without overwriting history.

- [ ] **Step 1: Verify prerequisite release**

```bash
python AI_SKILL_LIBRARY/v4/tools/release.py check --root .
cat AI_SKILL_LIBRARY/v4/releases/current.json
```

Expected before Legion release: AFMM release is known-good and all canonical validation passes.

- [ ] **Step 2: Build release using the repository tool**

Use the existing `release.py` build/promote commands exposed by its CLI; do not hand-create hashes. After build, rebuild the retrieval index using `build_retrieval_index.py` and rerun `ci_validate.py` against the exact release commit SHA.

- [ ] **Step 3: Verify rollback target**

The previous known-good AFMM release must remain in history and pass `verify_release()`. Promotion is blocked if rollback target is absent.

- [ ] **Step 4: Commit generated release artifacts**

```bash
git add AI_SKILL_LIBRARY/v4/releases AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml
git commit -m "release: prepare GITHUB_BRAIN_V4 AI Legion"
```

---

### Task 6: Roll out in five bounded production stages

**Files:**
- Modify only if required by existing deployment workflows/configs; deployment source remains repository exact SHA.
- Runtime verification records go to existing audit/deployment artifacts, not Stable memory.

**Interfaces:**
- Stage gates:
  1. `shadow`: plan/selection only, no external Legion worker execution.
  2. `read_only`: research/checker/OpenCode plan/explore/review.
  3. `isolated_write`: OpenCode patch/test in isolated workspace only.
  4. `learning`: skill mining/mutation/canary low-risk.
  5. `idle_autonomy`: scheduled low-risk jobs with durable queue.

- [ ] **Step 1: Deploy exact commit to runtime services**

Deploy Gateway, OpenCode worker and Autonomy Worker from the same approved GitHub source revision where applicable. No auto-deploy-on-push assumption; use existing deployment connectors/workflows and pin the commit.

- [ ] **Step 2: Verify exact SHA and health**

Required checks:

```text
Gateway /health deploymentSourceSha == approved SHA
OpenCode /health sourceSha == approved SHA
Autonomy /brain/autonomy/health sourceSha == approved SHA
Skill Gateway /brain/health exact source/release == approved release
```

If any mismatch occurs, deployment is not VERIFIED.

- [ ] **Step 3: Smoke each rollout stage before advancing**

Smoke read-only specialist task, conflict resolution, model-mesh fallback, OpenCode review, isolated patch/test, skill candidate quarantine, scheduler idempotency, and failure of all optional systems while Stable still answers.

- [ ] **Step 4: Verify no authority regression**

Check `/brain/route` still selects exactly one primary skill/capsule; FAST uses no external routing call; `/research/market` remains live-price research authority; Legion routes expose no financial/write capability beyond approved isolated coding writes.

- [ ] **Step 5: Mark release known-good only after production evidence**

Use the existing release/known-good workflow. If protected regression appears, immediately return to previous known-good release and disable later rollout stages without waiting for root-cause completion.

---

### Task 7: Final documentation and operational runbook

**Files:**
- Modify: `AI_SKILL_LIBRARY/GITHUB_BRAIN_V4.md`
- Modify: `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md`
- Create: `docs/AI_LEGION_OPERATIONS.md`
- Modify: `crypto-research-gateway/README.md`
- Create: `opencode-worker/README.md`

**Interfaces:**
- Documents authority chain, service boundaries, stage states, failure modes, rollback, allowed autonomous jobs and explicit high-risk gates.

- [ ] **Step 1: Document state labels precisely**

Use `DESIGNED`, `IMPLEMENTED`, `CI_VERIFIED`, `DEPLOYED`, `PRODUCTION_VERIFIED`, `KNOWN_GOOD`; never call source code alone LIVE.

- [ ] **Step 2: Document incident controls**

Include kill switches for Legion external execution, OpenCode writes and idle autonomy independently. Disabling optional planes must leave Stable route and research gateway operational.

- [ ] **Step 3: Run final validation**

```bash
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
cd crypto-research-gateway && npm test && npm run typecheck
cd ../opencode-worker && npm test && npm run typecheck
cd ..
node --test cloudflare-worker/test-brain-autonomy.mjs
```

- [ ] **Step 4: Commit docs**

```bash
git add AI_SKILL_LIBRARY/GITHUB_BRAIN_V4.md AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md docs/AI_LEGION_OPERATIONS.md crypto-research-gateway/README.md opencode-worker/README.md
git commit -m "docs: add AI Legion operations runbook"
```
