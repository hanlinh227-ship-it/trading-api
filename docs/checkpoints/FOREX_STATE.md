# FOREX STATE

Updated: 2026-08-17 (UTC+7)

## Objective
Maintain a repeatable Forex analysis/signal workflow for the 8 major currencies: USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD. Pair them into the 28 liquid crosses and rank only genuinely actionable opportunities.

## Current operating state
- Forex research is ACTIVE.
- The old rule “always maintain Top 3” is rejected. The scanner may return 0, 1, 2 or 3 trades.
- `NO TRADE` is a valid and important output.
- Do not invent a MARKET trade when fresh data, structure, macro/news quality or execution quality is inadequate.
- Crypto methodology is frozen separately; do not import crypto-specific BTC breadth/order-flow rules into Forex.

## Universe — 28 pairs
EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD,
EURJPY, EURGBP, EURCHF, EURAUD, EURNZD, EURCAD, GBPJPY,
GBPCHF, GBPAUD, GBPNZD, GBPCAD, AUDJPY, AUDNZD, AUDCAD,
AUDCHF, NZDJPY, NZDCAD, NZDCHF, CADJPY, CADCHF, CHFJPY.

## Minimal technical stack
Do not stack redundant indicators. Current common technical core is limited to:
- EMA20/50: trend, value/pullback location, H1/H4 slope/alignment;
- RSI14: momentum/exhaustion only;
- ATR14: structural SL buffer, chase/risk normalization;
- ADX14: trend-vs-chop quality gate;
- 6h/24h/72h cross-currency strength from all 28 pairs.

M15 is enough for the universe scan because H1/H4 can be derived locally. M5 is required only for live execution candidates. M1/latest is only for final executable-price refresh.

## Currency-specific live driver profiles
Each currency must be judged with its own macro/fundamental driver set; do not use one generic news formula for all currencies.

- USD: Fed/rate expectations, PCE/CPI, labour/NFP, US yields and broad risk conditions.
- EUR: ECB/rate path, HICP/core inflation, wages/services inflation, euro-area growth and energy shock.
- GBP: BoE/rate path, CPI/services inflation, wage growth and UK growth/activity.
- JPY: BoJ policy, wages/core inflation, JGB yields, carry dynamics and MOF intervention risk. FX intervention is under Japan MOF authority and executed by the BoJ on instruction.
- CHF: SNB policy, Swiss inflation, risk-off demand and explicit SNB willingness to intervene against rapid/excessive CHF appreciation.
- CAD: BoC policy, CPI/jobs, oil/energy path, US trade/growth and Canada-US trade policy risk.
- AUD: RBA policy, trimmed-mean inflation, labour/capacity pressure, China/global growth, commodities and risk sentiment.
- NZD: RBNZ OCR, CPI, spare capacity/labour, dairy/export conditions and global rates/risk.

Historical F3 does NOT reconstruct old macro/news point-in-time data after the fact; doing so would invite hindsight. Macro/news profiles are a live gate layered on top of the price-side engine.

## Research evidence

### F1 — rejected naive ranking
Fully covered July evidence at RR 1.5:
- forced all pairs: 140 signals, 136 resolved, 55 TP / 81 SL, 40.44% WR, +0.011R;
- naive Top3 strongest-score MARKET: 4 TP / 11 SL, 26.67% WR, -0.333R;
- same Top3 fixed LIMIT: 13 fills, 2 TP / 11 SL, -0.451R.

Lesson: highest raw strength/trend score is often crowded/exhausted. Raw-score ranking is rejected.

### F2 — anti-crowding quality gate
Blind holdout: Aug04, Aug05, Aug06, Aug10, Aug11 at 08:00 UTC.
- forced all-pair RR2.1: 126 resolved, 38 TP / 88 SL, 30.16% WR, -0.065R;
- selective MARKET: only 4 signals passed; 3 TP / 1 SL, 75.0% WR, +1.325R at test RR2.1;
- selective LIMIT: 3 fills, 2 TP / 1 SL, avg effective RR 3.133, +1.756R among resolved fills;
- four trades are far too few to claim stable 75% WR.

