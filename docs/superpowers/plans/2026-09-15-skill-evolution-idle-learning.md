# Skill Evolution and Idle Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fuse AutoSkill/SkillEvo patterns into Brain-native continual learning so verified experience can create/improve/merge skills, mutations compete against protected baselines, and a cloud scheduler can generate low-risk background learning work without direct Stable mutation.

**Architecture:** Extend Evergreen with a versioned Skill Factory/Evolution Engine. It consumes sanitized trajectories and Peer Tri-Layer evidence, writes only quarantine/evolution artifacts, runs replay/eval/mutation tournaments, and emits promotion candidates through existing admission/harmonization gates. A separate Cloudflare autonomy control plane uses Cron + Queue + D1 to schedule bounded idle objectives; compute/execution is delegated to Legion/Gateway workers and never performed in the FAST request path.

**Tech Stack:** Python 3.12, PyYAML, jsonschema, unittest, JavaScript Cloudflare Workers, D1, Cloudflare Queues/Cron, node:test.

**Spec:** `docs/superpowers/specs/2026-09-15-peer-tri-layer-ai-legion-design.md`

## Global Constraints

- AutoSkill/SkillEvo is a pattern source, not an authority or mandatory runtime framework.
- Persist only observable inputs/outcomes, corrections, provenance, evals and artifact refs; never hidden chain-of-thought.
- Candidate skill actions are exactly `discard | improve | merge | create`.
- Generated skills remain quarantine-only until admission, protected evals, sandbox/canary and promotion pass.
- Learning Layer A/B/C identity does not determine promotion Risk Class A/B/C/D.
- Self-learning never widens permissions, accesses stable secrets, signs wallets, executes financial actions, or performs destructive production writes.
- Idle learning yields to active user work and respects API/token/compute/concurrency/storage/network budgets.
- Open discovery may fetch public sources but cannot auto-trust executable code.
- Stable survives all learning/scheduler failures.

---

### Task 1: Define skill lineage, replay and mutation contracts

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/legion/evolution.yaml`
- Create: `AI_SKILL_LIBRARY/v4/schemas/skill_lineage.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/skill_replay.schema.json`
- Create: `AI_SKILL_LIBRARY/v4/schemas/skill_mutation.schema.json`
- Test: `AI_SKILL_LIBRARY/tests/test_skill_evolution_contracts.py`

**Interfaces:**
- Produces canonical states: `incubating`, `eval_ready`, `benchmarked`, `canary`, `champion_candidate`, `promoted`, `superseded`, `retired`.

- [ ] **Step 1: Write RED tests**

```python
def test_evolution_policy_never_writes_stable_directly():
    policy = load_yaml("AI_SKILL_LIBRARY/v4/legion/evolution.yaml")
    assert policy["direct_stable_write"] is False
    assert policy["permission_expansion_by_learning"] is False
    assert policy["actions"] == ["discard", "improve", "merge", "create"]
```

Also validate lineage IDs, parent/champion revision, replay sample provenance, immutable split labels (`mutate_dev`, `promotion_test`, `protected_regression`) and mutation budget bounds.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_evolution_contracts -v
```

- [ ] **Step 3: Implement schemas and policy**

`evolution.yaml` minimum:

```yaml
version: 1
direct_stable_write: false
permission_expansion_by_learning: false
actions: [discard, improve, merge, create]
mutation_budget: {min: 1, max: 6}
replay_splits: [mutate_dev, promotion_test, protected_regression]
promotion_requires: [provenance, license, security, authority, evals, regression, canary]
judge_only_promotion: forbidden
```

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_evolution_contracts -v
git add AI_SKILL_LIBRARY/v4/legion/evolution.yaml AI_SKILL_LIBRARY/v4/schemas/skill_*.schema.json AI_SKILL_LIBRARY/tests/test_skill_evolution_contracts.py
git commit -m "feat: define skill evolution contracts"
```

---

### Task 2: Implement experience mining and deterministic triage

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/tools/skill_evolution.py`
- Test: `AI_SKILL_LIBRARY/tests/test_skill_experience_mining.py`

**Interfaces:**
- `sanitize_trajectory(raw: dict) -> dict`
- `extract_reusable_experience(trajectory: dict) -> list[dict]`
- `triage_candidate(candidate: dict, existing_skills: list[dict]) -> str`
- `build_lineage_record(candidate: dict, *, action: str, now: str) -> dict`

- [ ] **Step 1: Write RED tests**

