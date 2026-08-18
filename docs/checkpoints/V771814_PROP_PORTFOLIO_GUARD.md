# V77.18.14 — PROP PORTFOLIO GUARD

Updated: 2026-08-18 UTC+7

## PURPOSE
Increase useful Hyro entry capacity without turning 3 simultaneous positions into one oversized correlated bet.

## CANONICAL POLICY
- Maximum 3 active symbols (positions + pending orders).
- Maximum 2 positions/orders in the same direction.
- Only one same-direction position/order from the same crypto cluster.
- Minimum 3 minutes between new PROP entries.
- Candidate ranking prefers A over B, then microstructure, RR, liquidity and portfolio diversity.
- Third slot is allowed only when portfolio guard passes; there is no requirement to fill all 3 slots.

## CLUSTERS
Stable groups include BTC, ETH beta, L1, DeFi, Meme, Payments, Exchange, AI and RWA. Unknown symbols receive a deterministic symbol-specific OTHER cluster.

## EXECUTION
`hyro-runtime.js` evaluates portfolio guard before calling execution. `hyro-execution.js` remains the final hard gate and now permits up to 3 active symbols. Existing combined open-risk cap, single-risk cap, daily hard stop, funding, RR, telemetry and native SL/TP gates remain authoritative.

## STATE
New additive key: `v771814:hyro:portfolio` for last-entry spacing/state. Never reset it as part of deploy cleanup. Existing Signal LIVE ORDERS, PROP execution/idempotency/notification/position manager and PERSONAL state are untouched.

## DO NOT REGRESS
Do not replace portfolio guard with a simple three-slot counter. Do not allow three same-direction high-beta coins simply because slot capacity exists. Do not increase slot count on account scale-up; scale risk with equity instead.
