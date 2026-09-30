# STACKHUB V2 TaskBounty Autonomous Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the passing read-only STACKHUB V2 scanner into a controlled TaskBounty worker that can access one selected bounty, prepare an isolated solver workspace, verify a patch, submit through TaskBounty's documented API, and persist claim/submission state without ever storing wallet private keys or performing prohibited human simulation.

**Architecture:** Keep discovery/policy/scoring read-only and add a separate mutation-capable TaskBounty client guarded by explicit runtime flags and `TASKBOUNTY_API_KEY`. Claims and submissions are idempotent state-machine transitions persisted in SQLite. The worker never enables payout configuration automatically and never accepts private keys; payout registration remains a separate explicit operation using public addresses only.

**Tech Stack:** Python 3.12+, asyncio/httpx, Pydantic v2, SQLite, Typer, pytest, pytest-asyncio, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-11-stackhub-v2-autonomous-bounty-design.md`

## Global Constraints
- Use only documented TaskBounty endpoints: `GET /api/v1/tasks`, `POST /api/v1/tasks/{id}/access`, `POST /api/v1/submissions`, and optional public-address payout configuration.
- `TASKBOUNTY_API_KEY` comes only from environment/runtime secret storage and is never persisted or logged.
- No private key, seed phrase, bank/card credential, CAPTCHA bypass, fake identity, fake engagement, location spoofing, or multi-account behavior.
- Mutation stays disabled unless `worker_enabled=true`, `dry_run=false`, API key exists, and the opportunity passed policy + verification gates.
- External spend remains exactly `0`.
- Only one active TaskBounty claim at a time for MVP.
- Solver workspace must be isolated from production trading code.
- A submission requires evidence of tests/verification; no blind submit.
- TDD order: RED -> minimum GREEN -> regression -> validators -> CI.

---

### Task 1: Runtime mutation gate

**Files:**
- Modify: `stackhub_v2/src/stackhub/config.py`
- Modify: `stackhub_v2/config/sources.yaml`
- Create: `stackhub_v2/tests/test_worker_config.py`

**Interfaces:**
- Add `RuntimeConfig.worker_enabled: bool = False`.
- Add `RuntimeConfig.max_active_claims: int = 1`.
- Permit `dry_run=false` only when `worker_enabled=true`, `external_spend_limit_usd == 0`, TaskBounty is enabled, and TaskBounty host is exactly `www.task-bounty.com`.
- Read-only mode remains valid and unchanged.

- [ ] Write failing tests for invalid combinations.
- [ ] Implement minimum config changes.
- [ ] Keep default config read-only and worker disabled.
- [ ] Run focused tests and commit.

### Task 2: Authenticated TaskBounty mutation client

**Files:**
- Modify: `stackhub_v2/src/stackhub/adapters/taskbounty.py`
- Create: `stackhub_v2/tests/test_taskbounty_mutations.py`

**Interfaces:**
- `TaskAccess(task_id: str, clone_url: str, expires_at: str | None)`.
- `SubmissionResult(id: str | None, task_id: str, status: str | None, external_link: str)`.
- `TaskBountyAdapter.access_task(task_id: str) -> TaskAccess`.
- `TaskBountyAdapter.submit_pr(task_id: str, external_link: str) -> SubmissionResult`.
- Methods require API key and non-read-only config; otherwise raise `TaskBountyProtocolError(error_code="mutation_disabled")`.
- Authorization header value must never appear in exception strings/log output.

- [ ] Contract-test `POST /tasks/{id}/access` with mocked HTTP.
- [ ] Contract-test `POST /submissions` with mocked HTTP.
- [ ] Add auth/rate-limit/idempotency-safe error mapping.
- [ ] Add secret-redaction tests.
- [ ] Run focused tests and commit.

### Task 3: Persistent claim/submission state machine

**Files:**
- Modify: `stackhub_v2/src/stackhub/repository.py`
- Create: `stackhub_v2/src/stackhub/worker_state.py`
- Create: `stackhub_v2/tests/test_worker_state.py`

**Interfaces:**
- States: `DISCOVERED -> ELIGIBLE -> ACCESSED -> SOLVING -> VERIFIED -> SUBMITTED -> WON|LOST|FAILED`.
- `record_claim(...)`, `get_active_claims()`, `record_submission(...)`, `record_verification_event(...)`.
- Replaying the same access/submission reference is idempotent.
- Enforce at most one active claim for MVP.

- [ ] Write failing transition/idempotency tests.
- [ ] Implement schema migration-compatible columns/tables.
- [ ] Reject illegal backward transitions.
- [ ] Run tests and commit.

### Task 4: Solver workspace + verification gate

**Files:**
- Create: `stackhub_v2/src/stackhub/solver.py`
- Create: `stackhub_v2/src/stackhub/verification.py`
- Create: `stackhub_v2/tests/test_verification.py`

**Interfaces:**
- `VerificationEvidence(test_command, exit_code, stdout_tail, stderr_tail, diff_path, passed)`.
- `verify_workspace(path: Path, test_command: Sequence[str]) -> VerificationEvidence`.
- Reject submission when tests did not run, exit code != 0, diff is empty, secret scan fails, or workspace path escapes the configured solver root.
- Do not execute arbitrary bounty-provided shell commands; only repository-approved/test-runner commands selected by STACKHUB policy.

- [ ] Write failing verification tests.
- [ ] Implement bounded subprocess execution with timeout.
- [ ] Add secret-pattern scan and path containment checks.
- [ ] Run tests and commit.

### Task 5: Autonomous worker orchestration

**Files:**
- Create: `stackhub_v2/src/stackhub/worker.py`
- Modify: `stackhub_v2/src/stackhub/cli.py`
- Create: `stackhub_v2/tests/test_worker.py`

**Interfaces:**
- `run_once()` selects highest-ranked allowed unclaimed opportunity.
- If worker disabled: no mutation.
- If enabled: access exactly one task, persist access, hand off to solver runner, require verification evidence, then submit PR URL.
- Failure before submission records `FAILED` with reason and does not retry more than source policy permits.
- CLI adds `worker-status` and `worker-once`; no command prints API key.

- [ ] Write failing no-mutation/default tests.
- [ ] Write successful mocked end-to-end access->verify->submit test.
- [ ] Implement orchestrator.
- [ ] Add crash/restart idempotency regression.
- [ ] Run tests and commit.

### Task 6: CI and operational docs

**Files:**
- Modify: `.github/workflows/stackhub-v2-ci.yml`
- Modify: `stackhub_v2/README.md`

**Requirements:**
- CI runs all worker/mutation tests with mocked API only.
- CI must not require a real TaskBounty API key.
- Document env var `TASKBOUNTY_API_KEY` without sample live secret.
- Document exact activation sequence and rollback to read-only.
- Document that payout setup is a separate explicit step using only a public receiving address.

- [ ] Run full suite.
- [ ] Run secret scan / verify no production trading files changed.
- [ ] Confirm GitHub Actions success.
- [ ] Do not enable live mutation until runtime secret is provisioned.
