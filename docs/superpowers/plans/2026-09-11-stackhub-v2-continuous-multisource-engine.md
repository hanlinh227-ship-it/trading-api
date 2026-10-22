# STACKHUB V2 Continuous Multi-Source Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a source-agnostic continuous revenue runtime that scans multiple legitimate AI-allowed sources, reserves and executes work concurrently, verifies/submits safely, falls back to approved service/asset work when external queues are empty, and reconciles only evidenced payouts as revenue.

**Architecture:** A global opportunity pool sits behind independent read-only scouts. A durable SQLite reservation/lifecycle layer owns work; specialized solvers cannot submit directly; verification gates every mutation; source adapters expose explicit capability manifests; a revenue orchestrator prioritizes work by expected realized revenue and uses fallback lanes rather than idling.

**Tech Stack:** Python 3.12+, asyncio, httpx, Pydantic v2, SQLite, Typer, pytest, pytest-asyncio, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-11-stackhub-v2-multithread-revenue-engine-design.md`

## Global Constraints

- `external_spend_limit_usd == 0` always.
- No wallet spending authority, private keys, seed phrases, CAPTCHA bypass, fake-human work, fake engagement, identity/IP/multi-account evasion.
- Mutation is disabled by default for every source until current API/terms/agent permission are independently verified.
- Checked-in configuration remains safe/read-only.
- Every submit/publish mutation requires verification evidence.
- Realized payout is the only authoritative revenue metric.
- TaskBounty is one adapter, never the core architecture.
- Engineering changes follow RED -> minimum GREEN -> focused regression -> full suite -> validators/CI where available.

---

### Task 1: Source-agnostic durable reservation and lifecycle

**Files:**
- Modify: `stackhub_v2/src/stackhub/worker_state.py`
- Modify: `stackhub_v2/src/stackhub/repository.py`
- Modify: `stackhub_v2/tests/test_worker_state.py`
- Create: `stackhub_v2/tests/test_reservations.py`

**Interfaces:**
- Produces `WorkerState` states: `DISCOVERED`, `ELIGIBLE`, `RESERVED`, `CLAIMED`, `SOLVING`, `VERIFIED`, `SUBMITTED`, `PAID`, `FAILED_RETRYABLE`, `FAILED_PERMANENT`, `EXPIRED`, `REJECTED`.
- Produces `Repository.reserve_next_opportunity(source: str | None, max_active_claims: int, reserved_at: datetime) -> dict[str, object] | None`.
- Produces `Repository.transition_claim(source: str, opportunity_id: str, target: WorkerState, observed_at: datetime, error_code: str | None = None) -> None`.

- [ ] Write failing tests proving two sequential reservations choose different opportunities, capacity is enforced globally, source filtering is optional, terminal states stop counting as active, and illegal backward/terminal transitions fail.
- [ ] Run focused tests and observe RED.
- [ ] Add migration-safe `reserved_at`, `updated_at`, `last_error_code` claim columns and canonical state machine.
- [ ] Implement atomic `BEGIN IMMEDIATE` reservation that counts active claims, ranks eligible unowned opportunities, and inserts/updates one reservation in the same transaction.
- [ ] Route transitions through `assert_transition`.
- [ ] Run focused tests and existing repository/worker-state regressions.
- [ ] Commit `feat: add source-agnostic durable reservations`.

### Task 2: Source capability registry and policy gate

**Files:**
- Create: `stackhub_v2/src/stackhub/source_capabilities.py`
- Modify: `stackhub_v2/src/stackhub/config.py`
- Modify: `stackhub_v2/config/sources.yaml`
- Create: `stackhub_v2/tests/test_source_capabilities.py`

**Interfaces:**
- Produces immutable `SourceCapabilities` with agent/mutation/onboarding/spend flags and verification timestamps.
- Produces `assert_source_eligible_for(action: str, capabilities: SourceCapabilities) -> None`.

- [ ] Write RED tests that reject any source requiring external spend and reject unverified claim/submit/publish mutation.
- [ ] Implement capability model and config parsing with all mutation flags false by default.
- [ ] Keep checked-in sources read-only and zero-spend.
- [ ] Run focused config/policy suite.
- [ ] Commit `feat: add source capability policy gate`.

### Task 3: Global opportunity normalization and scoring

**Files:**
- Create: `stackhub_v2/src/stackhub/opportunity.py`
- Modify: `stackhub_v2/src/stackhub/repository.py`
- Create: `stackhub_v2/src/stackhub/revenue_scoring.py`
- Create: `stackhub_v2/tests/test_opportunity_scoring.py`

**Interfaces:**
- Produces normalized `Opportunity` independent of source.
- Produces `score_opportunity(opportunity, metrics) -> Decimal` based on expected realized revenue per worker-minute with safety/payout/reliability penalties.

- [ ] Write RED tests for normalization and ranking across different sources/task classes.
- [ ] Implement common schema and persistence fields.
- [ ] Implement deterministic scoring without loosening policy gates.
- [ ] Run focused tests and reservation regressions.
- [ ] Commit `feat: normalize and rank multi-source opportunities`.

### Task 4: Adapter contract and independent scouts

**Files:**
- Create: `stackhub_v2/src/stackhub/adapters/base.py`
- Create: `stackhub_v2/src/stackhub/scout.py`
- Modify existing TaskBounty adapter to implement the base read interface.
- Create: `stackhub_v2/tests/test_adapter_contract.py`
- Create: `stackhub_v2/tests/test_scout.py`

**Interfaces:**
- `SourceAdapter.discover() -> list[Opportunity]`
- Optional mutation methods remain capability-gated.
- `Scout.run_once()` only discovers/normalizes/upserts; it never claims/submits.

- [ ] Write RED contract tests proving scouts cannot invoke mutation methods and multiple adapters feed one opportunity pool.
- [ ] Implement base adapter and scout runner.
- [ ] Adapt TaskBounty discovery without making TaskBounty special in the orchestrator.
- [ ] Run focused tests.
- [ ] Commit `feat: add source-agnostic scout adapters`.

### Task 5: Solver isolation, verification, and submission boundary

**Files:**
- Create/modify solver interface under `stackhub_v2/src/stackhub/solvers/`
- Create/modify verification gate under `stackhub_v2/src/stackhub/verification.py`
- Create: `stackhub_v2/src/stackhub/submission.py`
- Tests: solver isolation, verification rejection, idempotent submission.

**Interfaces:**
- Solvers return `Artifact + Evidence`; no adapter credentials or submit handle.
- Submission manager accepts only `VERIFIED` work.

- [ ] Write RED tests proving solver cannot submit and failed verification never mutates a source.
- [ ] Implement minimal isolated solver boundary.
- [ ] Implement verification evidence persistence.
- [ ] Implement idempotent capability-gated submission/publication manager.
- [ ] Run focused regressions.
- [ ] Commit `feat: isolate solving verification and submission`.

### Task 6: Revenue orchestrator and fallback lanes

**Files:**
- Create: `stackhub_v2/src/stackhub/orchestrator.py`
- Create: `stackhub_v2/src/stackhub/work_queue.py`
- Modify runtime CLI entrypoint.
- Create: `stackhub_v2/tests/test_orchestrator.py`

**Interfaces:**
- Global priority: near-deadline claimed work -> high-EV paid jobs -> normal paid jobs -> payout reconcile -> paid service requests -> approved reusable asset/service work -> source discovery/product improvement.
- `NO_EXTERNAL_JOB != IDLE` when approved fallback work exists.

- [ ] Write RED tests for bounded global active claims, independent scout activity, cross-source switching, and fallback queue selection.
- [ ] Implement bounded asyncio queues/semaphores using Task 1 reservations.
- [ ] Implement watchdog/stalled reservation handling only for safe-to-release states.
- [ ] Run focused concurrency tests.
- [ ] Commit `feat: orchestrate continuous multi-lane work`.

### Task 7: Unified payout reconciliation and revenue metrics

**Files:**
- Create: `stackhub_v2/src/stackhub/payouts.py`
- Modify: `stackhub_v2/src/stackhub/repository.py`
- Create: `stackhub_v2/src/stackhub/revenue_metrics.py`
- Create: `stackhub_v2/tests/test_payout_reconciliation.py`

**Interfaces:**
- Records payout only from external evidence.
- Computes paid today/7d/30d, revenue per source/lane/task class, payout latency, idle percentage, and source concentration.

- [ ] Write RED tests proving submitted/accepted amounts do not count as revenue before payout evidence.
- [ ] Implement idempotent payout records.
- [ ] Implement metrics and concentration calculation.
- [ ] Run focused tests.
- [ ] Commit `feat: reconcile payouts and revenue metrics`.

### Task 8: Onboarding, secrets, observability, and 24/7 release gate

**Files:**
- Create: `stackhub_v2/ACCOUNT_ONBOARDING.md`
- Create/modify CLI status command.
- Create/modify structured logging/secret redaction.
- Create/modify deployment/runtime health configuration and tests.

**Interfaces:**
- Account matrix marks `AUTO`, `ASSISTED`, or `DISCOVERY_ONLY` per verified platform.
- Secrets are environment/system-secret-only; repository stores names and public receiving addresses only when required.
- Runtime reports truthful scanner freshness, source health, queues, active claims, payout pending, realized revenue, idle percentage, and source concentration.

- [ ] Document exact user-required steps: account creation, email/phone/KYC/tax, API approval/key generation, payout method/public receiving address, secret names.
- [ ] Write RED secret-redaction/status tests.
- [ ] Implement truthful status and health checks.
- [ ] Run full local suite and project validators available in the repository.
- [ ] Check CI status where exposed by GitHub.
- [ ] Do not mark LIVE until deployment/runtime heartbeat is independently verified.
- [ ] Commit `docs: add STACKHUB onboarding and release gate`.
