# Cognitive Harmonization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded cognitive harmonization to the current GitHub Brain without changing its single-authority model.

**Architecture:** Introduce one Stable policy file that defines maker/checker, independent grader, bounded agent-loop, conflict reconciliation, artifact pyramid, and learning boundaries. Wire it into checkpoint/runtime/validator/release metadata while preserving FAST semantics, project authority, security, and existing skill routing.

**Tech Stack:** YAML policy, Python validators/tests, GitHub Actions release/CI.

**Spec:** `docs/superpowers/specs/2026-09-12-cognitive-harmonization-design.md`

## Global Constraints
- `task_router` remains mandatory.
- Exactly one primary reasoning skill remains required.
- Maximum supporting skills remains 2.
- FAST behavior and zero external routing RTT remain unchanged.
- Provider/external framework output is evidence only, never reasoning authority.
- No hidden chain-of-thought persistence.
- No permission expansion, financial execution, or trading authority change.
- Promotion requires validators/tests/CI and no protected regression.

---

### Task 1: Regression contract
**Files:**
- Create: `tests/test_cognitive_harmonization.py`

- [ ] Write a test that requires the new policy file and core invariants.
- [ ] Run CI/test workflow and confirm RED because the policy does not exist yet.
- [ ] Keep the failing result as RED evidence.

### Task 2: Stable harmonization policy
**Files:**
- Create: `AI_SKILL_LIBRARY/v4/stable/cognitive_harmonization.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/runtime.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/kernel.yaml`

- [ ] Add bounded agent-loop policy with repeat/replan ceilings.
- [ ] Add maker/checker and independent grader activation rules.
- [ ] Add authority-preserving evidence harmonization.
- [ ] Add artifact-pyramid output shaping.
- [ ] Add verified-only learning/distillation boundaries.
- [ ] Wire STANDARD/DEEP stages without changing FAST.

### Task 3: Validation and discovery
**Files:**
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/validate_v4.py`

- [ ] Add checkpoint discovery path for the harmonization policy.
- [ ] Validate required invariants and fail-closed settings.
- [ ] Verify Trading authority and existing invariants remain unchanged.

### Task 4: Release bundle
**Files:**
- Create: `AI_SKILL_LIBRARY/v4/releases/4.0.2/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/releases/current.json`

- [ ] Hash the exact Stable files included in the new release.
- [ ] Add harmonization policy as a release artifact.
- [ ] Point current release to the new immutable manifest only after hashes are correct.

### Task 5: GREEN verification
- [ ] Run the focused regression test.
- [ ] Run Brain/router/V4/authority/skill-gateway validators and full relevant test suite.
- [ ] Check PR diff for accidental Trading/security/permission changes.
- [ ] Confirm CI green before merge or production claims.