# MASTER TRADING STATE

Updated: 2026-08-17 15:46 UTC+7
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## Cross-chat protocol
Read this file first, then `CURRENT_HANDOFF.md`, then `CROSSMARKET_ROLLING_BLIND_V6.md`, `TRADE_MANAGEMENT_HOURLY_V1.md`, and the market-specific checkpoint. Do not reconstruct strategy state from memory when checkpoints exist. Never promote a method from one lucky/in-sample sample; never present stale prices as executable live prices.

## Universal rules
- Regime/bias -> macro/news/calendar -> structure -> setup -> execution -> structural SL -> realistic TP -> rolling managed review.
- Indicators must have distinct roles; avoid stacking.
- News/macro/event risk matters before entry and while a trade is active.
- Structure determines invalidation first; ATR is a buffer/normalizer.
- Forced BUY/SELL on every symbol is a research stress test, not automatically a live rule.
- Score direction separately from TP/SL.
- Do not optimize win rate alone; expectancy and RR matter.
- Separate `bias wrong` from `bias right but entry/barrier failed`.
- Never shrink TP just to manufacture a high WR.
- In-sample fitted results must never be presented as held-out validation.
- CUT is excluded from displayed TP/SL WR by user convention, but CUT count/rate, CUT R and total managed expectancy must always be reported.

## Rolling blind management — mandatory interpretation
Every filled MARKET or LIMIT order is conceptually re-evaluated sequentially at H+1, H+2, H+3... using only information observable up to that review point. Decision = HOLD or CUT. This is a BACKTEST/RESEARCH mechanism, not a recurring automation.

Old committed datasets do not preserve full H+1/H+2 snapshots for every trade. Never fake hourly decisions from final outcome, MFE/MAE or later candles. Forex F8-style rows do preserve a genuine H+3 close plus `market.bars`, allowing a limited H+3 proxy. Crypto old rows do not support equivalent honest hourly replay.

Canonical latest research checkpoint:
`docs/checkpoints/CROSSMARKET_ROLLING_BLIND_V6.md`

## Requested promotion target
A new managed method is promoted only with genuinely held-out/blind evidence showing:
- TP/SL WR >=80%;
- average planned/effective RR 1.0–1.5;
- positive total expectancy including CUT;
- non-trivial sample;
- management decisions based only on observable state.

**Current status: target NOT achieved.**

## Forex — broad research baseline
Universe: all 28 liquid pairs from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

Frozen F8 remains the broad comparator. Combined four consecutive 5-day validation blocks /560 forced signals:
- MARKET: 489 resolved, 248 TP /241 SL, WR 50.72%, weighted expectancy ~+0.233R;
- LIMIT: 403 resolved, 169 TP /234 SL, weighted expectancy ~+0.246R;
- recommended: 487 resolved, 247 TP /240 SL, ~+0.237R.
F8 typical RR evidence is ~1.42–1.45.

## Forex — strongest selective-entry candidate from latest zero-credit round
V5 fixed-rule research used first chronological half as development and froze one entry rule before the later validation half.

Frozen V5 rule selected on May18–22:
- BUY only;
- score >=1;
- ADX >=20;
- impulseEvidence >=3;
- H1 aligned with side;
- group/mode unrestricted.

Development May18–22:
- 31 trades, 23W/8L = 74.19% WR;
- +0.794R;
- avg requested-band RR 1.437.

Untouched validation May25–29:
- 28 trades, 17W/11L = **60.71% WR**;
- **+0.467R**;
- avg RR **1.403**;
- positive-day rate 75%.

This is the strongest new selective-entry result in the latest round, but it does NOT replace F8 as the broad benchmark and does NOT meet 80%.

H+3 management proxy frozen on development at -0.4R made zero CUTs in V5 development and validation, so V5 validation remained 60.71%. This does not disprove H+1/H+2 management; those snapshots are missing from old data.

## Rejected latest Forex variants
- V4.1 day-by-day threshold re-selection: validation/forward selected 36.00% WR, -0.142R; rejected as unstable.
- V6 confidence Top-5/day: development 60%, validation 40%, 0.000R at RR1.5; rejected.

## Crypto — current state
Recovered old set: 640 resolved trades across 12 dates, 229W/411L = 35.78% WR. No stable selective gate has generalized.

Latest fixed-rule V5 after conservative RR cap to 1.5:
- development: 57 trades, 56.14% WR, +0.404R;
- validation: 31 trades, **19.35% WR**, -0.516R; rejected.

Latest V6 Top-K:
- development: 48 trades, 75.00% WR, +0.875R;
- validation: 48 trades, **37.50% WR**, -0.062R; rejected.

Crypto therefore remains driven by current BTC + breadth/regime + D1/H4/H1 + momentum + M15/M5 path + genuinely fresh flow/news for live analysis. Static BUY/macro/symbol reputation and fixed confidence Top-K are not validated.

## RR remap used in latest offline audit
To compare old results with requested RR 1.0–1.5 without creating winners:
- original RR <1.0 excluded;
- original RR >1.5 capped to 1.5;
- original TP above 1.5 remains TP at 1.5 because price had to cross 1.5R first;
- original SL is never converted to TP without path evidence.
This is conservative and cannot prove that all losses would still have been losses at the nearer target.

## Practical live/research design
### Forex entry
Fresh exact price; current macro/news/calendar; F8 factor/archetype; H4/H1; M15; M5; structural SL; liquidity target; V5-style selective confidence may be used as an additional candidate filter, not as proven 80% logic.

### Crypto entry
Fresh exact price/coverage; BTC + breadth/regime; macro/risk + symbol news; D1/H4/H1; 6h/24h/72h momentum; M15/M5 anti-chase; structural SL; liquidity target; MARKET/LIMIT/NO TRADE.

### After fill
Sequential H+1/H+2/H+3... rolling review when the required observable snapshots are available. HOLD/CUT must never use future information.

## Provider efficiency
Latest V4/V5/V6 research used 0 market-data provider credits. Continue to reuse committed data before any new provider block is explicitly allowed.

## Handoff phrase
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, CROSSMARKET_ROLLING_BLIND_V6.md và TRADE_MANAGEMENT_HOURLY_V1.md trước. F8 là broad Forex baseline; V5 là selective-entry candidate 60.71% WR / RR1.403; mục tiêu 80% chưa đạt.`
