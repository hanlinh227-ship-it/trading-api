# V78 HYRO EXECUTION HARDENING BLUEPRINT

Status: DESIGN-LOCKED / SOURCE CHANGES NOT YET AUTHORIZED
Date: 2026-08-20
Owner: ChatGPT + Claude.ai Web co-engineering

## Goal
Harden the existing Hyro real-capital execution path without changing its current hard-risk policy, structural-SL authority, freshness/news requirements, account semantics, or current single-account execution authority.

## Non-negotiable invariants
- Never reset `TRADING_STATE` or delete/reset `v775:books`.
- Never weaken hard risk, quote freshness, structural SL, or hard-news/context safeguards.
- Never restore Futures Signal or Hyro TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- Production Claude API remains paused.
- Current Hyro is the sole real-capital execution path.
- Any future multi-account work must first exist as account identity/routing metadata only; it must not silently fan out a single decision into multiple real orders.

## Hardening order

### H1 — Deterministic client order identity / idempotency
Every create-order intent must derive a stable client-order identity from account identity + symbol + side + canonical plan identity + decision timestamp/scan lineage. Before sending a new order, execution must prove the intent is not already represented by a live/pending/exchange-known order. Ambiguous lookup failure must fail closed for NEW execution.

Acceptance:
- duplicate webhook/cron/manual invocation cannot create a second equivalent order;
- retry after timeout first reconciles by client-order identity before any re-submit;
- existing order-management behavior remains unchanged for already-open positions.

### H2 — Restart / deployment reconciliation
On Worker restart, deploy, or stale local execution cache, exchange state is authoritative for open/pending order existence while local state remains authoritative for internal policy metadata. Reconciliation must merge, never blanket-delete.

Acceptance:
- no forced close because code/version changed;
- no local state reset;
- unknown exchange position becomes managed-but-block-new until identity/risk metadata is reconciled;
- telemetry degradation never fabricates flat state.

### H3 — Partial-fill state machine
Represent requestedQty, filledQty, remainingQty, averageFillPrice, orderStatus, lastExchangeUpdateAt and reconciliation status separately. Risk and protective-order management must use actual filled exposure, not requested exposure.

Acceptance:
- PARTIALLY_FILLED is neither treated as zero fill nor full fill;
- protective SL/TP quantity never exceeds actual exposure;
- remaining order cancellation cannot accidentally cancel protective orders.

### H4 — Cancel scoping
Cancel operations must be account + symbol + exact order/clientOrderId scoped. No broad cancel-all may be introduced as a recovery shortcut.

Acceptance:
- canceling an entry cannot cancel its protective SL/TP sibling by wildcard;
- cancel failure is explicit and blocks conflicting replacement orders;
- order identity evidence is persisted before destructive calls.

### H5 — Position/order reconciliation health
Expose read-only execution health: account identity, telemetry freshness, exchange position count, local managed count, pending order count, unreconciled count, duplicate-intent blocks, last reconcile result, closedPnl freshness/degradation.

Acceptance:
- health view has no execution authority;
- missing optional closedPnl remains degraded rather than total disconnect;
- critical wallet/positions/orders failure remains fail-closed for new execution.

### H6 — Multi-account foundation (metadata only first)
Introduce an account registry abstraction only after H1-H5 are proven. Registry fields: accountId, provider, mode, credential binding names, phase/program, risk profile reference, executionEnabled, reconcile status. Default migration must create exactly one current Hyro account.

Acceptance:
- zero change in live order count after migration;
- no automatic copying/fan-out;
- current account behavior remains byte/decision equivalent;
- explicit per-account enablement required before future execution expansion.

## Required evidence before source promotion
For each hardening item Claude.ai Web and ChatGPT must fresh-read exact current functions and produce guarded patches with blob SHA checks. Real-capital source changes require deterministic validation plus a read-only/reconciliation test path before production promotion.

## Explicitly out of scope for the first hardening source patch
- risk percentage changes;
- strategy/ranking changes;
- new symbols/markets;
- auto-enable of additional accounts;
- lowering news/freshness requirements;
- broad cancel-all;
- any call to the paused production Claude API.
