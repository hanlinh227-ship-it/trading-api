# FOREX STATE

Updated: 2026-08-17 (UTC+7)

## Objective
Build a repeatable Forex method for all 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD. Research benchmark forces BUY or SELL on every valid pair at each blind cutoff so the method itself is measured without Top-3 selection bias. Forced-all-pair testing is research, not an instruction to trade every pair live.

## Research rules
- No Top-3 / NO-TRADE in forced benchmark.
- Freeze decision/entry/SL/TP before future candles.
- Score direction separately from TP/SL: chosen horizon plus 3h/6h/12h/24h where available.
- Separate `bias wrong` from `bias right but barrier/path failed`.
- Do not optimize win rate using tiny TP; judge WR + RR + expectancy + direction together.
- A revealed blind block becomes development data forever.
- New versions must beat the frozen baseline on the same untouched block.

## Universe
EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD,
EURJPY, EURGBP, EURCHF, EURAUD, EURNZD, EURCAD, GBPJPY,
GBPCHF, GBPAUD, GBPNZD, GBPCAD, AUDJPY, AUDNZD, AUDCAD,
AUDCHF, NZDJPY, NZDCAD, NZDCHF, CADJPY, CADCHF, CHFJPY.

## Minimal technical stack
Keep indicators limited to distinct jobs:
- EMA20/50: trend/value/slope;
- RSI14: momentum/exhaustion;
- ATR14: volatility and structural-SL normalization;
- ADX14: trend-vs-chop regime, never standalone direction.

Non-indicator state now matters more than adding indicators:
- 3h/6h/12h/24h/72h cross-currency factor strength/coherence;
- cross-sectional dispersion/rank separation across 8 currencies;
- 8h session position, breakout and sweep;
- pair archetype;
- horizon-matched structural SL/TP/expiry.

Historical research fetches one M15 Twelve Data series per pair and derives H1/H4/features locally.

## Currency-specific live driver profiles
Historical macro is not reconstructed with hindsight unless a point-in-time dataset is connected. Live analysis should overlay:
- USD: Fed/rate path, PCE/CPI, labour/NFP, US yields.
- EUR: ECB, HICP/core, wages/services, energy/growth.
- GBP: BoE, CPI/services, wages, UK activity.
- JPY: BoJ, wages/CPI, JGB yields, carry, MOF intervention.
- CHF: SNB, inflation, risk-off, FX intervention.
- CAD: BoC, CPI/jobs, oil, US trade/growth.
- AUD: RBA, trimmed inflation, labour/capacity, China/commodities/risk.
- NZD: RBNZ OCR, CPI, spare capacity/labour, dairy/global rates.

## Rejected / diagnostic lineage
### F1
Naive strongest-score Top3 rejected.
### F2
Selective 3 TP / 1 SL sample too small to validate.
### F3
Failed to confirm F2; forced RR1.8 = 44 TP / 84 SL, -0.037R.
### F4
Jul17/20/21/22/24 forced 140: MARKET -0.081R, LIMIT -0.018R, direction12/24 53.57%.
### F5 — rejected
Jul27/28 forced 56: MARKET 12 TP /43 SL, -0.383R; direction12/24 32.14%; 36/43 SL also wrong at 24h.
### F6 rotation — not exercised
May11–15: rotation gate triggered 0 times; baseline/F6 MARKET -0.084R, LIMIT -0.016R.
### Parallel dual-horizon — negative
MARKET -0.119R, LIMIT -0.254R aggregate.
### F7 consensus — useful component, not engine
Apr20–24 same-block comparator improved baseline MARKET -0.258R -> -0.150R and LIMIT -0.241R -> -0.054R, but direction accuracy barely changed and remained negative.

## F8 — CURRENT RESEARCH BASELINE
F8 is the first architecture to produce positive expectancy on **two consecutive untouched chronological holdouts without retuning between them**.

### Architecture
Development strictly precedes first validation: Apr27–May15.
Five pair archetypes and frozen model choices:
- USD_MAJOR -> `FACTOR_BAL`
- JPY_CROSS -> `SESSION_SWEEP`
- EUROPE_CROSS -> `FACTOR_BAL`
- COMMODITY_CROSS -> `FACTOR_FAST`
- MIXED_CROSS -> `FACTOR_BAL`

F8 adds no indicator stack. It uses:
- 3/6/12/24/72h currency-factor coherence;
- dispersion/rank separation;
- 8h session position/breakout/sweep;
- pair archetype;
- `IMPULSE_3H` as dominant mode;
- exceptional `REGIME_24H` only under strong persistence with no 3h veto;
- horizon-matched structural SL/TP/expiry;
- LIMIT only for genuine regime pullback.

### Holdout 1 — May18–22, frozen from development
140 forced signals.
MARKET / recommended:
- 127 resolved;
- 58 TP /69 SL;
- WR 45.67%;
- expectancy **+0.111R**;
- avg RR 1.448.
LIMIT:
- 101 resolved;
- 35 TP /66 SL;
- expectancy **+0.030R**.
Direction:
- chosen/3h 52.14%;
- 6h 67.14%;
- 12h 66.43%;
- 24h 61.43%.
Diagnostics: 69 MARKET SL; 52 bias-wrong, 17 chosen-direction-right; 32 later correct at 24h.

