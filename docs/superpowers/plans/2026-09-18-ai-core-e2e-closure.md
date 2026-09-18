# AI CORE E2E Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close AI CORE end-to-end with six evidence-backed readiness gates, truthful execution capacity, a real restore drill, and a live Front Door canary while preserving one canonical integration writer.

**Architecture:** Claude is the sole final integration writer. DeepSeek and FREE_ONLY cloud models operate as bounded specialist workers whose outputs are advisory or patch candidates until deterministic tests and existing evidence tooling verify them. A new fail-closed aggregator reads six independent gate evidences and emits `AI_CORE_ALWAYS_ON_READY=true` only when all six prove the same integrated revision.

**Tech Stack:** Python 3, unittest/pytest-compatible tests already used by AI_SKILL_LIBRARY, Node.js for Cloudflare Worker canary tests, GitHub Actions, existing Brain V4 / Model Mesh / Storage Mesh contracts.

**Spec:** `docs/superpowers/specs/2026-09-18-ai-core-e2e-closure-control-design.md`

## Global Constraints

- `GITHUB_BRAIN_V4` remains the sole Brain authority.
- `task_router` remains the sole routing authority.
- Claude remains the sole final integration writer for PR #442.
- Trading code and trading execution remain untouched.
- FREE_ONLY remains mandatory; no paid fallback and no quota circumvention.
- A model/provider in COOLDOWN, DEGRADED, QUARANTINED, or execution-dead state must not be counted as live capacity.
- The two quarantined local models remain non-executable until their existing admission/runtime rules clear them.
- Missing, malformed, stale-revision, or contradictory evidence must fail closed.
- No repository-only test may set `FRONT_DOOR_READY=true` without native ChatGPT/platform authorization plus a real live production canary.
- No schema/manifest-only check may set `DISASTER_RECOVERY_READY=true` without a real restore drill.
- No two models on one execution-dead host may satisfy critical-role redundancy.
- Shared readiness/release state is modified only by Claude after all task-local tests pass.

---

### Task 0: Make canonical CI collect every merged closure test

**Files:**
- Modify: `.github/workflows/ai-skill-library-ci.yml`

**Interfaces:**
- Consumes: the existing four pytest-style closure test modules.
- Produces: canonical CI evidence that all 41 module-level tests actually execute on every relevant PR/push.

- [ ] **Step 1: Add one focused pytest collection/execution step after canonical `ci_validate.py`**

Install pytest only in this CI job, without changing runtime/library dependencies:

```bash
python -m pip install 'pytest>=8,<9'
```

Then run exactly:

```bash
python -m pytest -q \
  AI_SKILL_LIBRARY/tests/test_survival_plane_proof.py \
  AI_SKILL_LIBRARY/tests/test_survival_recovery.py \
  AI_SKILL_LIBRARY/tests/test_always_on_retry.py \
  AI_SKILL_LIBRARY/tests/test_always_on_reconciler.py
```

- [ ] **Step 2: Verify the pytest step reports 41 collected tests**

Expected: 41 tests collected and all pass.

- [ ] **Step 3: Keep the existing unittest-based `ci_validate.py` path unchanged**

Do not replace unittest globally and do not rewrite assertions merely to satisfy the collector.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ai-skill-library-ci.yml
git commit -m "ci(ai-core): execute pytest-only closure tests"
```

---

### Task 1: Add the fail-closed six-gate aggregator

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/ai_core_always_on_gate.py`
- Create: `AI_SKILL_LIBRARY/tests/test_ai_core_always_on_gate.py`

**Interfaces:**
- Consumes: six evidence JSON files supplied as explicit CLI arguments plus `--source-sha <sha>`.
- Produces: one JSON object and seven machine-readable stdout lines:
  `CONTROL_PLANE_READY`, `DURABLE_JOB_READY`, `CRITICAL_ROLE_REDUNDANCY_READY`, `SURVIVAL_PLANE_READY`, `DISASTER_RECOVERY_READY`, `FRONT_DOOR_READY`, `AI_CORE_ALWAYS_ON_READY`.

