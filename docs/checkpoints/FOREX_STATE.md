# FOREX STATE

Updated: 2026-08-17 (UTC+7)

## Objective
Build a repeatable Forex method for all 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD. The research benchmark forces BUY or SELL on every valid pair at each blind cutoff so the method itself is measured without Top-3 selection bias. Forced-all-pair research is not a live mandate.

## Research integrity
- No Top-3 / NO-TRADE in forced benchmark.
- Freeze decision, entry, SL and TP before future candles.
- Score direction separately from TP/SL: chosen horizon plus 3h/6h/12h/24h where available.
- Separate `bias wrong` from `bias right but barrier/path failed`.
- Do not optimize win rate using tiny TP; judge WR + RR + expectancy + direction together.
- A revealed blind block becomes development data forever.
- A new version must beat the frozen baseline on the SAME untouched block before promotion.

## Universe
EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD,
EURJPY, EURGBP, EURCHF, EURAUD, EURNZD, EURCAD, GBPJPY,
GBPCHF, GBPAUD, GBPNZD, GBPCAD, AUDJPY, AUDNZD, AUDCAD,
AUDCHF, NZDJPY, NZDCAD, NZDCHF, CADJPY, CADCHF, CHFJPY.

## Minimal technical stack
Keep indicators limited to distinct roles:
- EMA20/50: trend, value and slope;
- RSI14: momentum/exhaustion;
- ATR14: volatility / structural-SL normalization;
- ADX14: trend-vs-chop, never standalone direction.

Non-indicator state is more important than adding indicators:
- 3h/6h/12h/24h/72h cross-currency factor strength/coherence;
- cross-sectional dispersion and rank separation across 8 currencies;
- 8h session location/breakout/sweep;
- pair archetype;
- horizon-matched SL/TP/expiry;
- bias-vs-barrier diagnostics.

Historical research fetches one M15 Twelve Data series per pair and derives H1/H4/features locally.

## Currency-specific live driver profiles
Do not reconstruct historical macro with hindsight unless a point-in-time dataset is connected.
- USD: Fed/rate path, PCE/CPI, labour/NFP, US yields.
- EUR: ECB, HICP/core, wages/services, energy/growth.
- GBP: BoE, CPI/services, wages, UK activity.
- JPY: BoJ, wages/CPI, JGB yields, carry, MOF intervention.
- CHF: SNB, inflation, risk-off, FX intervention.
- CAD: BoC, CPI/jobs, oil, US trade/growth.
- AUD: RBA, trimmed inflation, labour/capacity, China/commodities/risk.
- NZD: RBNZ OCR, CPI, spare capacity/labour, dairy/global rates.

## Rejected / diagnostic lineage
- F1 strongest-score Top3 rejected.
- F2 selective 3 TP / 1 SL sample too small to validate.
- F3 failed to confirm F2; forced RR1.8 = 44 TP / 84 SL, -0.037R.
- F4 Jul17/20/21/22/24: MARKET -0.081R, LIMIT -0.018R, direction12/24 53.57%.
- F5 Jul27/28 rejected: MARKET 12 TP / 43 SL, -0.383R, direction12/24 32.14%; 36/43 SL also wrong direction24.
- F6 May11–15 rotation gate never triggered; MARKET -0.084R, LIMIT -0.016R.
- Dual-horizon experiment aggregate negative: MARKET -0.119R, LIMIT -0.254R.
- F7 Apr20–24 consensus improved same-block expectancy but remained negative; useful component only.
- F9 three-horizon was positive on May25–29 but inferior to frozen F8 on the same block; do not promote.
- F10 leave-one-pair-out factor isolation was inferior to F8 on Jun01–05; self-inclusion is not the main weakness.
- F10 USD_MID candidate was not selected by its predeclared development threshold; frozen F8 survived unchanged.
- F11 day-conflict MID_FACTOR had no qualifying development day under any predeclared threshold, so selection correctly fell back to F8; do not loosen thresholds on the same data.

## F8 — CURRENT FROZEN RESEARCH BASELINE
F8 is the first architecture to stay positive across multiple consecutive chronological holdouts without retuning.

### Architecture
Original development strictly precedes first validation: Apr27–May15.
Frozen pair-archetype models:
- USD_MAJOR -> `FACTOR_BAL`
- JPY_CROSS -> `SESSION_SWEEP`
- EUROPE_CROSS -> `FACTOR_BAL`
- COMMODITY_CROSS -> `FACTOR_FAST`
- MIXED_CROSS -> `FACTOR_BAL`

F8 uses:
- 3/6/12/24/72h currency-factor coherence;
- dispersion/rank separation;
- 8h session position/breakout/sweep;
- pair archetype;
- `IMPULSE_3H` as dominant mode;
- exceptional `REGIME_24H` only under strong persistence with no 3h veto;
- horizon-matched structural SL/TP/expiry;
- LIMIT only for genuine pullback logic.

### Holdout 1 — May18–22
140 forced signals.
MARKET: 127 resolved, 58 TP /69 SL, WR45.67%, **+0.111R**, avg RR1.448.
LIMIT: 101 resolved, 35 TP /66 SL, **+0.030R**.
Direction: chosen/3h52.14%, 6h67.14%, 12h66.43%, 24h61.43%.

### Holdout 2 — May25–29, completely frozen
140 forced signals.
MARKET: 111 resolved, 61 TP /50 SL, WR54.95%, **+0.338R**.
LIMIT: 93 resolved, 45 TP /48 SL, **+0.435R**.
Recommended: 110 resolved, 60 TP /50 SL, **+0.333R**.
Direction: chosen68.57%, 3h71.43%, 6h/12h/24h53.57%.

