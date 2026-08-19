# V78 — CLAUDE PHASE 1 ARCHITECTURE BLUEPRINT

Source: Claude.ai CO-ARCHITECT review supplied 2026-08-19. Persisted by ChatGPT because Claude GitHub MCP write access returned 403.

Status: DESIGN EVIDENCE — no production behavior change.

## 1. Current system map

- `cloudflare-worker/index.js` V77.18.43 is the Cloudflare Worker fetch/scheduled entrypoint.
- `hub-v77171.js` V77.18.42 owns the primary Telegram HUB and delegates core Signal logic to `engine-v77168.js` V77.16.20.
- `engine-v77168.js` is a large multi-concern file containing data clients, indicators, V73 prior lookup, decision pipeline, books state and a legacy Telegram router/keyboard.
- Hyro stack spans `hyro-execution.js`, `hyro-scanner.js`, `hyro-market-context.js`, `hyro-portfolio-guard.js`, `hyro-runtime.js`, `hyro-position-manager.js`, and `hyro-position-review.js`.
- AI governance is split across `ai-arbiter.js`, `dual-ai-intervention.js`, and `claude-reviewer.js`.
- `binance-futures20-config.js`, `binance-futures20-engine.js`, `binance-futures20-runtime.js`, and `binance-usdm-client.js` were not found in the active import chain inspected by Claude and are currently treated as orphaned/non-production until ChatGPT independently confirms otherwise.

## 2. HUB problems and target

Observed problems:
- Three Telegram handling layers can overlap: `claude-telegram.js` -> `hub-v77171.js` -> `engine-v77168.js` fallback.
- Telegram secret verification logic is duplicated.
- Hyro profile/risk-display logic is duplicated between HUB and execution code while sharing the same profile key.
- Legacy keyboard/menu behavior remains inside the Signal engine and can return stale/confusing UX.
- HUB system status does not present a single authoritative view of AI/Hyro degraded states.
- Notification dedupe/cooldown logic is fragmented across several modules.

Target:
- one `telegram-router.js` for verification and dispatch;
- screen-provider modules rather than independent routers;
- one canonical Hyro profile/risk source;
- one `NotificationBus.notifyOnce(...)` abstraction;
- explicit screen domains: SIGNAL / WATCH / LIVE ORDER / POSITION / SYSTEM HEALTH / SETTINGS;
- retire legacy Signal-engine keyboard after cutover.

## 3. Signal / entry pipeline

Current problem:
Signal and Hyro implement overlapping but separate opportunity-analysis pipelines, including duplicated indicator/regime logic and independent conclusions for the same crypto symbols.

Target lifecycle:
`DISCOVERY -> DATA INTEGRITY -> CONTEXT -> STRUCTURE -> LOCATION -> TRIGGER -> RISK -> EXECUTION QUOTE -> DECISION -> LIFECYCLE`

Target abstractions:
- shared `MarketDataProvider` layer;
- shared indicator library;
- normalized `DecisionEvidence` object;
- venue capability-aware execution confirmation;
- explicit news-gate state rather than hidden soft fallback.

Important finding:
Claude found `getNewsClearance()` may return `SOFT_NO_EXTERNAL_NEWS_FEED` when `NEWS_GATE_URL` is absent. This means documentation/UX must not describe all such states as a strict external hard-news clearance unless the executable-order gate actually fails closed.

## 4. API/provider inventory

Market/reference data observed:
- Twelve Data
- Massive indices
- Bybit public
- OKX public
- Binance public
- KuCoin
- Gate.io

Private execution/account paths observed:
- Bybit private V5 signing implemented in multiple Hyro-related files.
- Binance USDM private client exists but is not in the active production chain identified by Claude.

AI:
- Anthropic Messages API is called by more than one runtime subsystem with separate prompts/budgets/snapshots.

Messaging:
- Telegram Bot API helper logic is duplicated across several files.

State:
- one `TRADING_STATE` KV namespace with many versioned key prefixes and no single documented key registry.

## 5. Hyro failure modes and target state machine

Claude identified these design risks beyond V77.18.46:
1. idempotency can depend on `symbol:side:entry`, allowing floating-entry variation to produce a new key for the same conceptual setup;
2. position-manager trade matching by side + avgPrice tolerance can reuse stale local management state after a close/reopen near the same price;
3. TP placement booleans can remain true after venue-side order cancellation unless reconciled;
4. no explicit cycle heartbeat / IN_PROGRESS marker for interrupted Worker cycles;
5. `cancelHyroPending()` uses broad cancel-all behavior that may affect reduce-only management orders;
6. `executeHyroPlan()` re-fetches telemetry even when the caller already holds fresh telemetry, increasing API use and creating a second account-state snapshot inside the same cycle.

Target execution state machine:
`DISCONNECTED -> CONNECTED_DEGRADED | CONNECTED_HEALTHY`
`CONNECTED_HEALTHY -> INTENT_CREATED -> SUBMITTED -> FILLED | REJECTED | TIMEOUT_UNKNOWN`
`TIMEOUT_UNKNOWN -> RECONCILING` using client order ID before treating the order as failed.
`FILLED -> POSITION_OPEN -> TP1_PLACED / BE_MOVED / TP2_PLACED / TRAILING_ARMED` with venue verification.
`POSITION_OPEN -> POSITION_CLOSED -> RECONCILED | RECONCILED_DEGRADED`.
`Any state -> PAUSED -> CANCEL_NEW_ENTRIES_ONLY`, preserving protective/management orders for open positions.

