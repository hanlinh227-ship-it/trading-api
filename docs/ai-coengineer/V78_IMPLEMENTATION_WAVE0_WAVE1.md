# V78 IMPLEMENTATION — WAVE 0 / WAVE 1

Status: OPEN — V78-001 RESOLVED / V78-002 RESOLVED / V78-003 IMPLEMENTED AWAITING CLAUDE REVIEW
Owner: CHATGPT + CLAUDE
Reviewer/integrator: reciprocal under implementation-forward protocol
Production source authorization: NONE until each source issue receives an explicit WRITE_LOCK scope.

## Integrity constraint
The complete Claude Phase 2 verbatim body is still not present in the GitHub bus or otherwise retrievable by ChatGPT in the current session context. ChatGPT therefore must not invent or falsely attribute the missing target HUB menu or the unexpanded V78-004..V78-091 semantics/acceptance criteria.

Confirmed exact facts currently available:
- `V78-001` = KV key registry, documentation-only, ZERO_BEHAVIOR — RESOLVED.
- `V78-002` = DecisionEvidence schema documentation, ZERO_BEHAVIOR — RESOLVED after Claude DecisionAction correction.
- `V78-003` = Hyro news-gate status documentation, ZERO_BEHAVIOR — IMPLEMENTED, awaiting Claude accuracy review.
- mapping contains IDs `V78-005`, `V78-006`, `V78-007`, `V78-014`.
- `V78-011` scope is narrowed; `verifyTelegram` work is deferred to `V78-081`.

## Wave 0

### V78-001 — KV/state registry baseline — RESOLVED
Scope: `docs/ai-coengineer/V78_KV_KEY_REGISTRY.md`
Class: ZERO_BEHAVIOR
Initial commit: `a45b8f33672273ac0ae580bf6f6bee54a8c63893`
Correction commit: `b451a086336bb9a6e59dc84031a1866e46e591da`
Claude WARN corrections incorporated:
- `v771816:signal:auto_notify:{sig}` TTL 1800s;
- Claude daily audit TTL 2592000s;
- Claude overnight TTL 172800s.
No runtime behavior/state mutation.

### V78-002 — DecisionEvidence schema — RESOLVED
Scope: `docs/ai-coengineer/V78_DECISION_EVIDENCE_SCHEMA.md`
Class: ZERO_BEHAVIOR
Initial commit: `0bbe2b0c0fccda112820cad1f8f65121ba0d8fce`
Resolution commit: `e432a62cac0031223fda889a9b1a28dfe34ff18c`
Claude correction incorporated in `DecisionAction`:
- `MARKET_PLAN`
- `LIMIT_PLAN`
- `DATA_BLOCK`
while preserving generic lifecycle actions.
Source-alignment note documents plan labels vs execution authority and DATA_BLOCK vs NO_TRADE.
No runtime consumer, KV key, risk gate, order, Telegram route or provider call changed.

### V78-003 — Hyro news-gate status — IMPLEMENTED / REVIEW REQUIRED
Scope: `docs/ai-coengineer/V78_HYRO_NEWS_GATE_STATUS.md`
Class: ZERO_BEHAVIOR
Commit: `b31aa8f364ba1fc7b210d0a1289bccd0f4df2125`
Objective: document current source-backed gap between funding/microstructure controls and authoritative hard-news/event-risk clearance.
Current finding:
- funding protection exists in `hyro-scanner.js:fundingView`;
- OI/long-short/orderbook/spread context exists in `hyro-market-context.js`;
- reviewed Hyro path does not prove an authoritative hard-news provider/gate before execution;
- funding must not be used as a news substitute per DECISION-009.
No production enforcement was added.

### W0-PENDING — Exact Claude Phase 2 ingest
Scope: `docs/ai-coengineer/V78_CLAUDE_PHASE2_BACKLOG.md`
Objective: persist the exact target HUB menu and exact V78-001..V78-091 backlog when the actual verbatim body is accessible to ChatGPT.
Acceptance: no invented items; all Claude IDs and acceptance criteria preserved exactly.

### W0-PENDING — Execution authority map
Class: ZERO_BEHAVIOR
Objective: durable documentation that Signal crypto analysis uses public GET data and Hyro is current real-capital execution authority; Binance20 remains NON_PRODUCTION.
Exact V78 ID: awaiting verbatim backlog.

### V78-041 — News/funding policy baseline — DECISION RECORDED
Decision: `DECISION-009`.
Funding remains separate carry/microstructure evidence; future executable hard-news enforcement requires its own scoped source issue.

### W0-PENDING — Deterministic baseline validation matrix
Class: ZERO_BEHAVIOR
Objective: define expected Signal advisory, Hyro execution, state-continuity, Telegram, health and provider-freshness behavior before mechanical source refactors.
Exact V78 ID: awaiting verbatim backlog.

## Implementation-forward co-engineering
Canonical governance now allows BOTH ChatGPT and Claude to implement scoped issues directly:
- if an issue/handoff is `IMPLEMENTABLE` / `IMPLEMENT_NOW` or has exact objective + file/function scope + acceptance criteria;
- if WRITE_LOCK is free;
- if no unresolved BLOCK applies;
- after refreshing HEAD;
- within the exact lock only.

The implementing AI commits, releases lock and hands exact SHA to the other AI for independent review. If Claude's connector remains 403/read-only, Claude returns exact patch/change material and ChatGPT applies it immediately without reopening design discussion.

## Wave 1 — NOT STARTED
No Wave 1 source change has been started in V78-001..V78-003.

Candidate concepts remain deferred until their exact V78 IDs/scopes are confirmed or the current handoff explicitly marks them IMPLEMENT_NOW:
- shared Bybit signed client;
- shared Telegram HTTP transport;
- DecisionEvidence shadow source adoption;
- Binance20 NON_PRODUCTION quarantine marker;
- provider capability inventory.

## Confirmed Phase 2 constraints awaiting verbatim expansion

| ID | Confirmed constraint |
|---|---|
| `V78-001` | KV key registry — RESOLVED. |
| `V78-002` | DecisionEvidence schema doc — RESOLVED. |
| `V78-003` | Hyro news-gate status doc — implemented, review pending. |
| `V78-005` | Exact Phase 2 ID exists; semantic body awaiting exact ingest. |
| `V78-006` | Exact Phase 2 ID exists; semantic body awaiting exact ingest. |
| `V78-007` | Exact Phase 2 ID exists; semantic body awaiting exact ingest. |
| `V78-014` | Exact Phase 2 ID exists; semantic body awaiting exact ingest. |
| `V78-011` | Scope narrowed; must not absorb `verifyTelegram`. |
| `V78-081` | `verifyTelegram` consolidation belongs here. |

## Explicitly deferred from current authorization
Do not start without a dedicated scoped issue/lock:
- idempotency redesign;
- cancel scoping;
- account-KV migration;
- engine split;
- HUB router cutover;
- NotificationBus behavior cutover;
- hard-news production enforcement;
- multi-account live enablement.
