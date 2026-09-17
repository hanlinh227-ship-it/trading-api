# Brain Expansion Integrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate bounded adapters for Langfuse, Ragas, DeepEval, Browser Use, and BAML while registering Microsoft Agent Framework, Letta, and Agno as reference-only sources, preserving all current GitHub Brain authorities.

**Architecture:** Keep task_router, Legion, Model Mesh, Memory Continuity, project authority, security, evidence, evals, and promotion gates canonical. New runtime capabilities live behind independently disableable adapters; reference frameworks never enter the runtime unless a future separately approved promotion changes their status.

**Tech Stack:** Existing repository Python/YAML/JSON tooling, current validators/CI, optional upstream SDKs only after audit, OpenTelemetry-compatible metadata where applicable.

**Spec:** `docs/superpowers/specs/2026-09-17-brain-expansion-integrations-design.md`

## Global Constraints

- Read `AI_SKILL_LIBRARY/checkpoint.json` first and follow its canonical pointers.
- Route work through current `task_router` and current project authority before edits.
- Never create a parallel router, brain, memory authority, agent control plane, or model selector.
- Stable behavior must work when all new adapters are off.
- Do not add an executable upstream dependency until repository identity, pinned ref, license, maintenance, security, supply-chain risk, overlap, permission impact, and rollback are documented.
- Do not persist raw prompts, raw private chat, private tool payloads, secrets, credentials, auth tokens, private keys, or hidden chain-of-thought.
- Browser execution must default to read-only and must not perform financial execution.
- No external eval score can auto-promote a candidate.
- Every completion claim requires actual tests/validators/CI evidence.

---

### Task 1: Refresh authority and audit all upstreams

**Files:**
- Read: `AI_SKILL_LIBRARY/checkpoint.json`
- Read: all checkpoint-selected stable authority files relevant to integrations, security, observability, evals, runtime, and promotion
- Modify/Create only the repository's existing source/intake registry locations selected by current checkpoint

**Interfaces:**
- Consumes: canonical checkpoint, source registry, integration policy, security/eval/observability contracts
- Produces: pinned upstream intake records for all eight candidates

- [ ] **Step 1: Verify baseline**

Run the current brain validator/CI commands discovered from checkpoint and repository docs before changing runtime code. Record the exact commands and outcomes.

- [ ] **Step 2: Audit upstream identity and ref**

For each candidate, verify canonical repo, default branch, current stable/tag/commit choice, archive status, and maintenance state. Use pinned commit/tag refs in any executable dependency or source record; do not rely on a floating branch for activation.

- [ ] **Step 3: Verify license and dependency risk**

Record verified license, notable transitive-license concerns, install surface, native/binary requirements, network behavior, and supply-chain/security concerns. A missing or ambiguous license blocks executable promotion.

- [ ] **Step 4: Classify overlap and permission ceiling**

Map every candidate to an existing capability and explicitly prove it does not become routing, reasoning, memory, model-selection, or control-plane authority.

- [ ] **Step 5: Commit intake-only changes**

Commit the audit separately from executable adapter work.

---

### Task 2: Add shared integration contracts and feature flags

**Files:**
- Modify/Create: follow current repository patterns under `AI_SKILL_LIBRARY/v4/integrations/`, schemas, runtime config, and tests
- Read: `AI_SKILL_LIBRARY/v4/integrations/brain_expansion_architecture.yaml`

**Interfaces:**
- Produces: one normalized adapter contract with `enabled`, `mode`, `authority=false`, pinned upstream metadata, health/failure state, and rollback/disable semantics

- [ ] **Step 1: Write failing contract tests**

Tests must fail if any candidate claims routing/reasoning/memory authority, if runtime adapters are enabled without audit fields, or if reference-only candidates become executable.

- [ ] **Step 2: Run targeted tests and confirm RED**

Use the repository's test runner discovered from current state; capture the expected failing assertions.

- [ ] **Step 3: Implement the minimal shared contract/registry changes**

Reuse existing integration and feature-flag patterns. Do not create a second configuration system.

- [ ] **Step 4: Run targeted tests and confirm GREEN**

- [ ] **Step 5: Commit shared contracts**

---

### Task 3: Implement Langfuse sanitized observability adapter

**Files:**
- Modify/Create: existing observability integration locations and targeted tests only
- Read: `AI_SKILL_LIBRARY/v4/stable/observability.yaml`

**Interfaces:**
- Consumes: already-sanitized diagnostic event metadata
- Produces: optional Langfuse trace/export events; never authority

- [ ] **Step 1: Write failing sanitization and failure-isolation tests**

Assert forbidden payloads cannot enter the adapter, disabled mode emits nothing, and exporter failure does not fail the stable request.

- [ ] **Step 2: Confirm RED**

- [ ] **Step 3: Add the minimal adapter behind a feature flag**

Use existing OpenTelemetry-compatible semantics when possible. Do not add prompt capture.

- [ ] **Step 4: Confirm GREEN and run observability sanitization evals**

