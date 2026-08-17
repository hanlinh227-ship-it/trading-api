# FOREX STATE

Updated: 2026-08-17 (UTC+7)

## Objective
Build a repeatable Forex method for the 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD. Current research mode deliberately blind-trades every valid pair so directional quality and barrier geometry can be measured without Top-3 selection bias. This forced mode is research/stress testing, not automatically a live rule.

## Current operating state
- Forex research is ACTIVE.
- Current research benchmark: every valid pair receives BUY or SELL at each blind cutoff; no Top-3 selection.
- Score direction separately at 6h/12h/24h and actual TP/SL so bias failure is not confused with entry/barrier failure.
- Once a blind block is revealed it becomes development data forever.
- Do not optimize only WR. Judge direction accuracy + expectancy + RR together.
- Live execution still requires fresh exact price, macro/news context, structure and event checks.

## Universe — 28 pairs
EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD,
EURJPY, EURGBP, EURCHF, EURAUD, EURNZD, EURCAD, GBPJPY,
GBPCHF, GBPAUD, GBPNZD, GBPCAD, AUDJPY, AUDNZD, AUDCAD,
AUDCHF, NZDJPY, NZDCAD, NZDCHF, CADJPY, CADCHF, CHFJPY.

## Minimal technical stack
Keep only:
- EMA20/50: trend, value/pullback location, H1/H4 slope/alignment;
- RSI14: momentum/exhaustion only;
- ATR14: volatility and structural-SL normalization;
- ADX14: trend-vs-chop regime, never standalone direction;
- 6h/24h/72h cross-currency strength across the full 28-pair network.

Research fetches one M15 Twelve Data series per pair and derives H1/H4 + indicators locally. Do not add MACD/Stochastic/Bollinger unless a future hypothesis proves a unique role.

## Currency-specific live driver profiles
Do not reconstruct these historically with hindsight unless proper point-in-time data is connected.
- USD: Fed/rate expectations, PCE/CPI, labour/NFP, US yields.
- EUR: ECB/rate path, HICP/core, wages/services, energy/growth.
- GBP: BoE/rate path, CPI/services, wages, UK activity.
- JPY: BoJ, wages/core CPI, JGB yields, carry and MOF intervention risk.
- CHF: SNB, Swiss inflation, risk-off and SNB FX intervention risk.
- CAD: BoC, CPI/jobs, oil and US trade/growth.
- AUD: RBA, trimmed inflation, labour/capacity, China/commodities/risk.
- NZD: RBNZ OCR, CPI, spare capacity/labour, dairy/global rates.

## Research progression

### F1 — rejected naive strongest-score selection
- forced July RR1.5: 55 TP / 81 SL from 136 resolved, 40.44%, +0.011R;
- naive Top3 MARKET: 4 TP / 11 SL, -0.333R;
- fixed Top3 LIMIT: 2 TP / 11 SL, -0.451R.
Conclusion: strongest raw trend score is not the best entry.

### F2 — promising but too small
Blind Aug04/05/06/10/11:
- forced RR2.1: 38 TP / 88 SL, -0.065R;
- selective MARKET: 3 TP / 1 SL, +1.325R;
- selective LIMIT: 2 TP / 1 SL, avg effective RR 3.133, +1.756R.
Four selective trades are far too few to claim stable 75%.

### F3 — failed to confirm F2
Blind Jul31/Aug03/Aug07/Aug12/Aug14:
- forced RR1.8: 44 TP / 84 SL from 128 resolved, 34.38%, -0.037R;
- selective MARKET: 1 TP / 1 SL + timeout, +0.400R;
- selective LIMIT: 1 TP / 1 SL + timeout, avg effective RR 3.445, +0.899R.

