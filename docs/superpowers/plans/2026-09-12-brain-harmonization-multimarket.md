# Brain Harmonization + Multi-Market Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a permanent skill harmonization policy and a research-only deep multi-market analysis skill while preserving existing production trading authority.

**Architecture:** Extend the existing V4 Stable/Skill Gateway model instead of creating a parallel brain. Add one checkpoint-resolved harmonization policy, one canonical multi-market analysis skill, and minimal router/catalog/trading-router changes; rely on existing Evergreen quarantine, conflict policy, release promotion and verification contracts.

**Tech Stack:** YAML/Markdown policy and skill definitions, existing Python validators/snapshot compiler, GitHub Actions Skill Gateway pipeline.

**Spec:** `docs/superpowers/specs/2026-09-12-brain-harmonization-multimarket-design.md`

## Global Constraints
- Production trading execution authority remains `docs/checkpoints/CURRENT_HANDOFF.md`.
- Multi-market capability is research/analysis only.
- Do not weaken Stable security, freshness, conflict or provider-authority rules.
- Preserve FAST zero-routing-network-call contract.
- New reasoning capability must be discoverable through the canonical catalog/router and execution-capsule compiler.

---

### Task 1: Add canonical harmonization policy
**Files:**
- Create: `AI_SKILL_LIBRARY/v4/stable/harmonization.yaml`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`

- [ ] Define authority-preserving normalization, dedupe, conflict, promotion, cognitive-loop and artifact-pyramid policies.
- [ ] Add checkpoint pointer so future chats/upgrades resolve the policy without hard-coded version knowledge.
- [ ] Verify YAML/JSON parse and checkpoint validator compatibility.

### Task 2: Add deep multi-market analysis skill
**Files:**
- Create: `AI_SKILL_LIBRARY/skills/trading/multi_market_analysis.md`
- Modify: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/router.yaml`

- [ ] Define research scope across crypto, FX, futures, indices, commodities/metals and equities.
- [ ] Encode regime -> cross-asset -> instrument -> microstructure -> risk/catalyst -> evidence synthesis workflow.
- [ ] Explicitly prohibit the skill from widening production execution authority.
- [ ] Register the skill and route triggers so the snapshot compiler can produce a capsule.

### Task 3: Integrate trading routing and harmonization
**Files:**
- Modify: `AI_SKILL_LIBRARY/skills/trading/trading_router.md`

- [ ] Route broad/cross-asset analysis to `multi_market_analysis`.
- [ ] Preserve current live/execution path and CURRENT_HANDOFF authority.
- [ ] Require harmonization/conflict policy before synthesizing multiple market/provider sources.

### Task 4: Validation and release readiness
**Files:** existing validators/tests only unless failures require targeted fixes.

- [ ] Run Brain/router/authority/V4/skill-registry/skill-gateway validators.
- [ ] Compile and validate exact-SHA Skill Gateway snapshot.
- [ ] Verify route matrix includes multi-market intent -> `multi_market_analysis` with valid execution capsule.
- [ ] Run CI and confirm no material regression.
- [ ] Do not claim production deployment unless exact-main deployment and runtime verification complete.
