# V78 IMPLEMENTATION — WAVE 0 / WAVE 1

Status: OPEN — V78-001 RESOLVED / V78-002 IMPLEMENTED DOCUMENTATION-ONLY / OTHER EXACT PHASE-2 MAPPINGS PARTIALLY AVAILABLE
Owner: CHATGPT
Reviewer: CLAUDE
Production source authorization: NONE until each source issue receives an explicit WRITE_LOCK scope.

## Integrity constraint
The complete Claude Phase 2 verbatim body is still not present in the GitHub bus or otherwise retrievable by ChatGPT in the current session context. ChatGPT therefore must not invent or falsely attribute the missing HUB menu, Claude-exact DecisionEvidence body, V78-003..V78-091 semantics, or acceptance criteria.

Confirmed exact facts supplied by the user in the current handoff:
- `V78-001` = KV key registry, documentation-only, ZERO_BEHAVIOR.
- `V78-002` = DecisionEvidence schema documentation, ZERO_BEHAVIOR.
- mapping contains new IDs `V78-005`, `V78-006`, `V78-007`, `V78-014`.
- `V78-011` scope is narrowed; `verifyTelegram` work is deferred to `V78-081`.

Until Claude's complete exact body is accessible, these ID constraints are preserved without guessing unexpanded semantics.

## Wave 0 — Documentation, invariants, evidence baselines

### V78-001 — KV/state registry baseline — RESOLVED
Former provisional ID: `V78-W0-02`
Class: ZERO_BEHAVIOR
Scope: `docs/ai-coengineer/V78_KV_KEY_REGISTRY.md`
Objective: canonical inventory of current `TRADING_STATE` key prefixes, owners, lifecycle, readers/writers, migration criticality and non-production state.
Hard constraints: do not rename/delete keys; preserve `v775:books`; no runtime behavior change.
Initial implementation commit: `a45b8f33672273ac0ae580bf6f6bee54a8c63893`
Claude review result: WARN — missing `v771816:signal:auto_notify:{sig}` plus two Claude-reviewer TTL description inaccuracies.
Correction commit: `b451a086336bb9a6e59dc84031a1866e46e591da`
Resolved corrections:
- added `v771816:signal:auto_notify:{sig}` from `engine-v77168.js:notifySignalPlans`, TTL 1800s;
- corrected `v771821:claude:daily_system_audit` TTL to 2592000s;
- corrected `v771822:claude:overnight` TTL to 172800s.
Acceptance: no runtime behavior/state mutation; registry accuracy corrected.
Rollback: documentation-only revert.

### V78-002 — DecisionEvidence schema — IMPLEMENTED DOCUMENTATION ONLY
Class: ZERO_BEHAVIOR
Scope: `docs/ai-coengineer/V78_DECISION_EVIDENCE_SCHEMA.md`
Objective: define the shared evidence contract for provider identity, timestamps, freshness, observations, hard gates, decision reason, data integrity and execution suitability without changing any current decision or execution path.
Implementation commit: `0bbe2b0c0fccda112820cad1f8f65121ba0d8fce`
Integrity condition: because Claude's verbatim Phase 2 schema body is not retrievable by ChatGPT, this implementation is explicitly not claimed as a verbatim Claude paste. Claude must compare field-for-field and provide exact corrections before future source/shadow adoption.
Acceptance: schema documentation exists; no source consumer, KV key, risk gate, order or Telegram behavior changed.
Rollback: documentation-only revert.

### W0-PENDING — Ingest exact Claude Phase 2 backlog
Class: ZERO_BEHAVIOR
Scope: `docs/ai-coengineer/V78_CLAUDE_PHASE2_BACKLOG.md`
Objective: persist exact target HUB menu, exact Claude DecisionEvidence schema body and exact V78-001..V78-091 body from Claude chat.
Dependency: Claude exact body must actually be available to ChatGPT.
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

No Wave 1 source change is authorized or started by V78-001/V78-002.

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
Candidate scope: source implementation of the accepted V78-002 schema only after Claude field-level review; populate/log alongside existing decisions without gating or replacing behavior.
Dependency: V78-002 reviewer PASS/correction + validation baseline.
Risk: LOW if shadow-only.
Validation: timestamp/provider/freshness/source identity, deterministic serialization, no decision changes.
Rollback: remove shadow generation.
Exact V78 source-adoption ID: PENDING CLAUDE BODY.

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
| `V78-001` | KV key registry; RESOLVED after Claude WARN corrections. |
| `V78-002` | DecisionEvidence schema documentation; implemented zero-behavior, awaiting Claude field-level comparison. |
| `V78-005` | New exact Phase 2 ID exists; semantic body must come from Claude exact resend. |
| `V78-006` | New exact Phase 2 ID exists; semantic body must come from Claude exact resend. |
| `V78-007` | New exact Phase 2 ID exists; semantic body must come from Claude exact resend. |
| `V78-014` | New exact Phase 2 ID exists; semantic body must come from Claude exact resend. |
| `V78-011` | Scope narrowed; must not absorb `verifyTelegram` consolidation. |
| `V78-081` | `verifyTelegram` consolidation is deferred here. |

## One-writer execution rule
Only ONE source issue may hold WRITE_LOCK at a time. V78-001 and V78-002 are documentation-only issues. Completing them does not authorize any Wave 1 source issue.

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
