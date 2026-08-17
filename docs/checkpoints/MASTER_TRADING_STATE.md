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

## Forex — current state
Universe: all 28 liquid pairs from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

Forced research benchmark:
- all valid pairs BUY/SELL;
- no Top3/NO-TRADE;
- chosen/3h/6h/12h/24h direction scored separately from TP/SL;
- revealed blocks become development forever;
- new method must beat frozen baseline on the same untouched block.

Minimal indicators:
- EMA20/50;
- RSI14;
- ATR14;
- ADX14.

Main state variables:
- 3/6/12/24/72h cross-currency factor coherence;
- cross-sectional dispersion/rank separation;
- 8h session state;
- pair archetype;
- horizon-matched SL/TP/expiry;
- bias-vs-barrier diagnostics.

### F8 — frozen research baseline
Archetypes:
- USD_MAJOR -> FACTOR_BAL
- JPY_CROSS -> SESSION_SWEEP
- EUROPE_CROSS -> FACTOR_BAL
- COMMODITY_CROSS -> FACTOR_FAST
- MIXED_CROSS -> FACTOR_BAL

F8 has now remained positive across **four consecutive chronological 5-day blocks without changing the engine**:
- May18–22: MARKET +0.111R;
- May25–29: MARKET +0.338R;
- Jun01–05: MARKET +0.247R;
- Jun08–12: MARKET +0.251R.

Combined 20 trading days / 560 forced signals:
- MARKET: 489 resolved, **248 TP /241 SL**, WR **50.72%**, weighted expectancy ~**+0.233R**;
- LIMIT: 403 resolved, 169 TP /234 SL, weighted expectancy ~**+0.246R**;
- recommended: 487 resolved, 247 TP /240 SL, weighted expectancy ~**+0.237R**.

Combined direction across 560 signals:
- chosen 58.57%;
- 3h 59.64%;
- 6h 55.36%;
- 12h 55.54%;
- 24h 53.21%.

F8 is the strongest Forex evidence so far and the frozen comparator for future research. It is not a guarantee and not a live auto-trade mandate.

### Recent attempted improvements
- F9 three-horizon: positive but inferior to F8 on same May25–29 block; reject as replacement.
- F10 USD_MID: development advantage did not meet its frozen selection margin; F8 remained unchanged and USD_MAJOR later performed +0.399R on Jun01–05.
- F10 leave-one-pair-out factor isolation: +0.239R vs F8 +0.247R on same Jun01–05, direction unchanged; reject.
- F11 day-conflict MID_FACTOR: all development thresholds activated zero days, selectedThreshold=null, so Jun08–12 remained frozen F8 and produced +0.251R MARKET. Do not lower thresholds on revealed data.

### Main remaining Forex weakness
Catastrophic common-factor/date-regime failure, not one consistently weak pair group.
Key revealed example Jun04:
- 5 TP /22 SL;
- MARKET -0.565R;
- direction12/24 21.43%;
- 19/22 SL true bias-wrong.

Next valid research must freeze one interpretable common-factor/day-regime hypothesis, then compare it with F8 on the same new untouched full 28-pair block. Do not add redundant indicators.

### Live Forex
Forced benchmark is research only. Live entries still require:
- fresh exact pair price;
- currency-specific macro/news drivers;
- F8 factor/archetype state;
- H4/H1 structure;
- M15 setup;
- M5 trigger;
- structural SL / realistic liquidity target;
- setup-dependent MARKET vs LIMIT.

### Twelve Data efficiency
One M15 series per 28 pairs ≈28 symbol credits/block. Derive H1/H4/features locally and reuse data. Workflows share quota concurrency + cooldown.

## Crypto / Breakout
Practical framework remains frozen/selective; direct exchange route Binance -> OKX -> Bybit preferred. No validated forced all-coin live engine.

## Metals / cash indices / futures
Remain separate workflows. Never substitute cash index with futures. MNQ/MES final execution uses fresh platform price when supplied.

## Handoff phrase
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan.`
