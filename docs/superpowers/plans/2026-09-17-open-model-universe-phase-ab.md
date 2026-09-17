# Open Model Universe Phase A/B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a validated, authority-free Open Model Universe registry and lifecycle contract without activating any model.

**Architecture:** A JSON Schema and empty canonical registry define metadata and lifecycle truth. A focused Python module validates transitions, while a validator enforces schema, authority, zero-paid-token, identity, and secret-safety invariants and is wired into canonical CI.

**Tech Stack:** Python 3.12, JSON Schema Draft 2020-12, YAML, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-17-open-model-universe-phase-ab-design.md`

## Global Constraints

- `task_router` remains the sole routing authority.
- Model Mesh remains authority-free model/provider selection after routing.
- Legion remains the bounded execution coordinator.
- Memory Continuity remains the only memory coordination path.
- Default is `OPEN_MODEL_ZERO_TOKEN_FIRST` with `NO_PAID_FALLBACK`.
- No model download, runtime activation, paid route, secret, or direct Stable mutation.
- Do not edit release/checkpoint/Browser Use files while PR #425 is open.

---

### Task 1: Registry and lifecycle RED tests

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_open_model_universe.py`

**Interfaces:**
- Consumes: proposed schema/registry/tool paths from the design.
- Produces: executable expectations for `validate_transition()` and `validate_open_model_universe()`.

- [ ] Write tests for schema, empty registry, authority, zero-paid-token, lifecycle, duplicate identity, secrets, and 1000-record scale.
- [ ] Run the focused suite and confirm it fails because implementation files are absent.
- [ ] Commit the RED test checkpoint.

### Task 2: Minimal schema, registry, and transition engine

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/schemas/open_model_universe.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml`
- Create: `AI_SKILL_LIBRARY/v4/tools/open_model_universe.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/validate_open_model_universe.py`

**Interfaces:**
- Produces: `LIFECYCLE_STATES`, `ALLOWED_TRANSITIONS`, `validate_transition(current, target)`, and `validate_open_model_universe(root)`.

- [ ] Implement the smallest schema and empty registry satisfying the approved contract.
- [ ] Implement fail-closed transition validation.
- [ ] Implement schema/invariant validation and CLI output.
- [ ] Run the focused suite to GREEN.
- [ ] Commit the implementation checkpoint.

### Task 3: Canonical validation integration

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`
- Modify: `AI_SKILL_LIBRARY/v4/tools/validate_v4.py`

**Interfaces:**
- Consumes: `validate_open_model_universe.py` CLI.
- Produces: canonical CI and V4 path-existence enforcement.

- [ ] Add a failing integration assertion for canonical validation.
- [ ] Wire the validator into `ci_validate.py` and required V4 paths.
- [ ] Run focused tests, all AI Skill Library tests, and exact-SHA canonical CI.
- [ ] Commit only after every validator is green.

### Task 4: Handoff and GitHub recovery state

**Files:**
- Create: `CHECKPOINTS/OPEN_MODEL_UNIVERSE_WORK_HANDOFF_LATEST.md`

- [ ] Record branch, SHAs, PR status, files, tests, blockers, rollback, and next exact task.
- [ ] Push the branch and open a PR without merging it.
- [ ] Record CI status truthfully; do not claim runtime activation.

