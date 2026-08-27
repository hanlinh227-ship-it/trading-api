# BYBIT AUTO 1.8.8 STATE

Date: 2026-08-27
Status: canonical state checkpoint for the BYBIT-AUTO-1.8.8 design

## Summary
BYBIT-AUTO-1.8.8 replaces the earlier fixed-capital/fixed-slot behavior with continuous equity-curve sizing and full-capital portfolio allocation. The design intentionally removes fixed position-count caps while retaining hard portfolio risk, correlation, exchange-minimum, fee/slippage and runtime headroom gates.

## Changes since 1.8.5
- Continuous equity-curve position sizing instead of fixed-dollar risk floors.
- Unlimited position-count sentinel: `maxOpenPositions = 1_000_000`.
- Unlimited same-direction count sentinel: `maxSameDirectionPositions = 1_000_000`.
- Portfolio margin allocation can scale up to 100% of available portfolio margin when enough valid setups exist.
- Per-position sizing uses an equity-aware slot-margin decay curve so one candidate does not automatically consume the whole account at larger equity levels.
- Target risk curve anchored at 6% for small equity and declining as equity scales; hard per-trade risk cap is 6.5% equity.
- Total managed open-risk hard cap increased to 24% equity to support multiple independent positions while preserving portfolio-level protection.
- Fixed dollar risk/reward floors are not execution authority; exchange minimums, fees, slippage and net edge remain enforced.

## Canonical 1.8.8 values
### Portfolio / position authority
- `maxOpenPositions`: `1_000_000` (unlimited sentinel)
- `maxSameDirectionPositions`: `1_000_000` (unlimited sentinel)
- `maxMarginPerPositionPct`: `100`
- `maxPortfolioMarginPct`: `100`
- `minFreeReservePct`: `0`
- runtime headroom authority: `PORTFOLIO_MARGIN_HEADROOM`

### Risk
- allocator mode: `CONTINUOUS_EQUITY_CURVE_FULL_CAPITAL_ALLOCATOR`
- `targetRiskPctOfEquity`: `6`
- `maxRiskPctOfEquity`: `6.5`
- effective risk target declines with equity scale via the equity curve
- `maxTotalOpenRiskPct`: `24`
- `minRiskUtilizationPct`: `60`
- `microAccountMinRiskUtilizationPct`: `35`
- `smallAccountMinRiskUtilizationPct`: `55`
- `minRR`: `1.5`
- `preferredRR`: `1.8`
- `maxRR`: `5`

### Adaptive / correlation
- score bounds: `66–84`
- correlation soft: `0.86`
- correlation hard: `0.95`
- `autoPromote`: `false`
- learning is bounded and cannot override hard safety gates

### Execution / protection invariants
- structural SL geometry remains mandatory
- anti-sweep protection remains deterministic
- fail-closed Claude + Codex AI gate remains mandatory for new exposure
- post-AI quote revalidation remains mandatory
- Smart CUT remains multi-signal, minimum-age gated and reduce-only
- daily target remains OFF
- 3 consecutive losses trigger a 30-minute new-entry pause while position management continues

## Important design note
`100% portfolio margin` means the allocator may distribute the account's usable margin across multiple qualified positions. It does not mean every individual trade is all-in. Runtime margin headroom, total open risk, correlation, exchange minimums and candidate quality remain authoritative.

## Learning state
Do not reset `TRADING_STATE`, Bybit learning KV, outcome history, provider accuracy, adaptive symbol/regime memory or post-mortem history when deploying or upgrading this version.
