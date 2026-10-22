# STACKHUB V2 Multithread Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing TaskBounty scanner/worker foundation into a continuously running, zero-spend, multi-worker runtime with durable reservations, bounded concurrency, solver isolation, truthful status reporting, and payout-ready accounting.

**Architecture:** Keep source discovery, policy, scoring, mutation, solving, verification, submission, and accounting as separate units. `RevenueOrchestrator` owns scheduling/backpressure; repository methods provide durable reservation/idempotency; concrete solvers are pluggable and cannot bypass verification. This plan deliberately covers only the runtime foundation and TaskBounty integration; additional marketplaces, passive-service publication, and adaptive optimizer logic are separate plans.

**Tech Stack:** Python 3.12+, asyncio, httpx, Pydantic v2, SQLite, Typer, pytest, pytest-asyncio, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-11-stackhub-v2-multithread-revenue-engine-design.md`

## Global Constraints

- `external_spend_limit_usd` is always exactly `0`.
- Wallet spend permission is absent; the runtime never signs or sends crypto transactions.
- No private keys, seed phrases, mnemonics, CAPTCHA bypass, fake-human activity, fake clicks/views, identity spoofing, IP evasion, or multi-account evasion.
- Only sources explicitly marked `agent_native=true` may produce claimable work.
- Newly added source mutations remain disabled until separately verified.
- Default checked-in config stays safe/read-only.
- Every submission requires verification evidence.
- Revenue means evidenced payout, never estimated reward or submitted task count.
- TDD sequence for every task: RED -> minimum GREEN -> focused regression -> full suite -> commit.

---

### Task 1: Multi-worker runtime configuration

**Files:**
- Modify: `stackhub_v2/src/stackhub/config.py`
- Modify: `stackhub_v2/config/sources.yaml`
- Create: `stackhub_v2/tests/test_runtime_pool_config.py`

**Interfaces:**
- Add `WorkerPoolConfig` with:
  - `scouts: int = Field(default=3, ge=1, le=3)`
  - `code_fix: int = Field(default=2, ge=1, le=2)`
  - `research_data: int = Field(default=2, ge=0, le=2)`
  - `service: int = Field(default=2, ge=0, le=2)`
  - `verification: int = Field(default=2, ge=1, le=2)`
  - `submission: int = Field(default=1, ge=1, le=1)`
- `RuntimeConfig.max_active_claims: int = Field(default=1, ge=1, le=4)`.
- `RuntimeConfig.worker_pools: WorkerPoolConfig = WorkerPoolConfig()`.
- Keep `external_spend_limit_usd == Decimal("0")` invariant unchanged.
- Checked-in `sources.yaml` remains `dry_run: true`, `worker_enabled: false`, `read_only: true`.

- [ ] **Step 1: Write failing configuration tests**

```python
from decimal import Decimal
import pytest
from pydantic import ValidationError
from stackhub.config import RuntimeConfig, SourceConfig, WorkerPoolConfig


def test_pool_defaults_match_approved_design():
    pools = WorkerPoolConfig()
    assert pools.scouts == 3
    assert pools.code_fix == 2
    assert pools.verification == 2
    assert pools.submission == 1


def test_active_claim_limit_is_capped_at_four(base_source):
    with pytest.raises(ValidationError):
        RuntimeConfig(
            dry_run=True,
            worker_enabled=False,
            external_spend_limit_usd=Decimal("0"),
            scan_interval_seconds=300,
            max_concurrent_tasks=5,
            max_active_claims=5,
            sources={"taskbounty": base_source()},
        )
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd stackhub_v2 && pytest tests/test_runtime_pool_config.py -q`

Expected: FAIL because `WorkerPoolConfig` does not exist and `max_active_claims` is capped at one.

- [ ] **Step 3: Implement the minimum typed config**

```python
class WorkerPoolConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    scouts: int = Field(default=3, ge=1, le=3)
    code_fix: int = Field(default=2, ge=1, le=2)
    research_data: int = Field(default=2, ge=0, le=2)
    service: int = Field(default=2, ge=0, le=2)
    verification: int = Field(default=2, ge=1, le=2)
    submission: int = Field(default=1, ge=1, le=1)
