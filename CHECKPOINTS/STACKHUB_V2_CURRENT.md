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

## Implementation state

### 1. Bounded worker pools — IMPLEMENTED
- scouts: 3
- code_fix: 2
- research_data: 2
- service: 2
- verification: 2
- submission: 1
- global active paid-task ceiling: 4
- Foundation commit: `5ea58d75d6fdc4dc3b2d36d9041e15a842bcba1b`.

### 2. Durable source-agnostic lifecycle/reservations — IMPLEMENTED
Lifecycle:
`DISCOVERED -> ELIGIBLE -> RESERVED -> CLAIMED -> SOLVING -> VERIFIED -> SUBMITTED -> PAID`
plus `FAILED_RETRYABLE`, `FAILED_PERMANENT`, `EXPIRED`, `REJECTED`.

Includes atomic SQLite `BEGIN IMMEDIATE` reservation, global capacity enforcement, migration-safe fields, terminal-state handling and transition validation. Focused lifecycle/reservation test evidence: `8 passed`.

### 3. Source capability policy gate — IMPLEMENTED
Action-specific `discover/claim/submit/publish/observe_payout` permissions, zero-spend reject, mutation/terms verification timestamps and read-only defaults. Focused evidence: `6 passed`.

### 4. Multi-source opportunity normalization/scoring — IMPLEMENTED
Commit: `fac4a72710d70c90c9db82f52e5ec72102f97a61`.
Common multi-lane schema plus expected-realized-revenue-per-worker-minute scoring. Focused evidence: `3 passed`.

### 5. Generic adapter/scout layer — IMPLEMENTED
Commits: `10dbd4f40d1ee3b1df248b7118f08a5d5716113f`, `0549a07e65c787c4079393e5a91ea34e143430f5`.
Generic discover/claim/submit contracts, read-only scouts, TaskBounty conforming to the generic contract. Focused evidence: `3 passed`.

### 6. Solver isolation + verification + submission — IMPLEMENTED
Commit: `f8ac47727cb05efef2d4f7cedfcfd832b5e1b113`.
Solver returns Artifact + Evidence without marketplace submit credentials. Verification blocks empty artifacts/missing evidence/secrets. Submission requires VERIFIED state, source capability approval and idempotency. Focused evidence: `3 passed`.

### 7. Continuous revenue orchestrator + fallback lanes — IMPLEMENTED
Commit: `b820555929fd52f51b2f2f54b51bc0003aa3a517`.
Cross-source global reservation, bounded concurrent execution, source switching, and fallback queue for Service/API, Digital Asset, source discovery and product improvement. Focused evidence: `2 passed`.

### 8. Payout reconciliation + revenue metrics — IMPLEMENTED
Commit: `4af0c38b8987753cdbbaf93a112b8a1b8731c6e7`.
Only externally evidenced payout counts as realized revenue. Tracks paid today/7d/30d and source concentration. Focused evidence: `3 passed`.

### 9. Account integration/runtime entrypoints — IMPLEMENTED
Core commits: `499b146ac5b1f244b30a9aecca871dd8959f63a1`, `21c96000158522780ebb4a597a564fb9b73a6c3a`, fixes `7ef741c81e3901ea1831b5663c7a847ea2ca8de8`, `004ba0e95be84b17fac9d3529e62a90a1bc62b59`.

Implemented:
- adapter registry;
- environment-secret doctor;
- isolated command solver bridge with marketplace credential stripping;
- truthful runtime status with `DRY-RUN` vs `LIVE-CANDIDATE` and mutation status;
- source-agnostic CLI: `doctor`, `scan-once`, `opportunities`, `status`, `orchestrate-once`, `run`;
- shared repository opportunity pool;
- `INTEGRATION.env.example` and `INTEGRATION_GUIDE.md`;
- safe read-only checked-in config remains unchanged;
- separate `config/sources.live.example.yaml` begins with `max_active_claims: 1` and no credentials;
- `deploy/stackhub-v2.service.example` for persistent 24/7 process management.

Combined focused scratch verification across Tasks 3-8 before final CI: `19 passed`.

## Fresh CI evidence on commit `004ba0e95be84b17fac9d3529e62a90a1bc62b59`
`STACKHUB V2 CI` run `34615953296`: SUCCESS.
- package install: success
- compile: success
- full STACKHUB V2 pytest suite: success
- committed credential/wallet-secret rejection: success
- checked-in default read-only proof: success
- GitHub Brain V4 authority validation: success
- current public TaskBounty discovery contract probe: success
- live read-only TaskBounty smoke + idempotency: success

`AI Skill Library CI` run `34615953318`: SUCCESS, including compile, integration tests, source/router/project authority/V3/V4 validators and upstream audit.

Earlier CI failures were used as regression evidence: first exposed missing `DRY-RUN`; second exposed missing `claims/submissions disabled`; both were fixed with truthful config-derived runtime reporting before the green run above.

## Account state supplied by user
- PayPal: available.
- TaskBounty account: available.
- TaskBounty API key: available but must remain in deployment/system secret storage; never commit or paste into chat.
- User states remaining required accounts are already available.

STACKHUB intentionally does not request PayPal passwords/session credentials. Configure platform payout inside the platform. Crypto payout, if used, is public receiving-address-only.

## Account integration procedure
1. Put `TASKBOUNTY_API_KEY` in deployment/system secret storage.
2. Configure `STACKHUB_SOLVER_COMMAND` to the authorized AI solver wrapper/CLI. Marketplace secrets are stripped from the solver subprocess environment.
3. Run `stackhub doctor --config config/sources.yaml`.
4. Run read-only `stackhub scan-once`; inspect `stackhub opportunities` and `stackhub status`.
5. Copy `config/sources.live.example.yaml` to a deployment-only path and keep `max_active_claims: 1` for the first mutation.
6. Run `stackhub orchestrate-once` and inspect the first real marketplace claim/submission end-to-end.
7. After independent first-task verification, run `stackhub run` under systemd for continuous operation.
8. Add other platforms with concrete source-specific adapters only after current API/terms/agent permission are verified. Human-only or unsupported platforms stay `ASSISTED`/`DISCOVERY_ONLY`.

## Remaining release gates
- Actual authenticated TaskBounty mutation using the user's private API key has NOT been run in this chat/tool environment because the secret is not exposed here.
- Actual solver CLI/account bridge has NOT been connected in this environment.
- 24/7 deployment heartbeat has NOT been independently observed.
- Non-TaskBounty accounts require their concrete official adapter implementations. The core is adapter-ready; unofficial or prohibited automation must not be invented.

## Operational status
STACKHUB V2 core/runtime is **integration-ready and CI-green**. It is **NOT yet verified LIVE 24/7 earning** until the user's secrets/solver are connected, one real mutation is verified, and the deployment heartbeat is observed.