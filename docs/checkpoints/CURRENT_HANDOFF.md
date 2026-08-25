# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-25 UTC+7

## ACTIVE PRODUCTION AUTHORITY
Production Worker: **Bybit Auto Trade Hub only**.
Canonical source version: `BYBIT-AUTO-1.4.0`.
Execution: Bybit LIVE. Signal V11 execution/scheduler: disabled. Existing `TRADING_STATE` KV: preserved. Daily target: OFF. AI core: Claude + Codex + DeepSeek final-entry review only.

## 1.4.0 ADAPTIVE EDGE ENGINE
New selection order:
`liquid universe -> setup -> regime -> per-coin/per-strategy/per-regime edge memory -> adaptive threshold -> correlation/beta gate -> fresh/re-anchor -> sizing/risk -> 3AI -> post-AI quote -> execution`.

Canonical adaptive defaults:
- regimes: TREND_UP / TREND_DOWN / RANGE / BREAKOUT_EXPANSION / HIGH_VOL_CHAOS / LOW_VOL_COMPRESSION;
- base score 70; adaptive hard bounds 68–85;
- learning influence = 0 below 10 closed samples; confidence increases gradually and is bounded;
- correlation soft 0.80, hard 0.90 for same-direction live exposure;
- beta-cluster stacking protected;
- per-symbol and symbol+strategy+regime expectancy memory;
- net expectancy after known fees/costs preferred over gross R;
- exit profile is bounded to DEFENSIVE / BALANCED / TREND_RUNNER;
- auto-promote = OFF permanently.

Learning never bypasses deterministic freshness, spread/chase, structural SL/TP, RR, risk, margin or protection gates.

## CONTINUOUS CAPITAL ALLOCATION
Sizing order:
`equity -> risk ceiling -> slot margin ceiling -> fee buffer -> leverage for margin efficiency -> final qty -> RR/risk validation`.

Defaults remain:
- planned risk/reward near $50 equity $1.50 / $3.00;
- max risk/trade 4%; total managed open risk 10%;
- max initial-margin budget/new position 20% before buffer;
- reserve target 30%; fee buffer 5%; portfolio IM target 65%;
- leverage cap 5x; max positions 3; max same direction 2;
- legacy oversized positions remain managed and may block new slots through `PORTFOLIO_MARGIN_HEADROOM`.

## ENTRY POLICY
Scan 60s; global new-entry spacing 300s; base score 70 with adaptive 68–85 bound; spread ceiling 9 bps unless stricter profile; chase ceiling 0.60 ATR unless stricter profile; one-shot re-anchor; mandatory post-AI quote; no daily target/trade quota.

## POSITION MANAGEMENT
Normal: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`.
Smart CUT ON only for canonical multi-signal thesis invalidation; severe emergency invalidation only; always `reduceOnly`.

## TELEGRAM
Dashboard must expose `BYBIT-AUTO-1.4.0 • LIVE` when deployed plus Adaptive Edge ON, adaptive score bounds, correlation bounds, Balance/Equity/Available/Initial Margin, capital limits, Smart CUT, positions/orders, PnL, AI and learning sample size.

## DEPLOYMENT CONTRACT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
Do not claim LIVE until `npm run check`, Cloudflare deploy and `/bybit/health` revision verification all pass.