```

Update `RuntimeConfig.max_active_claims` to `le=4` and add `worker_pools`.

- [ ] **Step 4: Run focused and existing config tests**

Run: `pytest tests/test_runtime_pool_config.py tests/test_config.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add stackhub_v2/src/stackhub/config.py stackhub_v2/config/sources.yaml stackhub_v2/tests/test_runtime_pool_config.py
git commit -m "feat: add bounded multithread runtime config"
```

---

### Task 2: Durable reservation and lifecycle model

**Files:**
- Modify: `stackhub_v2/src/stackhub/worker_state.py`
- Modify: `stackhub_v2/src/stackhub/repository.py`
- Modify: `stackhub_v2/tests/test_worker_state.py`
- Create: `stackhub_v2/tests/test_reservations.py`

**Interfaces:**
- States become: `DISCOVERED`, `ELIGIBLE`, `RESERVED`, `CLAIMED`, `SOLVING`, `VERIFIED`, `SUBMITTED`, `PAID`, `FAILED_RETRYABLE`, `FAILED_PERMANENT`, `EXPIRED`, `REJECTED`.
- Add repository method:
  - `reserve_next_opportunity(source: str, max_active_claims: int, reserved_at: datetime) -> dict[str, object] | None`
- Add:
  - `transition_claim(source: str, opportunity_id: str, target: WorkerState, observed_at: datetime) -> None`
- Reservation must be atomic using SQLite `BEGIN IMMEDIATE`; duplicate workers cannot reserve the same `(source, opportunity_id)`.
- Terminal states are excluded from active-claim counts.

- [ ] **Step 1: Write concurrent reservation tests**

```python
def test_reserve_next_is_unique(repo_with_two_ranked_opportunities, now):
    repo = repo_with_two_ranked_opportunities
    a = repo.reserve_next_opportunity("taskbounty", 2, now)
    b = repo.reserve_next_opportunity("taskbounty", 2, now)
    assert a is not None and b is not None
    assert a["opportunity_id"] != b["opportunity_id"]


def test_reservation_honors_capacity(repo_with_two_ranked_opportunities, now):
    repo = repo_with_two_ranked_opportunities
    assert repo.reserve_next_opportunity("taskbounty", 1, now) is not None
    assert repo.reserve_next_opportunity("taskbounty", 1, now) is None
```

- [ ] **Step 2: Run and verify RED**

Run: `pytest tests/test_worker_state.py tests/test_reservations.py -q`

- [ ] **Step 3: Implement migration-safe claim columns and atomic reservation**

Add `reserved_at`, `updated_at`, and `last_error_code` columns via `_ensure_column`. Use one transaction to count active claims, choose highest-ranked eligible unclaimed opportunity, and insert/update the reservation.

- [ ] **Step 4: Route every state change through `assert_transition`**

Do not allow direct backward transition or resurrection of terminal records.

- [ ] **Step 5: Run repository/state regression**

Run: `pytest tests/test_repository.py tests/test_worker_state.py tests/test_reservations.py -q`

- [ ] **Step 6: Commit**

```bash
git add stackhub_v2/src/stackhub/worker_state.py stackhub_v2/src/stackhub/repository.py stackhub_v2/tests/test_worker_state.py stackhub_v2/tests/test_reservations.py
git commit -m "feat: add durable task reservations"
```

---

### Task 3: Discovery must work safely in worker mode

**Files:**
- Modify: `stackhub_v2/src/stackhub/scanner.py`
- Modify: `stackhub_v2/tests/test_scanner.py`

**Interfaces:**
- Scanner discovery is always non-mutating regardless of `dry_run`.
- Constructor rejects non-zero external spend but no longer rejects `dry_run=false` by itself.
- Source mutation remains isolated in workers/adapters.

- [ ] **Step 1: Add live-worker discovery test**

```python
@pytest.mark.asyncio
async def test_scanner_can_discover_in_zero_spend_worker_mode(tmp_path, live_config):
    repo = StackHubRepository(tmp_path / "db.sqlite")
    repo.initialize()
    result = await Scanner(live_config, repo, {"taskbounty": FakeAdapter()}).run_once()
    assert result.discovered == 1
    assert repo.conn.execute("select count(*) from claims").fetchone()[0] == 0
