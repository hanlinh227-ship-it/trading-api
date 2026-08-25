# BYBIT AUTO TRADE — CANONICAL HANDOFF

Updated: 2026-08-25 UTC+7

## PURPOSE
This file is the fast handoff checkpoint for any new chat that receives a request such as: **"chỉnh sửa auto trade Bybit"**, **"tiếp tục bot Bybit"**, or equivalent.

## REQUIRED STARTUP IN A NEW CHAT
Before changing anything:
1. Fresh-read GitHub `main`; never infer current production state from an old chat.
2. Read, in order:
   - `docs/checkpoints/BYBIT_AUTO_TRADE_HANDOFF.md`
   - `docs/checkpoints/MASTER_TRADING_STATE.md`
   - `docs/checkpoints/CURRENT_HANDOFF.md`
   - current Bybit Auto source/config/validator/workflow files relevant to the requested change.
3. Treat GitHub `main` + current source + deployed runtime verification as the source of truth.
4. Preserve `TRADING_STATE`, open plans/positions and learning history unless an explicit migration is designed and validated. Never casually reset KV/state.
5. Every production change must increment `BYBIT_AUTO_VERSION`.
6. Never claim an update is LIVE until source validation, Cloudflare production deploy and `/bybit/health` runtime-revision verification pass.

## CURRENT CANONICAL PRODUCTION BASELINE
- Production authority: **Bybit Auto Trade Hub only**.
- Version at checkpoint creation: `BYBIT-AUTO-1.4.0`.
- Exchange: Bybit LIVE.
- Private authenticated transport: `VPS_BYBIT_PRIVATE_PROXY`.
- Signal V11 execution/scheduler on this production Worker: OFF.
- Daily profit target: OFF; bot scans/trades continuously but never forces an entry or trade quota.
- AI: Claude + Codex + DeepSeek are final-entry reviewers only; deterministic market/risk gates remain authoritative.

## LIVE DECISION PIPELINE
`Scheduler -> liquid universe -> deterministic setup -> Regime Engine -> Per-Coin Edge Memory -> Adaptive Threshold -> correlation/beta portfolio gate -> fresh/re-anchor -> Continuous Capital Allocation -> risk + portfolio-margin preflight -> Claude/Codex/DeepSeek final review -> post-AI fresh quote -> LIVE order -> verified SL/TP -> HOLD/BE/LOCK/TRAIL/SMART_CUT -> Telegram -> bounded learning`

## ADAPTIVE EDGE
- Regimes: `TREND_UP`, `TREND_DOWN`, `RANGE`, `BREAKOUT_EXPANSION`, `HIGH_VOL_CHAOS`, `LOW_VOL_COMPRESSION`.
- Base score 70; effective adaptive threshold hard-bounded to 68–85.
- Per-symbol and symbol+strategy+regime memory.
- Fewer than 10 closed samples: zero adaptive influence; confidence increases gradually with sample size.
- Prefer net expectancy after known costs over gross R.
- Correlation soft threshold 0.80; hard rejection 0.90 for same-direction exposure; beta-cluster stacking protected.
- Exit-learning recommendations are bounded to `DEFENSIVE`, `BALANCED`, `TREND_RUNNER` and may not synthesize arbitrary SL/TP.
- `autoPromote` remains permanently OFF.
- Learning must never weaken deterministic freshness, spread/chase, structural SL/TP, RR, risk, capital or protection gates.

## CAPITAL / RISK
- Risk is a ceiling, never a target that must be filled.
- Near $50 equity, planned baseline risk/reward is about $1.50 / $3.00, but actual size may be smaller.
- Max risk/trade: 4% equity.
- Max total managed open risk: 10% equity.
- Max initial-margin budget/new position: 20% equity before fee buffer.
- Reserve target: 30% equity.
- Fee/cost buffer: 5%.
- Portfolio initial-margin target ceiling: 65%.
- Max leverage: 5x, used for margin efficiency only.
- Max positions: 3; max same direction: 2.
- Legacy oversized positions remain managed; `PORTFOLIO_MARGIN_HEADROOM` may block only new entries until capacity returns.

## ENTRY / FREQUENCY
- Scan every 60 seconds.
- Global new-entry spacing: 300 seconds.
- Spread ceiling: 9 bps unless a stricter symbol profile applies.
- Chase ceiling: 0.60 ATR unless a stricter profile applies.
- One-shot bounded re-anchor and mandatory post-AI fresh quote.
- Continuous trading means continuous scanning/capital reuse, not forced entries. `NO_ENTRY` is correct when edge is insufficient.

## POSITION MANAGEMENT
Normal path: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`.
Smart CUT is ON as an exceptional multi-signal thesis-invalidation engine; it is not a simple loss/time cut and must always close with `reduceOnly`.
3 consecutive realized losses trigger a 30-minute pause on new entries while position management remains active.

## TELEGRAM
Production dashboard should expose version + LIVE status, Balance, Equity, Available, Initial Margin, Adaptive Edge status, score/correlation bounds, capital limits, Smart CUT, positions/orders, PnL, AI status and learning sample size.

## DO NOT REGRESS
Do not resurrect retired V11 execution, the old 80% single-position margin model, fixed dollar-risk forcing, daily profit targets, arbitrary AI execution authority, unbounded self-learning, stale-price entry, or any architecture superseded by current `main`.

## NEXT-CHAT SHORT COMMAND
If the user starts a new chat and says only **"chỉnh sửa auto trade Bybit"**, interpret it as: fresh-read this checkpoint and current GitHub `main`, recover the latest Bybit Auto production state, inspect the actual source before editing, preserve live state/open positions, version every update, and verify deployment before reporting completion.
