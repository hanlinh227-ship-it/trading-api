# STACKHUB V2 — CURRENT CHECKPOINT

Updated: 2026-09-11 +07

## Authority
- Repository: `hanlinh227-ship-it/trading-api`.
- Branch: `stackhub-v2-autonomous-bounty`.
- Approved design: `docs/superpowers/specs/2026-09-11-stackhub-v2-multithread-revenue-engine-design.md`.
- Implementation plan: `docs/superpowers/plans/2026-09-11-stackhub-v2-multithread-runtime-foundation.md` (or the current V2 multithread runtime plan referenced by branch HEAD).
- Goal: continuous zero-external-spend, multi-worker revenue orchestration for legitimate agent-native paid work; realized payout is the only authoritative revenue metric.

## Hard invariants
- `external_spend_limit_usd == 0` always.
- No wallet spending authority, private keys, seed phrases, CAPTCHA bypass, fake-human work, fake clicks/views, identity/IP/multi-account evasion.
- Only sources verified as agent-native may produce claimable work.
- New source mutations remain disabled until separately verified.
- Checked-in configuration stays safe/read-only by default.
- Every submission requires verification evidence.
- Do not call the runtime LIVE unless deployment/runtime is independently verified.

## Current implementation state
### Task 1 — bounded multithread runtime configuration: COMPLETE
Commit: `5ea58d75d6fdc4dc3b2d36d9041e15a842bcba1b` (`feat: add bounded multithread runtime config`).

Implemented:
- `WorkerPoolConfig` ceilings:
  - scouts: 3
  - code_fix: 2
  - research_data: 2
  - service: 2
  - verification: 2
  - submission: 1
- Global `max_active_claims` validation expanded from hard cap 1 to hard cap 4.
- `worker_pools` added to `RuntimeConfig` with safe defaults.
- Checked-in `stackhub_v2/config/sources.yaml` remains `dry_run: true`, `worker_enabled: false`, `read_only: true`, zero external spend.
- Added `stackhub_v2/tests/test_runtime_pool_config.py`.

Verification evidence:
- RED observed before implementation: import/collection failed because `WorkerPoolConfig` did not exist.
- GREEN after implementation: `pytest tests/test_runtime_pool_config.py tests/test_config.py -q` => `9 passed` locally.
- GitHub commit diff verified after write.
- GitHub combined status returned no CI statuses for this commit, so CI is NOT claimed.
- Runtime deployment/LIVE state is NOT claimed.

## Next action — Task 2
Implement durable reservation and lifecycle ownership before enabling concurrent mutation:
1. Replace lifecycle with `DISCOVERED -> ELIGIBLE -> RESERVED -> CLAIMED -> SOLVING -> VERIFIED -> SUBMITTED -> PAID` plus `FAILED_RETRYABLE`, `FAILED_PERMANENT`, `EXPIRED`, `REJECTED`.
2. Add migration-safe `reserved_at`, `updated_at`, `last_error_code` claim fields.
3. Add atomic `reserve_next_opportunity(source, max_active_claims, reserved_at)` using SQLite `BEGIN IMMEDIATE` so two workers cannot reserve the same opportunity.
4. Add `transition_claim(...)` and route state changes through `assert_transition`.
5. Verify focused reservation/state tests and full regression before continuing to scanner/solver/worker concurrency.

## Operational note
The system is not yet a verified 24/7 earning runtime. The worker-pool configuration foundation is in place, but durable reservation, orchestrator, solver isolation, verification/submission concurrency, payout reconciliation, deployment and runtime health still need to pass their release gates.
