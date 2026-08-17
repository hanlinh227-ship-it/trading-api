# MASTER TRADING STATE

Updated: 2026-08-17 (UTC+7)
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## Cross-chat protocol
Read this file first, then `CURRENT_HANDOFF.md`, then the market-specific checkpoint. Do not reconstruct strategy state from memory when checkpoints exist. Never promote a method from one lucky sample; never present stale prices as executable live prices.

## Universal rules
- Regime/bias -> structure -> setup -> execution -> structural SL -> realistic TP.
- Indicators must have distinct roles; avoid stacking.
- News/macro/event risk matters for live trades.
- Structure determines invalidation first; ATR is a buffer/normalizer.
- Forced BUY/SELL on every symbol is a research stress test, not automatically a live rule.
- Score direction separately from TP/SL.
- Do not optimize win rate alone; expectancy and RR matter.

## Market separation
Cash indices are not NQ/ES futures. Crypto has its own BTC/market-quality framework. Forex uses cross-currency factor/archetype logic. Metals remain separate.

## Forex — current high-level state
Universe: 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

Research benchmark:
- all valid pairs forced BUY/SELL at each blind cutoff;
- no Top-3/NO-TRADE in benchmark;
- direction checked at chosen/3h/6h/12h/24h;
- TP/SL dynamic/horizon-matched;
- revealed blind blocks become development data forever.

Minimal indicators:
- EMA20/50;
- RSI14;
- ATR14;
- ADX14.

Main non-indicator state:
- 3/6/12/24/72h cross-currency factor coherence;
- cross-sectional dispersion/rank separation;
- 8h session breakout/sweep/location;
- pair archetype;
- bias-vs-barrier diagnostics.

### Rejected/diagnostic lineage
F1 strongest-score selection rejected. F2 sample too small. F3 failed to confirm F2. F4 near break-even but not robust. F5 true bias failure and rejected. F6 rotation gate was not exercised. F7 five-vote consensus improved expectancy but remained negative. See `FOREX_STATE.md` for exact metrics.

### F8 — strongest current research baseline candidate
F8 uses strict walk-forward development Apr27–May15 and five frozen pair archetypes:
- USD_MAJOR -> FACTOR_BAL
- JPY_CROSS -> SESSION_SWEEP
- EUROPE_CROSS -> FACTOR_BAL
- COMMODITY_CROSS -> FACTOR_FAST
- MIXED_CROSS -> FACTOR_BAL

Holdout1 May18–22, 140 forced signals:
- MARKET 58 TP /69 SL from 127 resolved, WR45.67%, **+0.111R**;
- LIMIT **+0.030R**;
- direction6/12/24 = 67.14% /66.43% /61.43%;
- avg RR 1.448.

F8 was then frozen completely. Holdout2 May25–29, another 140 forced signals:
- MARKET 61 TP /50 SL from 111 resolved, WR54.95%, **+0.338R**;
- LIMIT 45 TP /48 SL from 93 resolved, **+0.435R**;
- recommended 60 TP /50 SL, **+0.333R**;
- chosen direction 68.57%, 3h 71.43%; avg RR1.447.

Combined 10 chronological holdout days / 280 forced signals:
- MARKET: 238 resolved, **119 TP /119 SL = 50.00% WR**, weighted expectancy ~**+0.217R**;
- LIMIT: 194 resolved, 80 TP /114 SL, weighted expectancy ~**+0.224R**;
- recommended: 237 resolved, 118 TP /119 SL, weighted expectancy ~**+0.214R**;
- combined chosen-direction 60.36%, 3h61.79%, 6h60.36%, 12h60.00%, 24h57.50%.

This is the first Forex method with positive expectancy across two consecutive chronological frozen holdouts. Promote F8 to **research baseline candidate**, not to guaranteed live auto-trading.

Group evidence:
- COMMODITY_CROSS remained strong in both holdouts; holdout2 +0.679R.
- MIXED_CROSS holdout2 +0.474R.
- JPY_CROSS holdout2 +0.394R.
- EUROPE_CROSS recovered to +0.420R after weak holdout1; do not modify it yet.
- USD_MAJOR remains the clearest weakness: holdout1 -0.131R, holdout2 +0.006R MARKET. This is the next focused research target.

Next step: freeze successful F8 groups, change only USD_MAJOR with one interpretable USD-specific component, and compare modified engine vs frozen F8 on the same untouched full 28-pair June holdout. June1–5 08:00 UTC were repo-searched absent before any such test.

## Forex live context
Forced-all-pair research success is not a mandate to trade all pairs live. Live analysis still requires fresh exact price, currency-specific macro/news context, F8 factor/archetype state, H4/H1 structure, M15 setup, M5 trigger, M1/latest execution refresh, structural SL and setup-dependent MARKET/LIMIT.

## Twelve Data efficiency
One M15 series per 28 pairs ≈28 symbol credits/block; derive H1/H4/features locally and reuse data. Workflows share quota concurrency + cooldown.

## Crypto / Breakout
Practical style remains frozen/selective; direct exchange route Binance -> OKX -> Bybit preferred. No validated forced all-coin live engine.

## Metals / cash indices / futures
Remain separate workflows. Never substitute cash index with futures. MNQ/MES final execution uses fresh platform price when supplied.

## Handoff phrase
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`
