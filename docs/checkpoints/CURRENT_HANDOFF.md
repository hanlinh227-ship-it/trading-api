# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 12:36 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint. Do not reconstruct strategy state from memory when checkpoints exist.

## User operating preferences
- Respond in Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file.
- Never call stale/web proxy prices executable/live. Refresh exact symbol before current entry/hold/cut decisions.
- Keep cash indices separate from NQ/ES futures.
- Structure defines SL first; size/RR follows.

## Immediate active task
Crypto / Breakout research and live-selection quality.

## Forced blind benchmark rule
When explicitly stress-testing:
- every Breakout-universe coin with valid historical data receives MARKET BUY or MARKET SELL;
- no WAIT / NO TRADE unless the user explicitly asks to test the selective live gate;
- entry, SL, TP freeze before future candles are opened;
- do not tune on a timestamp then call it blind.

This forced rule is a stress test only. It is not considered a suitable live-trading rule.

## Current conclusion: no validated all-market crypto engine
V24 remains the diagnostic comparator only.
Retained useful ingredients:
- 6h/24h/72h momentum;
- H4/H1 structure;
- H4 EMA context;
- BTC relative strength;
- M15/M5 setup and anti-chase;
- actual short-window taker flow when available;
- market breadth context;
- structure-based SL;
- realistic dynamic RR.

### V24 locked June validation
- 278 trades, 262 resolved;
- 112 TP / 150 SL;
- 42.75% WR;
- avg RR 1.647;
- +0.132R expectancy;
- extreme date instability from Jun30 7.27% / -0.807R to Jun24 83.33% / +1.228R.
Conclusion: not robust enough for live/main promotion.

### V25 — rejected
Whole-market climax reversal was tested on June development data.
Jun30 became 0 TP / 56 SL. Do not revive synchronized whole-market reversal.

### V26 — rejected true-blind May
Macro-always-owns-direction failed on untouched May:
- 275 trades, 272 resolved;
- 79 TP / 193 SL;
- 29.04% WR;
- avg RR 1.646;
- -0.235R expectancy;
- 4/5 dates negative.
Conclusion: macro direction cannot be made absolute.

## V27 FINAL random blind — completed and rejected
Locked cutoff: `2026-04-09T12:00:00Z`; MARKET entry after full M15 at `12:15 UTC`.
V27 kept V24 direction/scoring and changed timing only.
Result retained in `data/blind_backtest_v27_final.json`:
- 55 tested of 61 research-universe coins;
- 11 TP / 43 SL / 1 unresolved;
- WR 20.37%;
- avg RR 1.60R;
- expectancy -0.470R;
- direction 6h accuracy 21.82%;
- direction 24h accuracy 25.45%;
- price breadth 0.036;
- historical taker-flow coverage 0%.
Conclusion: simply waiting one M15 does not fix a bad market-state/directional sample.

## Final MARKET vs LIMIT blind execution comparison — Apr16
User then explicitly asked to compare MARKET and LIMIT on all Breakout research coins using the settled surviving framework.
Before outcomes were inspected, repo search confirmed no prior `2026-04-16` cutoff reference. Rules were frozen before the run:
- observation starts `2026-04-16T12:00:00Z`;
- signal/entry decision after one complete M15 at `2026-04-16T12:15:00Z`;
- scoring inputs rebuilt at signal time using the completed M15;
- direction uses surviving V24/V22 architecture: 6h/24h/72h momentum, H4/H1 structure, H4 EMA, BTC relative strength, breadth, and final-5m taker flow if historically available;
- MARKET enters immediately at observable +15m price;
- LIMIT is fixed at a 0.35R pullback toward the same structural SL;
- LIMIT expires after 6h;
- LIMIT keeps the same absolute TP as MARKET, so a filled limit naturally has a higher effective RR;
- if MARKET TP is hit before LIMIT fills, cancel LIMIT as `TARGET_BEFORE_FILL` rather than allowing a late fill.

Result retained: `data/final_market_vs_limit_blind.json`.
Historical-data coverage:
- universe 61;
- tested 55;
- same 6 failures: POPCAT, TAO, TON, FARTCOIN, GRASS, IP;
- historical taker-flow coverage 0% at this old timestamp.

Market context:
- price breadth 0.964, strongly bullish cross-market state;
- V24 regime classifier returned normal because old historical flow was unavailable.
Important nuance: extreme breadth alone must NOT be treated as an automatic no-trade veto. April16 was extreme bullish breadth yet direction was strong; breadth must interact with structure/continuation/whipsaw quality.

