# V78 IMPLEMENTATION — WAVE 0 / WAVE 1

Status: OPEN — PLANNING / SCOPING ONLY
Owner: CHATGPT
Reviewer: CLAUDE
Production source authorization: NONE until each issue receives an explicit WRITE_LOCK scope.

Important integrity constraint:
The exact Claude Phase 2 backlog V78-001..V78-091 has not yet been ingested. Therefore these are provisional Wave 0/Wave 1 implementation issues and MUST NOT be mapped to Claude's V78-### numbers until the exact backlog is supplied.

## Wave 0 — Documentation, invariants, evidence baselines

### V78-W0-01 — Ingest exact Claude Phase 2 backlog
Class: ZERO_BEHAVIOR
Scope: `docs/ai-coengineer/V78_CLAUDE_PHASE2_BACKLOG.md`
Objective: persist exact target HUB menu, exact DecisionEvidence schema, and exact V78-001..V78-091 numbering from Claude chat.
Dependency: none.
Acceptance: no invented items; all Claude issue IDs preserved exactly.
Rollback: revert documentation commit.

### V78-W0-02 — KV/state registry baseline
Class: ZERO_BEHAVIOR
Scope: documentation only; inventory all current TRADING_STATE key prefixes and owners.
Objective: build a canonical KV registry before any account-scoped migration.
Hard constraints: do not rename/delete keys; preserve `v775:books`.
Acceptance: every production key found in current imports/routes has owner, lifecycle, reader/writer, migration status.
Rollback: documentation-only revert.

### V78-W0-03 — Execution authority map
Class: ZERO_BEHAVIOR
Scope: documentation/evidence only.
Objective: record that current `engine-v77168.js` Signal crypto path uses unsigned public GET market-data calls and does not call `/v5/order/create`; Hyro is current real-capital execution path; Binance20 remains NON_PRODUCTION.
Acceptance: exact file/function evidence included; no behavior change.
Rollback: documentation-only revert.

### V78-W0-04 — V78-041 news/funding policy baseline
Class: ZERO_BEHAVIOR
Scope: `DECISIONS.md` / design docs only.
Objective: distinguish hard-news/context gate from funding-rate microstructure/carry gate before implementation.
Acceptance: funding cannot be documented as equivalent to news; executable order policy is explicit.
Rollback: architecture-decision revert before implementation.

### V78-W0-05 — Deterministic baseline validation matrix
Class: ZERO_BEHAVIOR
Scope: docs/test-plan only.
Objective: define current expected behavior for Signal advisory paths, Hyro execution, state continuity, Telegram routing, health, and provider freshness before mechanical refactors.
Acceptance: baseline covers no-reset, no-duplicate, no fabricated data, no accidental real order from Signal, and current Hyro execution authority.
Rollback: documentation-only revert.

## Wave 1 — Low-risk shared primitives, one issue at a time

### V78-W1-01 — Shared Bybit signed-client extraction
Class: ZERO_BEHAVIOR
Candidate scope: extract repeated Bybit HMAC/sign/request primitives used by Hyro execution/manager/review/demo into a shared client without changing endpoints, params, risk or order semantics.
Dependencies: W0-02, W0-05, exact Claude backlog ingest preferred before source authorization.
Risk: MEDIUM because private execution client is touched even if behavior should remain identical.
Validation: request canonicalization/signature parity fixtures; endpoint/verb/body equality; no state changes.
Rollback: restore per-module clients.
Reviewer skills: trading-regression-tester, hyro-execution-auditor, trading-risk-guardian.
Acceptance: byte/semantic-equivalent request construction for existing calls; no new endpoint; no changed risk.

### V78-W1-02 — Shared Telegram HTTP client extraction
Class: ZERO_BEHAVIOR
Candidate scope: centralize Telegram Bot API POST transport only; no router/menu/dedupe change yet.
Dependencies: W0-05.
Risk: LOW/MEDIUM.
Validation: same method, payload, chat/thread routing, parse behavior and error semantics at all migrated call sites.
Rollback: revert shared helper and imports.
Reviewer skills: trading-regression-tester.
Acceptance: output/payload parity; no callback routing change.

### V78-W1-03 — DecisionEvidence schema foundation in shadow mode
Class: SHADOW
Candidate scope: introduce the exact Claude-authored `DecisionEvidence` schema only after V78-W0-01 exact ingest; populate/log alongside existing decisions without gating or replacing behavior.
Dependencies: W0-01, W0-05.
Risk: LOW if shadow-only.
Validation: schema completeness, timestamp/provider/freshness/source identity, no decision changes.
Rollback: remove shadow object generation.
Reviewer skills: trading-data-integrity-auditor, trading-regression-tester.
Acceptance: existing decisions unchanged; evidence object serializes deterministically.

### V78-W1-04 — Binance20 NON_PRODUCTION quarantine marker
Class: ZERO_BEHAVIOR
Candidate scope: documentation/module header/validator guard only; no execution wiring.
Dependencies: W0-03.
Risk: LOW.
Validation: production import chain unchanged; no credentials/routes/scheduled handlers added.
Rollback: revert marker/guard.
Acceptance: future engineers cannot mistake Binance20 for active production execution.

### V78-W1-05 — Shared provider capability inventory
Class: ZERO_BEHAVIOR
Scope: documentation/schema only.
Objective: map Twelve Data, Massive, Bybit public/private, OKX, Binance public/USDM, KuCoin, Gate and Telegram/AI dependencies into capability contracts before AccountAdapter work.
Dependencies: W0-02/W0-03.
Risk: LOW.
Acceptance: provider capabilities and execution authority clearly separated; no source behavior change.

## One-writer execution rule
Only ONE Wave 1 source issue may hold WRITE_LOCK at a time. A separate exact lock must name its files/functions. Completing a planning issue does not authorize the next issue automatically.

## Explicitly deferred beyond Wave 1
Do not start yet:
- idempotency redesign;
- cancel scoping;
- account-KV migration;
- engine split;
- HUB router cutover;
- NotificationBus behavior cutover;
- hard-news gate production enforcement;
- multi-account live enablement.
These require exact Claude Phase 2 mapping and separate high-risk review.