```

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_scanner.py -q`

Expected: existing constructor rejects `dry_run=false`.

- [ ] **Step 3: Change guardrail to zero-spend-only for scanner**

```python
if config.external_spend_limit_usd != Decimal("0"):
    raise ValueError("Scanner requires zero external spend")
```

- [ ] **Step 4: Run scanner regression**

Run: `pytest tests/test_scanner.py -q`

- [ ] **Step 5: Commit**

```bash
git add stackhub_v2/src/stackhub/scanner.py stackhub_v2/tests/test_scanner.py
git commit -m "feat: allow safe discovery in worker mode"
```

---

### Task 4: Pluggable zero-spend solver boundary

**Files:**
- Create: `stackhub_v2/src/stackhub/solver.py`
- Create: `stackhub_v2/tests/test_solver.py`
- Modify: `stackhub_v2/src/stackhub/verification.py`
- Modify: `stackhub_v2/tests/test_verification.py`

**Interfaces:**
- `SolverRequest(task_id: str, clone_url: str, issue_url: str)`.
- `SolverResult(external_link: str, workspace: Path, diff_path: Path, test_command: tuple[str, ...])`.
- `SolverBackend.solve(request: SolverRequest) -> Awaitable[SolverResult]` protocol.
- `CommandSolverBackend` executes only an operator-configured argv template; `shell=False` always.
- Task text/issue URL are passed as argv/env values, never interpolated into shell syntax.
- Solver root is fixed; workspaces must remain descendants of it.
- No solver can call submit APIs directly.

- [ ] **Step 1: Write injection/isolation tests**

```python
@pytest.mark.asyncio
async def test_command_solver_never_uses_shell(monkeypatch, tmp_path):
    calls = []
    async def fake_exec(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeProcess(0)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = CommandSolverBackend(("solver-cli", "--task", "{task_id}"), tmp_path)
    await backend.solve(SolverRequest("x;rm -rf /", "https://clone.invalid/r", "https://issue.invalid/1"))
    assert calls
    assert "shell" not in calls[0][1]
```

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_solver.py tests/test_verification.py -q`

- [ ] **Step 3: Implement protocol and fixed-command backend**

Require explicit configured executable; if absent, worker runtime reports `solver_unavailable` and performs no claim mutation.

- [ ] **Step 4: Extend verification to consume `SolverResult`**

Verification still requires successful tests, non-empty diff, path containment, and secret-free patch.

- [ ] **Step 5: Run focused regression and commit**

```bash
pytest tests/test_solver.py tests/test_verification.py -q
git add stackhub_v2/src/stackhub/solver.py stackhub_v2/src/stackhub/verification.py stackhub_v2/tests/test_solver.py stackhub_v2/tests/test_verification.py
git commit -m "feat: add isolated pluggable solver backend"
```

---

### Task 5: Refactor TaskBounty worker for bounded concurrency

**Files:**
- Modify: `stackhub_v2/src/stackhub/worker.py`
- Modify: `stackhub_v2/tests/test_worker.py`

**Interfaces:**
- `TaskBountyWorker.run_once()` first calls repository reservation.
- It returns IDLE when capacity is full or no eligible candidate exists.
- `RESERVED -> CLAIMED` occurs only after `access_task()` succeeds.
- Solver errors become `FAILED_RETRYABLE` or `FAILED_PERMANENT` according to explicit error classification.
- Verification failure never calls `submit_pr()`.
- Submission remains idempotent.

- [ ] **Step 1: Replace single-active-claim regression with capacity tests**

```python
@pytest.mark.asyncio
async def test_two_workers_can_process_distinct_tasks_when_cap_is_two(...):
    results = await asyncio.gather(worker_a.run_once(), worker_b.run_once())
    submitted = [r for r in results if r["state"] == "SUBMITTED"]
    assert len(submitted) == 2
    assert len({r["task_id"] for r in submitted}) == 2
