# Brain Capability Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical capability-fusion layer that improves retrieval, response latency, memory, bounded execution, typed contracts and eval quality without changing the single authority chain or requiring new production dependencies.

**Architecture:** Extend existing V4 Stable policies rather than install upstream frameworks. A new stable capability contract maps absorbed patterns into native V4 constraints; runtime/context/memory/evals/harmonization are tightened around that contract, with reference sources registered separately.

**Tech Stack:** YAML/JSON policy contracts, Python unittest validators, GitHub Actions, Cloudflare Worker Skill Gateway.

**Spec:** `docs/superpowers/specs/2026-09-12-brain-capability-fusion-design.md`

## Global Constraints

- GITHUB_BRAIN_V4 remains the only AI brain authority.
- `docs/checkpoints/CURRENT_HANDOFF.md` remains current Trading authority.
- No mandatory new production dependency.
- FAST keeps zero durable memory, zero external routing calls and no project-state preload.
- Cache never serves live/current/trading-entry/credential/destructive/private-connected-source/deployment-runtime claims.
- New upstreams are reference/RAG only; training remains disabled.
- No hidden chain-of-thought persistence.

---

### Task 1: Contract regression tests

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_v4_capability_fusion.py`

**Interfaces:**
- Consumes: checkpoint/runtime/context/memory/harmonization/evals/source registry.
- Produces: regression guarantees for all capability-fusion invariants.

- [ ] Write tests requiring checkpoint discovery, optional semantic index, safe cache exclusions, typed contracts, bounded execution graph, authority-subordinate memory, new eval classes and upstream provenance.
- [ ] Run the new test and confirm failure before implementation.
- [ ] Commit the failing contract test.

### Task 2: Canonical capability-fusion Stable policy

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/v4/stable/harmonization.yaml`

**Interfaces:**
- Consumes: existing authority/security/harmonization rules.
- Produces: canonical native capability definitions and upstream-pattern mappings.

- [ ] Define execution graph, typed contracts, retrieval plane, semantic index/cache, selective memory, eval/provider/serving patterns.
- [ ] Point checkpoint at the policy.
- [ ] Require future capability/upstream upgrades to pass harmonization.
- [ ] Run the contract test and inspect remaining failures.

### Task 3: Fast knowledge and context plane

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/stable/runtime.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/context.yaml`

**Interfaces:**
- Consumes: capability-fusion policy.
- Produces: safe cache/index stages with existing FAST/STANDARD/DEEP limits.

- [ ] Add safe FAST cache stages without durable memory/tool calls.
- [ ] Add optional hybrid retrieval/rerank/fallback semantics for STANDARD/DEEP.
- [ ] Encode authority/freshness fingerprint invalidation.
- [ ] Run runtime/V4 and capability-fusion tests.

### Task 4: Selective memory and evaluation gates

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/stable/memory.yaml`
- Modify: `AI_SKILL_LIBRARY/evals.yaml`

**Interfaces:**
- Consumes: canonical context/authority metadata.
- Produces: consolidation/supersession rules plus retrieval/cache/adversarial/latency eval coverage.

- [ ] Add memory consolidation and semantic-index adapter constraints.
- [ ] Add eval benchmark classes and protected cache/authority checks.
- [ ] Run memory/eval/V4 tests.

### Task 5: Upstream reference registry

**Files:**
- Modify: `AI_SKILL_LIBRARY/sources.yaml`

**Interfaces:**
- Consumes: verified upstream repository/license metadata.
- Produces: provenance-aware RAG/reference entries with training disabled.

- [ ] Add LangGraph, Pydantic AI, Haystack, Qdrant, Mem0, Promptfoo, SGLang and GPTCache with verified licenses.
- [ ] Keep LiteLLM out of approved RAG until license is separately resolved; mention only as design-reference in fusion policy.
- [ ] Run source/integration tests.

### Task 6: Immutable V4 release

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/releases/4.1.0/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/releases/current.json`

**Interfaces:**
- Consumes: exact final Stable file hashes.
- Produces: immutable active capability-fusion release.

- [ ] Compute SHA-256 for release-controlled files.
- [ ] Create 4.1.0 manifest including capability fusion and changed stable policies.
- [ ] Compute manifest hash and update `current.json`.
- [ ] Run release/V4 validators.

### Task 7: Full verification and merge

**Files:**
- No new implementation files.

**Interfaces:**
- Consumes: completed branch.
- Produces: validated PR and exact-SHA post-merge runtime proof.

- [ ] Run all repository unit tests and V4/router/authority/Skill Gateway validators through CI.
- [ ] Open PR and require canonical CI success.
- [ ] Merge with expected head SHA.
- [ ] Verify `main`, exact-SHA production deployment, `/runtime/contract`, `/brain/health` and route smoke matrix.
