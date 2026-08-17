# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 12:22 UTC+7

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
- no WAIT / NO TRADE / LIMIT;
- entry, SL, TP freeze before future candles are opened;
- do not tune on a timestamp then call it blind.

This forced rule is a stress test only. It is no longer considered a suitable live-trading rule.

## Current conclusion: no validated all-market crypto engine
V24 remains the diagnostic comparator only.
Retained useful ingredients:
- 6h/24h/72h momentum;
- H4/H1 structure;
- H4 EMA context;
- BTC relative strength;
- M15 location/anti-chase;
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
User requested one final random all-universe test without prolonged tuning.
Before outcomes were inspected, repo search showed no April cutoff references and the random locked cutoff selected was:
- cutoff: `2026-04-09T12:00:00Z`;
- MARKET entry after a full M15 observation: `2026-04-09T12:15:00Z`.

V27 changed only timing from the V24 family:
- keep V24 direction/scoring architecture;
- wait one complete M15 before MARKET entry;
- use final 5 minutes of that M15 for taker-flow confirmation when historical flow exists;
- keep structural SL and 1.6R+ RR logic;
- still force BUY/SELL for every valid coin.

Result retained in `data/blind_backtest_v27_final.json`:
- Breakout research universe: 61 coins;
- 55 had valid historical frames and were tested;
- 6 historical-data failures: POPCAT, TAO, TON, FARTCOIN, GRASS, IP;
- 54 resolved;
- 11 TP / 43 SL;
- 1 unresolved;
- resolved WR: **20.37%**;
- avg planned RR: **1.60R**;
- expectancy: **-0.470R**;
- direction correct after 6h: **12/55 = 21.82%**;
- direction correct after 24h: **14/55 = 25.45%**.

Market context at the cutoff:
- price breadth = 0.036, an extremely bearish pre-entry breadth state;
- historical OKX taker-flow coverage at this old April timestamp was 0%, so V27 effectively tested the surviving price/structure core without usable microflow.

TP coins in this final sample:
- BTC BUY
- SOL SELL
- HYPE BUY
- TRX BUY
- ARB BUY
- ATOM BUY
- BCH SELL
- BONK SELL
- FLOKI BUY
- NEAR BUY
- WLD BUY

KAITO SELL was unresolved. All other tested symbols hit SL.

## Final research interpretation
Do NOT run another random date merely because V27 was poor; that would create selection/cherry-pick risk.

The evidence from V24 June, V26 May and V27 April now supports these conclusions:
1. forcing a position on every coin is not a robust live method;
2. changing bias ownership alone does not solve the problem;
3. simply delaying entry to +15m does not solve the problem;
4. extreme market breadth is repeatedly associated with poor forced-entry performance and should be treated as a market-quality warning, not blindly traded;
5. flow can add information when available but is not reliable enough to rescue every regime, and older historical flow coverage is limited;
6. the practical live engine should be **selective**, not forced MARKET.

## Best practical crypto evaluation framework from now on
For current/live requests:
1. refresh exact symbol and verify Breakout support;
2. evaluate BTC/market regime and breadth first;
3. analyze D1/H4/H1 structure + 6h/24h/72h momentum;
4. use M15/M5 for setup and anti-chase;
5. use actual order flow only when fresh and genuinely available;
6. calculate structural SL first;
7. require realistic liquidity room for TP/RR;
8. allow `NO TRADE / CHAOS` when breadth, volatility or two-sided whipsaw quality is poor;
9. rank/select only the strongest few setups instead of forcing all coins.

This selective live framework is now preferred over creating further forced-all-market versions unless the user explicitly asks for more research.

## Rejected methods — do not return
- generic indicator stacking;
- tiny TP to manufacture high WR;
- cosmetic RR increases;
- V25 synchronized whole-market climax reversal;
- V26 macro-always-owns-direction;
- V27 assumption that simply waiting one full M15 fixes forced-MARKET performance.

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
- `.github/workflows/blind-backtest-v24.yml`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/CRYPTO_RESEARCH_ARCHIVE.md`

Rejected/one-off V25, V26 and V27 runners should not remain active after conclusions are checkpointed; Git history preserves exact code.

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