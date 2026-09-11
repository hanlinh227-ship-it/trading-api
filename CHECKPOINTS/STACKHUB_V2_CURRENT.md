# STACKHUB V2 — CURRENT CHECKPOINT

Updated: 2026-09-11 +07

## Authority
- Repository: `hanlinh227-ship-it/trading-api`.
- Branch: `stackhub-v2-autonomous-bounty`.
- Approved design: `docs/superpowers/specs/2026-09-11-stackhub-v2-multithread-revenue-engine-design.md`.
- Current implementation plan: `docs/superpowers/plans/2026-09-11-stackhub-v2-continuous-multisource-engine.md`.
- Goal: continuous source-agnostic zero-external-spend revenue orchestration across External Jobs, Paid Services/APIs and Reusable Digital Assets. TaskBounty is one adapter only. Realized payout is the only authoritative revenue metric.

## Hard invariants
- `external_spend_limit_usd == 0` always.
- `NO_EXTERNAL_JOB != IDLE` when approved fallback revenue work exists.
- No wallet spending authority, private keys, seed phrases, CAPTCHA bypass, fake-human work, fake engagement, identity/IP/multi-account evasion.
- Only sources with verified agent/automation permission may produce claimable work.
- New source mutations remain disabled until separately verified.
- Checked-in default configuration stays safe/read-only.
- Every submission/publication requires verification evidence.
- Do not call the runtime LIVE unless deployment/runtime is independently verified.

## Implemented foundation

### 1. Bounded worker pools
- scouts: 3
- code_fix: 2
- research_data: 2
- service: 2
- verification: 2
- submission: 1
- global active paid-task ceiling: 4
- Original foundation commit: `5ea58d75d6fdc4dc3b2d36d9041e15a842bcba1b`.

### 2. Source-agnostic durable lifecycle/reservations
Canonical lifecycle:
`DISCOVERED -> ELIGIBLE -> RESERVED -> CLAIMED -> SOLVING -> VERIFIED -> SUBMITTED -> PAID`
with `FAILED_RETRYABLE`, `FAILED_PERMANENT`, `EXPIRED`, `REJECTED`.

Implemented atomic SQLite `BEGIN IMMEDIATE` reservation, global capacity enforcement, migration-safe claim fields, terminal-state handling and transition validation.
Focused lifecycle/reservation verification previously observed: `8 passed`.

### 3. Source capability policy gate
Implemented action-specific `discover/claim/submit/publish/observe_payout` capabilities, zero-spend rejection, mutation/terms verification timestamps and read-only defaults. Focused verification previously observed: `6 passed`.

### 4. Multi-source normalization and revenue scoring
Commit: `fac4a72710d70c90c9db82f52e5ec72102f97a61`.
Implemented normalized multi-lane opportunity schema and deterministic expected-realized-revenue-per-worker-minute scoring. RED was observed before implementation; focused scratch suite: `3 passed`.

### 5. Generic adapter/scout boundary
Commits: `10dbd4f40d1ee3b1df248b7118f08a5d5716113f`, `0549a07e65c787c4079393e5a91ea34e143430f5`.
Implemented generic discovery/claim/submit adapter contracts, read-only Scout, and TaskBounty adapter compatibility with the generic interface. Focused scratch suite: `3 passed`.

### 6. Solver isolation, verification and idempotent submission
Commit: `f8ac47727cb05efef2d4f7cedfcfd832b5e1b113`.
Solvers return Artifact + Evidence and receive no marketplace submit handle. Verification rejects empty artifacts, missing evidence and detected secrets. Submission requires `VERIFIED` state and source capability approval. Focused scratch suite: `3 passed`.

### 7. Continuous revenue orchestrator + fallback lanes
Commit: `b820555929fd52f51b2f2f54b51bc0003aa3a517`.
Implemented cross-source global reservation, bounded concurrent execution, source switching and fallback queue for Service/API, Digital Asset, source discovery and product improvement work. Focused scratch suite: `2 passed`.

### 8. Evidence-only payout reconciliation and revenue metrics
Commit: `4af0c38b8987753cdbbaf93a112b8a1b8731c6e7`.
Only externally evidenced payout records count as realized revenue. Metrics include paid today/7d/30d, source totals and source concentration. Focused scratch suite: `3 passed`.

### 9. Account integration/runtime entrypoints
Commits: `499b146ac5b1f244b30a9aecca871dd8959f63a1`, `21c96000158522780ebb4a597a564fb9b73a6c3a`.
Implemented:
- adapter registry;
- environment secret doctor;
- command-based isolated solver bridge with marketplace credential stripping;
- truthful runtime status;
- source-agnostic CLI commands: `doctor`, `scan-once`, `opportunities`, `status`, `orchestrate-once`, `run`;
- shared `RepositoryOpportunityPool`;
- `INTEGRATION.env.example`;
- `INTEGRATION_GUIDE.md`;
- safe read-only checked-in config remains unchanged;
- separate `config/sources.live.example.yaml` starts with `max_active_claims: 1` and contains no credentials;
- example systemd 24/7 service at `deploy/stackhub-v2.service.example`.

Combined focused scratch verification across Tasks 3-8 before the final CLI/docs commit: `19 passed`. CLI draft was syntax-compiled before write. This is NOT a claim that the full repository suite or deployment runtime has passed.

## Account state supplied by user
- PayPal: available.
- TaskBounty account: available.
- TaskBounty API key: available, but must remain in deployment/system secret storage and must not be committed or pasted into chat.

STACKHUB intentionally does not request PayPal passwords/session credentials. Marketplace payout is configured on the marketplace itself. Crypto payout integration, if used, is public receiving-address-only.

## Integration procedure
1. Put `TASKBOUNTY_API_KEY` in deployment/system secret storage.
2. Configure `STACKHUB_SOLVER_COMMAND` to an authorized solver wrapper/CLI; solver subprocess does not receive marketplace secrets.
3. Install package and run `stackhub doctor --config config/sources.yaml`.
4. Run read-only `stackhub scan-once`, inspect `stackhub opportunities` and `stackhub status`.
5. Copy `config/sources.live.example.yaml` to a deployment-only path. Keep `max_active_claims: 1` for first mutation.
6. Run `stackhub orchestrate-once` and manually inspect the first end-to-end marketplace result.
7. Only after first mutation is independently verified, use `stackhub run`/systemd for continuous runtime.
8. Add further platforms through source-specific adapters only after their current API/terms/agent permissions are verified. Unsupported/human-only sources remain `ASSISTED` or `DISCOVERY_ONLY`.

## Remaining release gates
- Full repository regression suite/validators have not yet been independently executed in this environment.
- GitHub CI status must be checked for the final branch HEAD; absence of checks is not success.
- Actual TaskBounty API connection using the user's secret has not been executed here because the secret is not exposed to this chat/tool environment.
- Actual solver command/account connection is not yet configured in this environment.
- Deployment service heartbeat has not been independently verified.
- Non-TaskBounty platforms still require concrete source adapters; the core is adapter-ready, but STACKHUB must not invent unofficial automation contracts.

## Operational status
STACKHUB V2 is **integration-ready at the core/runtime layer**, but is **NOT yet verified LIVE 24/7**. The next gate is user-side secret/solver integration followed by read-only doctor/scan and one-task live verification before continuous operation.