### F4 — pair-adaptive forced blind + dynamic barriers
Blind Jul17/20/21/22/24, 140 forced signals.
- MARKET: 49 TP / 73 SL, 18 timeout; WR 40.16%; avg RR 2.055; median 1.698; expectancy -0.081R.
- LIMIT: 126 fills, 40 TP / 70 SL among 110 resolved; WR 36.36%; avg effective RR 2.699; expectancy -0.018R.
- direction 6h/12h/24h = 52.14% / 53.57% / 53.57%.
Conclusion: modest directional edge only. LIMIT nearly break-even but cannot cure wrong bias.

Important F4 lesson: high TP rate can be fake progress when TP is too close. AUDUSD had 75% MARKET WR but 0% direction12h and median RR ~0.436R; EURAUD had 100% WR with median RR ~0.578R. Never optimize WR alone.

### F5 — REJECTED: long-horizon + economic target
Blind Jul27/28, 56 forced signals. F5 retained minimal indicators, added LONGHORIZON candidate, deeper swing SL under strong agreement and rejected tiny TP in favor of next viable liquidity/ADR target.

Result:
- MARKET: 55 resolved, 12 TP / 43 SL, 1 timeout; WR 21.82%; avg RR 1.985; median 2.065; expectancy -0.383R.
- LIMIT: 53 fills, 10 TP / 42 SL among 52 resolved; WR 19.23%; avg effective RR 2.552; expectancy -0.362R.
- direction 6h/12h/24h = 28.57% / 32.14% / 32.14%.
- 43 SL: only 7 were later correct at 24h; 36 were also wrong direction24.
Conclusion: genuine bias failure, not mainly SL geometry. F5 is rejected as a solution.

Jul27 was especially diagnostic: 6 TP / 22 SL; direction24 only 17.86%; all 22 SL were also wrong at 24h.

### F6 rotation comparator — NOT EXERCISED
Hypothesis: when the 6h currency-strength vector sharply opposes the 24h/72h vector, temporarily prioritize short-horizon rotation for pairs whose own 6h strength has turned.

Final retained JSON for the untouched May11–15 block:
- rotation gate never became active; overrides = 0;
- F6 therefore equals the baseline exactly;
- MARKET: 108 resolved, 35 TP / 73 SL, 31 timeout + 1 ambiguous; WR 32.41%; avg RR 2.413; expectancy -0.084R;
- LIMIT: 125 fills, 30 TP / 72 SL among 102 resolved; WR 29.41%; avg effective RR 3.105; expectancy -0.016R;
- direction 6h/12h/24h = 50.71% / 55.00% / 52.86%;
- 28/73 SL later became correct at 24h.
Conclusion: do not call F6 win/loss and do not loosen thresholds on the same May block. The target state never triggered.

### Parallel dual-horizon experiment — negative aggregate
Another repo experiment on Jun24/Jun30/Jul02/Jul07/Jul10:
- MARKET 44 TP / 70 SL from 114 resolved, WR 38.60%, expectancy -0.119R;
- LIMIT 20 TP / 65 SL from 85 resolved, expectancy -0.254R;
- selected direction accuracy 51.43%; 3h direction 57.14%; 24h 47.86%.
Some individual pairs looked good, but aggregate remained negative; do not cherry-pick pair winners.

### F7 — five-vote consensus comparator, PARTIAL improvement only
Unseen historical holdout Apr20–24. Important nuance: timestamps were absent from repo before creation, but this is not pure chronological walk-forward because the current baseline itself was developed using later 2026 data. It is still a valid same-block comparator between baseline and F7.

F7 direction = majority vote across five distinct views:
1. 6h cross-currency strength;
2. 24h strength;
3. 72h strength;
4. H4 trend;
5. H1 trend.
Barriers/execution unchanged from F5. All 28 pairs forced; baseline and F7 evaluated on identical 140 signals.

Baseline on same Apr20–24 block:
- MARKET: 27 TP / 100 SL from 127 resolved; WR 21.26%; avg RR 2.536; expectancy -0.258R.
- LIMIT: 22 TP / 100 SL from 122 resolved; avg effective RR 3.191; expectancy -0.241R.
- direction12 = 41.43%; direction24 = 50.00%; avg signed 24h move = -0.420 ATR.

