# Front Door Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make fresh authenticated chat sessions resume canonical project state through the existing Universal Brain front door and prove account/client integration separately from backend readiness.

**Architecture:** Reuse `/brain/bootstrap`, BrainProjectState, Universal Auth, and client adapters. Add default-project resolution and a readiness gate. Repository code never claims it can force-install a native ChatGPT/Claude integration.

**Tech Stack:** Cloudflare Worker JavaScript, existing BrainProjectState Durable Object, YAML client adapter registry, node tests.

**Spec:** docs/superpowers/specs/2026-09-18-always-on-survival-plane-master-architecture.md

## Global Constraints
- ChatGPT/Claude/Gemini are clients, not Brain authorities.
- No full transcript becomes canonical state.
- Project continuity remains bounded and versioned.
- Account-level connector authorization is human-controlled evidence.

---

### Task 1: Default project resolution

**Files:**
- Create: `cloudflare-worker/project-resolution.js`
- Test: `cloudflare-worker/test-project-resolution.mjs`

**Interfaces:**
- `resolveProjectId(request, clientConfig, storedDefault)->string|null`
- Explicit request project wins; otherwise approved default; never guess across projects.

- [ ] **Step 1:** Write failing resolution tests.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement deterministic resolver.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 2: Bootstrap integration

**Files:**
- Modify: `cloudflare-worker/project-continuity-handler.js`
- Test: `cloudflare-worker/test-project-continuity-handler.mjs`

**Interfaces:**
- Fresh session returns runtime revision, project state, latest handoff, job refs, and explicit initialized state.
- No secret material or raw transcript.

- [ ] **Step 1:** Add failing fresh-session tests.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Integrate resolver without widening scopes.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 3: Client adapter readiness evidence

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/adapters/registry.yaml`
- Create: `AI_SKILL_LIBRARY/v4/front_door/readiness.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_front_door_readiness.py`

**Interfaces:**
- Each client has backend_contract_ready and account_integration_verified as separate booleans.
- FRONT_DOOR_READY requires both for the selected primary client.

- [ ] **Step 1:** Write tests proving backend-ready alone cannot set FRONT_DOOR_READY.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Add readiness schema/policy.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 4: New-session canary

**Files:**
- Modify: `cloudflare-worker/validate-universal-canary.mjs`
- Test: `cloudflare-worker/test-universal-canary.mjs`

**Interfaces:**
- Session A writes state version N.
- Independent Session B with no transcript bootstraps same N.
- Stale update receives 409.

- [ ] **Step 1:** Add failing canary assertions.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Extend canary implementation.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Commit.

### Task 5: Final AI Core always-on gate

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/ai_core_always_on_gate.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Test: `AI_SKILL_LIBRARY/tests/test_ai_core_always_on_gate.py`

**Interfaces:**
- Reads six readiness proofs only.
- Emits `AI_CORE_ALWAYS_ON_READY=true` only when all six are true.

- [ ] **Step 1:** Write failing truth-table tests for all six flags.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Implement gate.
- [ ] **Step 4:** Run GREEN.
- [ ] **Step 5:** Run full Python + Universal Fabric + Phase 6 + Storage Mesh gates.
- [ ] **Step 6:** Commit.