Key lesson: Aug05 forced benchmark produced 0 TP / 25 SL while F2 selected zero trades. `NO TRADE` can be more valuable than forcing exposure.

### F3 — currency profiles + ADX + structural execution
F3 was frozen before five new holdout cutoffs were opened. Exact cutoff strings had no repo hits before F3 creation:
- 2026-07-31 08:00 UTC
- 2026-08-03 08:00 UTC
- 2026-08-07 08:00 UTC
- 2026-08-12 08:00 UTC
- 2026-08-14 08:00 UTC

F3 changes versus F2:
- keeps EMA20/50 + RSI14 + ATR14 and adds only ADX14 for trend/chop quality;
- applies currency-specific ADX/chase/volatility gates, stricter for JPY/CHF/CAD-sensitive setups;
- uses 6h/24h/72h currency strength plus H4/H1 alignment and M15 confirmation;
- continuation near value is classified MARKET;
- expected pullback is classified LIMIT at M15 EMA20 when structurally valid, otherwise a capped pullback fallback;
- structure defines SL first;
- RR 1.8 and 2.1 were both predeclared; 1.8 is baseline, not selected after outcomes.

F3 blind baseline RR1.8 — all 28 pairs evaluated at all 5 dates:
- forced benchmark: 140 signals, 128 resolved, 44 TP / 84 SL, 34.38% WR, -0.037R;
- selective gate: only 3 signals across 5 dates;
- selective MARKET: 1 TP / 1 SL, 1 timeout, 50.0% WR among resolved, +0.400R;
- selective LIMIT: 3/3 filled; 1 TP / 1 SL, 1 timeout, 50.0% resolved WR, avg effective RR 3.445, +0.899R among resolved;
- selective HYBRID: 1 TP / 1 SL, 1 timeout, +0.400R.

F3 predeclared stretch RR2.1:
- forced benchmark: 39 TP / 89 SL from 128 resolved, 30.47% WR, -0.055R;
- selective MARKET: 1 TP / 1 SL + 1 timeout, 50.0% resolved WR, +0.550R;
- selective LIMIT: 1 TP / 1 SL + 1 timeout, avg effective RR 3.921, +1.103R among resolved.

F3 date lessons at RR1.8:
- Jul31: EURNZD SELL MARKET passed and TP; LIMIT also filled and TP with ~2.799 effective RR.
- Aug03: EURGBP BUY classified LIMIT; both MARKET and LIMIT timed out in 24h.
- Aug07: no setup passed while forced benchmark was only 3 TP / 22 SL among resolved.
- Aug12: no setup passed while forced benchmark was 7 TP / 21 SL.
- Aug14: EURAUD SELL classified LIMIT but SL.

Interpretation:
- F3 does NOT confirm the apparent F2 75% WR. The next blind block fell to 50% among only two resolved selective trades.
- Therefore the engine is not yet statistically stable and must not be advertised as a 75% system.
- LIMIT improved payoff geometry materially when it worked, but did not improve hit rate in F3.
- Forced all-pair direction remains negative expectancy at both 1.8R and 2.1R, so forcing every pair is rejected as a live rule.
- The correct direction remains selective quality gating + `NO TRADE`, not more indicators or a bias-flip formula.

Retained evidence:
- `scripts/blind_backtest_forex_f2.py`
- `data/blind_backtest_forex_f2.json`
- `scripts/blind_backtest_forex_f3.py`
- `data/blind_backtest_forex_f3.json`

## Important per-currency diagnostic from F3 forced benchmark
These are pair-involvement diagnostics, NOT independent currency-model win rates because each pair contributes to two currencies:
- AUD 54.55%
- NZD 45.45%
- GBP 40.62%
- JPY 40.62%
- USD 37.50%
- EUR 24.24%
- CHF 20.00%
- CAD 9.68%

