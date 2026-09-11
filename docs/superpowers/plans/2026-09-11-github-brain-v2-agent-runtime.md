# GITHUB_BRAIN_V2 Adaptive Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fast, layered agent control plane around the existing GitHub-first router without breaking current project authority or V2 compatibility.

**Architecture:** Keep domain skills unchanged and add compact orchestration registries for bootstrap, runtime profiles, memory, evals, observability, and security. A single validator enforces cross-file contracts; CI runs regression tests plus existing V2 validators. FAST avoids heavy layers, STANDARD loads bounded context, and DEEP activates planning/critique/eval only for complex/high-risk work.

**Tech Stack:** YAML, Python 3.12, PyYAML, jsonschema, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-11-github-brain-v2-agent-runtime-design.md`

## Global Constraints
- `task_router` remains mandatory for every request.
- Existing Trading authority paths remain unchanged.
- Do not preload all skills, project state, memory, tools, or Trading context.
- Control-plane layers do not consume domain supporting-skill budget.
- FAST path must remain minimal and non-mutating.
- Hidden chain-of-thought must not be persisted in observability.
- Destructive/financial/credential-sensitive side effects are not silently authorized.

---

### Task 1: Lock the runtime contract with failing tests

**Files:**
- Create: `AI_SKILL_LIBRARY/tests/test_agent_runtime_contract.py`
- Create: `AI_SKILL_LIBRARY/tests/test_agent_runtime_validator.py`

**Interfaces:**
- Consumes: current checkpoint/router/project contracts.
- Produces: exact required file names, profile rules, privacy/security invariants, and validator API expectations.

- [ ] Add tests requiring `bootstrap.yaml`, `runtime.yaml`, `memory.yaml`, `evals.yaml`, `observability.yaml`, `security.yaml`, `schemas/runtime.schema.json`, and `validate_runtime.py`.
- [ ] Require checkpoint pointers and V2 minor-version advancement.
- [ ] Require FAST/STANDARD/DEEP ordering and bounded budgets.
- [ ] Require memory privacy exclusions, eval regression gates, no chain-of-thought traces, and security risk classes.
- [ ] Require validator rejection cases for invalid fast path, unbounded memory, persistent chain-of-thought, and permissive destructive defaults.
- [ ] Trigger CI and confirm tests fail because implementation files/pointers are absent.

### Task 2: Add layered control-plane registries

**Files:**
- Create: `AI_SKILL_LIBRARY/bootstrap.yaml`
- Create: `AI_SKILL_LIBRARY/runtime.yaml`
- Create: `AI_SKILL_LIBRARY/memory.yaml`
- Create: `AI_SKILL_LIBRARY/evals.yaml`
- Create: `AI_SKILL_LIBRARY/observability.yaml`
- Create: `AI_SKILL_LIBRARY/security.yaml`
- Create: `AI_SKILL_LIBRARY/schemas/runtime.schema.json`

**Interfaces:**
- `bootstrap.yaml` points to canonical registries and exposes only compact startup metadata.
- `runtime.yaml` owns profile selection/stages/budgets.
- Memory/eval/observability/security files are loaded only when the runtime profile activates them.

- [ ] Implement FAST/STANDARD/DEEP with explicit stage lists and numeric context/tool/memory/replan limits.
- [ ] Make FAST disable project authority, durable memory, plugins, planner, critic, eval, and persistent trace by default.
- [ ] Define bounded memory layers and write/retrieval/privacy policy.
- [ ] Define failure-to-eval pipeline and promotion gates.
- [ ] Define trace event allowlist and forbid hidden reasoning persistence.
- [ ] Define permission classes and conservative defaults for high-impact side effects.

### Task 3: Implement runtime validation

**Files:**
- Create: `AI_SKILL_LIBRARY/validate_runtime.py`

**Interfaces:**
- Produces `validate_runtime_data(bootstrap, runtime, memory, evals, observability, security) -> tuple[list[str], list[str]]`.
- CLI returns nonzero on policy/schema errors.

- [ ] Validate bootstrap pointer completeness.
- [ ] Validate profile order `FAST < STANDARD < DEEP` and monotonic bounded budgets.
- [ ] Validate FAST path exclusions and replan budget 0.
- [ ] Validate memory layer names, item/token caps, provenance/confidence/supersession metadata, and privacy exclusions.
- [ ] Validate eval failure conversion and protected promotion gates.
- [ ] Validate observability excludes chain-of-thought and bounds trace size.
- [ ] Validate security classes and no default allow for destructive/financial/credential-sensitive actions.
- [ ] Validate runtime JSON schema.

### Task 4: Wire runtime into bootstrap/protocol/router

**Files:**
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AGENTS.md`
- Modify: `AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md`
- Modify: `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`
- Modify: `AI_SKILL_LIBRARY/router.yaml`

**Interfaces:**
- New chats discover `bootstrap.yaml` from checkpoint.
- Router chooses execution profile before loading project/domain context.
- Detailed registries remain lazy.

- [ ] Advance checkpoint version to `2.1.0` and add all runtime registry/validator paths.
- [ ] Change bootstrap instructions to `checkpoint.json -> bootstrap.yaml -> task_router`, with detailed brain/core/router lazy-load rules.
- [ ] Add profile selection before project authority loading.
- [ ] Preserve all existing domain routes and current authorities.
- [ ] Document controlled learning loop and no autonomous promotion.

### Task 5: Extend CI and verify no regressions

**Files:**
- Modify: `.github/workflows/ai-skill-library-ci.yml`

**Interfaces:**
- CI compiles and runs `validate_runtime.py` in addition to all existing checks.

- [ ] Add branch/path coverage for the feature branch if needed.
- [ ] Compile new validator.
- [ ] Add `Validate adaptive agent runtime` step.
- [ ] Run full unittest discovery and all existing validators/ingest/upstream audit.
- [ ] Compare branch to main and inspect changed files.
- [ ] Merge only after branch/PR CI is green, then verify post-merge main CI.