Test that accepted user correction + reproducible fix yields an experience candidate; one-off unverified text yields none; hidden reasoning/secrets/raw private prompts cause rejection; semantically matching skill returns `improve` or `merge`; distinct measured capability returns `create`; weak/duplicate candidate returns `discard`.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_experience_mining -v
```

- [ ] **Step 3: Implement sanitizer and triage**

Persist only:

```python
ALLOWED_TRAJECTORY_FIELDS = {
    "task_id", "domain", "primary_skill", "observable_input_summary",
    "observable_output_summary", "verification_outcomes", "user_corrections",
    "failure_refs", "evidence_refs", "artifact_refs", "timestamp"
}
```

Triage must call existing `admit_skill()` for any proposed `create` candidate before returning an promotable artifact.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_experience_mining -v
git add AI_SKILL_LIBRARY/v4/tools/skill_evolution.py AI_SKILL_LIBRARY/tests/test_skill_experience_mining.py
git commit -m "feat: mine reusable skill experience"
```

---

### Task 3: Implement replay construction, eval compilation and bounded mutations

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/skill_evolution.py`
- Create: `AI_SKILL_LIBRARY/tests/fixtures/skill_evolution/replay.json`
- Create: `AI_SKILL_LIBRARY/tests/test_skill_evolution_replay.py`

**Interfaces:**
- `build_replay(lineage: dict, samples: list[dict]) -> dict`
- `compile_eval_rules(skill: dict, replay: dict) -> list[dict]`
- `generate_mutations(skill: dict, *, evidence: list[dict], budget: int) -> list[dict]`

- [ ] **Step 1: Write RED tests**

Require frozen deterministic replay, no sample leakage between `mutate_dev` and `promotion_test`, 3-6 binary eval rules when enough evidence exists, mutation budget <=6, and mutations unable to change risk/permission ceilings unless separately classified for manual authorization.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_evolution_replay -v
```

- [ ] **Step 3: Implement replay and mutations**

Mutation candidates may change prompt/procedure/checklist/output validation only inside the skill's existing contract. Any request to add tools, permissions, privileged sources, financial execution, credential access or destructive action is emitted as `permission_expansion=true` and cannot proceed unattended.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_evolution_replay -v
git add AI_SKILL_LIBRARY/v4/tools/skill_evolution.py AI_SKILL_LIBRARY/tests/fixtures/skill_evolution AI_SKILL_LIBRARY/tests/test_skill_evolution_replay.py
git commit -m "feat: add replay driven skill mutations"
```

---

### Task 4: Implement champion selection and promotion-candidate output

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/tools/skill_evolution.py`
- Modify: `AI_SKILL_LIBRARY/v4/tools/evergreen.py`
- Test: `AI_SKILL_LIBRARY/tests/test_skill_evolution_promotion.py`

**Interfaces:**
- `evaluate_mutation(baseline: dict, mutation: dict, eval_results: list[dict]) -> dict`
- `select_champion(baseline: dict, candidates: list[dict], policy: dict) -> dict`
- `build_promotion_candidate(champion: dict, lineage: dict) -> dict`

- [ ] **Step 1: Write RED tests**

Test candidate must beat baseline quality by existing continuous-intelligence requirement where applicable, protected dimensions may not regress, judge preference alone is insufficient, unresolved conflict blocks promotion, and Class C/D risk still follows current explicit-authorization rules.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_evolution_promotion -v
```

- [ ] **Step 3: Implement selection using existing baseline comparison**

Reuse `compare_candidate()` semantics from `evergreen.py` rather than creating a competing promotion algorithm. `build_promotion_candidate()` writes only to `AI_SKILL_LIBRARY/v4/evergreen/quarantine/` or an explicitly supplied temporary output path.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_evolution_promotion -v
git add AI_SKILL_LIBRARY/v4/tools/skill_evolution.py AI_SKILL_LIBRARY/v4/tools/evergreen.py AI_SKILL_LIBRARY/tests/test_skill_evolution_promotion.py
git commit -m "feat: gate evolved skill champions"
```

---

### Task 5: Define idle-learning job types and budgets

**Files:**
- Create: `AI_SKILL_LIBRARY/v4/legion/autonomy.yaml`
- Create: `AI_SKILL_LIBRARY/v4/schemas/autonomy_job.schema.json`
- Test: `AI_SKILL_LIBRARY/tests/test_idle_learning_policy.py`

**Interfaces:**
- Job types: `failure_analysis`, `capability_gap`, `source_discovery`, `free_model_discovery`, `source_reverify`, `skill_mining`, `skill_mutation`, `regression_run`, `retrieval_eval`, `routing_benchmark`, `sandbox_patch`, `canary_low_risk`.

- [ ] **Step 1: Write RED tests**

