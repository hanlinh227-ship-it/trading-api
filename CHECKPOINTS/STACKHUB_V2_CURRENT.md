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
- Checked-in configuration stays safe/read-only by default.
- Every submission/publication requires verification evidence.
- Do not call the runtime LIVE unless deployment/runtime is independently verified.

## Completed foundation

### A. Bounded worker-pool configuration — COMPLETE
Original commit: `5ea58d75d6fdc4dc3b2d36d9041e15a842bcba1b`.

Current ceilings:
- scouts: 3
- code_fix: 2
- research_data: 2
- service: 2
- verification: 2
- submission: 1
- global `max_active_claims`: up to 4

Checked-in runtime remains `dry_run: true`, `worker_enabled: false`, zero external spend.

### B. Architecture generalized to continuous multi-source — COMPLETE
Design updated in commit `3182fbb706f27566a702d1f87a4103f1b51e79c1`.
Implementation plan created in commit `1d8abd62ad293e2dbdcb0567a160edf53d0ed834`.

Architecture now has three coordinated revenue lanes:
1. External Job / Bounty Lane
2. Paid Service / API Lane
3. Reusable Digital Asset Lane

### C. Source-agnostic durable reservation/lifecycle — IMPLEMENTED, focused-tested
Canonical lifecycle:
`DISCOVERED -> ELIGIBLE -> RESERVED -> CLAIMED -> SOLVING -> VERIFIED -> SUBMITTED -> PAID`
with `FAILED_RETRYABLE`, `FAILED_PERMANENT`, `EXPIRED`, `REJECTED`.

Implemented:
- migration-safe `reserved_at`, `updated_at`, `last_error_code` claim fields;
- SQLite `BEGIN IMMEDIATE` atomic reservation;
- optional source filter so global reservation can rank across sources;
- global active-claim capacity enforcement;
- terminal states no longer consume active capacity;
- transition validation through `assert_transition`;
- legacy state aliases/migration for current worker compatibility.

Relevant branch commits include:
- `3d7e329119eddcd2282da8f22a8bf5ccc657d0e0`
- `064977b104887151580b84a633070958ce8002d8`
- `bfe12d2c221e5c85df371f3ac006fc0d857987fd`
- `df67a70df91fdd987e1ceeeccb2e90ab51226506`

Verification evidence:
- RED observed: `reserve_next_opportunity` missing.
- GREEN scratch focused lifecycle/reservation suite: `8 passed`.
- Full repository suite/CI is NOT yet claimed.

### D. Source capability policy gate — IMPLEMENTED, focused-tested
Implemented:
- `SourceCapabilities` manifest;
- action-specific discovery/claim/submit/publish/payout-observation permissions;
- hard reject for `external_spend_required=true`;
- mutation requires explicit capability plus mutation/terms verification timestamps;
- runtime worker guardrail generalized from TaskBounty-specific to any enabled mutable source;
- TaskBounty remains read-only in checked-in config and only auto-discovery is enabled.

Relevant commits:
- `6feb5e3561873b8d71ad0adc0827f073d3bf8aed`
- `46b3d5828a4cf60e2abe558f4c07ae2e45b692fc`
- `530d7b3b1b399f8c4505e431f3ee12eee72f2df2`
- `248ee541fb0221cf363c92650cf2d9425e2e1ea8`

Verification evidence:
- RED observed: `stackhub.source_capabilities` missing.
- GREEN scratch capability + config guardrail suite: `6 passed`.
- Full repository suite/CI is NOT yet claimed.

### E. Account onboarding matrix — DOCUMENTED
`stackhub_v2/ACCOUNT_ONBOARDING.md` created in commit `0fbfdf83b0785b598d6503681de315b91c5b4962`.

It separates:
- user-required signup/OTP/KYC/tax/payment setup;
- STACKHUB-automatable post-onboarding actions;
- secrets that must never be committed or pasted into source;
- initial account order for Job, Service/API and Digital Asset lanes.

## Next implementation actions
1. Global opportunity normalization and cross-source revenue scoring.
2. Adapter contract + independent read-only scouts.
3. Solver isolation + verification + capability-gated submission/publication.
4. Revenue orchestrator with bounded concurrency and fallback lanes.
5. Unified payout reconciliation and revenue/source-concentration metrics.
6. Truthful status/secret redaction/deployment watchdog.
7. Full regression + validators + CI.
8. Verify source APIs/terms one source at a time, add credentials through secret storage, then enable a deliberately small live-task cap.

## User-required onboarding blockers before live earning
Human action is required for any platform that asks for account signup acceptance, CAPTCHA, email/phone OTP, KYC/identity verification, tax declarations, bank/PayPal setup, legal agreements or explicit API approval. ChatGPT/STACKHUB must not bypass or impersonate the user for these steps.

## Operational note
STACKHUB V2 is NOT yet a verified 24/7 earning runtime. The architecture, durable reservation and source capability gate are now multi-source, but adapters, orchestrator, solver/verification/submission boundaries, payout reconciliation, full regression, deployment and runtime heartbeat remain release gates.