```

- [ ] **Step 2: Add failed verification non-submission test for the new state names**

- [ ] **Step 3: Run and verify RED**

Run: `pytest tests/test_worker.py -q`

- [ ] **Step 4: Implement reservation-driven worker**

Do not select candidates with an in-memory active-id set; repository ownership is authoritative.

- [ ] **Step 5: Run worker + repository regressions**

Run: `pytest tests/test_worker.py tests/test_reservations.py tests/test_worker_state.py -q`

- [ ] **Step 6: Commit**

```bash
git add stackhub_v2/src/stackhub/worker.py stackhub_v2/tests/test_worker.py
git commit -m "feat: support bounded concurrent TaskBounty workers"
```

---

### Task 6: Revenue orchestrator and backpressure

**Files:**
- Create: `stackhub_v2/src/stackhub/orchestrator.py`
- Create: `stackhub_v2/tests/test_orchestrator.py`

**Interfaces:**
- `RevenueOrchestrator(config, repo, scanners, workers, *, sleeper=asyncio.sleep)`.
- `run_once()` performs one discovery cycle, fills only available claim capacity, then collects worker results.
- `run_forever(stop_event)` uses `asyncio.TaskGroup` and bounded loops; no unbounded task creation.
- Claimed/deadline-sensitive work always runs before idle/service work.
- Source rate-limit delay overrides faster poll cycles.

- [ ] **Step 1: Write backpressure test**

```python
@pytest.mark.asyncio
async def test_orchestrator_never_exceeds_global_claim_cap(fake_runtime):
    orchestrator = RevenueOrchestrator(...)
    await orchestrator.run_once()
    assert repo.active_claim_count() <= fake_runtime.max_active_claims
```

- [ ] **Step 2: Write source-outage isolation test**

One scout failure must not cancel independent workers; health is recorded and the next poll uses bounded backoff.

- [ ] **Step 3: Verify RED**

Run: `pytest tests/test_orchestrator.py -q`

- [ ] **Step 4: Implement minimum orchestrator**

Use semaphores/capacity from repository; do not create more code-fix worker coroutines than `worker_pools.code_fix`.

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/test_orchestrator.py tests/test_scanner.py tests/test_worker.py -q
git add stackhub_v2/src/stackhub/orchestrator.py stackhub_v2/tests/test_orchestrator.py
git commit -m "feat: add revenue orchestrator with backpressure"
```

---

### Task 7: Payout ledger and truthful revenue accounting

**Files:**
- Modify: `stackhub_v2/src/stackhub/repository.py`
- Create: `stackhub_v2/src/stackhub/accounting.py`
- Create: `stackhub_v2/tests/test_accounting.py`

**Interfaces:**
- `record_payout(source, opportunity_id, asset, amount, txid_or_reference, paid_at)` is idempotent.
- `RevenueSummary(realized_today_usd, realized_7d_usd, realized_30d_usd, pending_submissions, paid_count)`.
- `get_revenue_summary(now)` counts only rows in the payout ledger as realized revenue.
- No estimated opportunity value appears as realized income.
- TaskBounty reconciliation adapter is not invented in this plan; until a verified status/payout endpoint exists, records stay pending.

- [ ] **Step 1: Write accounting truth tests**

```python
def test_submitted_reward_is_not_realized_revenue(repo, now):
    # seed a $100 opportunity and submitted claim
    summary = get_revenue_summary(repo, now)
    assert summary.realized_today_usd == Decimal("0")
    assert summary.pending_submissions == 1
```

- [ ] **Step 2: Write idempotent payout test**

Two identical payout observations must produce one ledger row.

