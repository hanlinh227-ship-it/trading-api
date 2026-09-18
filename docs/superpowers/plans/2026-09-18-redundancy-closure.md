# Critical Role Redundancy Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove every CRITICAL role has at least two independent execution paths and make worker loss/rejoin automatic.

**Architecture:** Extend Free Worker Mesh and Phase 6 operational measurements. Independence is based on failure domain, not logical aliases. Tailscale is a network convenience; Headscale remains an escape contract.

**Tech Stack:** Python 3, existing WorkerRegistry/FreeWorkerMesh/FederationOps, YAML contracts, unittest.

**Spec:** docs/superpowers/specs/2026-09-18-always-on-survival-plane-master-architecture.md

## Global Constraints
- No new worker registry.
- No routing/model-selection authority.
- Same-host aliases never count as independent.
- Privacy and free-only policy outrank capacity.
- Trading authority remains false.

---

### Task 1: Failure-domain identity

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/local_runtime/workers.py`
- Create: `AI_SKILL_LIBRARY/v4/local_runtime/failure_domain.py`
- Test: `AI_SKILL_LIBRARY/tests/test_failure_domain.py`

**Interfaces:**
- `failure_domain(worker)->str`
- `independent(a,b)->bool`

- [ ] **Step 1:** Write tests proving two aliases on one host are not independent.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement deterministic domain identity using host/provider boundary metadata.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 2: Redundancy evaluator

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/critical_role_redundancy.py`
- Test: `AI_SKILL_LIBRARY/tests/test_critical_role_redundancy.py`

**Interfaces:**
- `evaluate_role_redundancy(role_matrix, workers, providers)->dict`
- CRITICAL target: independent_paths >= 2.

- [ ] **Step 1:** Write failing tests for 1-path, 2-path, and fake-alias cases.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement evaluator.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 3: Worker rejoin contract

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/local_runtime/free_worker_mesh.py`
- Test: `AI_SKILL_LIBRARY/tests/test_worker_rejoin.py`

**Interfaces:**
- stale heartbeat -> excluded
- fresh heartbeat + capability probe -> placeable
- no authority mutation

- [ ] **Step 1:** Write stale/rejoin tests.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement bounded rejoin path.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 4: Private mesh adapter contract

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/local_runtime/private_mesh.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_private_mesh_contract.py`

**Interfaces:**
- Backends: `tailscale`, `headscale`.
- Network membership never implies worker admission.

- [ ] **Step 1:** Write failing contract tests.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Add policy and validation.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 5: Redundancy proof

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/redundancy_closure_gate.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`

**Required output:**
```text
CRITICAL_ROLE_REDUNDANCY_READY=PASS|FAIL
REASONING_INDEPENDENT_PATHS=<n>
CODING_INDEPENDENT_PATHS=<n>
VERIFICATION_INDEPENDENT_PATHS=<n>
```

- [ ] **Step 1:** Add proof tests.
- [ ] **Step 2:** Run Phase 6 regression.
- [ ] **Step 3:** Run redundancy proof.
- [ ] **Step 4:** Keep flag FAIL until real second path evidence exists.
- [ ] **Step 5:** Commit.