- [ ] **Step 1: Write failing tests for missing evidence, stale SHA, malformed evidence, one false gate, and all-six-pass**

Use temporary JSON fixtures shaped as:

```python
{
    "source_sha": "abc123",
    "gate": "CONTROL_PLANE_READY",
    "ready": True,
    "proofs": ["test-proof"]
}
```

Assert that every negative case returns process exit code `1`, keeps the affected gate false, and keeps `AI_CORE_ALWAYS_ON_READY=false`. Assert that six valid fixtures with the same SHA return `0` and `AI_CORE_ALWAYS_ON_READY=true`.

- [ ] **Step 2: Run the new test module and verify RED**

Run:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_core_always_on_gate -v
```

Expected: import/file-not-found failure because the gate does not exist yet.

- [ ] **Step 3: Implement the minimal aggregator**

Implement a CLI that:

```text
requires exactly one evidence path per named gate
loads JSON without implicit defaults
requires evidence.source_sha == --source-sha
requires evidence.gate == expected gate name
requires evidence.ready is literally true
requires proofs to be a non-empty list
sets final ready only when all six validations pass
writes optional --output JSON atomically
prints each gate line and final line
returns 0 only when final ready is true
```

Do not let the aggregator mutate any underlying evidence file.

- [ ] **Step 4: Run Task 1 tests and verify GREEN**

Run the same unittest command.

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/tools/ai_core_always_on_gate.py AI_SKILL_LIBRARY/tests/test_ai_core_always_on_gate.py
git commit -m "feat(ai-core): add fail-closed always-on readiness gate"
```

---

### Task 2: Make execution liveness load-bearing for redundancy

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/worker_execution_liveness.py`
- Modify: `AI_SKILL_LIBRARY/tests/test_worker_execution_liveness.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/critical_role_redundancy_proof.py`
- Create: `AI_SKILL_LIBRARY/tests/test_critical_role_redundancy_proof.py`

**Interfaces:**
- Consumes: current worker/runtime records plus execution-liveness evidence.
- Produces: `CHECKPOINTS/evidence/CRITICAL_ROLE_REDUNDANCY_PROOF.json` with gate name `CRITICAL_ROLE_REDUNDANCY_READY`.

- [ ] **Step 1: Add failing tests for execution-dead local workers**

Create fixtures where a local worker has healthy heartbeat/resources but `execution_liveness="EXECUTION_DEAD"`. Assert that it cannot satisfy any critical role and cannot count as an independent redundant path.

Create a second fixture with two hosted workers from independent provider paths and assert that redundancy can pass only when both are execution-live and policy-eligible.

- [ ] **Step 2: Run focused liveness/redundancy tests and verify RED**

```bash
python -m unittest   AI_SKILL_LIBRARY.tests.test_worker_execution_liveness   AI_SKILL_LIBRARY.tests.test_critical_role_redundancy_proof -v
```

Expected: new redundancy tests fail before the proof tool exists.

- [ ] **Step 3: Extend liveness output without changing its existing truth semantics**

Ensure `worker_execution_liveness.py` emits enough structured fields for downstream proof:

```text
worker_id
execution_liveness
stranded_roles
critical_stranded
source_sha
proof_timestamp
```

A SIGILL/subprocess exit 132 remains execution-dead; it must never be converted into a catchable healthy state.

- [ ] **Step 4: Implement critical-role redundancy proof**

The proof tool must:

- reject execution-dead workers;
- reject duplicate paths that share the same execution host/failure domain when independence is required;
- preserve exact-model versus capability-provider distinction;
- list every critical role and the independent paths that cover it;
- emit `ready=false` if any critical role has fewer than two qualifying independent paths;
- bind the evidence to the current source SHA.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 2 command.

Expected: all liveness/redundancy tests pass.

- [ ] **Step 6: Commit**

```bash
git add   AI_SKILL_LIBRARY/v4/tools/worker_execution_liveness.py   AI_SKILL_LIBRARY/tests/test_worker_execution_liveness.py   AI_SKILL_LIBRARY/v4/tools/critical_role_redundancy_proof.py   AI_SKILL_LIBRARY/tests/test_critical_role_redundancy_proof.py
git commit -m "feat(ai-core): gate redundancy on real execution liveness"
```

---

### Task 3: Produce a real bounded restore-drill proof

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/storage/recovery.py`
- Modify: `AI_SKILL_LIBRARY/v4/survival/recovery.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/storage_restore_drill.py`
- Create: `AI_SKILL_LIBRARY/tests/test_storage_restore_drill.py`

