# BYBIT BTC-ONLY MIGRATION — 2026-09-04

## USER AUTHORITY
Replace all legacy Bybit trading-bot strategy/runtime logic with one BTCUSDT Linear Perpetual bot while preserving live Bybit API connectivity, signed client, credentials routing, VPS private transport and live account access.

## TARGET
- Symbol: BTCUSDT only.
- Exchange: Bybit V5 Linear Perpetual.
- Live API transport/credentials: PRESERVE.
- Legacy multi-coin strategy logic: RETIRE.
- Legacy signal/runtime execution authority: RETIRE.
- New engine principle: market structure, liquidity, order flow, volatility/regime, price action and execution quality. Indicators may be diagnostic/context only, never sole trade authority.
- No strategic daily trade quota. Entry count is bounded by risk/margin/exchange limits, not an arbitrary trade counter.
- No martingale, no averaging-down loser rescue.
- Winner pyramiding permitted only after prior risk is reduced/protected and portfolio active-risk remains inside budget.
- Continuous equity compounding with faster scale-down under drawdown.

## SAFETY INVARIANTS
- Keep Bybit V5 API client and signed/private transport unchanged unless an incompatibility is proven.
- Keep live credentials/env variable names unchanged.
- Every live order must be reconciled and protection geometry validated.
- API ACK alone is not proof of a protected live position.
- No guarantee of positive PnL; objective is bounded downside with convex scaling when edge is confirmed.

## MIGRATION METHOD
1. Inventory current Bybit runtime files and routes.
2. Preserve API/transport modules.
3. Replace scanner/strategy/risk/manager/runtime contracts with BTC-only counterparts.
4. Disable/remove legacy multi-symbol execution paths and scheduler references.
5. Add BTC-only health/runtime identity.
6. Validate syntax and route reachability before any LIVE claim.

This checkpoint is the migration authority for the BTC-only rewrite.
