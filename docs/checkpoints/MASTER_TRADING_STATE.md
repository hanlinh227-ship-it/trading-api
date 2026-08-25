# MASTER TRADING STATE

Updated: 2026-08-25 UTC+7
Purpose: single canonical state for the Trading project.

## CURRENT PRODUCTION AUTHORITY — BYBIT AUTO 1.4.0

GitHub `main` + deployed Cloudflare runtime are authoritative.

Current production contract:
- production hub = `BYBIT_AUTO_TRADE_ONLY`;
- production version = `BYBIT-AUTO-1.4.0`;
- exchange execution authority = Bybit Auto LIVE;
- Signal V11 runtime/scheduler on this Worker = OFF;
- private authenticated transport = `VPS_BYBIT_PRIVATE_PROXY`;
- existing `TRADING_STATE` KV is preserved; never reset it;
- daily profit target = OFF;
- trading policy = continuous, constrained by safety/risk/capital/adaptive-edge gates.

## VERSIONING
Every production change increments `BYBIT_AUTO_VERSION`. Source is LIVE only after `/bybit/health` reports the deployed commit revision and readiness is valid.

## VERSION HISTORY
- `BYBIT-AUTO-1.4.0` — Adaptive Edge Engine: deterministic regime classification, bounded per-symbol/per-strategy/per-regime learning, net expectancy after costs, adaptive score threshold 68–85, live rolling correlation/beta-cluster portfolio gate, bounded exit-profile recommendation, no auto-promote.
- `BYBIT-AUTO-1.3.1` — portfolio initial-margin headroom protection for legacy oversized positions.
- `BYBIT-AUTO-1.3.0` — Continuous Capital Allocation with reserve/slot/risk ceilings.
- `BYBIT-AUTO-1.2.8` — Smart CUT multi-signal thesis-invalidation engine.

## LIVE PIPELINE
`Scheduler -> liquid universe -> deterministic setup -> Regime Engine -> Per-Coin Edge Memory -> Adaptive Threshold -> correlation/beta portfolio gate -> fresh/re-anchor -> Continuous Capital Allocation -> risk + portfolio-margin preflight -> Claude/Codex/DeepSeek final review -> post-AI fresh quote -> LIVE order -> verified SL/TP -> HOLD/BE/LOCK/TRAIL/SMART_CUT -> Telegram -> bounded learning`

## ADAPTIVE EDGE ENGINE — CANONICAL
Regimes: `TREND_UP`, `TREND_DOWN`, `RANGE`, `BREAKOUT_EXPANSION`, `HIGH_VOL_CHAOS`, `LOW_VOL_COMPRESSION`.

Rules:
- regime is deterministic; AI does not classify or override it;
- each qualified setup is tagged with regime and beta cluster;
- learning memory aggregates by symbol and by symbol+strategy+regime;
- learning records win rate, avg R, net R after known costs, MFE, MAE, hold time and fees when available;
- <10 closed samples has zero adaptive influence; confidence rises gradually and only reaches full weight at large sample;
- adaptive score threshold is hard-bounded to 68–85;
- bad historical expectancy may raise the threshold, but learning can never weaken freshness, SL, RR, capital or risk gates;
- rolling 1m correlation is checked against same-direction live exposure; soft threshold 0.80, hard rejection 0.90; beta-cluster stacking is rejected when correlation is high or unavailable but cluster exposure is clearly duplicated;
- candidate ranking uses quality margin above threshold plus bounded historical net expectancy and RR;
- exit learning is bounded to `DEFENSIVE`, `BALANCED`, `TREND_RUNNER`; it may not synthesize arbitrary SL/TP;
- auto-promote is permanently OFF.

## CONTINUOUS CAPITAL ALLOCATION
- risk is a ceiling, never a quantity target;
- base planned risk/reward near $50 equity = $1.50 / $3.00;
- max risk/trade = 4% equity;
- max total managed open risk = 10% equity;
- max initial-margin budget/new position = 20% equity before fee buffer;
- minimum reserve target = 30% equity;
- fee/cost buffer = 5%; portfolio initial-margin target ceiling = 65%;
- max leverage = 5x for margin efficiency only;
- max positions = 3; max same direction = 2;
- `PORTFOLIO_MARGIN_HEADROOM` blocks only new entries; management of legacy/open positions continues.

## ENTRY / FREQUENCY
- scan every 60s;
- global new-entry spacing = 300s;
- base score 70, adaptive effective threshold 68–85;
- configured spread ceiling 9 bps, stricter symbol rule wins;
- chase ceiling 0.60 ATR, stricter symbol rule wins;
- bounded one-shot re-anchor;
- post-AI fresh quote mandatory;
- no daily profit target or trade quota.

## POSITION MANAGEMENT
Normal path: `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`.
Smart CUT remains exceptional multi-signal thesis invalidation and always `reduceOnly`.

## LOSS CONTROL
3 consecutive realized losses -> 30-minute new-entry pause. Position management stays active.

## TELEGRAM / LEARNING
Dashboard exposes version/LIVE, Balance, Equity, Available, Initial Margin, Adaptive Edge state, score/correlation bounds, capital limits, Smart CUT, positions/orders, PnL, AI and learning sample size. Learning is bounded and cannot self-promote.

## PERMANENT INVARIANTS
Never reset state, fabricate live data, bypass freshness/SL/RR/risk/capital/protection gates, exceed 5x leverage, size up to force a dollar-risk target, resurrect the old 80% single-position margin model, let adaptive learning auto-promote, let learning lower safeguards outside hard bounds, or let retired V11 execution compete with Bybit Auto.

## DEPLOYMENT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`. `npm run check`, Cloudflare deploy and `/bybit/health` revision verification must all pass before declaring LIVE.
