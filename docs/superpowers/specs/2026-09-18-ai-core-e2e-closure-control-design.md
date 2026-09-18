# AI CORE E2E Closure Control Design

**Date:** 2026-09-18  
**Status:** Approved by operator  
**Repository:** hanlinh227-ship-it/trading-api  
**Target PR:** #442  
**Canonical integration writer:** Claude branch / PR #442

## 1. Goal

Close the existing AI CORE end-to-end without creating a second Brain, router, scheduler, registry, evidence authority, or release authority.

The design optimizes for two properties at the same time:

1. maximum useful parallelism across existing workers and models; and
2. one final integration writer so parallel work cannot race shared state.

The project remains AI-CORE-only until the closure gate passes. Trading work stays untouched.

## 2. Canonical Authority

These authorities do not change:

- `GITHUB_BRAIN_V4` is the sole Brain authority.
- `task_router` is the sole routing authority.
- AI Legion defines specialist roles only.
- Model Mesh selects provider/model/runtime for an already-defined role.
- Open Model Universe governs model admission only.
- Claude/local runtime owns runtime lifecycle and residency.
- Existing evidence/release machinery remains the only evidence/release authority.
- Trading execution authority remains outside AI CORE.

Every worker introduced below has:

```text
routing_authority=false
reasoning_authority=false
model_selection_authority=false
merge_authority=false
deployment_authority=false
evidence_authority=false
trading_authority=false
```

## 3. One Writer / Many Workers

### 3.1 Claude

Claude is the sole final integration writer for PR #442.

Claude owns:

- `AI_SKILL_LIBRARY/v4/storage/**`
- integration-sensitive shared state
- final readiness aggregation
- final regression/gate execution
- final reconciliation of accepted specialist patches

No other lane may directly resolve semantic conflicts in Claude-owned shared files.

### 3.2 ChatGPT control lane

ChatGPT coordinates:

- task ownership
- dependency ordering
- model/worker assignment
- overlap prevention
- evidence verification
- durable PR handoffs

ChatGPT does not create a second runtime or routing authority.

### 3.3 DeepSeek

DeepSeek is a bounded implementation worker only.

A DeepSeek coding task must contain:

- exact `allowed_paths`
- exact focused test paths
- expected behavior
- explicit forbidden shared paths
- bounded output budget

DeepSeek never self-selects a shared integration task.

### 3.4 Free cloud model workers

Use every currently eligible FREE_ONLY provider when health permits.

Current eligible cloud paths:

- Groq / `openai/gpt-oss-120b`
- Gemini Developer API / `gemini-flash-latest`
- Cloudflare Workers AI / `@cf/zai-org/glm-4.7-flash`
- OpenRouter / `openrouter/free`
- Mistral / `mistral-small-latest`
- Alibaba Model Studio / `qwen3.8-flash`
- NVIDIA NIM / `meta/muse-glimmer-30b`

Health and quota gates outrank desired parallelism. A provider in COOLDOWN, DEGRADED, or unavailable state is not forced.

Recommended parallel specialist roles:

- Groq: reproduce failures and focused test gaps
- Cloudflare GLM: integration invariant/conflict scan
- OpenRouter: independent code-quality/fail-closed review
- Alibaba Qwen: mechanical task decomposition and candidate patch planning
- NVIDIA NIM: adversarial false-readiness canary design
- Gemini: long-context consistency review when healthy
- Mistral: integration sequencing review when healthy

### 3.5 Local open models

Open Model Universe currently has eight AVAILABLE and mesh-eligible local rows:

- Qwen3 0.6B Q8
- Qwen3 1.7B Q8
- Granite 3.3 2B Q4_K_M
- Qwen3 4B Q4_K_M
- SmolLM2 360M Q8
- Granite 4.2 3B Q4_K_M
- Phi-3 Mini Q4
- Qwen3 8B Q4_K_M

Two rows remain quarantined and must not execute:

- BitNet b1.58 2B I2_S
- Ministral 3 3B Reasoning Q4_K_M

The current PR evidence shows the present local host has execution-liveness failure because the local inference engine terminates with SIGILL. Therefore:

- eligible local models may be addressable in scheduler/JIT/cache contracts;
- they are not counted as executable capacity until a live inference path proves execution;
- execution liveness must be measured separately from resource/heartbeat liveness.

## 4. Closure Gates

AI CORE closure requires six evidence-backed gates.

### Gate A — CONTROL_PLANE_READY

Pass only when canonical ingress, Brain V4, task_router, AI Legion, Model Mesh, verifier, and project-state path remain coherent on the integrated revision.

Existing control-plane tests and release checks may be reused. Do not create a parallel control plane.

### Gate B — DURABLE_JOB_READY

Pass only when the durable job contract, retry semantics, reconciliation behavior, and failure-state persistence are verified together.

Primary implementation surfaces:

- `AI_SKILL_LIBRARY/v4/always_on/job.schema.json`
- `AI_SKILL_LIBRARY/v4/always_on/policy.yaml`
- `AI_SKILL_LIBRARY/v4/always_on/retry.py`
- `AI_SKILL_LIBRARY/v4/always_on/reconciler.py`

