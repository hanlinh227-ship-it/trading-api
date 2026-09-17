# Open Model Universe First Local E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register one production-quality, evidence-backed local CPU model, provide a Claude-compatible projection packet, and complete the authority-free ChatGPT↔Brain control-plane contract without implementing runtime behavior.

**Architecture:** Keep the canonical Open Model Universe registry authority-free and non-activating. Add one verified Qwen2.5-1.5B-Instruct Q4_K_M row plus a separate first-model evidence packet so provenance/security/projection fields do not distort the existing registry schema. Add declarative ingress/output contracts only; Claude remains owner of runtime projection, lifecycle, scheduler, acquisition, cache, adapters, workers, and failover.

**Tech Stack:** YAML metadata/contracts, JSON Schema, Python `unittest` + existing Open Model Universe validator/CI.

**Spec:** `CHECKPOINTS/OPEN_MODEL_UNIVERSE_WORK_HANDOFF_LATEST.md` plus the 2026-09-17 `PERSONAL AI FEDERATION — WORK CONTINUATION VIA CHATGPT WEB` continuation contract supplied to ChatGPT Web.

## Global Constraints

- Canonical base is the refreshed `main`; do not overwrite parallel Memory Continuity work.
- `task_router` remains sole routing authority; registry/ingress contracts have `authority: false` semantics.
- No runtime implementation, scheduler, lifecycle manager, download manager, cache, adapter, worker registration, failover, Web QA, Web Eval, or merge orchestration changes.
- No paid per-token fallback and no automatic model activation/download from registry discovery.
- Do not fabricate benchmark scores or unknown vendor hardware requirements.
- Pin model source to an immutable upstream revision and exact artifact SHA-256/size.
- Do not claim runtime LIVE.

---

### Task 1: Contract tests for the first real local model

**Files:**
- Modify: `AI_SKILL_LIBRARY/tests/test_open_model_universe.py`
- Create: `AI_SKILL_LIBRARY/v4/schemas/first_valid_local_model.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/open_model_universe/first_valid_local_model.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/tools/validate_open_model_universe.py`

**Interfaces:**
- Consumes: current Open Model Universe registry/schema/validator.
- Produces: exactly one registered, non-active local model plus a strict evidence/projection packet consumable by Claude's existing `ModelProfile` projection seam.

- [ ] **Step 1: Write failing tests**

Add tests that require: exactly one checked-in real model; immutable 40-hex revision; exact SHA-256 and byte size; authority false; `REGISTERED` not runtime-active; first-model packet with all required provenance/security fields; projection identity matching registry; no fake benchmark score; unknown vendor hardware values explicitly marked and activation-blocking where appropriate.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest AI_SKILL_LIBRARY.tests.test_open_model_universe -v`

Expected: FAIL because registry is empty and first-model evidence/schema files do not exist.

- [ ] **Step 3: Implement minimal metadata/contracts**

Populate the registry with official `Qwen/Qwen2.5-1.5B-Instruct-GGUF` Q4_K_M at immutable revision `91cad51170dc346986eccefdc2dd33a9da36ead9`, exact artifact SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, size `1117320736`, Apache-2.0, llama.cpp/Ollama support, 32,768-token model context, no paid-token requirement, and `authority: false`. Put expanded artifact/security/admission/runtime-projection evidence in `first_valid_local_model.yaml` under a strict dedicated schema.

- [ ] **Step 4: Run focused tests and validator**

Run:
- `python -m unittest AI_SKILL_LIBRARY.tests.test_open_model_universe -v`
- `python AI_SKILL_LIBRARY/v4/tools/validate_open_model_universe.py --root .`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(model-universe): add first verified local model record`

---

### Task 2: ChatGPT↔Brain ingress/output contract

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/open_model_universe/chatgpt_brain_contract.yaml`
- Modify: `AI_SKILL_LIBRARY/tests/test_open_model_universe.py`

**Interfaces:**
- Consumes: canonical `task_router` authority and existing Brain flow.
- Produces: declarative request/response fields and invariants; no model choice or permission widening at ingress.

- [ ] **Step 1: Write failing tests**

Require input fields `source`, `request`, `project_context`, `conversation_context`, `desired_depth`, `attachments`, `constraints`, `privacy_class`; exact flow `ingress → task_router → project/domain resolution → memory → skills → Model Mesh → runtime scheduler → verifier → synthesis → response`; ingress prohibitions; response fields `request_id`, `task_id`, `route`, `selected_model_ref`, `runtime_ref`, `verification_status`, `result`, `evidence_refs`, `limitations`, `runtime_metrics_ref`; no hidden reasoning field.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest AI_SKILL_LIBRARY.tests.test_open_model_universe -v`

Expected: FAIL because the contract file does not exist.

- [ ] **Step 3: Add the minimal declarative contract**

Create `chatgpt_brain_contract.yaml` with the exact fields/invariants above and explicit `routing_authority: task_router`, `ingress_selects_model: false`, `ingress_can_widen_permissions: false`, `hidden_reasoning_exposed: false`.

- [ ] **Step 4: Run focused tests**

Run: `python -m unittest AI_SKILL_LIBRARY.tests.test_open_model_universe -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(brain): define ChatGPT ingress response contract`

---

### Task 3: Claude unblock packet and end-to-end governance handoff

**Files:**
- Create: `CHECKPOINTS/WEB_WORK_CONTINUATION_HANDOFF_LATEST.md`
- Modify: `AI_SKILL_LIBRARY/tests/test_open_model_universe.py`

**Interfaces:**
- Consumes: first-model evidence packet and ChatGPT↔Brain contract.
- Produces: `FIRST_VALID_LOCAL_MODEL_RECORD`, exact Claude instruction, blockers/status, and no merge/runtime authority.

- [ ] **Step 1: Write failing test**

Require the handoff to contain `FIRST_VALID_LOCAL_MODEL_RECORD`, immutable model/artifact/checksum/size/quantization/license/admission/source evidence, the exact instruction `Use this record as input to the existing ModelProfile projection path. Do not alter canonical registry semantics.`, refreshed main/PR state, ingress status, unresolved hardware/admission caveats, and `WORK_CONTINUATION_ACTIVE`/`REGISTRY_PROJECTION_READY` without `runtime LIVE` claims.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest AI_SKILL_LIBRARY.tests.test_open_model_universe -v`

Expected: FAIL because the handoff does not yet exist.

- [ ] **Step 3: Write the handoff**

Record current canonical main SHA, PR #427 merged, PR #428 open/runtime-owned, first model evidence, projection mapping, ingress contract, unknowns/blockers, and the next exact task. Keep benchmark/champion fields unset until Web Eval provides empirical evidence.

- [ ] **Step 4: Run full verification**

Run:
- `python -m unittest AI_SKILL_LIBRARY.tests.test_open_model_universe -v`
- `python AI_SKILL_LIBRARY/v4/tools/ci_validate.py`

Expected: all relevant checks PASS; any unrelated infrastructure/deployment check is reported separately rather than relabeled as success.

- [ ] **Step 5: Commit**

Commit message: `docs(model-universe): publish Claude unblock handoff`

## Self-review

- Spec coverage: first model identity/provenance/security, runtime projection, ingress/output contract, Claude handoff, authority boundaries, zero-cost/offline/privacy/lineage and unresolved-field handling are covered.
- Scope exclusions: no runtime, Web QA, Web Eval, integration/merge work.
- No placeholders are permitted in implementation artifacts; unknown factual values use explicit `UNKNOWN` semantics with blocking impact.
