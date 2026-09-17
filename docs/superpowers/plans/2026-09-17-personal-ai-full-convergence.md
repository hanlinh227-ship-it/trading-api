# Personal AI Full Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the non-runtime control plane that is immediately ready to consume Claude's real runtime evidence for B2, B3, B4, Wave 0, baseline freeze, multi-model federation, and controlled self-development.

**Architecture:** Add focused Python contract modules under `AI_SKILL_LIBRARY/v4/control_plane/`. They consume existing Open Model Universe and Model Mesh authority, expose injected runtime boundaries, and never implement Claude-owned runtime functions. Every module fails closed and has a focused test file.

**Tech Stack:** Python 3.12, stdlib dataclasses/typing/hashlib/json, PyYAML, existing Model Mesh/Open Model Universe tools, unittest.

**Spec:** `docs/superpowers/specs/2026-09-17-personal-ai-full-convergence-design.md`

## Global Constraints

- `GITHUB_BRAIN_V4` and `task_router` remain sole routing/reasoning authority.
- Model Mesh alone selects models; ingress never hardcodes a model.
- FREE_ONLY, privacy, permission, and admission gates fail closed.
- Claude owns runtime lifecycle/acquisition/execution; control plane accepts runtime evidence only.
- No fake runtime evidence can count as B2/B3 PASS.
- No self-development change writes to or self-approves canonical main.

---

### Task 1: Local candidate projection and selection contracts

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/control_plane/__init__.py`
- Create: `AI_SKILL_LIBRARY/v4/control_plane/model_selection.py`
- Test: `AI_SKILL_LIBRARY/tests/test_personal_ai_model_selection.py`

**Interfaces:**
- Consumes: Open Model Universe admitted records plus runtime health/resource/benchmark evidence.
- Produces: `project_local_candidate(...)`, `validate_selection_request(...)`, `select_models(...)`.

- [ ] Write tests proving quarantined/unknown evidence is rejected, identity is lossless, unknown capability remains unknown, Qwen is not hardcoded, profile caps are enforced, warm qualified candidates are preferred only inside a small quality delta, and lineage variants do not count as independent.
- [ ] Run the focused test and confirm failures are caused by the missing module.
- [ ] Implement the minimum generic projection and selection behavior.
- [ ] Run the focused test and Model Mesh regression suite.
- [ ] Commit the independently passing slice.

### Task 2: Canonical ingress and Verifier V1

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/control_plane/ingress.py`
- Create: `AI_SKILL_LIBRARY/v4/control_plane/verifier.py`
- Test: `AI_SKILL_LIBRARY/tests/test_personal_ai_ingress_verifier.py`

**Interfaces:**
- Consumes: canonical ingress envelope and untrusted model output.
- Produces: validated routed request, selection request, and task-specific verification report.

- [ ] Write tests for required ingress fields, permission/privacy/FREE_ONLY preservation, mandatory router evidence, no direct model selection, and all seven verifier classes.
- [ ] Run the focused test and confirm RED.
- [ ] Implement deterministic verifier dispatch and fail-closed ingress validation.
- [ ] Run the focused test plus Brain authority tests.
- [ ] Commit the independently passing slice.

### Task 3: Golden E2E harness and real-evidence gate

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/control_plane/e2e.py`
- Test: `AI_SKILL_LIBRARY/tests/test_personal_ai_golden_e2e.py`

**Interfaces:**
- Consumes: ingress/router/selector/runtime/verifier/synthesis callables.
- Produces: ordered trace, response envelope, B2/B3/B4 readiness evidence.

- [ ] Write tests for exact trace order, injected Claude runtime boundary, fake-runtime rejection, artifact identity matching, verifier rejection, and warm/sleep evidence retention.
- [ ] Run the focused test and confirm RED.
- [ ] Implement the orchestration harness without runtime logic.
- [ ] Run focused and ingress/model-selection regressions.
- [ ] Commit the independently passing slice.

### Task 4: Golden Wave 0 ingestion and baseline freeze

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/control_plane/benchmark.py`
- Create: `AI_SKILL_LIBRARY/v4/control_plane/wave0.json`
- Test: `AI_SKILL_LIBRARY/tests/test_personal_ai_wave0_baseline.py`

**Interfaces:**
- Consumes: 12 real run envelopes and raw evidence references.
- Produces: benchmark-run v1 projection and immutable `PERSONAL_AI_BASELINE_001` record.

- [ ] Write tests for exact 3/3/2/2/2 composition, environment/prompt/benchmark linkage, raw failure retention, real-runtime-only gate, reproducibility, cold/warm metrics, and no partial freeze.
- [ ] Run the focused test and confirm RED.
- [ ] Implement Wave 0 loader, run ingestion, readiness check, and atomic baseline record builder.
- [ ] Run focused and E2E regressions.
- [ ] Commit the independently passing slice.

### Task 5: Multi-Model Federation V1 governance

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/control_plane/federation.py`
- Create: `AI_SKILL_LIBRARY/v4/control_plane/specialists.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_personal_ai_federation.py`

**Interfaces:**
- Consumes: specialist capability/evidence contracts, candidates, execution profile, resource state, outcome records.
- Produces: bounded execution plan, champion/challenger decision, and routing-quality metrics.

- [ ] Write tests for FAST=1 primary, STANDARD<=2 models, DEEP<=4 specialists plus bounded verifier, all canonical specialist groups, lineage independence, evidence-only promotion, no universal winner, and routing metrics.
- [ ] Run the focused test and confirm RED.
- [ ] Implement profile planning, specialist contract validation, champion governance, and metrics.
- [ ] Run focused and Model Mesh regressions.
- [ ] Commit the independently passing slice.

### Task 6: Controlled Self-Development V1 governance

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/control_plane/self_development.py`
- Test: `AI_SKILL_LIBRARY/tests/test_personal_ai_self_development.py`

**Interfaces:**
- Consumes: branch target, gate results, baseline/candidate scorecards, rollback target.
- Produces: authorized state transitions and merge-readiness decision.

- [ ] Write tests for every state, protected-main refusal, branch isolation, unrun/failed gates, protected-dimension zero tolerance, known rollback target, PR-only merge readiness, and forbidden actions.
- [ ] Run the focused test and confirm RED.
- [ ] Implement the minimum state machine and scorecard gate.
- [ ] Run focused and existing SkillEvo/self-development regressions.
- [ ] Commit the independently passing slice.

### Task 7: Canonical validation, handoff, and PR readiness

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Create: `CHECKPOINTS/PERSONAL_AI_FULL_CONVERGENCE_WORK_HANDOFF_LATEST.md`
- Modify: `CHECKPOINTS/OPEN_MODEL_UNIVERSE_WORK_HANDOFF_LATEST.md`
- Test: `AI_SKILL_LIBRARY/tests/test_personal_ai_control_plane_wiring.py`

**Interfaces:**
- Consumes: all prior modules and current Claude dependency state.
- Produces: canonical checkpoint pointers, CI entrypoint coverage, and exact continuation handoff.

- [ ] Write a failing wiring test for checkpoint paths, CI invocation, authority boundaries, and handoff status fields.
- [ ] Run the focused test and confirm RED.
- [ ] Add checkpoint/CI wiring and honest readiness status; do not claim B2/B3/B4 PASS without real Claude evidence.
- [ ] Run all focused tests, Open Model Universe tests, Model Mesh tests, authority tests, and `ci_validate.py --source-sha <HEAD>`.
- [ ] Refresh origin/Claude/PR truth, reconcile if required, push branch, open/update PR, and report exact merge-ready HEAD only when green.