### Holdout 3 — Jun01–05, frozen again
140 forced signals.
MARKET: 129 resolved, 66 TP /63 SL, WR51.16%, **+0.247R**.
LIMIT: 112 resolved, 50 TP /62 SL, WR44.64%, **+0.325R**.
Recommended: 129 resolved, 66 TP /63 SL, **+0.252R**.
Direction: chosen/3h50.00%, 6h46.43%, 12h52.86%, 24h45.71%.
Diagnostics: 63 SL; 54 bias-wrong, 9 chosen-direction-right; 15 later correct at 24h.

Day instability remains visible:
- Jun01: MARKET +0.845R, LIMIT +1.182R.
- Jun04: 5 TP /22 SL, MARKET **-0.565R**, direction12/24 only 21.43%; 19/22 SL were true bias failures.
- Despite Jun04, the full block stayed +0.247R.

USD_MAJOR on Jun01–05: 18 TP /14 SL, WR56.25%, MARKET **+0.399R**, LIMIT +0.525R. Therefore do not force a special USD model merely because the first two holdouts looked weaker.

### Holdout 4 — Jun08–12, F11 fell back to frozen F8
F11 predeclared a market-day conflict gate and thresholds 0.55/0.65/0.75. On 700 development signals all thresholds activated zero days, so `selectedThreshold = null` before validation. F11 made zero overrides and Jun08–12 is another untouched frozen-F8 validation block.

140 forced signals.
MARKET: 122 resolved, 63 TP /59 SL, WR51.64%, **+0.251R**.
LIMIT: 97 resolved, 39 TP /58 SL, WR40.21%, **+0.199R**.
Recommended: 121 resolved, 63 TP /58 SL, WR52.07%, **+0.267R**.
Direction: chosen63.57%, 3h65.00%, 6h54.29%, 12h49.29%, 24h52.14%.
Diagnostics: 59 SL; 40 bias-wrong, 19 chosen-direction-right, 21 later correct at 24h.

## Combined F8 evidence — four consecutive 5-day blocks
May18–22 + May25–29 + Jun01–05 + Jun08–12 = **560 forced signals / 20 trading days** without changing the frozen F8 engine.

MARKET:
- 489 resolved;
- **248 TP /241 SL = 50.72% WR**;
- weighted expectancy about **+0.233R per resolved trade**.

LIMIT:
- 403 resolved;
- **169 TP /234 SL = 41.94% WR**;
- weighted expectancy about **+0.246R**.

Recommended execution:
- 487 resolved;
- **247 TP /240 SL = 50.72% WR**;
- weighted expectancy about **+0.237R**.

Combined direction across 560 signals:
- chosen horizon: 328/560 = **58.57%**;
- 3h: 334/560 = **59.64%**;
- 6h: 310/560 = **55.36%**;
- 12h: 311/560 = **55.54%**;
- 24h: 298/560 = **53.21%**.

This is the strongest Forex evidence in the project. F8 is the frozen research baseline. It is not a guarantee and not permission to auto-trade every pair live.

## Execution conclusion
- Do NOT globally choose MARKET or LIMIT.
- MARKET has higher hit rate in combined evidence.
- LIMIT has lower hit rate but slightly higher weighted expectancy among resolved fills because entry geometry is better.
- Keep the frozen F8 execution classifier; LIMIT only when structural pullback criteria exist.

## What to improve next
Do not modify F8 globally. Remaining weakness is **date/common-factor catastrophe risk**, not a consistently bad pair group.
Next legitimate work:
1. study bad revealed dates such as Jun04;
2. create one interpretable common-factor/day-regime hypothesis before opening a new untouched block;
3. new method must compare against frozen F8 on the same 28-pair dates;
4. if development cannot justify the gate, keep F8 unchanged instead of lowering thresholds;
5. preserve bias-vs-barrier diagnostics and MARKET-vs-LIMIT comparison.

## Practical live framework
Forced-all-pair research success is not a live mandate. Live process:
1. refresh exact pair/current price;
2. check currency-specific macro/news drivers;
3. evaluate frozen F8 factor-coherence + archetype state;
4. H4/H1 structure;
5. M15 setup/invalidation;
6. M5 trigger;
7. M1/latest only for executable refresh;
8. structural SL first and horizon/liquidity target;
9. MARKET vs LIMIT by setup, never globally.

## Twelve Data efficiency
- one M15 series per pair = ~28 symbol credits per historical block;
- derive H1/H4/features locally;
- reuse local data for model comparisons;
- workflows share `twelvedata-api` concurrency + cooldown to avoid HTTP429.

## Active evidence
- `scripts/blind_backtest_forex_f8.py`
- `data/blind_backtest_forex_f8.json`
- `scripts/blind_backtest_forex_f8_holdout2.py`
- `data/blind_backtest_forex_f8_holdout2.json`
- `data/blind_backtest_forex_f10_loo.json`
- `data/blind_backtest_forex_f10_usd_mid.json`
- `scripts/blind_backtest_forex_f11_day_conflict.py`
- `data/blind_backtest_forex_f11_day_conflict.json`

## Cross-chat rule
At a new chat read `MASTER_TRADING_STATE.md`, `CURRENT_HANDOFF.md`, this file, then live pipeline status before executable Forex entries.
