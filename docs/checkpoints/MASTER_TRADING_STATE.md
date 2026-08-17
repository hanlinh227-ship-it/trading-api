# MASTER TRADING STATE

Updated: 2026-08-17 15:18 UTC+7
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## Cross-chat protocol
Read this file first, then `CURRENT_HANDOFF.md`, then `CROSSMARKET_80WR_OFFLINE_AUDIT.md`, then the market-specific checkpoint. Do not reconstruct strategy state from memory when checkpoints exist. Never promote a method from one lucky sample; never present stale prices as executable live prices.

## Universal rules
- Regime/bias -> structure -> setup -> execution -> structural SL -> realistic TP.
- Indicators must have distinct roles; avoid stacking.
- News/macro/event risk matters for live trades.
- Structure determines invalidation first; ATR is a buffer/normalizer.
- Forced BUY/SELL on every symbol is a research stress test, not automatically a live rule.
- Score direction separately from TP/SL.
- Do not optimize win rate alone; expectancy and RR matter.
- Separate `bias wrong` from `bias right but entry/barrier failed`.
- Never shrink TP just to manufacture a high WR.
- In-sample fitted results must never be presented as held-out validation.

## Latest cross-market audit — mandatory context
The 2026-08-17 zero-provider-credit audit explicitly targeted >=80% WR with average RR >=1.0 (preferred >=1.5) using only already committed Forex/Crypto results.

**Result: target NOT validated.**
Do not claim 80% has been achieved. Any 80% produced by hindsight/cherry-picking old outcomes is rejected.

Canonical audit file:
`docs/checkpoints/CROSSMARKET_80WR_OFFLINE_AUDIT.md`

Pre-audit recovery marker:
`docs/checkpoints/archive/2026-08-17_1507_PRE_80WR_OPTIMIZATION.md`
Recovery commit: `de58e0a0ea2a6054b9c5839736be0efa80d01dce`.

Latest audit used **0 Twelve Data credits and 0 exchange market-data calls**.

## Market separation
Cash indices are not NQ/ES futures. Crypto has its own BTC/market-quality framework. Forex uses cross-currency factor/archetype logic. Metals remain separate.

## Forex — current state
Universe: all 28 liquid pairs from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

### F8 — frozen research baseline
Minimal indicators: EMA20/50, RSI14, ATR14, ADX14.
Main state variables:
- 3/6/12/24/72h cross-currency factor coherence;
- cross-sectional dispersion/rank separation;
- 8h session state;
- pair archetype;
- horizon-matched SL/TP/expiry;
- bias-vs-barrier diagnostics.

Frozen archetypes:
- USD_MAJOR -> FACTOR_BAL
- JPY_CROSS -> SESSION_SWEEP
- EUROPE_CROSS -> FACTOR_BAL
- COMMODITY_CROSS -> FACTOR_FAST
- MIXED_CROSS -> FACTOR_BAL

Four consecutive chronological 5-day frozen validation blocks:
- May18–22: MARKET +0.111R;
- May25–29: MARKET +0.338R;
- Jun01–05: MARKET +0.247R;
- Jun08–12: MARKET +0.251R.

Combined 20 trading days / 560 forced signals:
- MARKET: 489 resolved, **248 TP / 241 SL, WR 50.72%, weighted expectancy ~+0.233R**;
- LIMIT: 403 resolved, 169 TP / 234 SL, weighted expectancy ~+0.246R;
- recommended: 487 resolved, 247 TP / 240 SL, weighted expectancy ~+0.237R.

F8 remains the strongest Forex evidence and the frozen comparator. The latest offline 80WR audit did not validate a replacement.

Main remaining Forex weakness: common-factor/date-regime catastrophe risk. Jun04 remains the key revealed example: 5 TP / 22 SL, -0.565R, 19/22 SL true bias failures.

## Crypto / Breakout — current state
No validated forced all-coin live engine.

Latest zero-credit audit recovered 640 resolved trades across 12 committed historical dates:
- 229 wins / 411 losses;
- **35.78% WR**;
- mean -0.057R;
- average RR 1.639.

Regime-aware historical selectors did not generalize:
- broad V1 walk-forward: 27.08% WR, -0.268R, avg RR 1.685;
- regime-aware V3 walk-forward: 25.93% WR, -0.304R, avg RR 1.735;
- best direct in-sample V3 rule: 59.26% WR, +0.569R, avg RR 1.679, diagnostic only.

Therefore Crypto live selection must prioritize current BTC + market breadth/regime + D1/H4/H1 + M15/M5 path. Static symbol reputation is not a reliable primary gate.

## Practical live rules
### Forex
- refresh exact pair/current price;
- currency-specific macro/news context;
- frozen F8 factor/archetype state;
- H4/H1 structure;
- M15 setup;
- M5 trigger;
- structural SL / realistic liquidity target;
- setup-dependent MARKET vs LIMIT / NO TRADE.

### Crypto
- refresh exact symbol/current price and coverage;
- BTC + breadth/regime first;
- D1/H4/H1 structure and 6h/24h/72h momentum;
- M15/M5 setup and anti-chase;
- order flow only when genuinely fresh/available;
- structural SL and realistic liquidity room;
- continuation-MARKET, pullback-LIMIT, or NO TRADE.

## Provider efficiency
Forex historical work: one M15 series per 28 pairs ≈28 Twelve Data symbol credits/block, H1/H4/features derived locally. Reuse existing committed data before opening any new provider block.

## Metals / cash indices / futures
Remain separate workflows. Never substitute cash index with futures. MNQ/MES final execution uses fresh platform price when supplied.

## Handoff phrase
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md, docs/checkpoints/CURRENT_HANDOFF.md và docs/checkpoints/CROSSMARKET_80WR_OFFLINE_AUDIT.md trước, sau đó đọc checkpoint thị trường liên quan. Không được nói mục tiêu 80% đã đạt.`