## 6. Multi-account foundation

Current Hyro code is account-name/key/env-var coupled.

Target abstractions:
- `AccountAdapter {accountId, venue, mode, credentials, capabilities}`
- `AccountRegistry`
- account-scoped KV keys: `acct:{id}:...`
- `ExecutionVenue` abstraction
- venue capability contract for spot/derivatives/native SLTP/position modes/order types/leverage/closed-PnL semantics/rate limits
- one account failure isolated from other accounts

This is a new architecture and MUST NOT restore legacy TK2/multi-account code.

## 7. Keep

Recommended to preserve conceptually:
- V77.18.46 Hyro telemetry separation principles;
- `hyro-portfolio-guard.js` single-purpose cluster/diversity guard;
- `system-health.js` stateful dedupe concepts as a model for NotificationBus;
- frozen V73 / V74 authority / V76 research constraints;
- validator rule that validation must never mutate production source.

## 8. Refactor

- extract one shared Bybit signed client;
- decompose `engine-v77168.js` into data/indicator/decision/books/UI concerns;
- remove HUB duplicate Hyro risk/profile calculations;
- consolidate notification dedupe;
- consolidate Telegram secret verification and routing.

## 9. Deprecate / quarantine candidates

- `binance-futures20-*` and `binance-usdm-client.js`: quarantine as non-production pending explicit decision to delete or use as a future adapter pilot.
- legacy keyboard/router inside `engine-v77168.js` after unified-router migration.
- independent AI runtime duplication should be redesigned, but Claude requested ChatGPT decide whether `claude-reviewer.js` and `dual-ai-intervention.js` have intentionally distinct purposes.

## 10. State/KV migration

Migration must be additive:
1. document current key registry;
2. add account-scoped keys with legacy fallback reads;
3. dual-read/dual-write where necessary during migration;
4. cut over only after evidence;
5. remove obsolete keys only after soak period;
6. never delete/reset `TRADING_STATE` or `v775:books`.

## 11. Target folder structure

```text
cloudflare-worker/
  core/        kv.js, telegram-client.js, telegram-router.js, notification-bus.js
  providers/   twelvedata-client.js, massive-client.js, bybit-public/signed-client.js,
               okx-client.js, binance-spot/usdm-client.js, indicators.js
  accounts/    account-registry.js, account-adapter.js, hyro-adapter.js
  signal/      discovery.js, context.js, decision-pipeline.js, books-state.js, signal-screens.js
  hyro/        telemetry.js, risk.js, execution.js, portfolio-guard.js,
               position-manager.js, position-review.js, scanner.js, market-context.js
  ai/          reviewer.js, arbiter.js, adaptive-tuning.js, hub-ux-tuning.js
  health/      system-health.js, release-notifier.js
  index.js     thin route + scheduled orchestrator
```

## 12. Phased implementation

- Phase 0: AI-001/AI-002 stabilization/documentation.
- Phase 1: architecture blueprint (this document).
- Phase 2: KV registry + shared Bybit client + shared Telegram helper, aiming for zero behavior change.
- Phase 3: NotificationBus in shadow/log-only mode before cutover.
- Phase 4: mechanical split of `engine-v77168.js` while preserving behavior and validator locks.
- Phase 5: Hyro state-machine hardening: idempotency, scoped cancellation, ambiguous timeout reconciliation, telemetry handoff.
- Phase 6: AccountAdapter foundation with existing Hyro as first adapter.
- Phase 7: unified HUB/router and retirement of legacy keyboard.
- Phase 8: decide/implement future of orphaned Binance code and rationalize AI runtime duplication.

Every implementation phase requires scoped ownership + WRITE_LOCK + independent review.

## 13. High-risk migrations

- idempotency-key change;
- cancel-order scoping;
- account-scoped KV migration;
- mechanical split of engine module state/caches.

These must not be bundled together.

## 14. Quick wins

- create a KV key registry document;
- annotate closure messages when realized P/L freshness is unavailable;
- surface Hyro degraded/AI status cleanly in HUB system status;
- document actual news-gate fallback semantics;
- formally label orphaned Binance20 files as non-production until decided.

## 15. Claude questions for ChatGPT

1. Should `claude-reviewer.js` and `dual-ai-intervention.js` be merged, or are they intentionally distinct?
2. Should orphaned Binance20 modules be deleted or retained as a future AccountAdapter pilot?
3. Is the second telemetry read inside `executeHyroPlan` intentional defense-in-depth or accidental duplication?
4. Is HUB `buildHyroProfile()` display-only and safe to replace with canonical dynamic-risk output?
5. Is news-gate soft-pass-by-default intentional production behavior, and should executable orders continue to soft-pass when no external news service exists?

This document records Claude's Phase 1 design evidence. ChatGPT must independently verify source claims before production implementation.