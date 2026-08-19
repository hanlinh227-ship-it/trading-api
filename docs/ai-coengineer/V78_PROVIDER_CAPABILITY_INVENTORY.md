# V78-007 — PROVIDER CAPABILITY INVENTORY

Status: IMPLEMENTED — DOCUMENTATION ONLY / ZERO_BEHAVIOR
Owner: CHATGPT
Reviewer: CLAUDE

## Purpose
Create a capability/authority inventory for current market-data, context and execution providers so later V78 work can broaden symbol/market intelligence without confusing analysis data with execution authority.

This issue changes no production source, provider selection, API call, risk, order, KV or routing behavior.

## Capability classes

- `ANALYSIS_PUBLIC`: public/analysis market data; never grants order authority.
- `ANALYSIS_KEYED`: authenticated/keyed data API used for analysis; never grants order authority by itself.
- `CONTEXT_PUBLIC`: public microstructure/context evidence; never grants order authority.
- `EXECUTION_PRIVATE`: signed account/order API; may have execution capability only when runtime/account/risk policy explicitly authorizes it.
- `NON_PRODUCTION_PRIVATE`: private execution capability exists in code but is quarantined from production authority.

## Current inventory

| Provider/path | Capability | Current markets/symbol role | Credential/auth | Execution authority | Current notes |
|---|---|---|---|---|---|
| Twelve Data (`engine-v77168.js`) | ANALYSIS_KEYED | Forex, metals, indexes; candles/quotes and index identity validation | `TWELVE_DATA_API_KEY` | NONE | Explicit credit budgeting/reserve exists; symbol/instrument identity and freshness remain mandatory. |
| Massive (`engine-v77168.js`) | ANALYSIS_KEYED | Index data, e.g. NDX/DJI/SPX/DAX/N225 mapping | `MASSIVE_API_KEY` | NONE | Used as index data path/fallback hierarchy; analysis authority only. |
| Bybit public market API — Signal | ANALYSIS_PUBLIC | Crypto tickers/candles/public analysis | unsigned public GET | NONE | Signal crypto is advisory; public Bybit data must not imply execution permission. |
| OKX public market API — Signal | ANALYSIS_PUBLIC | Crypto candles/public analysis | unsigned public GET | NONE | Advisory/analysis only. |
| Bybit public market/context — Hyro scanner/context | CONTEXT_PUBLIC | Crypto market state, funding/carry, OI, long/short, orderbook/spread where available | public | NONE by itself | Funding is not hard-news clearance; context does not submit orders. |
| Bybit private Hyro stack | EXECUTION_PRIVATE | Current Hyro account telemetry, orders, positions and management | signed private credentials | YES, safety-gated | Current active real-capital authority per V78-005; critical telemetry/risk/idempotency/reconciliation still gate execution. |
| Bybit DEMO validation path | EXECUTION_PRIVATE (DEMO) | Hyro demo/challenge validation | signed DEMO credentials/environment | DEMO ONLY | CHALLENGE must preserve forced-DEMO `propEnv()` invariant from V78-006 H-16. |
| Binance USDM standalone modules | NON_PRODUCTION_PRIVATE | Standalone Binance futures implementation | private capability exists in code | NONE in current production | DECISION-005: NON_PRODUCTION / QUARANTINED. No import/route/scheduled promotion without separate reviewed issue. |
| News/context gate configured externally | CONTEXT / POLICY INPUT | Event/news clearance when configured | environment/config dependent | NONE by itself | Missing/unverified news evidence must not be represented as authoritative hard-news PASS for executable decisions. |

## Market expansion rules

V78 may expand intelligence across more markets and symbols, but expansion must be capability-driven rather than symbol-list-only.

For every new market/symbol/provider combination, record at least:
1. canonical internal symbol;
2. provider symbol;
3. instrument class (`spot`, `cash`, `index`, `perpetual`, `future`, `forex`, `metal`, etc.);
4. quote/candle semantics;
5. provider timestamp source and freshness threshold;
6. timezone/session semantics where relevant;
7. analysis-vs-execution authority;
8. credential/rate-limit requirements;
9. fallback policy;
10. disagreement behavior;
11. whether the provider can be used for execution sizing/price validation or analysis only.

Adding more symbols must never silently substitute spot for perpetual, cash index for futures, or an analysis quote for an execution-authoritative quote.

## Provider selection principles

- Prefer the provider whose instrument identity matches the requested market exactly.
- Preserve independent evidence when providers disagree; do not average disagreement into fabricated authority.
- A fallback must preserve instrument class and freshness requirements.
- `MISSING`, `STALE`, `DEGRADED`, `UNKNOWN` remain explicit states.
- Provider availability alone cannot convert a blocked setup into an executable trade.
- Private execution clients require explicit account registration + runtime wiring + RiskPolicy; mere code capability is insufficient.

## Future V78 abstraction target

A future `MarketDataProvider` contract should expose capabilities rather than assuming every provider supports every market:

```text
providerId
instrumentClasses[]
marketDataCapabilities[]
authClass
freshnessPolicy
symbolMapper
rateLimitPolicy
executionAuthoritative: boolean
```

Execution remains separate through `ExecutionVenue` / `AccountAdapter` and must not be folded into generic market-data provider selection.

## Acceptance criteria

- [x] Current known Signal/Hyro/Binance provider roles are separated by capability.
- [x] Public/keyed analysis data is separated from private execution authority.
- [x] Bybit Hyro private authority is identified as safety-gated.
- [x] Binance20 quarantine is preserved.
- [x] Provider/instrument/freshness requirements for future symbol expansion are explicit.
- [x] No production source/API/risk/order/state behavior changed.

## Reviewer request
Claude should verify this inventory against current source and identify exact missing active providers/capabilities, wrong market classifications, or authority mistakes. Return PASS/WARN/BLOCK with source evidence. Future provider expansion should use this inventory as the baseline rather than simply adding symbols to arrays.