**Interfaces:**
- Consumes: existing recovery manifest and recovery APIs.
- Produces: `CHECKPOINTS/evidence/STORAGE_RESTORE_DRILL.json` with gate name `DISASTER_RECOVERY_READY`.

- [ ] **Step 1: Write a failing temporary-directory restore drill**

The test must create protected sample state containing:

```json
{
  "project_id": "e2e-closure-test",
  "revision": 7,
  "payload": {"marker": "restore-me"}
}
```

The test must:

1. persist it through the existing recovery/backup contract into a temporary location;
2. remove the primary temporary state;
3. restore into a different empty temporary location;
4. verify byte/content identity and recorded revision;
5. verify the drill evidence names the current source SHA and exact restored artifact identity.

Also test corrupt backup input and missing backup input; both must produce `ready=false`.

- [ ] **Step 2: Run the restore-drill test and verify RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_storage_restore_drill -v
```

Expected: failure because the drill tool does not exist yet.

- [ ] **Step 3: Implement only the recovery hooks required by the real drill**

Reuse current storage/survival recovery APIs. Do not create a second backup framework. The drill tool may use temporary filesystem adapters for CI, but the same manifest verification and integrity checks used by production recovery must run.

Evidence must include:

```text
gate=DISASTER_RECOVERY_READY
ready
source_sha
backup_identity
restored_identity
integrity_verified
primary_removed_before_restore
restore_destination_was_empty
proofs
```

- [ ] **Step 4: Run restore tests and existing storage recovery tests**

```bash
python -m unittest   AI_SKILL_LIBRARY.tests.test_storage_restore_drill   AI_SKILL_LIBRARY.tests.test_survival_recovery -v
```

Then run the existing Storage Mesh focused suite selected by the repository's current storage test pattern.

Expected: all focused recovery/storage tests pass.

- [ ] **Step 5: Commit**

```bash
git add   AI_SKILL_LIBRARY/v4/storage/recovery.py   AI_SKILL_LIBRARY/v4/survival/recovery.py   AI_SKILL_LIBRARY/v4/tools/storage_restore_drill.py   AI_SKILL_LIBRARY/tests/test_storage_restore_drill.py
git commit -m "feat(ai-core): prove disaster recovery with a real restore drill"
```

---

### Task 4: Seal Control, Durable Job, and Survival evidence on one revision

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/survival_plane_proof.py`
- Create: `AI_SKILL_LIBRARY/v4/tools/ai_core_closure_evidence.py`
- Create: `AI_SKILL_LIBRARY/tests/test_ai_core_closure_evidence.py`

**Interfaces:**
- Consumes: current control-plane tests, Always-On contract/tests, Survival proof/tests.
- Produces three evidence files:
  - `CHECKPOINTS/evidence/CONTROL_PLANE_READY.json`
  - `CHECKPOINTS/evidence/DURABLE_JOB_READY.json`
  - `CHECKPOINTS/evidence/SURVIVAL_PLANE_READY.json`

- [ ] **Step 1: Write failing evidence tests**

For each evidence file assert:

- `source_sha` equals the exact tested revision;
- `gate` is the exact expected name;
- `ready` is true only when every named focused command returns zero;
- `proofs` contains the exact command names/results used.

Simulate one failing command and assert the corresponding evidence remains false.