Do not tune these percentages directly on the same revealed block. They indicate where the current price-only model is weakest. In particular, CAD/CHF/EUR require stronger live macro/context gating rather than looser technical filters.

## Practical Forex framework from now on

### 1. Currency regime first
Build 6h/24h/72h strength for all 8 currencies across the 28-pair network. Prefer at least 2/3 horizon agreement and do not allow 6h to directly contradict the proposed trade.

### 2. Apply the currency-specific macro profile
Before live entry, check the relevant central-bank, inflation, labour/growth and currency-specific external drivers listed above. Macro is a gate/context layer, not an excuse to override clearly broken price structure.

### 3. H4/H1 structure
- H4 defines broader tradable regime.
- H1 must align and its EMA20 slope must not contradict the thesis.
- ADX is used only to reject chop/weak-trend states, not as a directional signal.
- Extreme raw score is not rewarded automatically.

### 4. M15 setup
Require a real setup: controlled continuation, breakout-retest, sweep/reclaim, rejection or displacement with room. Avoid chase and oversized structural risk.

### 5. M5 live trigger
M5 confirms/rejects actual execution. It decides whether the observed M15 setup is still valid now.

### 6. MARKET vs LIMIT
Prefer MARKET when continuation is clean, H4/H1/strength align and price remains near value.
Prefer LIMIT only when a pullback is structurally expected and a real M15 EMA/SR/FVG/OB/retracement zone exists. LIMIT must have expiry/cancel conditions.

F3 confirms: LIMIT can improve RR strongly, but it does not automatically improve win rate.

### 7. SL / RR
- Structural invalidation first; ATR is buffer/floor only.
- Practical baseline should seek >=1.5R room.
- 1.8R is the current research baseline balance.
- 2.1R can be used only when structure/liquidity genuinely supports it; it is not a universal target.
- If structure cannot support a worthwhile target, `NO TRADE`.

### 8. Correlation / selection
- Maximum 3 trades, but 0–2 is normal.
- Default: one appearance per currency in the selected set to avoid duplicated factor exposure.
- Do not force Top 3.

## Twelve Data efficiency
Preferred staged architecture:
1. Universe scan: one M15 `/time_series` per pair = 28 symbol credits.
2. Derive H1/H4, EMA/RSI/ATR/ADX and 6h/24h/72h strength locally.
3. Fetch M5 only for up to 3 finalists.
4. Fetch M1/latest only for up to 3 executable finalists.

Target: about 34 symbol credits for a full scan with three finalists rather than full multi-timeframe calls for every pair. Raw historical dumps are not committed.

## Risk
General discretionary default: approximately 0.25%-0.50% account risk per trade unless prop rules/user instruction specify otherwise. Count correlated exposure together.

## Live output
For each eligible signal:
- pair + BUY/SELL;
- exact refreshed price/source/time;
- MARKET or LIMIT and why;
- Entry;
- hard structural SL;
- TP and realistic RR;
- 6h/24h/72h currency-strength context;
- currency-specific macro driver status;
- H4/H1/M15/M5 reasoning;
- cancellation/early-exit condition;
- confidence/rank.

If nothing passes, output `NO TRADE`.

## Rejected methods — do not revive without new evidence
- force BUY/SELL on all 28 pairs as a live rule;
- always maintain exactly Top 3;
- rank solely by highest EMA/RSI/raw-strength score;
- indicator stacking with overlapping roles;
- repeated exposure to the same currency factor;
- rigid universal RR from one sample;
- rigid LIMIT distance on every setup;
- claim 75% WR from F2's four trades.

## Cross-chat rule
At a new chat, read `MASTER_TRADING_STATE.md`, `CURRENT_HANDOFF.md`, this file, then live pipeline status before issuing Forex entries.
