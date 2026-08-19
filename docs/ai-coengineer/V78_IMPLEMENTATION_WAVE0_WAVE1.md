# V78 IMPLEMENTATION — WAVE 0 / WAVE 1

Status: OPEN — V78-001 IMPLEMENTED / OTHER EXACT PHASE-2 MAPPINGS PARTIALLY AVAILABLE
Owner: CHATGPT
Reviewer: CLAUDE
Production source authorization: NONE until each source issue receives an explicit WRITE_LOCK scope.

## Integrity constraint
The complete Claude Phase 2 verbatim body is still not present in the GitHub bus or currently retrievable chat attachment. ChatGPT therefore must not invent the missing HUB menu, DecisionEvidence body, V78-002..V78-091 semantics, or acceptance criteria.

Confirmed exact facts supplied by the user in the current handoff:
- `V78-001` = KV key registry, documentation-only, ZERO_BEHAVIOR.
- mapping contains new IDs `V78-005`, `V78-006`, `V78-007`, `V78-014`.
- `V78-011` scope is narrowed; `verifyTelegram` work is deferred to `V78-081`.

Until Claude's exact body is accessible, these ID constraints are preserved without guessing which provisional item each unexpanded ID describes.

## Wave 0 — Documentation, invariants, evidence baselines

### V78-001 — KV/state registry baseline — IMPLEMENTED
Former provisional ID: `V78-W0-02`
Class: ZERO_BEHAVIOR
Scope: `docs/ai-coengineer/V78_KV_KEY_REGISTRY.md`
Objective: canonical inventory of current `TRADING_STATE` key prefixes, owners, lifecycle, readers/writers, migration criticality and non-production state.
Hard constraints: do not rename/delete keys; preserve `v775:books`; no runtime behavior change.
Implementation commit: `a45b8f33672273ac0ae580bf6f6bee54a8c63893`
Acceptance: registry covers current Signal, HUB, Hyro execution/runtime/management/review, health, release, AI/tuning and quarantined Binance20 state; high-safety keys are explicitly additive-only.
Rollback: revert documentation commit.
Reviewer: CLAUDE.

### W0-PENDING — Ingest exact Claude Phase 2 backlog
Class: ZERO_BEHAVIOR
Scope: `docs/ai-coengineer/V78_CLAUDE_PHASE2_BACKLOG.md`
Objective: persist exact target HUB menu, exact DecisionEvidence schema and exact V78-001..V78-091 body from Claude chat.
Dependency: none.
Acceptance: no invented items; all Claude IDs and acceptance criteria preserved exactly.
Rollback: documentation-only revert.

### W0-PENDING — Execution authority map
Class: ZERO_BEHAVIOR
Scope: documentation/evidence only.
Objective: record that current `engine-v77168.js` Signal crypto path uses unsigned public GET market-data calls and does not call `/v5/order/create`; Hyro is current real-capital execution path; Binance20 remains NON_PRODUCTION.
Acceptance: exact file/function evidence included; no behavior change.
Rollback: documentation-only revert.
Exact V78 ID: PENDING CLAUDE BODY.

### V78-041 — News/funding policy baseline — DECISION RECORDED
Class: ZERO_BEHAVIOR design decision
Scope: `DECISIONS.md` / design docs only.
Objective: distinguish hard-news/context gate from funding-rate microstructure/carry gate before implementation.
Acceptance: funding cannot be documented as equivalent to news; executable-order policy is explicit.
Decision: `DECISION-009`.
Production enforcement: explicitly deferred to a later scoped issue.

### W0-PENDING — Deterministic baseline validation matrix
Class: ZERO_BEHAVIOR
Scope: docs/test-plan only.
Objective: define expected behavior for Signal advisory paths, Hyro execution, state continuity, Telegram routing, health and provider freshness before mechanical refactors.
Acceptance: covers no-reset, no-duplicate, no fabricated data, no accidental real order from Signal and current Hyro execution authority.
Exact V78 ID: PENDING CLAUDE BODY.

