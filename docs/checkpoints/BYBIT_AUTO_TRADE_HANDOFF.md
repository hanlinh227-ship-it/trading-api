# BYBIT AUTO TRADE — CANONICAL HANDOFF

Updated: 2026-08-25 UTC+7

## PURPOSE
Fast handoff for any new chat receiving **"chỉnh sửa auto trade Bybit"**, **"tiếp tục bot Bybit"**, or equivalent.

## REQUIRED STARTUP IN A NEW CHAT
1. Fresh-read GitHub `main`; never infer current production state from an old chat.
2. Read, in order:
   - `docs/checkpoints/BYBIT_AUTO_TRADE_HANDOFF.md`
   - `docs/checkpoints/MASTER_TRADING_STATE.md`
   - `docs/checkpoints/CURRENT_HANDOFF.md`
   - current Bybit Auto source/config/validator/workflow files relevant to the requested change.
3. GitHub `main` + current source + deployed runtime verification are authoritative.
4. Preserve `TRADING_STATE`, open plans/positions and learning history unless an explicit migration is designed and validated. Never casually reset KV/state.
5. Every Bybit production change increments `BYBIT_AUTO_VERSION`.
6. Never claim an update is LIVE until source validation, Cloudflare production deploy and `/bybit/health` runtime-revision verification pass.

## CURRENT CANONICAL PRODUCTION BASELINE
- Bybit production execution authority: **Bybit Auto only**.
- Version: `BYBIT-AUTO-1.4.1`.
- Exchange: Bybit LIVE.
- Private authenticated transport: `VPS_BYBIT_PRIVATE_PROXY`.
- Signal V11 execution/scheduler: OFF.
- Daily target: OFF; continuous scanning/trading with safety/risk/capital/adaptive gates.
- AI: Claude + Codex + DeepSeek are final-entry reviewers only.
- Telegram surface is now a Unified Trading Hub with top-level BYBIT and MEME buttons. MEME is a separate DESIGN_ONLY branch and has no wallet/signing/execution authority.

## LIVE DECISION PIPELINE
`Scheduler -> liquid universe -> deterministic setup -> Regime Engine -> Per-Coin Edge Memory -> Adaptive Threshold -> correlation/beta portfolio gate -> fresh/re-anchor -> Continuous Capital Allocation -> risk + portfolio-margin preflight -> Claude/Codex/DeepSeek final review -> post-AI fresh quote -> LIVE order -> verified SL/TP -> HOLD/BE/LOCK/TRAIL/SMART_CUT -> Telegram -> bounded learning`

## ADAPTIVE EDGE
- Regimes: TREND_UP / TREND_DOWN / RANGE / BREAKOUT_EXPANSION / HIGH_VOL_CHAOS / LOW_VOL_COMPRESSION.
- Base score 70; adaptive threshold 68–85 hard bounds.
- Per-symbol and symbol+strategy+regime memory.
- <10 closed samples: zero adaptive influence.
- Prefer net expectancy after known costs.
- Correlation soft 0.80; hard 0.90 for same-direction exposure.
- Exit profile bounded to DEFENSIVE / BALANCED / TREND_RUNNER.
- Auto-promote permanently OFF.
- Learning cannot weaken deterministic freshness, spread/chase, structural SL/TP, RR, risk, capital or protection gates.

## CAPITAL / RISK
- Risk is a ceiling, never a target that must be filled.
- Near $50 equity planned baseline ≈ $1.50 risk / $3 reward; actual size may be smaller.
- Max risk/trade 4% equity; total managed open risk 10%.
- Max initial-margin budget/new position 20% before fee buffer.
- Reserve target 30%; fee/cost buffer 5%; portfolio initial-margin target 65%.
- Max leverage 5x for margin efficiency only.
- Max positions 3; max same direction 2.
- Legacy oversized positions remain managed; `PORTFOLIO_MARGIN_HEADROOM` may block only new entries.

## ENTRY / FREQUENCY
- Scan every 60 seconds.
- Global new-entry spacing 300 seconds.
- Spread ceiling 9 bps unless stricter symbol profile.
- Chase ceiling 0.60 ATR unless stricter profile.
- One-shot bounded re-anchor + mandatory post-AI fresh quote.
- No forced trade quota. `NO_ENTRY` is correct when edge is insufficient.

## POSITION MANAGEMENT
Normal path: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`.
Smart CUT is ON as exceptional multi-signal thesis invalidation and always closes `reduceOnly`.
3 consecutive realized losses trigger a 30-minute pause on new entries while management remains active.

## TELEGRAM
Unified root -> BYBIT branch -> dashboard/positions/3AI/risk/learning/runtime. BYBIT dashboard must expose current version + LIVE, Balance, Equity, Available, Initial Margin, Adaptive Edge, score/correlation bounds, capital limits, Smart CUT, positions/orders, PnL, AI and learning sample size.

## DO NOT REGRESS
Do not resurrect retired V11 execution, old 80% single-position margin model, fixed dollar-risk forcing, daily profit targets, arbitrary AI execution authority, unbounded self-learning or stale-price entry.

## NEXT-CHAT SHORT COMMAND
If the user says only **"chỉnh sửa auto trade Bybit"**, fresh-read this checkpoint and current GitHub `main`, recover the latest production state, inspect actual source before editing, preserve live state/open positions, version every update, and verify deployment before reporting completion.
