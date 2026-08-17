# FOREX STATE

Updated: 2026-08-17 (UTC+7)

## Objective
Maintain a repeatable Forex analysis/signal workflow for the 8 major currencies: USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD. Pair them into the 28 liquid crosses and rank only genuinely actionable opportunities.

## Current operating state
- Forex research is ACTIVE.
- The old rule “always maintain Top 3” is no longer considered safe. The live scanner may return 0, 1, 2 or 3 trades.
- `NO TRADE` is a valid and important output when the market-quality/entry-quality gate fails.
- Do not invent a MARKET trade when fresh data, structure, or news quality is inadequate.
- Crypto methodology is frozen separately; do not transfer crypto-specific BTC breadth/order-flow rules into Forex.

## Universe — 28 pairs
EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD,
EURJPY, EURGBP, EURCHF, EURAUD, EURNZD, EURCAD, GBPJPY,
GBPCHF, GBPAUD, GBPNZD, GBPCAD, AUDJPY, AUDNZD, AUDCAD,
AUDCHF, NZDJPY, NZDCAD, NZDCHF, CADJPY, CADCHF, CHFJPY.

## Research evidence

### F1 — diagnostic / rejected selection logic
F1 fetched one Twelve Data M15 series per pair and derived H1/H4 plus 24h/72h currency strength locally. Its early June development block had insufficient lookback coverage, so its RR choice is not valid evidence.

The fully covered July block is now revealed/development data forever:
- forced all-pair MARKET at RR 1.5: 140 signals, 136 resolved, 55 TP / 81 SL, 40.44% WR, +0.011R expectancy;
- naive “Top 3 strongest score” MARKET: 15/15 resolved, 4 TP / 11 SL, 26.67% WR, -0.333R;
- same Top 3 with fixed 0.30R LIMIT: 13 fills, 2 TP / 11 SL, 15.38% WR, -0.451R despite higher effective RR.

Lesson: the highest absolute trend/strength score is often a crowded or exhausted entry. Ranking by raw strength alone is rejected.

### F2 — anti-crowding / quality-gate candidate
F2 uses the revealed July F1 block only as development and locks an untouched holdout before outcomes:
- validation cutoffs: 2026-08-04, 08-05, 08-06, 08-10, 08-11 at 08:00 UTC;
- one M15 series per pair; H1/H4 derived locally;
- 6h/24h/72h cross-currency strength;
- H4/H1 alignment + H1 EMA slope;
- moderate RSI band, M15 momentum confirmation, anti-chase and structural-risk gates;
- extreme score is penalized instead of rewarded;
- a currency cannot appear twice in the selected set;
- structure defines SL first;
- fixed test LIMIT = 0.25R pullback, 4h expiry;
- RR grid was selected only from development forced-market data.

Development selected RR 2.1, but it does NOT generalize as a universal RR:
- development forced: 44 TP / 84 SL from 128 resolved, 34.38% WR, +0.066R;
- blind validation forced: 38 TP / 88 SL from 126 resolved, 30.16% WR, -0.065R.
Conclusion: forcing every pair is not robust and RR 2.1 must not be treated as a universal target.

Selective F2 blind holdout:
- only 4 setups passed the strict quality gate across 5 daily cutoffs;
- MARKET: 3 TP / 1 SL = 75.00% WR, RR 2.1 in the test, +1.325R expectancy;
- LIMIT: 3 fills of 4; 2 TP / 1 SL, 66.67% WR among fills; average effective RR 3.133; +1.756R among resolved fills; one MARKET winner reached target before the limit filled;
- HYBRID: 3 resolved, 2 TP / 1 SL, +1.411R; one signal did not resolve because its limit missed a continuation.

Important: 4 selective trades is far too small to claim a stable 75% win rate. F2 is a promising quality gate, NOT a fully validated profit engine.

Blind date lessons:
- Aug04: EURNZD SELL passed; MARKET TP; 0.25R LIMIT missed because target was reached first.
- Aug05: forced-all-pair result was 0 TP / 25 SL among resolved trades, while F2 selected ZERO trades. This is strong evidence that `NO TRADE`/market-quality filtering matters.
- Aug06: EURJPY BUY passed and MARKET TP.
- Aug10: GBPUSD BUY passed and MARKET TP; LIMIT also filled and TP.
- Aug11: GBPAUD BUY passed and SL. The gate reduces bad exposure but is not infallible.

Retained result: `data/blind_backtest_forex_f2.json`.
Active reusable research engine: `scripts/blind_backtest_forex_f2.py`.

## Practical Forex analysis framework from now on

### 1. Currency regime first
Before judging a pair, score the individual currencies across the 28-pair network:
- 6h strength = immediate session impulse;
- 24h strength = intraday regime;
- 72h strength = short swing context.
Prefer pairs where at least 2/3 horizons agree, with 6h not contradicting the proposed trade.