## Wave 1 — Low-risk shared primitives, one issue at a time

The exact Claude Phase 2 mapping for these provisional Wave 1 concepts remains unavailable in retrievable source. Do not start source changes until the relevant exact V78 ID/scope is confirmed.

### Provisional — Shared Bybit signed-client extraction
Class: ZERO_BEHAVIOR
Candidate scope: extract repeated Bybit HMAC/sign/request primitives used by Hyro execution/manager/review/demo without changing endpoints, params, risk or order semantics.
Dependency: V78-001 + baseline validation.
Risk: MEDIUM because private execution client is touched.
Validation: request canonicalization/signature parity; endpoint/verb/body equality; no state changes.
Rollback: restore per-module clients.
Reviewer skills: trading-regression-tester, hyro-execution-auditor, trading-risk-guardian.
Exact V78 ID: PENDING CLAUDE BODY.

### Provisional — Shared Telegram HTTP client extraction
Class: ZERO_BEHAVIOR
Candidate scope: centralize Telegram Bot API POST transport only; no router/menu/dedupe change.
Important mapping constraint: if this work overlaps `V78-011`, its scope must remain narrowed; `verifyTelegram` consolidation is **not** part of V78-011 and is deferred to `V78-081`.
Risk: LOW/MEDIUM.
Validation: method/payload/chat/error parity.
Rollback: revert helper/import migration.
Exact V78 ID: PENDING CLAUDE BODY except the V78-011/V78-081 constraint above.

### Provisional — DecisionEvidence shadow foundation
Class: SHADOW
Candidate scope: introduce the exact Claude-authored schema only after its body is ingested; populate/log alongside existing decisions without gating or replacing behavior.
Dependency: exact Phase 2 ingest + validation baseline.
Risk: LOW if shadow-only.
Validation: timestamp/provider/freshness/source identity, deterministic serialization, no decision changes.
Rollback: remove shadow generation.
Exact V78 ID: PENDING CLAUDE BODY.

### Provisional — Binance20 NON_PRODUCTION quarantine marker
Class: ZERO_BEHAVIOR
Scope: documentation/module header/validator guard only; no execution wiring.
Dependency: execution-authority map.
Risk: LOW.
Validation: production import chain unchanged; no credentials/routes/scheduled handlers added.
Rollback: revert marker/guard.
Exact V78 ID: PENDING CLAUDE BODY.

### Provisional — Shared provider capability inventory
Class: ZERO_BEHAVIOR
Scope: documentation/schema only.
Objective: map Twelve Data, Massive, Bybit public/private, OKX, Binance public/USDM, KuCoin, Gate, Telegram and AI dependencies into capability contracts before AccountAdapter work.
Dependency: V78-001 + execution-authority map.
Risk: LOW.
Exact V78 ID: PENDING CLAUDE BODY.

## Confirmed Phase 2 ID constraints awaiting verbatim expansion

| ID | Confirmed constraint |
|---|---|
| `V78-005` | New exact Phase 2 ID exists; semantic body must come from Claude exact resend. |
| `V78-006` | New exact Phase 2 ID exists; semantic body must come from Claude exact resend. |
| `V78-007` | New exact Phase 2 ID exists; semantic body must come from Claude exact resend. |
| `V78-014` | New exact Phase 2 ID exists; semantic body must come from Claude exact resend. |
| `V78-011` | Scope narrowed; must not absorb `verifyTelegram` consolidation. |
| `V78-081` | `verifyTelegram` consolidation is deferred here. |

## One-writer execution rule
Only ONE source issue may hold WRITE_LOCK at a time. V78-001 used a documentation-only lock and has been released. Completing V78-001 does not authorize any Wave 1 source issue.

## Explicitly deferred
Do not start yet:
- any Wave 1 source extraction without exact mapping/review;
- idempotency redesign;
- cancel scoping;
- account-KV migration;
- engine split;
- HUB router cutover;
- NotificationBus behavior cutover;
- hard-news gate production enforcement;
- multi-account live enablement.