### Holdout 2 — May25–29, F8 completely frozen
The May18–22 result was NOT used to retune anything. Same archetype models, bias logic, SL/TP, execution and forced-all-pair rule.

140 forced signals.
MARKET:
- 111 resolved;
- 61 TP /50 SL;
- WR **54.95%**;
- expectancy **+0.338R**.
LIMIT:
- 93 resolved;
- 45 TP /48 SL;
- WR 48.39%;
- expectancy **+0.435R**;
- 8 no-fill; 11 target-before-fill.
Recommended execution:
- 110 resolved;
- 60 TP /50 SL;
- WR 54.55%;
- expectancy **+0.333R**.
Direction:
- chosen 68.57%;
- 3h 71.43%;
- 6h/12h/24h 53.57% each.
Diagnostics: 50 MARKET SL; 28 bias-wrong, 22 chosen-direction-right; 32 later correct at 24h.

### Combined two F8 chronological holdouts — 10 days / 280 forced signals
MARKET resolved:
- 238 resolved;
- **119 TP /119 SL = 50.00% WR**;
- weighted expectancy about **+0.217R per resolved trade**.
LIMIT resolved:
- 194 resolved;
- 80 TP /114 SL = 41.24% WR;
- weighted expectancy about **+0.224R**.
Recommended execution:
- 237 resolved;
- 118 TP /119 SL = 49.79% WR;
- weighted expectancy about **+0.214R**.

Combined direction accuracy across 280 signals:
- chosen horizon: 169/280 = **60.36%**;
- 3h: 173/280 = **61.79%**;
- 6h: 169/280 = **60.36%**;
- 12h: 168/280 = **60.00%**;
- 24h: 161/280 = **57.50%**.

This is the strongest Forex evidence so far. F8 is promoted to **research baseline candidate**, not a guarantee and not yet permission to auto-trade every pair live.

## F8 group stability
Holdout 2 confirmed several group effects instead of reversing them all:
- COMMODITY_CROSS: MARKET 8 TP /4 SL, WR 66.67%, **+0.679R**; dir24 86.67%.
- MIXED_CROSS: 19 TP /12 SL, WR 61.29%, **+0.474R**.
- JPY_CROSS: 15 TP /11 SL, WR 57.69%, **+0.394R**.
- EUROPE_CROSS recovered to 6 TP /4 SL, **+0.420R** after being weak in holdout1; do not change it based on one bad week.
- USD_MAJOR remains the consistently weakest archetype: holdout1 MARKET -0.131R; holdout2 only +0.006R. This is the next legitimate improvement target.

Important execution nuance:
- F8 holdout1 favored MARKET overall.
- Holdout2 showed LIMIT can improve expectancy when it actually receives a valid pullback, but the engine marked only 2 trades LIMIT-eligible; therefore **do not switch globally to LIMIT**.
- Keep execution classifier setup-dependent.

## Next research step
Freeze F8 as comparator. Do NOT modify the successful groups merely to chase more WR.
Target **USD_MAJOR only** with a new interpretable USD-specific bias component while leaving JPY/EUROPE/COMMODITY/MIXED behavior unchanged.
Requirements for the next version:
1. use May18–29 only as development now that it is revealed;
2. choose the USD-major modification before opening new June holdout dates;
3. compare F8 frozen baseline vs modified engine on the same full 28-pair block;
4. still force all 28 pairs so aggregate side effects are visible;
5. no new technical indicator unless it has a unique role;
6. preserve bias-vs-barrier diagnostics and MARKET-vs-LIMIT comparison.

## Practical live framework
F8 forced-all-pair success is research evidence, not a live mandate. Current live process:
1. refresh exact pair/current price;
2. currency-specific macro/news drivers;
3. F8 factor-coherence + archetype state;
4. H4/H1 structure;
5. M15 setup/invalidation;
6. M5 trigger;
7. M1/latest only for executable refresh;
8. structural SL first, target based on realistic liquidity/horizon;
9. MARKET vs LIMIT by F8 execution classifier, never globally.

## Twelve Data efficiency
- one M15 series per pair = ~28 symbol credits per historical block;
- derive H1/H4/features locally;
- reuse local data for model comparisons;
- workflows share `twelvedata-api` concurrency and a cooldown to avoid HTTP 429.

## Active evidence
- `scripts/blind_backtest_forex_f8.py`
- `data/blind_backtest_forex_f8.json`
- `scripts/blind_backtest_forex_f8_holdout2.py`
- `data/blind_backtest_forex_f8_holdout2.json`
- older F4–F7 artifacts remain diagnostic/history, not active baseline.

## Cross-chat rule
At a new chat read `MASTER_TRADING_STATE.md`, `CURRENT_HANDOFF.md`, this file, then live pipeline status before executable Forex entries.
