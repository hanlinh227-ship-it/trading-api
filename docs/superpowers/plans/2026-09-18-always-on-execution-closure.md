# Always-On Execution Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable background jobs, idempotent leases, bounded retry/dead-letter behavior, and a non-authoritative reconciliation loop without creating a second Brain/router/scheduler.

**Architecture:** Extend the existing Universal Fabric shared-state abstractions and Cloudflare Worker runtime. Cloudflare Queue/Workflow are primary adapters; provider-neutral contracts make NATS/Temporal future escapes. All jobs are routed by `task_router`, models are selected by Model Mesh, and every recovery action stays subordinate.

**Tech Stack:** Python 3, JavaScript Cloudflare Workers, YAML/JSON schemas, Durable Objects, Cloudflare Queue/Workflow adapters, unittest/node tests.

**Spec:** docs/superpowers/specs/2026-09-18-always-on-survival-plane-master-architecture.md

## Global Constraints

- GITHUB_BRAIN_V4 is the sole Brain authority.
- task_router is the sole routing authority.
- Model Mesh remains the model/provider selection layer.
- No new scheduling authority is created.
- PAID_STORAGE_ALLOWED=false and no paid execution fallback is enabled.
- Background loops are bounded/event-driven; no busy polling.
- Duplicate delivery must be side-effect safe.
- Trading authority remains false.

---

### Task 1: Durable job contract

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/always_on/job.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/always_on/policy.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_always_on_job_contract.py`

**Interfaces:**
- Produces `job_id, request_id, project_id, role_id, capability, privacy_class, priority, idempotency_key, attempt, max_attempts, created_at, available_at, deadline_at, lease_owner, lease_expires_at, source_revision, evidence_refs, authority`.
- `authority` must be false.

- [ ] **Step 1: Write failing contract tests**

```python
def test_job_contract_is_non_authoritative():
    policy = load_yaml("AI_SKILL_LIBRARY/v4/always_on/policy.yaml")
    assert policy["routing_authority"] is False
    assert policy["scheduling_authority"] is False
    assert policy["trading_authority"] is False
```

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_always_on_job_contract -v`

Expected: FAIL because files do not exist.

- [ ] **Step 3: Add schema and policy with exact required fields**

- [ ] **Step 4: Run GREEN**

Run: `python3 -m unittest AI_SKILL_LIBRARY.tests.test_always_on_job_contract -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/always_on AI_SKILL_LIBRARY/tests/test_always_on_job_contract.py
git commit -m "feat(always-on): define durable job contract"
```

### Task 2: Queue adapter contract

**Files:**
- Create: `cloudflare-worker/brain-job-queue.js`
- Modify: `cloudflare-worker/universal-state.js`
- Modify: `AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml`
- Test: `cloudflare-worker/test-brain-job-queue.mjs`

**Interfaces:**
- `createJobQueue(env)`
- `enqueue(job)`
- `ack(jobId)`
- `deadLetter(job, reason)`
- Backend names: `cloudflare_queue`, `nats_jetstream`.

- [ ] **Step 1: Write failing Node tests**

```js
assert.equal(queue.authority,false);
await queue.enqueue(job);
assert.equal(fake.sent.length,1);
```

- [ ] **Step 2: Run RED**

Run: `node cloudflare-worker/test-brain-job-queue.mjs`

- [ ] **Step 3: Implement Cloudflare adapter and provider-neutral interface**

- [ ] **Step 4: Run GREEN**

Run: `node cloudflare-worker/test-brain-job-queue.mjs`

- [ ] **Step 5: Commit**

```bash
git add cloudflare-worker/brain-job-queue.js cloudflare-worker/universal-state.js AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml cloudflare-worker/test-brain-job-queue.mjs
git commit -m "feat(always-on): add durable queue adapter"
```

### Task 3: Lease and idempotency state

**Files:**
- Create: `cloudflare-worker/brain-job-state.js`
- Test: `cloudflare-worker/test-brain-job-state.mjs`
- Modify: `cloudflare-worker/prepare-wrangler.mjs`

**Interfaces:**
- Durable Object methods: `acquire(jobId, workerId, ttlMs)`, `complete(jobId, resultRef)`, `fail(jobId, failureKind)`, `releaseExpired(now)`.
- Stale worker results cannot overwrite a newer terminal version.

- [ ] **Step 1: Add failing lease tests**
- [ ] **Step 2: Run RED:** `node cloudflare-worker/test-brain-job-state.mjs`
- [ ] **Step 3: Implement optimistic versioned state and idempotency key guard**
- [ ] **Step 4: Run GREEN**
- [ ] **Step 5: Commit:** `git commit -am "feat(always-on): add job lease state"`

### Task 4: Bounded retry and dead-letter

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/always_on/retry.py`
- Test: `AI_SKILL_LIBRARY/tests/test_always_on_retry.py`

**Interfaces:**
- `classify_failure(kind)->"retryable"|"terminal"`
- `next_retry_delay(attempt, base_seconds=5, cap_seconds=900)->int`
- `should_dead_letter(attempt, max_attempts)->bool`

- [ ] **Step 1: Write failing retry classification tests**
- [ ] **Step 2: Run RED**
- [ ] **Step 3: Implement bounded exponential backoff with deterministic jitter injection for tests**
- [ ] **Step 4: Run GREEN**
- [ ] **Step 5: Commit**

### Task 5: Reconciler

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/always_on/reconciler.py`
- Test: `AI_SKILL_LIBRARY/tests/test_always_on_reconciler.py`

**Interfaces:**
- `reconcile(desired, observed)->list[Action]`
- Actions include `REQUEUE_EXPIRED_LEASE`, `QUARANTINE_PROVIDER`, `REQUEST_REPLICA_REPAIR`, `EXCLUDE_STALE_WORKER`.
- It cannot route or select models.

- [ ] **Step 1: Write failing desired-vs-observed tests**
- [ ] **Step 2: Run RED**
- [ ] **Step 3: Implement pure deterministic reconciliation**
- [ ] **Step 4: Run GREEN**
- [ ] **Step 5: Commit**

### Task 6: Execution closure proof

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/always_on_execution_proof.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Test: `AI_SKILL_LIBRARY/tests/test_always_on_execution_proof.py`

**Required output:**
```text
CONTROL_PLANE_READY=PASS
DURABLE_JOB_READY=PASS
IDEMPOTENCY=PASS
RETRY_DEADLETTER=PASS
RECONCILER=PASS
```

- [ ] **Step 1: Write proof tests**
- [ ] **Step 2: Run focused suites**
- [ ] **Step 3: Run full Python suite**
- [ ] **Step 4: Run `npm --prefix cloudflare-worker run test:universal-fabric`**
- [ ] **Step 5: Run canonical CI validator**
- [ ] **Step 6: Commit proof and checkpoint pointer**
