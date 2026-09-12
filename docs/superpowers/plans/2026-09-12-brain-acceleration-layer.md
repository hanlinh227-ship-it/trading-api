# Brain Acceleration Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical acceleration layer for faster retrieval, typed skill contracts, bounded execution graphs, provider latency routing and regression-safe caching without changing the single authority chain.

**Architecture:** Extend GITHUB_BRAIN_V4 with one stable `acceleration.yaml` policy referenced by checkpoint/router/runtime/context/harmonization. Keep all external frameworks optional pattern sources; no new mandatory service or second router is introduced. Publish the change as a new immutable V4 feature release only after tests and validators pass.

**Tech Stack:** YAML/JSON policy contracts, Python `unittest`, existing V4 validators/release tooling, GitHub Actions, Cloudflare Worker Skill Gateway.

**Spec:** `docs/superpowers/specs/2026-09-12-brain-acceleration-layer-design.md`

## Global Constraints

- One canonical Brain and one authority chain.
- Zero-local remains the default runtime mode.
- No mandatory Qdrant/LangGraph/Pydantic AI/Haystack/Mem0/LiteLLM/GPTCache/SGLang dependency.
- Cache/index/provider-routing output is subordinate to authority, security and freshness.
- FAST keeps durable memory = 0, tool candidates = 0 and no external semantic-service requirement.
- Trading execution authority stays `docs/checkpoints/CURRENT_HANDOFF.md`.
- Multi-market stays analysis/research only.
- Stable file changes require a new immutable V4 release manifest.

---

### Task 1: Add failing acceleration contract tests

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_v4_acceleration.py`

**Interfaces:**
- Consumes: checkpoint, stable router/runtime/context/harmonization, projects registry.
- Produces: regression contract for all later tasks.

- [ ] **Step 1: Write tests** asserting `stable_acceleration_path`, existence of `v4/stable/acceleration.yaml`, safe cache exclusions, provider-not-authority, bounded graph budgets, acceleration preflight ordering, FAST invariants and unchanged trading authority.
- [ ] **Step 2: Push only the test and verify CI fails** because acceleration policy/pointer do not yet exist.
- [ ] **Step 3: Record the expected failure in the implementation notes/PR history.**

### Task 2: Add canonical acceleration policy and checkpoint pointer

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/stable/acceleration.yaml`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`

**Interfaces:**
- Produces: `stable_acceleration_path` and canonical acceleration contract.

- [ ] **Step 1: Define retrieval/index policy** with exact-first, semantic-candidate, lexical fallback, provenance and optional adapters.
- [ ] **Step 2: Define cache safety** excluding live/current, trading final answers, credentials, destructive actions, deployments and financial actions.
- [ ] **Step 3: Define typed capsule requirements** for input/output contract id, permission ceiling, freshness, tools, sources and failure mode.
- [ ] **Step 4: Define bounded execution graph/provider scheduling/eval fallback rules.**
- [ ] **Step 5: Add checkpoint pointer.**

### Task 3: Wire acceleration into router, runtime and context

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/stable/router.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/runtime.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/context.yaml`

**Interfaces:**
- Consumes: canonical acceleration policy.
- Produces: bounded profile behavior and routing order.

- [ ] **Step 1: Add `acceleration_preflight` after `task_router` and before runtime/authority-dependent execution.**
- [ ] **Step 2: Add profile-specific acceleration budgets with FAST external semantic lookup disabled.**
- [ ] **Step 3: Add semantic index/cache invalidation/fallback rules to context policy while preserving `cache_never_outranks_fresh_authority`.**
- [ ] **Step 4: Confirm existing router/runtime validators remain valid.**

### Task 4: Extend harmonization for future upstream upgrades

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/stable/harmonization.yaml`

**Interfaces:**
- Produces: future-upgrade mapping into canonical capability categories.

- [ ] **Step 1: Add upstream capability categories:** retrieval/index, memory/context, orchestration/graph, provider routing, evaluation, inference serving, cache.
- [ ] **Step 2: Require equivalent upstreams to strengthen canonical policy rather than create duplicate primary skills/routers/authorities.**
- [ ] **Step 3: Preserve fail-closed conflict and security rules.**

### Task 5: Publish immutable V4 feature release

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/releases/4.0.3/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Modify if required by repo convention: `AI_SKILL_LIBRARY/v4/releases/history.yaml`

**Interfaces:**
- Produces: verified immutable release pointer for all modified stable files.

- [ ] **Step 1: Compute exact SHA-256 values using existing release tooling/conventions.**
- [ ] **Step 2: Create `4.0.3` manifest including acceleration plus changed stable roles.**
- [ ] **Step 3: Update current pointer with exact manifest hash.**
- [ ] **Step 4: Run release/V4 validators.**

### Task 6: Full verification and production rollout

**Files:**
- No additional production files unless a validator exposes a required compatibility update.

**Interfaces:**
- Produces: evidence-backed merge/rollout verdict.

- [ ] **Step 1: Run all `AI_SKILL_LIBRARY/tests` and router/authority/V4/Skill Gateway validators.**
- [ ] **Step 2: Verify Skill Gateway snapshot/compiler, Worker tests and dry-run.**
- [ ] **Step 3: Open PR and require all canonical CI workflows to pass.**
- [ ] **Step 4: Merge with expected head SHA.**
- [ ] **Step 5: Verify `main`, exact-SHA production deployment, `/runtime/contract`, `/brain/health` and route smoke matrix.**
- [ ] **Step 6: Treat the known external Cloudflare GitHub App check separately unless it becomes causally linked to the canonical deployment path.**