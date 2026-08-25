# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-25 UTC+7

## ACTIVE PRODUCTION AUTHORITY
Production Worker execution authority: **Bybit Auto only**.
Canonical Bybit source version: `BYBIT-AUTO-1.4.1`.
Execution: Bybit LIVE. Signal V11 execution/scheduler: disabled. Existing `TRADING_STATE` KV: preserved. Daily target: OFF. AI core: Claude + Codex + DeepSeek final-entry review only.

Telegram is now a **Unified Trading Hub** with two top-level branches:
- `BYBIT` — LIVE execution branch.
- `MEME` — `MEME-AUTO-0.1.0-DESIGN`, DESIGN_ONLY, NO WALLET, NO SIGNING, NO EXECUTION.

## BYBIT 1.4.x ADAPTIVE EDGE ENGINE
Selection order:
`liquid universe -> setup -> regime -> per-coin/per-strategy/per-regime edge memory -> adaptive threshold -> correlation/beta gate -> fresh/re-anchor -> sizing/risk -> 3AI -> post-AI quote -> execution`.

Canonical adaptive defaults:
- regimes: TREND_UP / TREND_DOWN / RANGE / BREAKOUT_EXPANSION / HIGH_VOL_CHAOS / LOW_VOL_COMPRESSION;
- base score 70; adaptive hard bounds 68–85;
- learning influence = 0 below 10 closed samples; confidence increases gradually and is bounded;
- correlation soft 0.80, hard 0.90 for same-direction live exposure;
- beta-cluster stacking protected;
- per-symbol and symbol+strategy+regime expectancy memory;
- net expectancy after known fees/costs preferred over gross R;
- exit profile bounded to DEFENSIVE / BALANCED / TREND_RUNNER;
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

## BYBIT ENTRY / MANAGEMENT
Scan 60s; global new-entry spacing 300s; base score 70 with adaptive 68–85 bound; spread ceiling 9 bps unless stricter profile; chase ceiling 0.60 ATR unless stricter profile; one-shot re-anchor; mandatory post-AI quote; no daily target/trade quota.

Normal position management: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`.
Smart CUT ON only for canonical multi-signal thesis invalidation; severe emergency invalidation only; always `reduceOnly`.

## MEME DESIGN BRANCH
Canonical checkpoint: `docs/checkpoints/MEME_AUTO_DESIGN_CHECKPOINT.md`.
Current theoretical design is for Solana meme spot trading starting from about $30: $5 reserve, 1 position, $4–$7 position range, no leverage/DCA/martingale, hard token safety before score, wallet-level holder/bundler/sniper/insider/dev intelligence, confirmed momentum regimes/setups, future Jupiter execution, Smart CUT + partial TP + principal recovery + runner, bounded learning with auto-promote OFF.

This branch MUST remain read-only/design-only until a separate wallet/data/execution integration phase is explicitly designed, validated and enabled.

## TELEGRAM
Root menu must expose exactly the two conceptual systems `BYBIT` and `MEME`. BYBIT submenu retains dashboard/positions/AI/risk/stats/runtime. MEME submenu exposes design/safety/entry-exit/capital/learning and clearly states NO WALLET / NO SIGNING / NO EXECUTION.

## DEPLOYMENT CONTRACT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
Do not claim a production update LIVE until `npm run check`, Cloudflare deploy and `/bybit/health` revision verification all pass.
