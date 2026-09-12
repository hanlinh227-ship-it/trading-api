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

### 9. Runtime/account integration entrypoints — IMPLEMENTED
Core commits include `499b146ac5b1f244b30a9aecca871dd8959f63a1`, `21c96000158522780ebb4a597a564fb9b73a6c3a`, `004ba0e95be84b17fac9d3529e62a90a1bc62b59`, plus account-integration commits through `ad5f56b4e7994c3fbc528b6208ab642544f94f1a`.

Implemented:
- adapter registry;
- environment-secret doctor;
- isolated command solver bridge with marketplace credential stripping;
- truthful runtime status with `DRY-RUN` vs `LIVE-CANDIDATE` and mutation status;
- source-agnostic CLI: `doctor`, `scan-once`, `opportunities`, `status`, `orchestrate-once`, `run`;
- shared repository opportunity pool;
- safe read-only checked-in config;
- one-task live-config example with `max_active_claims: 1` and no credentials;
- systemd 24/7 service example with persistent SQLite storage and external environment file;
- unified `accounts.py` integration registry with modes `AUTO`, `OBSERVE`, `ASSISTED`, `PAYOUT_ONLY`;
- `python -m stackhub.account_doctor` reports readiness and missing env variable NAMES without printing secret values;
- deployment secret template `INTEGRATION.env.example`;
- deployment-ready `INTEGRATION_GUIDE.md`.

Current account modes:
- TaskBounty: `AUTO` after authenticated live mutation gate; `TASKBOUNTY_API_KEY`.
- Gumroad: `OBSERVE`; `GUMROAD_ACCESS_TOKEN`; current product creation/upload remains assisted because the official API does not support it.
- RapidAPI: `ASSISTED` unless the account has an explicit supported Platform API contract/entitlement verified for the intended action.
- Adobe Stock: `ASSISTED` for Contributor Portal upload/review; STACKHUB may prepare/validate assets and metadata but does not invent an upload API.
- PayPal: `PAYOUT_ONLY`; STACKHUB never requests PayPal password/session credentials.
- GitHub: authorized tooling/OAuth/App/CLI only; no account password or 2FA recovery secret stored by STACKHUB.

## Fresh CI evidence on current integration head `ad5f56b4e7994c3fbc528b6208ab642544f94f1a`
`STACKHUB V2 CI` PR run `34616855520`: SUCCESS.
`STACKHUB V2 CI` push run `34616852221`: SUCCESS.
`AI Skill Library CI` run `34616855458`: SUCCESS.

The prior run on `ac8c9fbb64fe7e6721f5c447ff9c92dd380899f9` passed all pytest tests (`82 passed`) but intentionally failed the committed-secret detector because a test fixture resembled a real `tb_live_*` token. The fixture was changed to a non-credential-shaped fake value; the subsequent current-head runs above are green. This failure is retained as security regression evidence.

## Account state supplied by user
- PayPal: available.
- TaskBounty account/API key: available.
- User states all remaining account pieces are already available.
- Real secret values must remain in deployment/system secret storage and must not be committed or pasted into chat.

## Integration procedure
1. Create deployment environment file/secret store outside Git, e.g. `/etc/stackhub/stackhub.env`.
2. Set only credentials actually required by enabled adapters, currently including `TASKBOUNTY_API_KEY`; add `GUMROAD_ACCESS_TOKEN` only for Gumroad observation/API operations.
3. Configure `STACKHUB_SOLVER_COMMAND` to an authorized AI solver wrapper/CLI. Marketplace/account secrets are stripped from the solver subprocess environment.
4. Run `python -m stackhub.account_doctor` and `stackhub doctor --config ...`.
5. Run read-only `stackhub scan-once`; inspect `stackhub opportunities` and `stackhub status`.
6. Copy `config/sources.live.example.yaml` to a deployment-only path and keep `max_active_claims: 1` for the first authenticated mutation.
7. Run `stackhub orchestrate-once` and inspect one real claim/solve/verify/submit cycle end-to-end.
8. Only after independent first-task verification, run `stackhub run` under the provided systemd service for continuous operation.
9. Increase concurrency only after observed stability and payout/acceptance evidence.

## Continuous job-source expansion
TaskBounty remains one AUTO source, not the center. The highest-priority next AUTO-job candidate identified from current public documentation is MoltJobs because it exposes official agent-native REST/CLI/MCP workflows for discovery, bidding/start, submission and payout. It is NOT yet marked integrated because bid-pending/award lifecycle semantics must be represented explicitly rather than faked as a direct claim. Any paid bid-credit purchase remains prohibited by the zero-spend invariant.

Other candidate sources remain `DISCOVERY_ONLY`/`ASSISTED` until their current API, agent permission, claim/bid semantics, submission semantics and payout evidence are verified.

## Remaining LIVE release gates
- Actual authenticated mutation using the user's private marketplace credential has not been executed in this chat/tool environment because secret values are intentionally unavailable here.
- The user's real solver CLI/account bridge has not been connected in this environment.
- One real claim -> solve -> verify -> submit cycle must be observed successfully.
- 24/7 deployment heartbeat/restart recovery must be independently observed.
- Additional AUTO sources beyond TaskBounty require concrete official adapters and contract tests; unsupported/human-only actions remain assisted.

## Operational status
STACKHUB V2 core/runtime is **ACCOUNT-INTEGRATION-READY and CI-GREEN**. It is **NOT yet verified LIVE 24/7 earning** until deployment secrets/solver are connected, one real mutation is verified, and the persistent runtime heartbeat is observed.
