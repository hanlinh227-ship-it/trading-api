# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 12:07 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint(s). Do not reconstruct strategy state from memory when checkpoints exist.

## User operating preferences
- Respond in Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file, not only a patch/snippet.
- Never call a stale/web proxy price executable/live. Refresh the exact requested symbol through the active feed immediately before current entry/hold/cut decisions.
- Keep cash indices separate from NQ/ES futures.
- Structure defines SL first; position size/RR follows.

## Immediate active task
Crypto / Breakout research. Goal: improve win rate and RR while preserving strict blind integrity.

Forced blind stress rules remain:
- every valid Breakout-universe coin gets MARKET BUY or MARKET SELL;
- no WAIT / NO TRADE / LIMIT inside the forced benchmark;
- decision, entry, SL and TP freeze before future candles are revealed;
- SL/TP are coin/setup-specific and structure/volatility-aware;
- never tune on a timestamp and then call that same timestamp true blind.

## Current status: no validated main/live crypto engine
**V24-Core remains only the diagnostic comparator.**
Useful retained ingredients: 6h/24h/72h momentum, H4/H1 structure, H4 EMA context, BTC relative strength, M15 location/anti-chase, first-minutes OKX taker flow, market breadth/flow context, structural SL and dynamic ~1.6R–1.95R.

V24 initial Jul04/Jul02 results were exceptional, but locked unchanged June validation showed unstable generalization:
- 278 trades, 262 resolved;
- 112 TP / 150 SL;
- 42.75% WR;
- avg RR 1.647;
- +0.132R expectancy.
Per date: Jun30 7.27% / -0.807R; Jun27 33.33% / -0.126R; Jun24 83.33% / +1.228R; Jun21 50.91% / +0.338R; Jun18 38.64% / +0.018R.
Result retained: `data/blind_backtest_v24_validation.json`.

## Critical failure diagnosis
Jun30 was not simply wrong-side bias:
- V24 SELL = 4 TP / 46 SL; V24 BUY = 0/5;
- changing 51 sides in V25 produced 46 symbols that hit SL in BOTH directions;
- zero V24-SL became V25-TP;
- four V24 winners became V25 losers.
Conclusion: Jun30 is primarily **market-quality/timing/barrier failure**.

Jun27 differed: flow agreement was better than conflict and several changed sides improved, which motivated testing macro anchoring separately.

## V25 — rejected
V25 development on already-revealed June data tested macro anchoring plus a synchronized breadth+OFI whole-market climax reversal.
- 278 trades, 263 resolved, 111 TP / 152 SL;
- 42.21% WR, avg RR 1.624, +0.114R;
- Jun30 climax flip = 0 TP / 56 SL.
**Whole-market climax reversal is rejected. Do not revive it.**

## V26 locked true-blind May — rejected
Before V26 creation, repository search found no `2026-05-*` cutoff references. V26 froze one clean hypothesis: BUY/SELL always follows macro momentum/structure; flow/regime can alter confidence/RR but cannot flip side. V25 climax reversal was excluded.

Locked May result (`data/blind_backtest_v26.json`):
- 275 trades, 272 resolved;
- 79 TP / 193 SL;
- 3 unresolved;
- 29.04% WR;
- avg RR 1.646;
- expectancy **-0.235R**.
Per date:
- May30 32.73% / -0.145R;
- May27 25.93% / -0.311R;
- May24 21.82% / -0.429R (`distribution_reversal`);
- May21 43.64% / +0.163R;
- May18 20.75% / -0.460R.
Four of five dates were negative. **Macro-always-owns-direction is rejected.**
May is now development/diagnostic data and must never be reused as unseen validation.

## May diagnostic lessons
Breadth:
- <=0.10: 23.36% WR / -0.385R;
- 0.30–0.70: 43.64% / +0.163R;
- 0.70–0.90: 32.73% / -0.145R;
- >=0.90: 21.82% / -0.429R.
Extreme breadth is a **risk marker to investigate**, not a finalized threshold.

Flow was not universally confirmatory:
- aligned with macro side: 24.64% / -0.320R;
- conflict/neutral: 39.66% / +0.031R;
- unavailable: 26.90% / -0.301R.
Do not hard-code the June observation that flow agreement is always superior.

Barrier timing:
- overall median SL arrival ~39 M5 candles;
- median TP arrival ~70 M5 candles;
- May24 median SL ~23 candles;
- May18 median SL ~21.5 candles.
Together with Jun30 two-sided SL behavior, the problem has shifted from bias selection toward market quality, entry timing and barrier survival.

## Rejected methods — do not return
- generic/redundant indicator stacking;
- tiny TP used to manufacture high WR;
- cosmetic RR increases without improving the trade thesis;
- V25 synchronized whole-market climax reversal;
- V26 macro-always-owns-direction.

## Immediate next correct research direction
Do NOT create another bias-flip formula first.
Use already-revealed June + May as development data to investigate **pre-entry market quality + timing + barrier geometry** without optimizing exact thresholds to those dates.

Priority questions:
1. Can extreme breadth combined with pre-entry volatility/structure flag terminal/whipsaw states before entry?
2. Does using a natural longer observation window such as a completed M15 opening bar improve barrier survival versus the first-5m snapshot?
3. Do M5/M15 expansion, reclaim/failure, opening-range behavior or distance to structural invalidation explain two-sided SL states better than direction scores?
4. Should the live engine eventually have a separate pre-entry `CHAOS / NO TRADE` gate while forced-MARKET research continues to issue BUY/SELL?

Any successor must be minimal and theory-driven, frozen before opening future outcomes, and true-blind tested on a completely untouched block, preferably April 2026. June and May are development data from now on.

## Active crypto files after cleanup
Keep:
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- `data/blind_backtest_v24_validation.json`
- `data/blind_backtest_v26.json` — retained negative true-blind evidence / diagnostic source
- `.github/workflows/blind-backtest-v24.yml`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`

Cleanup completed: rejected V25 script/workflow/result, V24-vs-V25 comparison script/workflow, rejected V26 script/workflow, and V26 diagnostic script/workflow were removed from the active tree. Their conclusions are checkpointed and exact artifacts remain recoverable from Git history.

## Other markets
- Forex Top-3 remains PAUSED until explicitly re-enabled; see `FOREX_STATE.md`.
- Metals: XAUUSD/XAGUSD separate workflow; see `METALS_STATE.md`.
- Cash indices are cash and must never be silently replaced by NQ/ES futures; see `CASH_INDICES_STATE.md`.
- NQ/ES futures remain a separate MNQ/MES workflow; see `FUTURES_NQ_ES_STATE.md`.

## Infrastructure
Repo: `hanlinh227-ship-it/trading-api`.
Crypto route: Binance -> OKX -> Bybit; OKX has been reliable in recent research. Do not spend Twelve Data credits on crypto when direct exchange REST works.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`