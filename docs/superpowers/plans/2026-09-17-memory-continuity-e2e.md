# Memory Continuity End-to-End Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete verified handoff -> persisted focus -> new-chat bootstrap -> authority-gated resume without changing router, trading execution, image-render runtime, provider routing, or other project state.

**Architecture:** Add one pure bootstrap resolver under the existing `memory_continuity` subsystem. It consumes the persisted focus pointer plus a verified current-project authority record and returns context-only resume state. Wire canonical bootstrap/checkpoint pointers only; persist one verified handoff for this Memory Continuity project after tests pass.

**Tech Stack:** Python stdlib, YAML/JSON configuration, existing GitHub Brain CI.

**Spec:** `docs/superpowers/specs/2026-09-17-memory-continuity-fabric-design.md`

## Global Constraints

- `task_router` remains the only routing authority.
- Memory remains context-only and authority-free.
- `cross_project_read=false` and `cross_project_write=false`.
- Do not modify `cloudflare-worker/image-render/`, `TRADING_STATE`, `IMAGE_RENDER_BATCH`, `IMAGE_LOGICAL_JOB`, provider mesh, trading execution, or production runtime switches.
- Fail closed on missing focus, unverified focus, project/domain mismatch, ambiguity, or unverified authority.
- No raw private chat, credentials, API keys, private keys, tokens, or secrets may be persisted.

---

### Task 1: New-chat bootstrap resolver

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_memory_continuity_bootstrap.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/memory_continuity_bootstrap.py`

**Interfaces:**
- Consumes: `focus: dict`, `authority: dict`
- Produces: `bootstrap_resume(focus: dict, authority: dict) -> dict`

- [ ] Write failing tests for valid resume, missing focus, unverified focus, authority mismatch, and authority-free returned context.
- [ ] Run CI and verify RED because bootstrap implementation is absent.
- [ ] Add minimal resolver implementation.
- [ ] Run CI and verify GREEN.

### Task 2: Canonical bootstrap wiring

**Files:**
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/bootstrap.yaml`

**Interfaces:**
- Expose `memory_continuity_bootstrap_path`.
- Require continuity lookup after checkpoint refresh for implicit `continue`/resume intent, before bounded memory injection and after project authority resolution.

- [ ] Add pointers/instructions without changing routing authority or other subsystem paths.
- [ ] Run full repository validation.

### Task 3: Verified foreground handoff and E2E proof

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/memory_continuity/focus.json`
- Create: `AI_SKILL_LIBRARY/tests/test_memory_continuity_e2e.py`

**Interfaces:**
- Persist only a verified, resume-eligible foreground handoff for `memory-continuity-fabric`.
- E2E test loads the real `focus.json`, runs bootstrap with matching verified authority, and verifies the returned project/next action while authority flags stay false.

- [ ] Add E2E test first.
- [ ] Verify RED while focus is null.
- [ ] Persist the verified handoff through the existing writeback contract semantics.
- [ ] Verify GREEN and full CI.
- [ ] Confirm changed-file diff contains no protected subsystem paths.
