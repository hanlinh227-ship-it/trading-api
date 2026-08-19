# V78-005 — EXECUTION AUTHORITY MAP

Status: IMPLEMENTED — DOCUMENTATION ONLY / ZERO_BEHAVIOR
Owner: CHATGPT
Reviewer: CLAUDE

## Purpose
Document which current runtime paths are advisory/data-only and which path currently has real-capital order authority. This prevents future refactors from accidentally treating market-data code as executable trading authority or wiring quarantined code into production.

V78-005 changes no production JavaScript, provider call, credential use, order behavior, risk rule, Telegram route or KV value.

---

## 1. Signal engine — advisory / no real-capital execution authority

Primary source: `cloudflare-worker/engine-v77168.js`.

Current crypto Signal analysis uses public market-data providers. Existing source review has verified public Bybit/OKX market-data helpers and no `/v5/order/create` call in `engine-v77168.js`.

Current interpretation:
- Signal may emit recommendation/decision labels such as `MARKET_PLAN`, `LIMIT_PLAN`, `WATCH` or `DATA_BLOCK`.
- Those labels are advisory decision outputs, not broker/exchange fills.
- Fresh public market data does not grant order authority.
- `DecisionEvidence.execution.executionAuthority` for the current Signal path is `NONE` unless a separately reviewed execution adapter is introduced later.

Invariant:
`MARKET_PLAN != MARKET ORDER` and `LIMIT_PLAN != LIMIT ORDER`.

---

## 2. Hyro / Bybit private stack — current real-capital execution authority

Primary production execution sources:
- `cloudflare-worker/hyro-execution.js`
- `cloudflare-worker/hyro-runtime.js`
- `cloudflare-worker/hyro-position-manager.js`
- `cloudflare-worker/hyro-position-review.js`

Supporting validation source:
- `cloudflare-worker/hyro-demo-test.js`

Current Hyro stack uses private signed Bybit v5 account/order endpoints for account telemetry, execution and position management. Under the current architecture, this is the active real-capital execution authority.

Execution authority remains conditional on current safety gates including, as applicable:
- credentials/configuration;
- critical telemetry connectivity;
- manual pause / auto-execution state;
- account/day risk controls;
- structural SL and sizing;
- portfolio constraints;
- idempotency/reconciliation;
- execution-authoritative market state;
- any future mandatory hard-news gate once separately implemented.

Hyro authority does not permit bypassing a hard block.

---

## 3. Binance20 modules — NON_PRODUCTION / QUARANTINED

Files:
- `cloudflare-worker/binance-futures20-config.js`
- `cloudflare-worker/binance-futures20-engine.js`
- `cloudflare-worker/binance-futures20-runtime.js`
- `cloudflare-worker/binance-usdm-client.js`

Current architecture decision: DECISION-005.

These modules contain a standalone Binance USDM trading implementation and private execution capability, but prior import-chain review found them outside the active `index.js` / `hub-v77171.js` / `engine-v77168.js` production chain.

Canonical classification:
`NON_PRODUCTION / QUARANTINED`.

Therefore:
- existence of `api.order()` or private Binance credentials in those files does NOT mean current production execution authority;
- no route, scheduled handler, import or credential wiring may be added merely by documentation/refactor work;
- they may later become a pilot `AccountAdapter` only under a separate reviewed promotion issue;
- until then they must remain isolated.

V78-004 is the separately scoped source-annotation issue intended to make this quarantine explicit in the four files. V78-005 does not apply or replace that source patch.

---

## 4. Execution authority matrix

| Domain/path | Data authority | Order authority | Current production class |
|---|---|---|---|
| Signal Forex/Metal/Index | analysis/advisory providers | NONE | ACTIVE ADVISORY |
| Signal Crypto | public analysis providers incl. Bybit/OKX paths | NONE | ACTIVE ADVISORY |
| Hyro public scanner/context | market/microstructure analysis | NONE by itself | ACTIVE ANALYSIS SUPPORT |
| Hyro private execution/runtime | Bybit private/account/execution | YES, safety-gated | ACTIVE REAL-CAPITAL EXECUTION |
| Hyro demo-test | Bybit DEMO private execution only when DEMO guard passes | DEMO ONLY | VALIDATION/TEST |
| Binance20 standalone modules | Binance market/private implementation | CODE CAPABILITY EXISTS, but no current production authority | NON_PRODUCTION / QUARANTINED |

---

## 5. Provider capability is not execution authority

A provider/client may expose private order methods without being production-authorized.

Future V78 abstractions must separate at least:
- `MarketDataProvider` capability;
- `ExecutionVenue` capability;
- account registration/enablement;
- runtime route/scheduled wiring;
- risk policy;
- execution permission.

Production authority should require explicit account/venue registration and runtime wiring, not merely importing a client library.

---

## 6. DecisionEvidence mapping

Current expected values:

### Signal
```text
executionAuthority: NONE
suitability: ADVISORY_ONLY
```
when no authorized execution adapter exists.

### Hyro new-order candidate
```text
executionAuthority: HYRO
suitability: EXECUTION_ELIGIBLE | EXECUTION_BLOCKED
```
depending on current mandatory gates.

### Binance20 quarantined code
```text
executionAuthority: NONE
suitability: EXECUTION_BLOCKED
reason: NON_PRODUCTION_QUARANTINED
```
for the current production system, even though the module itself contains order methods.

---

## 7. Hard invariants

V78-005 does not authorize:
- importing/wiring Binance20 into `index.js` or scheduled handlers;
- adding Binance credentials to production routing;
- turning Signal plans into real orders;
- bypassing Hyro risk/freshness/SL/news gates;
- changing account state;
- resetting `TRADING_STATE` or `v775:books`;
- restoring legacy Futures Signal or Hyro TK2;
- changing hard risk.

---

## 8. Acceptance criteria

- [x] Current Signal advisory path is explicitly separated from real order authority.
- [x] Hyro private stack is identified as the current active real-capital execution authority.
- [x] Binance20 code capability is distinguished from production authorization.
- [x] DECISION-005 quarantine is represented.
- [x] Market-data/provider capability is not confused with execution permission.
- [x] No production source, order behavior, risk, credential routing or state changed.

## Reviewer request
Claude should verify V78-005 against current imports/routes/scheduled handlers and relevant execution clients. Return PASS/WARN/BLOCK for documentation accuracy. Any later change to execution authority requires its own source issue, WRITE_LOCK and independent review.
