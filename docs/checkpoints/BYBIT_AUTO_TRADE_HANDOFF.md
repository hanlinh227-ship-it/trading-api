# BYBIT AUTO TRADE — MIGRATION NOTICE

Updated: 2026-09-04 UTC+7

## STATUS
The legacy multi-coin Bybit Auto strategy is RETIRED as a trading authority.

## NEW DIRECTION
A single BTCUSDT Linear Perpetual bot replaces legacy strategy logic. Existing Bybit API/VPS transport, credentials, health plumbing and reusable execution infrastructure are preserved. Legacy strategy/risk/scan components must not be treated as production authority after this migration begins.

## DESIGN PRINCIPLES
- BTCUSDT only.
- Strategy authority comes from market structure, liquidity, order flow, volatility/regime, derivatives positioning and execution microstructure; indicators are supporting context only.
- No martingale and no adding to losing exposure merely because price moved against the position.
- Unlimited strategic trade count; new entries are constrained by portfolio active-risk, margin, drawdown and execution-quality budgets rather than a hard daily trade quota.
- Winner pyramiding is allowed only after prior risk is reduced/protected and a fresh independent setup is confirmed.
- Continuous equity compounding with aggressive scale-down during drawdown.
- Exchange/API hard limits remain authoritative.

## MIGRATION SAFETY
Do not delete secrets, VPS transport code, authenticated Bybit client code, Telegram plumbing, runtime health endpoints, deployment workflows, or persistent account state merely because legacy strategy files are retired.

## TARGET RUNTIME
`BYBIT-BTC-HYPERSCALE-2.0` (design/migration in progress until runtime validation passes).