For live use, overlay real macro context:
- central-bank policy/rate expectations;
- inflation, employment and growth data;
- DXY/US yields for USD;
- risk-on/risk-off for JPY/CHF/AUD/NZD;
- commodity context for CAD/AUD/NZD.

### 2. H4/H1 structure, not raw score
- H4 defines the broader tradable direction/regime.
- H1 must agree with the trade and its EMA20 slope should not contradict it.
- Do not reward the most extreme score automatically; extreme trends may already be exhausted/crowded.
- D1 remains useful for deeper live context, but F2 showed H4/H1 + multi-horizon currency strength can be derived cheaply for the universe scan.

### 3. M15 setup quality
Require a real setup, not simply “trend is strong”:
- continuation after controlled pullback;
- breakout + hold/retest;
- liquidity sweep + reclaim/rejection;
- displacement with room to the next liquidity target.
Avoid entries that are far from M15 value/EMA or have oversized structural risk.

### 4. M5 execution trigger
M5 is required before a live MARKET entry:
- confirms continuation/reclaim/rejection;
- rejects a setup if M5 directly contradicts the H1/M15 thesis;
- helps distinguish MARKET continuation from LIMIT pullback.

M1/latest is only for final executable price refresh.

### 5. Selection / correlation gate
- Rank quality, not raw trend magnitude.
- Maximum 3 trades, but 0–2 is completely valid.
- Do not select two trades dominated by the same currency factor unless explicitly justified; default is one appearance per currency in the Top set.
- Avoid stacking equivalent USD, JPY, AUD, etc. exposure through multiple correlated pairs.

### 6. MARKET vs LIMIT
Do NOT use a rigid LIMIT distance for every trade.

Prefer MARKET when:
- H4/H1 and currency strength align;
- M15/M5 show clean continuation;
- price is not excessively chased;
- waiting for a pullback risks missing the move.

Prefer LIMIT only when:
- a controlled pullback is structurally expected;
- a clear M15 S/R, EMA/VWAP, FVG/OB or retracement zone exists;
- the order has a cancellation/expiry condition;
- better entry meaningfully improves RR without invalidating the thesis.

F2 confirms the same execution lesson seen in crypto: a better LIMIT price can improve effective RR but can also miss a real continuation winner.

### 7. SL and RR
- Structural invalidation first; ATR is only a buffer/floor.
- Never choose SL from a desired lot size.
- Do not hard-code RR 2.1 just because it won the F2 development grid.
- Practical default: require at least about 1.5R room; prefer roughly 1.8–2.1R when the next real liquidity/structure target supports it; use a smaller realistic RR rather than placing TP beyond structure.
- If the structure cannot support a worthwhile RR, `NO TRADE`.

### 8. News gate
Before live entry, check high-impact events relevant to either currency. CPI, NFP, central-bank decisions/speeches, employment and inflation data can invalidate a purely technical entry. Do not open blindly into red-impact events.

## Twelve Data efficiency plan
Research proved that separate D1/H4/H1/M15 calls are unnecessary for the universe scan.

Preferred staged design:
1. Universe scan: one M15 `/time_series` per pair = 28 symbol credits; batch into groups while respecting the plan's per-minute quota.
2. Derive 6h/24h/72h strength and H1/H4 locally from that M15 history.
3. Fetch M5 only for the few candidates that pass the universe gate, maximum 3 under normal operation.
4. Fetch M1/latest only for pairs that are genuinely execution candidates, maximum 3.

A full 28-pair scan plus M5+M1 for three finalists therefore targets about 34 Twelve Data symbol credits rather than full multi-timeframe calls for all 28 pairs. Raw historical research dumps should not be committed.

## Risk
General discretionary default: approximately 0.25%-0.50% account risk per trade unless a prop-firm rule or user instruction specifies otherwise. Correlated exposure must be counted together.

## Live output format
For each eligible signal:
- pair + BUY/SELL;
- exact refreshed current price/source/time;
- MARKET or LIMIT and why;
- Entry;
- hard structural SL;
- TP / realistic RR;
- 6h/24h/72h currency-strength context;
- H4/H1/M15/M5 setup reason;
- macro/news gate;
- cancellation/early-exit condition;
- confidence/rank.

If nothing passes, output `NO TRADE` rather than manufacturing three positions.

## Rejected methods — do not revive without new evidence
- always force BUY/SELL on all 28 pairs as a live rule;
- always maintain exactly Top 3 regardless of quality;
- rank solely by the highest EMA/RSI/raw-strength score;
- repeated exposure to the same currency factor in the Top set;
- rigid universal RR chosen from one development sample;
- rigid LIMIT pullback on every signal;
- indicator stacking without a distinct role.

## Cross-chat rule
At a new chat, read `MASTER_TRADING_STATE.md`, `CURRENT_HANDOFF.md`, this file, then live pipeline status before issuing Forex entries.