- [ ] **Step 2: Run the new tests and verify RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_ai_core_closure_evidence -v
```

- [ ] **Step 3: Implement the evidence runner**

The runner executes only focused existing checks:

```text
Control:
  personal AI control-plane wiring
  canonical route / project-state coherence checks already present

Durable job:
  test_always_on_job_contract
  test_always_on_retry
  test_always_on_reconciler

Survival:
  test_survival_policy
  test_survival_secrets
  test_survival_provenance
  test_survival_recovery
  test_survival_plane_proof
```

Do not duplicate subsystem logic in the evidence runner. Capture process exit status and bind output to the supplied source SHA.

- [ ] **Step 4: Run focused evidence tests and subsystem suites**

Run:

```bash
python -m unittest   AI_SKILL_LIBRARY.tests.test_ai_core_closure_evidence   AI_SKILL_LIBRARY.tests.test_always_on_job_contract   AI_SKILL_LIBRARY.tests.test_always_on_retry   AI_SKILL_LIBRARY.tests.test_always_on_reconciler   AI_SKILL_LIBRARY.tests.test_survival_policy   AI_SKILL_LIBRARY.tests.test_survival_secrets   AI_SKILL_LIBRARY.tests.test_survival_provenance   AI_SKILL_LIBRARY.tests.test_survival_recovery   AI_SKILL_LIBRARY.tests.test_survival_plane_proof -v
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add   AI_SKILL_LIBRARY/v4/tools/survival_plane_proof.py   AI_SKILL_LIBRARY/v4/tools/ai_core_closure_evidence.py   AI_SKILL_LIBRARY/tests/test_ai_core_closure_evidence.py
git commit -m "feat(ai-core): seal closure evidence on one revision"
```

---

### Task 5: Reuse and harden the existing production Front Door canary

**Files:**
- Modify: `cloudflare-worker/validate-universal-canary.mjs`
- Modify: `cloudflare-worker/test-universal-canary.mjs`
- Create only if needed for evidence normalization: `AI_SKILL_LIBRARY/v4/tools/front_door_readiness_proof.py`
- Test only if that proof tool is created: `AI_SKILL_LIBRARY/tests/test_front_door_readiness_proof.py`

**Interfaces:**
- Consumes: existing authorized production canary results from `validate-universal-canary.mjs` plus an external/native ChatGPT account-authorization proof when the platform makes one available.
- Produces: `CHECKPOINTS/evidence/FRONT_DOOR_LIVE_CANARY.json` with gate name `FRONT_DOOR_READY`.

- [ ] **Step 1: Preserve the already-proven production checks**

Do not duplicate or remove the existing canary checks for:

```text
/brain/universal/health exact source SHA
all user adapters
project-state read
project-state write
independent Claude bootstrap/resume
stale expected_version -> HTTP 409
project isolation
high-risk fail-closed behavior
```

- [ ] **Step 2: Add anti-cache proof to the existing request helper**

Add a per-run unpredictable public canary nonce that is safe to log and send it as a request header or query parameter together with `cache-control: no-store`. Tests must assert each live canary request carries the anti-cache marker and that the marker contains no secret/token material.

- [ ] **Step 3: Keep native account authorization fail-closed**

The repository can prove service-principal adapter authentication but cannot prove native ChatGPT account/platform authorization by itself.

The normalized Front Door evidence must therefore remain:

```json
{
  "gate": "FRONT_DOOR_READY",
  "ready": false
}
```

until both the live canary passes on the exact source SHA and a real platform/native-account authorization proof is supplied.

- [ ] **Step 4: Run the existing canary tests**

```bash
cd cloudflare-worker
node test-universal-canary.mjs
```

Expected: green, including new anti-cache assertions.

- [ ] **Step 5: Execute the real production canary through the existing authorized deployment workflow**

Do not paste tokens into source or chat. The production run must prove the exact deployed source SHA.

- [ ] **Step 6: Commit only the minimal canary hardening**

```bash
git add cloudflare-worker/validate-universal-canary.mjs cloudflare-worker/test-universal-canary.mjs
git commit -m "test(front-door): harden live canary against cached proof"
```

If a separate evidence-normalization tool is necessary, commit it with its focused test in the same task.

---

### Task 6: Integrate all six evidences and close AI CORE

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/ci_validate.py` only after all six evidence producers exist
- Use: `AI_SKILL_LIBRARY/v4/tools/ai_core_always_on_gate.py`
- Update only through existing evidence/release authority: canonical readiness/release record already used by the repository

