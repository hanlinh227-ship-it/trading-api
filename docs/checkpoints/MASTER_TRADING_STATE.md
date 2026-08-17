# MASTER TRADING STATE

Updated: 2026-08-17 (UTC+7)
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## 1. Cross-chat protocol
- At the start of a new Trading chat, read this file first, then `docs/checkpoints/CURRENT_HANDOFF.md`, then the market-specific checkpoint(s).
- Do not reconstruct strategy state from memory when checkpoints exist.
- When a material rule, API path, symbol universe, risk rule, or validation conclusion changes, update the relevant market checkpoint, CURRENT_HANDOFF, then this master file when high-level state changes.
- Never promote a method because of one unusually strong backtest; keep sample size/regime diversity explicit.
- Never present stale/web proxy prices as executable live prices. Refresh the exact symbol through the active feed immediately before current-price/entry/hold/cut decisions.

## 2. Canonical checkpoint files
- `docs/checkpoints/CURRENT_HANDOFF.md`
- `docs/checkpoints/FOREX_STATE.md`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`
- `docs/checkpoints/METALS_STATE.md`
- `docs/checkpoints/CASH_INDICES_STATE.md`
- `docs/checkpoints/FUTURES_NQ_ES_STATE.md`
- `docs/checkpoints/DATA_INFRA_STATE.md`

## 3. User operating preferences
- Default response language: Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file.
- Be concise and execution-oriented while preserving exact price/time/source, Entry/SL/TP/RR and validation caveats when relevant.

## 4. Universal analysis rules
- Separate market context from execution timing.
- Multi-timeframe sequence: regime/bias -> structure -> setup -> LTF trigger -> structural SL -> realistic TP/liquidity target.
- Indicators must have distinct roles; avoid redundant stacking.
- News/macro/event risk must be checked when relevant.
- Structure determines invalidation first. ATR/volatility is a buffer/floor, not a reason to invent SL.
- Position sizing follows SL and allowed risk.
- Forced BUY/SELL on every symbol is diagnostic stress testing only, not a live rule.
- `NO TRADE` is valid and preferred when quality is insufficient.

## 5. Market separation
- Cash indices are NOT futures. NAS100/USTEC means Nasdaq-100 cash unless futures are explicitly requested.
- Futures NQ/ES/MNQ/MES are separate instruments.
- Crypto Breakout availability must be verified; exchange availability alone is not enough.
- Forex uses a separate cross-currency framework; do not import crypto BTC breadth/order-flow logic into Forex.

## 6. Current high-level status

### Forex — active research / selective framework
Universe: 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

Current minimal technical core:
- EMA20/50: trend/value/slope;
- RSI14: momentum/exhaustion;
- ATR14: SL/chase normalization;
- ADX14: trend-vs-chop quality;
- 6h/24h/72h cross-currency strength.

Currency-specific live macro profiles are required:
- USD Fed/PCE-CPI/labour/yields;
- EUR ECB/HICP/wages-services/energy-growth;
- GBP BoE/CPI-services/wages/growth;
- JPY BoJ/wages-CPI/JGB/carry/MOF intervention;
- CHF SNB/inflation/risk-off/intervention;
- CAD BoC/CPI-jobs/oil/US trade-growth;
- AUD RBA/trimmed inflation/labour/China-commodities-risk;
- NZD RBNZ/CPI/spare capacity-labour/dairy-global rates.

F1 July diagnostic:
- forced RR1.5: 55 TP / 81 SL from 136 resolved, 40.44%, +0.011R;
- naive Top3 strongest-score: 4 TP / 11 SL, -0.333R;
- raw strongest-score selection rejected.

F2 blind Aug04/05/06/10/11:
- forced RR2.1: 38 TP / 88 SL from 126 resolved, -0.065R;
- selective MARKET: only 4 signals, 3 TP / 1 SL, 75% WR, +1.325R;
- four trades are too few to claim stable 75%.

F3 blind holdout locked before outcomes: Jul31, Aug03, Aug07, Aug12, Aug14 at 08:00 UTC.
Baseline RR1.8:
- all 28 pairs evaluated across five dates = 140 forced signals;
- forced: 128 resolved, 44 TP / 84 SL, 34.38% WR, -0.037R;
- selective gate: only 3 signals;
- MARKET: 1 TP / 1 SL + 1 timeout, 50% resolved WR, +0.400R;
- LIMIT: 3 fills, 1 TP / 1 SL + 1 timeout, avg effective RR 3.445, +0.899R among resolved;
- HYBRID: 1 TP / 1 SL + 1 timeout, +0.400R.

Predeclared RR2.1 F3:
- forced: 39 TP / 89 SL from 128 resolved, -0.055R;
- selective MARKET: 1 TP / 1 SL + 1 timeout, +0.550R;
- selective LIMIT avg effective RR 3.921, +1.103R among resolved.

Current Forex conclusion:
- F3 does not confirm F2's apparent 75% win rate; no stable Forex WR claim is justified yet.
- LIMIT improves payoff geometry but has not proven a hit-rate advantage.
- Forced all-pair trading remains negative expectancy.
- Continue with selective quality gate + `NO TRADE`; do not add more overlapping indicators or flip bias formulas.
- Research baseline RR ~1.8; stretch ~2.1 only when real structure/liquidity supports it.
- Active retained research: `scripts/blind_backtest_forex_f2.py`, `data/blind_backtest_forex_f2.json`, `scripts/blind_backtest_forex_f3.py`, `data/blind_backtest_forex_f3.json`.

Forex live execution style:
1. 6h/24h/72h currency strength across 28 pairs.
2. Currency-specific live macro/news gate.
3. H4/H1 structure + EMA slope.
4. ADX rejects chop; RSI checks momentum/exhaustion; ATR normalizes risk/chase.
5. M15 real setup + structural invalidation.
6. M5 live trigger.
7. Correlation control; output 0–3 trades.
8. MARKET for clean continuation; LIMIT only for expected pullback with expiry/cancel condition.
9. Exact M1/latest refresh before executable entry.

### Crypto / Breakout — practical style frozen
- Direct exchange data through GitHub runner preferred over Twelve Data.
- Route: Binance -> OKX -> Bybit.
- No validated forced all-market crypto engine.
- V24 diagnostic; V25/V26/V27 rejected as documented.
- Live direction remains selective: BTC/market-quality first, D1/H4/H1 + short momentum, M15/M5, fresh order flow only when available, structure SL, realistic RR, MARKET-vs-LIMIT by setup, explicit `NO TRADE / CHAOS`.

### Metals
- XAUUSD/XAGUSD separate workflow.
- H4/H1 bias; M15/M5 setup; M1 final timing/price refresh. Use structure, EMA, RSI, VWAP/Volume Profile/SR where available plus DXY/US yields/Fed/high-impact US news.

### Cash indices
- Cash indices only by default: Nasdaq-100, S&P 500, Dow, Nikkei 225, DAX and supported cash indices.
- Never substitute futures when entitlement blocks a cash-index symbol.

### Futures NQ/ES
- Separate system, only when explicitly requested.
- Prefer MNQ/MES micros; structural SL first, then size to about USD 500 max risk and roughly USD 1,500 target when ~1:3 structure supports it.
- User/platform realtime MNQ/MES price has priority for final execution when supplied.

## 7. Twelve Data efficiency
Forex staged architecture:
- universe scan: one M15 series per 28 pairs = 28 symbol credits;
- derive H1/H4, EMA/RSI/ATR/ADX and strength locally;
- M5 only for up to 3 finalists;
- M1/latest only for executable finalists;
- target about 34 symbol credits for a full scan with three finalists.

## 8. Live execution quality gate
Before issuing a current MARKET entry:
1. exact symbol refreshed now;
2. requested symbol == returned symbol;
3. timestamp/source freshness validated;
4. relevant context/timeframes available;
5. no stale/execution-ready failure;
6. structure and invalidation identified;
7. relevant news/event risk checked;
8. Entry/SL/TP/RR calculated from refreshed price.

## 9. Handoff phrase
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`
