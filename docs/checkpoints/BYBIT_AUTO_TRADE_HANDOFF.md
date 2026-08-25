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
- Version: `BYBIT-AUTO-1.6.0`.
- Exchange: Bybit LIVE.
- Private authenticated transport: `VPS_BYBIT_PRIVATE_PROXY`.
- Signal V11 execution/scheduler: OFF.
- Daily target: OFF; continuous scanning/trading with safety/risk/capital/adaptive gates.
- AI: Claude + Codex + DeepSeek are final-entry reviewers only.
- Telegram surface: Unified Trading Hub with BYBIT and MEME branches. MEME remains DESIGN_ONLY with no wallet/signing/execution authority.

## LIVE DECISION PIPELINE
`Scheduler -> liquid universe -> deterministic setup -> Regime Engine -> Per-Coin Edge Memory -> Adaptive Threshold -> correlation/beta portfolio gate -> fresh/re-anchor -> Scaled Trade Band Allocator -> risk + portfolio-margin preflight -> Claude/Codex/DeepSeek final review -> post-AI fresh quote -> LIVE order -> verified SL/TP -> HOLD/BE/LOCK/TRAIL/SMART_CUT -> Telegram -> bounded learning`

## SCALED TRADE BAND — 1.6.0
- Base equity: $50.
- Scale step: every +$10 confirmed equity.
- At $50: TP minimum $5, TP maximum $10, max SL/risk ceiling $5.
- At $60: TP $6-$11, max SL $6.
- At $70: TP $7-$12, max SL $7.
- Continue +$1 to TP minimum, TP maximum and SL ceiling for every +$10 equity step.
- Below the base balance, the same ladder scales down symmetrically, subject to absolute floors.
- The SL ladder is a maximum loss ceiling, not a requirement to force a wider stop. Structural SL remains authoritative and actual risk may be smaller because of structure, capital, quantity-step or margin constraints.
- A candidate whose structural reward cannot reach the current TP minimum is rejected with `STRUCTURE_REWARD_BELOW_LADDER_MIN`; TP is never stretched beyond valid structure merely to hit the dollar target.
- Single-trade hard risk cap: 10% equity, matching the $5-at-$50 ceiling.
- Total managed open-risk cap: 20% equity, so multiple positions cannot all consume full individual SL ceilings simultaneously.

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

## CAPITAL / MARGIN
- Max leverage 10x for margin efficiency only; leverage does not override risk caps.
- Max initial-margin budget/new position 22% before fee buffer.
- Reserve target 30%; fee/cost buffer 5%; portfolio initial-margin ceiling 65%.
- Max positions 3; max same direction 2.
- Legacy positions remain managed; `PORTFOLIO_MARGIN_HEADROOM` may block only new entries.

## ENTRY / FREQUENCY
- Scan every 60 seconds.
- Global new-entry spacing 300 seconds.
- Spread ceiling 9 bps unless stricter symbol profile.
- Chase ceiling 0.60 ATR unless stricter profile.
- One-shot bounded re-anchor + mandatory post-AI fresh quote.
- No forced trade quota. `NO_ENTRY` is correct when edge or current TP minimum is unsupported.

## POSITION MANAGEMENT
Normal path: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`.
Smart CUT is ON as exceptional multi-signal thesis invalidation and always closes `reduceOnly`.
3 consecutive realized losses trigger a 30-minute pause on new entries while management remains active.

## TELEGRAM
Unified root -> BYBIT branch -> dashboard/positions/3AI/risk/learning/runtime. BYBIT dashboard must expose current version + LIVE, Balance, Equity, Available, Initial Margin, Adaptive Edge, score/correlation bounds, capital limits, Smart CUT, positions/orders, PnL, AI and learning sample size.
Entry alert exposes compact SL price + USD risk and TP price + USD reward.

## DO NOT REGRESS
Do not resurrect retired V11 execution, old 80% single-position margin model, daily profit targets, arbitrary AI execution authority, unbounded self-learning or stale-price entry. Do not convert the scaled SL ceiling into a forced wider technical stop.

## NEXT-CHAT SHORT COMMAND
If the user says only **"chỉnh sửa auto trade Bybit"**, fresh-read this checkpoint and current GitHub `main`, recover the latest production state, inspect actual source before editing, preserve live state/open positions, version every update, and verify deployment before reporting completion.
