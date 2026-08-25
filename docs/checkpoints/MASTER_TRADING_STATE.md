# MASTER TRADING STATE

Updated: 2026-08-25 UTC+7
Purpose: single canonical state for the Trading project.

## CURRENT PRODUCTION AUTHORITY — BYBIT AUTO 1.3.1

GitHub `main` + deployed Cloudflare runtime are authoritative.

Current production contract:
- production hub = `BYBIT_AUTO_TRADE_ONLY`;
- production version = `BYBIT-AUTO-1.3.1`;
- exchange execution authority = Bybit Auto LIVE;
- Signal V11 runtime/scheduler on this Worker = OFF;
- private authenticated transport = `VPS_BYBIT_PRIVATE_PROXY`;
- existing `TRADING_STATE` KV is preserved; never reset it;
- daily profit target = OFF;
- trading policy = continuous, constrained by safety/risk/capital gates.

## VERSIONING
Every production change increments `BYBIT_AUTO_VERSION`. Source is LIVE only after `/bybit/health` reports the deployed commit revision and readiness is valid.

## VERSION HISTORY
- `BYBIT-AUTO-1.3.1` — adds portfolio initial-margin headroom protection so legacy oversized positions remain managed but cannot be stacked with a new slot until capital headroom recovers.
- `BYBIT-AUTO-1.3.0` — Continuous Capital Allocation: slot-based sizing, 30% reserve target, ≤20% equity initial-margin budget per new position before fee buffer, 4% single-risk cap, 10% total open-risk cap, base $1.50/$3 planned risk/reward near $50 equity, max 5x leverage for margin efficiency, Smart CUT retained, Telegram capital telemetry.
- `BYBIT-AUTO-1.2.8` — Smart CUT multi-signal thesis-invalidation engine.

## LIVE PIPELINE
`Scheduler -> liquid-universe scan -> deterministic setup -> fresh/re-anchor -> Continuous Capital Allocation -> risk + portfolio-margin preflight -> Claude/Codex/DeepSeek review -> post-AI fresh quote -> LIVE order -> verified SL/TP -> HOLD/BE/LOCK/TRAIL/SMART_CUT -> Telegram -> learning`

## CONTINUOUS CAPITAL ALLOCATION
- risk is a ceiling, never a quantity target;
- base planned risk near $50 equity = $1.50; base planned reward = $3.00;
- max risk/trade = 4% equity;
- max total managed open risk = 10% equity;
- max initial-margin budget/new position = 20% equity before fee buffer;
- minimum reserve target = 30% equity;
- per-slot fee/cost buffer = 5%;
- portfolio initial-margin target ceiling = 65% equity;
- max leverage = 5x, for margin efficiency only;
- max positions = 3; max same direction = 2;
- if capital is binding, actual risk is reduced rather than position size being forced upward;
- `PORTFOLIO_MARGIN_HEADROOM` blocks only new entries when existing/legacy margin plus a new reserved slot would exceed the portfolio ceiling; open-position management remains active.

## ENTRY / FREQUENCY
- scan every 60s;
- global new-entry spacing = 300s;
- score floor 70;
- configured spread ceiling 9 bps, stricter symbol rule wins;
- chase ceiling 0.60 ATR, stricter symbol rule wins;
- bounded one-shot re-anchor;
- post-AI fresh quote mandatory;
- no daily profit target or trade quota.

## POSITION MANAGEMENT
Normal path: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`.
Smart CUT is an exceptional multi-signal thesis-invalidation exit. It never fires merely because a trade is slow, M1 is noisy, a later scan changes view, or profit gives back. CUT remains `reduceOnly`.

## LOSS CONTROL
3 consecutive realized losses -> 30-minute new-entry pause. Position management stays active.

## TELEGRAM CAPITAL TELEMETRY
Expose Balance, Equity, Available, Total Initial Margin / IM rate, capital reserve/slot limits, Smart CUT, positions/orders, realized PnL, AI state and loss streak.

## PERMANENT INVARIANTS
Never reset state, fabricate live data, bypass freshness/SL/RR/risk/capital/protection gates, exceed 5x leverage, size up to force a dollar-risk target, resurrect the old 80% single-position margin model, or let retired V11 execution compete with Bybit Auto.

## DEPLOYMENT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`. `npm run check` must pass; Cloudflare deploy and `/bybit/health` revision verification must pass before declaring LIVE.