### Gate C — CRITICAL_ROLE_REDUNDANCY_READY

Pass only when every critical role has a genuinely independent execution path.

Two models on one execution-dead host do not count as redundancy.

A hosted provider may satisfy a capability fallback only when the existing exact-model-vs-capability-provider truth remains explicit.

### Gate D — SURVIVAL_PLANE_READY

Pass only when survival policy, secret-reference policy, artifact scan, provenance/SBOM trust contracts, and survival-plane proof agree on the current integrated revision.

Primary surfaces:

- `AI_SKILL_LIBRARY/v4/survival/**`
- `AI_SKILL_LIBRARY/v4/tools/survival_plane_proof.py`

### Gate E — DISASTER_RECOVERY_READY

Pass only after a real bounded restore drill proves that protected state can be reconstructed from the declared recovery path.

A schema, manifest, or backup contract alone is not a restore drill.

Primary surfaces:

- `AI_SKILL_LIBRARY/v4/storage/recovery.py`
- `AI_SKILL_LIBRARY/v4/storage/recovery_manifest.json`
- `AI_SKILL_LIBRARY/v4/survival/recovery.py`
- `AI_SKILL_LIBRARY/v4/survival/recovery_policy.yaml`

### Gate F — FRONT_DOOR_READY

Backend readiness is necessary but not sufficient.

The existing Front Door work has already proven:

- backend route readiness
- deterministic project resolution
- client-adapter contract
- new-session resume
- optimistic-version-conflict 409 behavior

`FRONT_DOOR_READY` remains false until both of these exist:

1. native ChatGPT account/platform authorization; and
2. a live production canary proving the real front-door path.

No repository-only test may manufacture this proof.

## 5. Final Aggregation

Create one fail-closed final gate:

`AI_SKILL_LIBRARY/v4/tools/ai_core_always_on_gate.py`

with tests in:

`AI_SKILL_LIBRARY/tests/test_ai_core_always_on_gate.py`

The gate reads evidence produced by the existing subsystems and reports exactly:

```text
CONTROL_PLANE_READY=
DURABLE_JOB_READY=
CRITICAL_ROLE_REDUNDANCY_READY=
SURVIVAL_PLANE_READY=
DISASTER_RECOVERY_READY=
FRONT_DOOR_READY=
AI_CORE_ALWAYS_ON_READY=
```

Rules:

- missing evidence => false
- stale-revision evidence => false
- malformed evidence => false
- a failed sub-gate => false
- `AI_CORE_ALWAYS_ON_READY=true` only if all six sub-gates are true on the same integrated revision

The aggregator must not set any underlying gate itself.

## 6. Evidence Discipline

Every load-bearing evidence file must name the exact revision it proves.

Evidence may be advisory or authoritative only according to existing repository authority rules. Model outputs are always advisory until deterministic tests or existing evidence tooling verifies the claim.

The Free AI accelerator may surface:

- test gaps
- conflict risks
- likely regressions
- candidate fixes
- canary suggestions

It may not publish readiness truth.

## 7. Parallelism Rules

Parallel work is allowed only when file ownership is disjoint.

Allowed in parallel:

- free-model analysis/review
- focused test generation
- DeepSeek changes under exact allowlists
- Claude Storage Mesh/shared integration
- front-door live-canary preparation that does not alter shared state

Serialize:

- shared-state changes
- release/readiness flags
- final evidence aggregation
- semantic merge-conflict resolution
- final release decision

## 8. Recovery and Stability Rules

The system must prefer truthful reduced capacity over false availability.

Examples:

- local SIGILL => mark execution dead and route elsewhere
- provider 429 => cooldown and rotate
- provider 5xx => degrade/fail over
- free-tier uncertainty => exclude from FREE_ONLY
- restore drill absent => disaster recovery false
- native ChatGPT authorization absent => front door false

No health problem may be hidden by a fallback that changes the meaning of the requested execution mode.

## 9. End-to-End Definition of Done

The project is complete only when all of the following hold on the canonical integrated revision:

- PR #442 CI is green
- focused subsystem tests are green
- combined AI CORE tests are green
- Storage Mesh tests are green
- Always-On tests are green
- Survival tests are green
- worker execution liveness is truthful
- critical-role redundancy is independently proven
- a real restore drill passes
- cloud/provider execution evidence is live
- local execution is either live-proven or explicitly excluded from executable capacity
- Front Door backend readiness passes
- native ChatGPT authorization is present
- the live production Front Door canary passes
- all six closure gates pass
- `AI_CORE_ALWAYS_ON_READY=true`

Trading remains untouched until this definition is satisfied.

## 10. Rollback

If any new closure integration breaks a previously green subsystem:

1. keep the failing readiness gate false;
2. revert only the smallest closure change that introduced the regression;
3. preserve evidence showing the failed attempt;
4. continue other independent specialist work;
5. never rewrite evidence to make a failing gate pass.