F7:
- 13/140 direction overrides;
- MARKET: 27 TP / 102 SL from 129 resolved; WR 20.93%; avg RR 2.661; expectancy -0.150R.
- LIMIT: 136 fills, 23 TP / 102 SL from 125 resolved; WR 18.40%; avg effective RR 3.383; expectancy -0.054R.
- direction12 = 42.14%; direction24 = 50.71%; avg signed 24h move improved to +0.059 ATR.
- 102 SL: 35 later correct at 24h, 67 still wrong direction24.

Interpretation:
- F7 materially improved expectancy vs the same baseline, especially LIMIT (-0.241R -> -0.054R), and improved average signed 24h move from negative to slightly positive;
- classification accuracy barely improved (~+0.7 percentage point) and MARKET WR slightly worsened;
- F7 is NOT a winning/validated engine; treat consensus voting only as a candidate component.
- regime/date instability is still huge: Apr23 F7 MARKET +0.766R and LIMIT +1.062R, while Apr24 MARKET -0.848R and LIMIT -0.815R.

Critical path lesson from F7:
- Apr20/21 had many SLs whose 24h direction later became correct, so barrier/entry mattered substantially;
- Apr22/24 failures were mostly true bias failures;
- one universal barrier or one universal direction tweak cannot solve both states.

## Current research direction after F7
Do NOT add more indicators and do NOT keep creating cosmetic versions.
The next genuine hypothesis should target **market-day/common-factor regime quality** before pair direction:
1. measure common USD/risk/carry factor and cross-sectional currency dispersion/breadth;
2. distinguish synchronized factor trend from rotation/chop;
3. when the common factor is strong, pair direction should respect it; when dispersion is high, pair-specific relative strength may dominate;
4. keep every pair forced BUY/SELL in the benchmark, but let the day-regime variable alter direction/barrier logic rather than simply skip bad days;
5. continue splitting SL into `bias wrong` versus `direction later right`;
6. compare any new method with the current baseline on the SAME untouched block;
7. once a block is revealed, never tune on it and call it blind again.

F7 is the best recent **candidate component** because it improved payoff expectancy on the same block, but no forced all-pair Forex method is validated profitable yet.

## Practical live framework
Forced all-pair trading remains research only. Live analysis should still use:
1. currency-specific macro/news context;
2. 6h/24h/72h currency strength and common-factor regime;
3. H4/H1 structure + EMA slope;
4. ADX regime, RSI exhaustion, ATR volatility only in distinct roles;
5. M15 setup and structural invalidation;
6. M5 execution trigger;
7. exact M1/latest refresh before executable entry;
8. MARKET for clean continuation; LIMIT only for an expected structural pullback with cancellation/expiry.

## Twelve Data efficiency
- one M15 series per pair = ~28 symbol credits per historical block;
- derive H1/H4, EMA/RSI/ATR/ADX and currency strength locally;
- model variants on the same block must reuse local data;
- use a cooldown before a new workflow because another run can consume the rolling per-minute quota;
- a previous F5 attempt hit HTTP 429 before data fetch; only quota cooldown was changed, never the frozen test rules.

## Active evidence
- `scripts/blind_backtest_forex_f4.py`, `data/blind_backtest_forex_f4.json`
- `scripts/blind_backtest_forex_f5.py`, `data/blind_backtest_forex_f5.json`
- `scripts/blind_backtest_forex_f6.py`, `data/blind_backtest_forex_f6.json`
- `data/blind_backtest_forex_f6_dual_horizon.json`
- `scripts/blind_backtest_forex_f7.py`, `data/blind_backtest_forex_f7.json`

## Cross-chat rule
At a new chat, read `MASTER_TRADING_STATE.md`, `CURRENT_HANDOFF.md`, this file, then live pipeline status before issuing Forex entries.