- [ ] **Step 5: Commit Langfuse adapter**

---

### Task 4: Implement Ragas and DeepEval CI/offline evaluation adapters

**Files:**
- Modify/Create: existing eval tooling/registry paths and targeted tests
- Read: `AI_SKILL_LIBRARY/evals.yaml`

**Interfaces:**
- Consumes: explicit benchmark fixtures or sanitized test examples
- Produces: normalized evaluation evidence mapped to existing failure taxonomy; never promotion authority

- [ ] **Step 1: Write failing tests**

Assert both adapters are disabled from production request path by default, normalized outputs map to existing eval dimensions, and external scores cannot trigger promotion.

- [ ] **Step 2: Confirm RED**

- [ ] **Step 3: Implement minimal adapters**

Prefer optional/dev dependencies or isolated extras if repository conventions support them. Avoid forcing heavy eval dependencies into FAST/STANDARD runtime.

- [ ] **Step 4: Confirm GREEN and run retrieval/behavior regression fixtures**

- [ ] **Step 5: Commit eval adapters**

---

### Task 5: Implement Browser Use sandbox execution adapter

**Files:**
- Modify/Create: existing browser/execution integration paths, security bindings, tests, and feature flags
- Read: current security policy and browser runtime verification evals

**Interfaces:**
- Consumes: router-approved bounded browser task plus current permission classification
- Produces: verified browser execution result and diagnostic evidence

- [ ] **Step 1: Write failing security tests**

Required failures: default write attempt without explicit allowance; destructive action without existing approval; financial execution through generic browser adapter; credential persistence; success claim without runtime confirmation.

- [ ] **Step 2: Confirm RED**

- [ ] **Step 3: Implement minimal sandbox adapter**

The adapter must not choose objectives. It receives an already-routed task, honors permission boundaries, supports independent disablement, and reports failure accurately.

- [ ] **Step 4: Confirm GREEN and run browser runtime verification tests**

- [ ] **Step 5: Commit Browser Use adapter**

---

### Task 6: Implement optional BAML typed-contract adapter

**Files:**
- Modify/Create: current structured-output/contract integration paths and tests

**Interfaces:**
- Consumes: explicitly selected structured-output contract
- Produces: validated typed output compatible with existing canonical schema semantics

- [ ] **Step 1: Write failing compatibility tests**

Assert BAML is optional, existing Pydantic/JSON Schema behavior remains valid, disabling BAML preserves semantics, and BAML cannot become business-logic authority.

- [ ] **Step 2: Confirm RED**

- [ ] **Step 3: Implement minimal optional adapter**

Avoid provider lock-in and avoid converting unrelated schemas merely to adopt BAML.

- [ ] **Step 4: Confirm GREEN**

- [ ] **Step 5: Commit BAML adapter**

---

### Task 7: Register Microsoft Agent Framework, Letta, and Agno as reference-only sources

**Files:**
- Modify: current source registry/intake files selected by checkpoint
- Test: source/authority/duplicate-capability validators

**Interfaces:**
- Produces: provenance-preserving reference entries only

- [ ] **Step 1: Write or extend validation fixtures**

Fail if these entries become executable dependencies, routing authorities, Memory Continuity writers, Model Mesh replacements, or Legion replacements.

- [ ] **Step 2: Confirm RED for intentionally invalid fixtures**

- [ ] **Step 3: Add reference-only records with verified license/provenance/pinned refs**

- [ ] **Step 4: Confirm GREEN**

- [ ] **Step 5: Commit reference sources**

---

### Task 8: Full verification, activation decision, and handoff

**Files:**
- Modify only if verification finds defects
- Produce: final handoff/checkpoint artifact following current repository conventions

**Interfaces:**
- Consumes: all prior tasks
- Produces: verified integration state with exact activation status per candidate

- [ ] **Step 1: Run targeted adapter tests**

Run every new unit/integration/eval suite and record command/output summary.

- [ ] **Step 2: Run current full brain validators and CI**

Use checkpoint-selected validator paths. Do not substitute a partial test for required CI.

- [ ] **Step 3: Compare against baseline**

Confirm no protected regression in correctness, verification, safety, or authority; check latency/cost impact where relevant.

- [ ] **Step 4: Verify runtime state**

Distinguish `architecture_registered`, `sandbox_ready`, `enabled`, and `production_verified`. Never call an adapter LIVE without actual runtime evidence.

- [ ] **Step 5: Verify rollback**

Disable each runtime adapter independently and rerun the critical stable-path smoke tests.

- [ ] **Step 6: Update canonical checkpoint/release pointers only if current repository policy and all required gates permit**

Do not create a new release or version bump merely to satisfy this plan; follow current release policy exactly.

- [ ] **Step 7: Final commit/handoff**

Report: files changed, upstream refs/licenses, dependencies added, feature flags, exact tests/validators/CI, failures fixed, unresolved blockers, activation state, rollback steps, and commit SHAs.
