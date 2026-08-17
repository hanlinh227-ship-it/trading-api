# FOREX STATE

Updated: 2026-08-17 (UTC+7)

## Objective
Build a repeatable Forex method for the 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD. Current research mode deliberately blind-trades every valid pair so directional quality and barrier geometry can be measured without Top-3 selection bias. This forced mode is research/stress testing, not automatically a live rule.

## Current operating state
- Forex research is ACTIVE.
- Current user-requested research mode: every valid pair must receive BUY or SELL at each blind cutoff; no Top-3 ranking requirement.
- Research must separately score direction at 6h/12h/24h and TP/SL outcome so bias errors are not confused with entry/barrier errors.
- Live execution still requires fresh exact price, macro/news context and structure; a forced blind research trade does not imply a live trade should always be taken.
- Avoid excessive indicators; each indicator must have a distinct role.

## Universe — 28 pairs
EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD,
EURJPY, EURGBP, EURCHF, EURAUD, EURNZD, EURCAD, GBPJPY,
GBPCHF, GBPAUD, GBPNZD, GBPCAD, AUDJPY, AUDNZD, AUDCAD,
AUDCHF, NZDJPY, NZDCAD, NZDCHF, CADJPY, CADCHF, CHFJPY.

## Minimal technical stack
Use only:
- EMA20/50: trend, value/pullback location, H1/H4 slope/alignment;
- RSI14: momentum/exhaustion only;
- ATR14: volatility, structural-SL buffer, normalization;
- ADX14: trend-vs-chop regime, never a directional signal;
- 6h/24h/72h cross-currency strength from the full 28-pair network.

M15 is the single historical provider interval for research. H1/H4 and the indicators above are derived locally. Raw historical dumps are not committed.

## Currency-specific live driver profiles
These are live context gates and should not be reconstructed historically with hindsight unless a proper point-in-time dataset is connected.
- USD: Fed/rate expectations, PCE/CPI, labour/NFP, US yields.
- EUR: ECB/rate path, HICP/core, wages/services, energy/growth.
- GBP: BoE/rate path, CPI/services, wages, UK growth/activity.
- JPY: BoJ, wages/core CPI, JGB yields, carry and MOF intervention risk.
- CHF: SNB, Swiss inflation, risk-off and SNB FX intervention risk.
- CAD: BoC, CPI/jobs, oil and US trade/growth.
- AUD: RBA, trimmed inflation, labour/capacity, China/commodities/risk.
- NZD: RBNZ OCR, CPI, spare capacity/labour, dairy/global rates.

## Research progression

### F1 — rejected naive strongest-score selection
July fully covered block at RR1.5:
- forced: 55 TP / 81 SL from 136 resolved, 40.44%, +0.011R;
- naive Top3 MARKET: 4 TP / 11 SL, -0.333R;
- fixed Top3 LIMIT: 2 TP / 11 SL among 13 fills, -0.451R.
Conclusion: raw strongest trend/score is not the best Forex entry.

### F2 — promising but tiny selective sample
Blind Aug04/05/06/10/11:
- forced RR2.1: 38 TP / 88 SL from 126 resolved, -0.065R;
- selective MARKET: 4 signals, 3 TP / 1 SL, 75% WR, +1.325R;
- selective LIMIT: 3 fills, 2 TP / 1 SL, avg effective RR 3.133, +1.756R.
Four selective trades are far too few to claim stable 75%.

### F3 — currency-profile + ADX selective holdout
Blind cutoffs: Jul31, Aug03, Aug07, Aug12, Aug14 at 08:00 UTC.
Baseline RR1.8:
- forced: 140 signals, 128 resolved, 44 TP / 84 SL, 34.38% WR, -0.037R;
- selective MARKET: 1 TP / 1 SL + 1 timeout, +0.400R;
- selective LIMIT: 1 TP / 1 SL + 1 timeout, avg effective RR 3.445, +0.899R.
Conclusion: F3 did not confirm F2's apparent 75% WR. LIMIT improved payoff geometry but not hit rate.

### F4 — pair-adaptive forced blind + dynamic barriers
User then changed the research objective: do not choose Top 3; blind-trade every symbol to judge the method itself. F4 implements that request.

Integrity:
- exact validation cutoff strings were searched before F4 creation and absent from the repo;
- validation: Jul17, Jul20, Jul21, Jul22, Jul24 2026 at 08:00 UTC;
- every valid pair receives BUY or SELL;
- decision uses only data available at/before cutoff;
- TP/SL are NOT fixed RR;
- MARKET and adaptive pullback LIMIT are both evaluated;
- direction is scored independently at 6h/12h/24h.