Assert every idle job has domain, risk class, permission ceiling, token/API/compute/network/storage budget, idempotency key and active-user preemption flag. Assert `live_financial_execution`, `credential_mutation`, `destructive_production`, `permission_widening` are absent/forbidden.

- [ ] **Step 2: Run RED**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_idle_learning_policy -v
```

- [ ] **Step 3: Implement bounded policy**

Use existing global hard limits; autonomy policy may be stricter but never larger. Default one idle job lease at a time per domain, max retry 3, and all network/source discovery work remains Evergreen-only.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_idle_learning_policy -v
git add AI_SKILL_LIBRARY/v4/legion/autonomy.yaml AI_SKILL_LIBRARY/v4/schemas/autonomy_job.schema.json AI_SKILL_LIBRARY/tests/test_idle_learning_policy.py
git commit -m "feat: define bounded idle learning jobs"
```

---

### Task 6: Build the cloud autonomy control plane with durable queue/state

**Files:**
- Create: `cloudflare-worker/brain-autonomy.js`
- Create: `cloudflare-worker/test-brain-autonomy.mjs`
- Create: `cloudflare-worker/migrations/0001_brain_autonomy.sql`
- Create: `cloudflare-worker/wrangler-autonomy.toml`
- Create: `cloudflare-worker/README-brain-autonomy.md`

**Interfaces:**
- Cron handler: generate due low-risk objectives only.
- Queue consumer: lease/dispatch jobs idempotently.
- HTTP `GET /brain/autonomy/health`
- HTTP `GET /brain/autonomy/status`
- HTTP `POST /brain/autonomy/enqueue` for authenticated internal callers only.

- [ ] **Step 1: Create D1 schema**

```sql
CREATE TABLE jobs (
  job_id TEXT PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  job_type TEXT NOT NULL,
  domain TEXT NOT NULL,
  risk_class TEXT NOT NULL,
  permission_ceiling TEXT NOT NULL,
  state TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  not_before TEXT NOT NULL,
  lease_until TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX jobs_due ON jobs(state, not_before);
```

- [ ] **Step 2: Write RED worker tests**

Test duplicate idempotency key is ignored, active-user flag pauses background dispatch, high-risk jobs are rejected, budget exhaustion defers rather than retries immediately, lease expiry permits safe replay, and payload/log sanitizer strips secret-like fields.

- [ ] **Step 3: Run RED**

```bash
node --test cloudflare-worker/test-brain-autonomy.mjs
```

- [ ] **Step 4: Implement scheduler/queue consumer**

Cron creates only policy-approved objectives. Queue consumer calls the authenticated Legion runtime endpoint with immutable job payload and records status/artifact refs, never hidden reasoning or provider secrets.

- [ ] **Step 5: Run GREEN and commit**

```bash
node --test cloudflare-worker/test-brain-autonomy.mjs
git add cloudflare-worker/brain-autonomy.js cloudflare-worker/test-brain-autonomy.mjs cloudflare-worker/migrations cloudflare-worker/wrangler-autonomy.toml cloudflare-worker/README-brain-autonomy.md
git commit -m "feat: add durable idle learning control plane"
```

---

### Task 7: Register AutoSkill/SkillEvo references and continuous-learning evals

**Files:**
- Modify: `AI_SKILL_LIBRARY/v4/legion/upstreams.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/evals.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/index/workspace_map.yaml`
- Test: `AI_SKILL_LIBRARY/tests/test_skill_evolution_integration.py`

**Interfaces:**
- Consumes Tasks 1-6.
- Produces reference provenance and protected regression requirements.

- [ ] **Step 1: Write RED tests**

Require `ECNU-ICALK/AutoSkill` status `approved_reference`, MIT license, absorbed patterns `experience_skill_mining`, `skill_merge_versioning`, `replay_mutation`, `champion_promotion`; no routing/reasoning authority and no mandatory runtime dependency.

- [ ] **Step 2: Add eval classes**

Add protected evals for replay leakage, judge-only promotion, permission-expansion mutation, idle-budget overflow, scheduler duplicate dispatch, secret sanitization and Stable independence.

- [ ] **Step 3: Run tests and canonical validation**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_skill_evolution_integration -v
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)" --skip-tests
node --test cloudflare-worker/test-brain-autonomy.mjs
```

- [ ] **Step 4: Commit**

```bash
git add AI_SKILL_LIBRARY/v4/legion/upstreams.yaml AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml AI_SKILL_LIBRARY/evals.yaml AI_SKILL_LIBRARY/v4/index/workspace_map.yaml AI_SKILL_LIBRARY/tests/test_skill_evolution_integration.py
git commit -m "feat: integrate continuous skill evolution"
```