### MARKET result
- 55 trades;
- 52 resolved;
- 27 TP / 25 SL;
- 3 unresolved;
- WR resolved 51.92%;
- expectancy +0.350R;
- direction 6h accuracy 80.00%;
- direction 24h accuracy 89.09%;
- first 0.5R move favorable on 42 coins, adverse on 12, neither on 1.

Critical barrier lesson:
- around 20 of the 25 MARKET SL trades still finished in the predicted direction after 24h;
- therefore many SLs were caused by adverse excursion / whipsaw before the later directional move, not simply wrong bias.
This reinforces market-quality + barrier geometry + entry-path analysis.

### LIMIT 0.35R result
- 55 pending orders;
- 42 filled = 76.36% fill rate;
- 3 reached MARKET TP before LIMIT could fill;
- 10 did not fill within 6h;
- among 42 fills: 40 resolved, 19 TP / 21 SL, 2 unresolved;
- WR among resolved fills 47.50%;
- effective RR averaged 3.00R because the same structural SL and absolute TP were kept from a 0.35R better entry;
- expectancy among resolved filled trades +0.900R.

Interpretation:
- LIMIT did NOT improve hit rate versus MARKET; filled-limit WR was lower (47.5% vs 51.92%).
- LIMIT improved payoff geometry dramatically when filled: ~3R versus 1.6R base MARKET in this no-flow sample.
- LIMIT missed 8 MARKET winners: ARB, MOODENG, OP, ORDI, TIA never pulled back 0.35R within 6h; KAITO, TRUMP, AIXBT hit MARKET TP before the LIMIT could fill.
- LIMIT avoided 4 MARKET SL trades by never filling within 6h: FIL, JTO, WIF, XPL.
- DOT was MARKET unresolved and LIMIT not filled.
- Among filled orders there was no evidence that 0.35R pullback itself turns a MARKET loser into a winner when the same structural SL is retained; if price pulls through the limit and continues to the same SL, both executions lose.

## Best practical crypto evaluation framework from now on
For current/live requests:
1. refresh exact symbol and verify Breakout support;
2. evaluate BTC/market regime and breadth first;
3. analyze D1/H4/H1 structure + 6h/24h/72h momentum;
4. use M15/M5 for setup and anti-chase;
5. use actual order flow only when fresh and genuinely available;
6. calculate structural invalidation first;
7. compare MARKET versus pullback execution when the setup allows it;
8. require realistic liquidity room for TP/RR;
9. allow `NO TRADE / CHAOS` when price path, volatility or two-sided whipsaw quality is poor;
10. rank/select only the strongest few setups instead of forcing all coins.

Execution lesson from Apr16:
- MARKET is preferable when continuation is strong and waiting 0.35R would miss the move;
- LIMIT is preferable only when a pullback is structurally expected and the improved RR compensates for missed fills;
- do not blindly place the same 0.35R LIMIT on every signal;
- the next meaningful improvement should distinguish **continuation MARKET setups** from **pullback LIMIT setups** before entry, rather than changing bias formulas again.

## Rejected methods — do not return
- generic indicator stacking;
- tiny TP to manufacture high WR;
- cosmetic RR increases without a better entry thesis;
- V25 synchronized whole-market climax reversal;
- V26 macro-always-owns-direction;
- V27 assumption that simply waiting one full M15 fixes forced-MARKET performance;
- treating extreme breadth alone as an automatic reversal or automatic no-trade rule.

## Active crypto evidence to preserve
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- `data/blind_backtest_v24_validation.json`
- `data/blind_backtest_v26.json`
- `data/blind_backtest_v27_final.json`
- `data/final_market_vs_limit_blind.json`
- `.github/workflows/blind-backtest-v24.yml`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`

One-off MARKET-vs-LIMIT runner/workflow should be removed after this conclusion is checkpointed; Git history preserves exact code.

## Other markets
- Forex Top-3 remains PAUSED until explicitly re-enabled.
- Metals use separate XAUUSD/XAGUSD workflow.
- Cash indices are never silently substituted with futures.
- NQ/ES futures remain a separate MNQ/MES workflow.

## Infrastructure
Repo: `hanlinh227-ship-it/trading-api`.
Crypto live route: Binance -> OKX -> Bybit. Do not spend Twelve Data credits on crypto when direct exchange REST works.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`