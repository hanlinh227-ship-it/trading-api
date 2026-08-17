# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 12:02 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint(s). Do not reconstruct strategy state from memory when checkpoints exist.

## User operating preferences
- Respond in Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file, not only a diff/snippet.
- Never call a stale/web proxy price executable/live. Refresh the exact requested symbol through the active feed immediately before current entry/hold/cut decisions.
- Keep cash indices separate from NQ/ES futures.
- Structure defines SL first; position size/RR follows.

## Immediate active task
Crypto / Breakout method research. Goal: improve win rate and RR without violating strict blind integrity.

Forced blind stress rules:
- every valid Breakout-universe coin gets MARKET BUY or MARKET SELL;
- no WAIT / NO TRADE / LIMIT inside the forced benchmark;
- decision, entry, SL and TP freeze before future candles are revealed;
- SL/TP are coin/setup-specific and structure/volatility-aware;
- never tune on a timestamp and then call that same timestamp true blind.

## Current best status
There is **no validated main/live crypto engine** yet.

V24-Core remains the diagnostic comparator:
- 6h/24h/72h momentum;
- H4/H1 structure;
- H4 EMA context;
- BTC relative strength;
- M15 location/anti-chase;
- first-5m OKX taker flow;
- market price/flow breadth context;
- structural SL;
- dynamic roughly 1.6R–1.95R.

V24 initial Jul04/Jul02 evidence was exceptionally strong, but unchanged V24 June validation exposed extreme instability:
- 278 trades, 262 resolved;
- 112 TP / 150 SL;
- 42.75% WR;
- avg RR 1.647;
- expectancy +0.132R.
Per date: Jun30 7.27% / -0.807R; Jun27 33.33% / -0.126R; Jun24 83.33% / +1.228R; Jun21 50.91% / +0.338R; Jun18 38.64% / +0.018R.
Therefore V24 is diagnostic only, not live/main.

## Critical June diagnosis
Jun30:
- 51/56 V24 decisions were SELL;
- SELL = 4 TP / 46 SL; BUY = 0/5;
- high score, trend label and macro/flow agreement did not protect performance.

V24-vs-V25 barrier comparison on Jun30 changed 51 sides:
- 46 symbols hit SL in BOTH directions;
- 0 V24-SL became V25-TP;
- 4 V24-TP became V25-SL;
- 1 unresolved became SL.
This is strong evidence of **market-quality/timing/barrier failure**, not a simple wrong-direction problem.

Jun27 had a different pattern: macro/flow agreement was better than conflict and 3/5 changed sides improved from V24-SL to V25-TP. That motivated isolated testing of macro anchoring.

## V25 development — rejected
V25 development on already-revealed June data tested:
- macro direction anchor;
- flow as confidence/RR context;
- whole-market reversal when price breadth and OFI showed synchronized extreme climax.

Result:
- 278 trades, 263 resolved, 111 TP / 152 SL;
- 42.21% WR, avg RR 1.624, +0.114R;
- Jun30 climax flip = 0 TP / 56 SL = -1R.
Conclusion: **whole-market climax reversal is rejected and must not be revived.**

## V26 locked true-blind May — completed and rejected
Before V26 was created, repository search returned no `2026-05-*` cutoff references. V26 froze exactly one conceptual change from V24:
- BUY/SELL side always follows the macro momentum/structure score;
- microflow and V24 regime context may affect confidence/RR but cannot flip side;
- V25 climax reversal excluded;
- same structural SL and RR ladder retained.

Locked May cutoffs: May30, May27, May24, May21, May18 at 12:00 UTC.
GitHub Actions run `31995597625` completed successfully and committed `data/blind_backtest_v26.json`.

True-blind result:
- 275 trades;
- 272 resolved;
- 79 TP / 193 SL;
- 3 unresolved;
- 29.04% WR;
- avg RR 1.646;
- expectancy **-0.235R**.
Per date:
- May30: 32.73% / -0.145R;
- May27: 25.93% / -0.311R;
- May24: 21.82% / -0.429R (`distribution_reversal`);
- May21: 43.64% / +0.163R;
- May18: 20.75% / -0.460R.
Four of five dates were negative. **Macro-always-owns-direction is rejected as a general solution.** The Jun27 development improvement did not generalize.

May is now development/diagnostic data and must never again be counted as unseen validation for a successor.

## V26 May diagnostic — completed
Breadth buckets:
- <=0.10: 107 resolved, 25 TP / 82 SL, 23.36% WR, -0.385R;
- 0.30–0.70: 55 resolved, 24 TP / 31 SL, 43.64%, +0.163R;
- 0.70–0.90: 32.73%, -0.145R;
- >=0.90: 21.82%, -0.429R.
Extreme breadth is therefore a **risk marker to investigate**, not a finalized filter/threshold because this is only five date-level samples.

Flow behavior on May contradicted the June simplification:
- flow aligned with macro side: 24.64% WR / -0.320R;
- conflict/neutral: 39.66% / +0.031R;
- unavailable: 26.90% / -0.301R.
Do not hard-code “flow agreement = superior” from June alone. Flow value is regime-dependent.

Barrier timing:
- overall median SL arrival ~39 M5 candles;
- median TP arrival ~70 M5 candles;
- May24 median SL ~23 candles;
- May18 median SL ~21.5 candles.
This, together with Jun30's two-sided SL behavior, shifts research away from another directional formula.

## Rejected methods — do not return
- generic/redundant indicator stacking;
- tiny TP to manufacture high WR;
- cosmetic RR increases without directional/quality improvement;
- V25 synchronized whole-market climax reversal;
- V26 macro-always-owns-direction.

## Immediate next correct research direction
Do NOT create another bias-flip version immediately.
Use the now-revealed June + May samples as development data to study **pre-entry market quality, entry timing and barrier geometry**.

Questions to answer before freezing a successor:
1. Can extreme breadth + pre-entry volatility/structure identify whipsaw/terminal conditions?
2. Does waiting/observing longer than the first 5 minutes improve barrier survival in extreme conditions while preserving forced MARKET entry later?
3. Do M5/M15 expansion, reclaim/failure, distance to structural invalidation, or opening-range behavior explain the two-sided SL states better than score direction?
4. Can a separate live-only `CHAOS / NO TRADE` quality gate be defined from pre-entry information without contaminating the forced-MARKET benchmark?

Do not optimize exact breadth thresholds on May/June. Build a minimal theory-driven timing/quality hypothesis, freeze it, then test on a completely untouched block, preferably April 2026.

## Files to preserve
Core diagnostic lineage:
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- `data/blind_backtest_v24_validation.json`
- `data/blind_backtest_v26.json` temporarily as decisive negative blind evidence / next diagnostic source
- `.github/workflows/blind-backtest-v24.yml`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`

Concluded V25/V26 one-off scripts/workflows and diagnostics should be removed from the active tree after checkpointing; Git history preserves exact experiments.

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