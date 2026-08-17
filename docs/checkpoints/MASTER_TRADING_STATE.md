# MASTER TRADING STATE

Updated: 2026-08-17 (UTC+7)
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## 1. Cross-chat protocol
- At the start of a new Trading chat, read this file first, then `docs/checkpoints/CURRENT_HANDOFF.md`, then the market-specific checkpoint(s).
- Do not reconstruct strategy state from memory when checkpoints exist.
- When a material rule, API path, symbol universe, risk rule, or validation conclusion changes, update the relevant market checkpoint, CURRENT_HANDOFF, then this master file when high-level state changes.
- Never promote a method because of one unusually strong backtest; keep sample size/regime diversity explicit.
- Never present stale/web proxy prices as executable live prices. Refresh exact symbol through the active feed immediately before current-price/entry/hold/cut decisions.

## 2. Canonical checkpoint files
- `docs/checkpoints/CURRENT_HANDOFF.md`
- `docs/checkpoints/FOREX_STATE.md`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/METALS_STATE.md`
- `docs/checkpoints/CASH_INDICES_STATE.md`
- `docs/checkpoints/FUTURES_NQ_ES_STATE.md`
- `docs/checkpoints/DATA_INFRA_STATE.md`

## 3. Universal trading/research rules
- Separate market context from execution timing.
- Multi-timeframe sequence: regime/bias -> structure -> setup -> LTF trigger -> structural SL -> realistic TP/liquidity target.
- Indicators must have distinct roles; avoid redundant stacking.
- News/macro/event risk must be checked when relevant.
- Structure determines invalidation first; ATR/volatility is buffer/floor.
- Position sizing follows SL and allowed risk.
- Forced BUY/SELL on every symbol is a research stress test, not automatically a live rule.
- Direction accuracy and TP/SL outcome should be evaluated separately.
- Do not optimize WR alone; expectancy and RR matter.

## 4. Market separation
- Cash indices are NOT futures. NAS100/USTEC means Nasdaq-100 cash unless futures are explicitly requested.
- Futures NQ/ES/MNQ/MES are separate instruments.
- Crypto Breakout availability must be verified; exchange availability alone is insufficient.
- Forex uses a separate cross-currency framework; do not import crypto BTC breadth/order-flow logic into Forex.

## 5. Current high-level status

### Forex — active forced-blind method research
Universe: 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

Current research benchmark:
- no Top-3 selection;
- every valid pair gets BUY or SELL at each blind cutoff;
- score direction 6h/12h/24h plus TP/SL outcome;
- TP/SL may be dynamic rather than fixed RR;
- revealed blind blocks become development data forever.

Minimal stack:
- EMA20/50 = trend/value/slope;
- RSI14 = momentum/exhaustion;
- ATR14 = volatility/SL normalization;
- ADX14 = regime/trend-vs-chop;
- 6h/24h/72h cross-currency strength.

Currency-specific live macro profiles remain required: USD Fed/PCE-CPI/labour/yields; EUR ECB/HICP/wages-services/energy-growth; GBP BoE/CPI-services/wages/growth; JPY BoJ/JGB/carry/MOF intervention; CHF SNB/inflation/risk-off/intervention; CAD BoC/jobs-CPI/oil/US trade-growth; AUD RBA/inflation/labour/China-commodities-risk; NZD RBNZ/CPI/spare-capacity/dairy-global rates.

#### F1-F3 compressed
- F1 naive strongest-score Top3 rejected.
- F2 selective four-trade sample looked strong but was too small.
- F3 new holdout failed to confirm F2; forced RR1.8 = 44 TP / 84 SL from 128 resolved, -0.037R.

#### F4 pair-adaptive forced blind
Jul17/20/21/22/24, 140 signals:
- MARKET 49 TP / 73 SL, expectancy -0.081R, avg RR 2.055;
- LIMIT 40 TP / 70 SL, expectancy -0.018R, avg effective RR 2.699;
- direction12/24 53.57%/53.57%.
Conclusion: modest directional edge, LIMIT nearly break-even but not robust.

#### F5 — rejected
Jul27/28, 56 forced signals:
- MARKET 12 TP / 43 SL, WR 21.82%, -0.383R;
- LIMIT 10 TP / 42 SL, -0.362R;
- direction12/24 32.14%/32.14%;
- 36/43 SL were also wrong at 24h.
Conclusion: genuine bias failure; LONGHORIZON/economic-target changes did not solve it.

#### F6 rotation — unexercised
May11–15, same 140-signal baseline vs F6:
- predeclared rotation gate never triggered; overrides=0;
- F6 therefore equaled baseline: MARKET 33 TP / 88 SL, -0.208R; direction12 55%, direction24 52.86%.
Do not loosen thresholds on May and call the same block blind.

#### Parallel dual-horizon — negative aggregate
Jun24/Jun30/Jul02/Jul07/Jul10:
- MARKET 44 TP / 70 SL from 114 resolved, -0.119R;
- LIMIT 20 TP / 65 SL, -0.254R;
- aggregate direction ~51%.
Do not cherry-pick individual pair winners.

#### F7 five-vote consensus — partial improvement only
Unseen historical Apr20–24 comparator; same 140 signals baseline vs F7. Not pure chronological walk-forward because the baseline was developed using later 2026 data.

F7 majority vote sources: 6h/24h/72h cross-currency strength + H4 trend + H1 trend. Barriers unchanged.

Baseline same block:
- MARKET 27 TP / 100 SL, expectancy -0.258R;
- LIMIT 22 TP / 100 SL, expectancy -0.241R;
- direction12 41.43%, direction24 50.00%, avg signed 24h move -0.420 ATR.

F7:
- 13 direction overrides;
- MARKET 27 TP / 102 SL, WR 20.93%, avg RR 2.661, expectancy -0.150R;
- LIMIT 23 TP / 102 SL, avg effective RR 3.383, expectancy -0.054R;
- direction12 42.14%, direction24 50.71%, avg signed 24h move +0.059 ATR;
- 35/102 SL later correct at 24h; 67 remained wrong direction24.

Conclusion:
- F7 improves expectancy materially vs the exact same baseline, especially LIMIT, but directional accuracy barely improves and the method remains negative;
- F7 consensus is a candidate component only, NOT a validated winning engine;
- regime instability remains extreme: Apr23 positive, Apr24 catastrophic.

### Next Forex research direction
Do NOT add more indicators. The next genuine hypothesis should be a market-day/common-factor regime layer:
- common USD/risk/carry factor;
- cross-sectional breadth/dispersion;
- synchronized trend vs rotation/chop;
- still force every pair BUY/SELL in benchmark, but let regime alter directional weights/barriers;
- compare new method and baseline on the same untouched block;
- keep separating bias failure vs later-correct path/barrier failure.

### Crypto / Breakout — practical style frozen
- Direct exchange data through GitHub runner preferred over Twelve Data.
- Route: Binance -> OKX -> Bybit.
- No validated forced all-market crypto engine.
- V24 diagnostic; V25/V26/V27 rejected as documented.
- Live framework remains selective: BTC/market-quality first, D1/H4/H1 + short momentum, M15/M5, fresh order flow only when available, structural SL, realistic RR, MARKET-vs-LIMIT by setup, explicit NO TRADE/CHAOS.

### Metals
Separate XAUUSD/XAGUSD workflow: H4/H1 bias; M15/M5 setup; M1 final timing/price refresh; DXY/US yields/Fed/high-impact news context.

### Cash indices
Cash indices only by default. Never substitute futures when entitlement blocks a cash-index symbol.

### Futures NQ/ES
Separate system, only when explicitly requested. Prefer MNQ/MES micros; structural SL first, then size to roughly USD 500 max risk and ~USD 1,500 target when ~1:3 structure supports it.

## 6. Twelve Data efficiency
- one M15 series for each of 28 pairs ≈ 28 symbol credits per historical block;
- derive H1/H4, EMA/RSI/ATR/ADX and strength locally;
- reuse cached data for model comparators;
- workflows share `twelvedata-api` concurrency and cooldown to avoid HTTP 429.

## 7. Live execution quality gate
Before a current MARKET entry:
1. exact symbol refreshed now;
2. requested symbol == returned symbol;
3. timestamp/source freshness validated;
4. relevant context/timeframes available;
5. no stale/execution-ready failure;
6. structure and invalidation identified;
7. relevant news/event risk checked;
8. Entry/SL/TP/RR calculated from refreshed price.

## 8. Handoff phrase
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`