- [ ] **Step 3: Implement schema/methods and summary calculation**

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_accounting.py tests/test_repository.py -q
git add stackhub_v2/src/stackhub/repository.py stackhub_v2/src/stackhub/accounting.py stackhub_v2/tests/test_accounting.py
git commit -m "feat: add realized payout accounting"
```

---

### Task 8: CLI runtime wiring and status

**Files:**
- Modify: `stackhub_v2/src/stackhub/cli.py`
- Modify: `stackhub_v2/tests/test_cli.py`
- Modify: `stackhub_v2/README.md`

**Interfaces:**
- `stackhub status --config ... --db ...` reports actual `dry_run`, `worker_enabled`, source health, active claims, pending submissions, and realized revenue.
- Remove hard-coded `STACKHUB V2 — DRY-RUN` when config is worker mode.
- `stackhub run` constructs discovery + orchestrator; worker mutations are started only when config allows them, API key exists, and solver backend health check succeeds.
- Absence of API key or solver backend produces a clear non-secret error and no claims.
- No `withdraw`, wallet-send, spend, or private-key command is introduced.

- [ ] **Step 1: Replace stale CLI assertions**

```python
def test_status_reports_runtime_mode_from_config(tmp_path):
    result = runner.invoke(app, ["status", "--config", str(config), "--db", str(db)])
    assert result.exit_code == 0
    assert "worker_enabled=" in result.stdout
    assert "realized_today_usd=" in result.stdout
```

- [ ] **Step 2: Add no-solver/no-key fail-closed tests**

- [ ] **Step 3: Verify RED**

Run: `pytest tests/test_cli.py -q`

- [ ] **Step 4: Wire CLI to orchestrator/accounting**

- [ ] **Step 5: Update README from read-only scanner wording to zero-spend revenue runtime wording**

Document dry-run default, required runtime secrets, solver backend, and rollback procedure.

- [ ] **Step 6: Run tests and commit**

```bash
pytest tests/test_cli.py -q
git add stackhub_v2/src/stackhub/cli.py stackhub_v2/tests/test_cli.py stackhub_v2/README.md
git commit -m "feat: wire multithread revenue runtime CLI"
```

---

### Task 9: Full verification and live-canary gate

**Files:**
- Modify only if required by failing tests: `.github/workflows/stackhub-v2-ci.yml`
- Create: `stackhub_v2/config/worker.example.yaml`
- Modify: `stackhub_v2/README.md`

**Requirements:**
- Default `config/sources.yaml` remains safe/read-only.
- `worker.example.yaml` contains no credentials and explicitly sets `external_spend_limit_usd: "0"`.
- First live canary uses `max_active_claims: 1` even though the runtime supports four.
- Increase to 2 then 4 only after at least one verified end-to-end submission and no duplicate-claim regression.
- Do not represent a submission as income until payout evidence exists.

- [ ] **Step 1: Run complete test suite**

Run: `cd stackhub_v2 && pytest -q`

Expected: all tests PASS.

- [ ] **Step 2: Run repository secret scan/CI validators**

Expected: no `tb_live_*`, wallet private key, seed phrase, or bearer credential committed.

- [ ] **Step 3: Confirm CI succeeds on the branch**

- [ ] **Step 4: Perform a dry-run runtime smoke test**

```bash
stackhub scan-once --config config/sources.yaml --db runtime-data/stackhub-v2.db
stackhub status --config config/sources.yaml --db runtime-data/stackhub-v2.db
```

Expected: discovery/status work and no claims/submissions are created.

- [ ] **Step 5: Prepare but do not automatically force live mode**

Live mode requires runtime `TASKBOUNTY_API_KEY`, a healthy approved solver command, Git credentials capable of creating the required PR, and the one-task canary config. If any requirement is missing, remain fail-closed.

- [ ] **Step 6: Commit final operational docs/config example**

```bash
git add stackhub_v2/config/worker.example.yaml stackhub_v2/README.md .github/workflows/stackhub-v2-ci.yml
git commit -m "docs: add zero-spend worker activation runbook"
```

---

## Follow-on plans after this foundation

This spec is intentionally decomposed. After the runtime foundation is verified, create separate implementation plans for:

1. **Source Expansion:** one verified agent-native marketplace adapter per task/commit; mutation stays disabled until contract tests pass.
2. **Passive Service Factory:** repository audit / code-review / research services with zero-spend publication adapters.
3. **Payout Reconciliation:** source-specific acceptance/payment observation only where official endpoints are verified.
4. **Revenue Optimizer:** adaptive source/task weights only after enough real payout observations exist.

This ordering prevents marketplace-specific uncertainty from destabilizing the core worker runtime.