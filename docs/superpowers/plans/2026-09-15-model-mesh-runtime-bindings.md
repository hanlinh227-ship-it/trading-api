# Model Mesh Runtime Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all configured and FREE_ONLY-eligible AI providers executable through the existing Model Mesh without storing secret values in GitHub or snapshots.

**Architecture:** Add a separate runtime binding registry keyed by `provider_id`. Build it into a generated Worker module, join bindings to selected models at execution time, and expose sanitized provider-config health. Missing/paid/unknown providers remain inactive without breaking the mesh.

**Tech Stack:** Python 3, Node.js ES modules, Cloudflare Workers, GitHub Actions, existing Model Mesh runtime.

**Spec:** `docs/superpowers/specs/2026-09-15-model-mesh-runtime-bindings-design.md`

## Global Constraints
- FREE_ONLY remains mandatory.
- FAST external execution remains zero.
- SECRET data never leaves Brain.
- Never persist or return credential values.
- Missing provider credentials fail closed per provider, not globally.
- No provider is ACTIVE solely because a key exists.

---

### Task 1: Runtime binding contract
**Files:**
- Create: `AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json`
- Create: `cloudflare-worker/test-model-mesh-bindings.mjs`
- Modify: `cloudflare-worker/package.json`

**Interfaces:**
- Produces binding records `{provider_id, endpoint_family, endpoint_url, secret_name, account_id_env?, enabled}`.

- [ ] Write failing test that validates all registered provider IDs have a safe binding and no secret-looking values.
- [ ] Run `node test-model-mesh-bindings.mjs` and confirm RED because registry/generator is missing.
- [ ] Add runtime binding registry for all current providers.
- [ ] Run test and `npm run check` until GREEN.
- [ ] Commit.

### Task 2: Generate runtime bindings for Worker
**Files:**
- Modify: `cloudflare-worker/prepare-model-mesh.mjs`
- Generated: `cloudflare-worker/generated/model-mesh-bindings.js`
- Test: `cloudflare-worker/test-model-mesh-bindings.mjs`

**Interfaces:**
- Produces `MODEL_MESH_BINDINGS` object keyed by provider ID.

- [ ] Extend test to require generated module shape and reject raw secret values.
- [ ] Confirm RED.
- [ ] Update prepare script to read/validate JSON registry and emit generated module.
- [ ] Run prepare + tests GREEN.
- [ ] Commit.

### Task 3: Join model evidence to runtime binding
**Files:**
- Modify: `cloudflare-worker/model-mesh/provider-client.js`
- Modify: `cloudflare-worker/test-model-mesh-execute.mjs`

**Interfaces:**
- Executor receives evidence-only models and resolves public binding metadata by `provider_id` immediately before calling provider adapter.

- [ ] Change test model to contain no `endpoint_url` or `secret_name`; expect execution to succeed via binding.
- [ ] Confirm RED.
- [ ] Import bindings and resolve selected worker before `callProvider`.
- [ ] Missing binding/secret returns `provider_not_configured` for that worker only.
- [ ] Run model-mesh tests GREEN.
- [ ] Commit.

### Task 4: Sanitized provider configuration health
**Files:**
- Modify existing Model Mesh handler/runtime health path.
- Test: `cloudflare-worker/test-model-mesh-handler.mjs`

**Interfaces:**
- Health returns provider IDs, `configured` boolean, binding-enabled boolean, and eligible model count; never secret values.

- [ ] Add failing health assertions.
- [ ] Confirm RED.
- [ ] Implement sanitized health metadata.
- [ ] Run tests GREEN.
- [ ] Commit.

### Task 5: CI, release integrity, deploy, smoke
**Files:**
- Modify checkpoint/release metadata only through canonical release tooling if hashes drift.
- Modify deploy workflow only if runtime binding generation is not already invoked by `prepare:model-mesh`.

- [ ] Run Python canonical validation and `npm run check`.
- [ ] Ensure release manifest hashes runtime bindings.
- [ ] Open PR and require all existing CI gates GREEN.
- [ ] Merge to main.
- [ ] Deploy exact-main SHA to Cloudflare.
- [ ] Verify `/brain/mesh/health` and planner remain healthy.
- [ ] Verify configured provider statuses without exposing secrets.
- [ ] Provider-by-provider smoke test only eligible FREE_ONLY models; leave missing/paid/unknown providers `INTEGRATED_NOT_ACTIVE`.