**Interfaces:**
- Consumes: six gate evidence files from Tasks 2–5 plus existing control/durable/survival evidence.
- Produces: final `AI_CORE_ALWAYS_ON_READY` result for the exact PR #442 integrated revision.

- [ ] **Step 1: Run every focused subsystem suite on the exact integration SHA**

Required groups:

```text
Storage Mesh
Always-On
Survival
worker execution liveness
critical-role redundancy
Front Door backend/unit canary
control-plane wiring
```

Expected: all deterministic tests green.

- [ ] **Step 2: Generate all non-human evidence on the same SHA**

Generate:

```text
CONTROL_PLANE_READY.json
DURABLE_JOB_READY.json
CRITICAL_ROLE_REDUNDANCY_PROOF.json
SURVIVAL_PLANE_READY.json
STORAGE_RESTORE_DRILL.json
```

Generate `FRONT_DOOR_LIVE_CANARY.json` only from the authorized real canary.

- [ ] **Step 3: Run the six-gate aggregator**

```bash
python AI_SKILL_LIBRARY/v4/tools/ai_core_always_on_gate.py   --source-sha "$(git rev-parse HEAD)"   --control CHECKPOINTS/evidence/CONTROL_PLANE_READY.json   --durable-job CHECKPOINTS/evidence/DURABLE_JOB_READY.json   --critical-redundancy CHECKPOINTS/evidence/CRITICAL_ROLE_REDUNDANCY_PROOF.json   --survival CHECKPOINTS/evidence/SURVIVAL_PLANE_READY.json   --disaster-recovery CHECKPOINTS/evidence/STORAGE_RESTORE_DRILL.json   --front-door CHECKPOINTS/evidence/FRONT_DOOR_LIVE_CANARY.json   --output CHECKPOINTS/evidence/AI_CORE_ALWAYS_ON_READY.json
```

Expected before the live Front Door canary: exit `1`, `FRONT_DOOR_READY=false`, `AI_CORE_ALWAYS_ON_READY=false`.

Expected after all six real proofs: exit `0` and all seven lines true.

- [ ] **Step 4: Wire the final gate into canonical validation only after it can legitimately pass**

Add the final gate to `ci_validate.py` so release validation fails closed if any of the six proofs is later removed, stale, or false.

Do not weaken tests to make the gate green.

- [ ] **Step 5: Run canonical validation**

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$SOURCE_SHA"
```

Expected: green with no newly introduced failure.

- [ ] **Step 6: Run one final whole-branch review with the most capable available reviewer**

The reviewer must inspect:

- all closure-gate code;
- restore-drill correctness;
- execution-liveness truthfulness;
- redundancy independence;
- Front Door canary fail-closed behavior;
- any deferred/minor findings from specialist workers.

Any Critical/Important finding is fixed and re-reviewed before closure.

- [ ] **Step 7: Record readiness through the existing canonical authority**

Only when the exact integrated revision has all six gates true may the canonical release/evidence authority record:

```text
AI_CORE_ALWAYS_ON_READY=true
```

No hand-edited readiness override is permitted.

- [ ] **Step 8: Confirm Trading remained untouched**

Verify the closure diff contains no Trading implementation changes.

- [ ] **Step 9: Commit final closure wiring**

```bash
git add AI_SKILL_LIBRARY/v4/tools/ci_validate.py CHECKPOINTS/evidence
git commit -m "feat(ai-core): close always-on E2E readiness gates"
```