Pair adaptation:
- each pair may choose one of only three predeclared low-complexity models from development-only evidence: `BALANCED`, `STRUCTURE`, `REGIME`;
- model-switching is regularized; the pair stays BALANCED unless another model has a material development advantage;
- result: most pairs remained BALANCED; only EURNZD and GBPJPY selected REGIME, while GBPCHF selected STRUCTURE. This is evidence that the available development sample did not justify aggressive pair-specific model proliferation.

Dynamic barriers:
- SL = recent M15 structural swing plus ATR buffer, with volatility floor/cap;
- TP = prior 24h/72h directional liquidity when realistic, otherwise trailing realized daily-range projection;
- no universal 1.8R/2.1R target;
- LIMIT = modest pullback toward M15 value/EMA with five-hour expiry and same absolute structural SL/TP.

F4 blind aggregate — 5 cutoffs x 28 pairs = 140 signals:
- MARKET: 122 resolved, 49 TP / 73 SL, 18 timeout;
- MARKET resolved WR 40.16%; avg planned RR 2.055; median RR 1.698; expectancy -0.081R;
- LIMIT: 126/140 fills = 90.0%; 110 resolved fills, 40 TP / 70 SL; 6 no-fill; 8 target-before-fill; 16 filled timeouts;
- LIMIT resolved WR 36.36%; avg effective RR 2.699; expectancy -0.018R;
- direction 6h: 73/140 = 52.14%;
- direction 12h: 75/140 = 53.57%;
- direction 24h: 75/140 = 53.57%.

Interpretation of F4:
- pair-adaptive direction produced only a modest >50% directional edge and is NOT strong enough yet;
- dynamic TP/SL increased MARKET hit rate versus the F3 forced fixed-RR block on a different sample, but expectancy remained negative, so higher WR alone is not progress;
- LIMIT moved expectancy close to break-even (-0.018R) by improving payoff geometry, but its hit rate was lower; LIMIT is not a cure for bad bias;
- the main weakness is still pair-level bias for several symbols, while a second weakness is barrier geometry/path dependence.

Important pair diagnostics from the five F4 blind dates:
- GBPUSD: direction12/24 = 80%/80%, MARKET WR 50%, +0.421R;
- USDJPY: direction12/24 = 80%/80%, MARKET WR 75%, +0.967R;
- GBPAUD: direction12/24 = 100%/100%, MARKET WR 75%, +0.973R;
- AUDCAD: direction12/24 = 100%/80%, MARKET WR 50%, +0.102R;
- weak bias examples: GBPJPY direction12/24 = 0%/0%; EURUSD 40%/40%; USDCAD 40%/40%; GBPCHF 40%/40%; CADJPY 40%/40%.

Do not overinterpret pair WR from only five cutoffs. Also do not reward artificial high WR created by tiny payoff targets: AUDUSD showed MARKET WR 75% but direction12h 0% and median planned RR only ~0.436R; EURAUD had 100% MARKET WR with median RR ~0.578R. These are examples of why direction + expectancy + RR must be reviewed together.

Retained F4 evidence:
- `scripts/blind_backtest_forex_f4.py`
- `data/blind_backtest_forex_f4.json`
- `.github/workflows/blind-backtest-forex-f4.yml`

## Current research direction after F4
Do NOT add more overlapping indicators. The next improvements should target the diagnosed failure source:
1. pair-level directional reliability first;
2. distinguish strong-consensus trend from conflicted/mixed-horizon state;
3. improve weak-pair logic (especially GBPJPY, EURUSD, USDCAD, GBPCHF/CADJPY) without tuning on the same F4 dates and calling them blind;
4. prevent low-RR targets from manufacturing pretty WR; compare expectancy and direction, not WR alone;
5. identify `SL but direction24 correct` separately from `SL and direction24 wrong` to decide whether to adjust entry/barrier or bias;
6. MARKET vs LIMIT remains a secondary execution decision after direction quality.

## Practical live framework
Even though forced all-pair trading is the current research benchmark, live analysis still follows:
1. 6h/24h/72h currency strength;
2. currency-specific macro/news context;
3. H4/H1 structure + EMA slope;
4. ADX regime, RSI exhaustion, ATR volatility only in their defined roles;
5. M15 setup and structural invalidation;
6. M5 execution trigger;
7. exact M1/latest refresh before executable price;
8. MARKET for clean continuation; LIMIT only for an expected structural pullback with cancellation/expiry.

## Twelve Data efficiency
- one M15 series per pair = 28 symbol credits per full historical block;
- derive H1/H4, EMA/RSI/ATR/ADX and cross-currency strength locally;
- changing models/barriers on the same downloaded block must reuse local data rather than generate extra provider calls where possible;
- live deep fetches should be staged only when needed.

## Cross-chat rule
At a new chat, read `MASTER_TRADING_STATE.md`, `CURRENT_HANDOFF.md`, this file, then live pipeline status before issuing Forex entries.
