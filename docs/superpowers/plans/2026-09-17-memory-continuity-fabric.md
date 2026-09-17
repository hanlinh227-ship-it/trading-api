# Memory Continuity Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-scoped, authority-free continuity resolver that can resume one verified foreground project in a new chat without contaminating other projects.

**Architecture:** Add a self-contained Python continuity module plus policy and tests. Wire it into canonical memory policy only through an additive pointer; do not alter routers, project runtimes, provider bindings, trading state, or image-render state.

**Tech Stack:** Python standard library, YAML policy files, unittest/pytest-compatible tests, existing Brain CI.

**Spec:** `docs/superpowers/specs/2026-09-17-memory-continuity-fabric-design.md`

## Global Constraints

- `task_router` remains the only routing authority.
- Current project authority always wins over memory.
- No external memory repository becomes an executable dependency.
- Cross-project reads and writes fail closed.
- Sensitive data and raw private chat are not durable continuity data.
- Existing trading/image/project runtime files are not modified.

---

### Task 1: RED tests for continuity isolation

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_memory_continuity.py`

**Interfaces:**
- Consumes: none.
- Produces expected API: `normalize_work_state(payload)`, `select_continuation(states, explicit_project=None, explicit_domain=None)`, `gate_against_authority(selection, authority)`.

- [ ] **Step 1:** Add tests for single-primary resume, ambiguity fail-closed, background exclusion, explicit scope, stale/superseded rejection, authority mismatch, sensitive input rejection, and no-authority flags.
- [ ] **Step 2:** Run the test suite and verify RED because `memory_continuity.py` does not exist.
- [ ] **Step 3:** Keep this failing commit isolated from production code.

### Task 2: Minimal pure continuity resolver

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/memory_continuity.py`

**Interfaces:**
- `normalize_work_state(payload: dict) -> dict`
- `select_continuation(states: list[dict], explicit_project: str | None = None, explicit_domain: str | None = None) -> dict`
- `gate_against_authority(selection: dict, authority: dict) -> dict`

- [ ] **Step 1:** Implement recursive sensitive-key rejection and required-field normalization.
- [ ] **Step 2:** Implement exact-scope selection with exactly one foreground primary record when no explicit project exists.
- [ ] **Step 3:** Implement authority gate that drops mismatched memory.
- [ ] **Step 4:** Run the targeted test suite and verify GREEN.

### Task 3: Add active continuity policy

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/memory_continuity/policy.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/memory.yaml`

**Interfaces:**
- Policy declares `enabled: true` but `authority: false`, `routing_authority: false`, `reasoning_authority: false`, `stable_mutation: false`.
- Canonical memory file references the policy and preserves all existing lifecycle/security rules.

- [ ] **Step 1:** Add policy with fail-closed scope, external-concept attribution, no executable dependencies, and candidate-gated writes.
- [ ] **Step 2:** Append a minimal `continuity` pointer to canonical memory policy.
- [ ] **Step 3:** Run memory continuity tests plus Brain validators.

### Task 4: Validate isolation and repository impact

**Files:**
- No new production files.

- [ ] **Step 1:** Compare `main...feature/memory-continuity-fabric` and verify changed files are limited to docs, continuity namespace, continuity tests, and the canonical memory pointer.
- [ ] **Step 2:** Verify no `cloudflare-worker/image-render/*`, trading execution, provider mesh, runtime binding, or release manifest file changed.
- [ ] **Step 3:** Run repository CI/status checks on the exact PR head.
- [ ] **Step 4:** Merge only if all required checks pass; otherwise leave the feature isolated and inactive on main.
