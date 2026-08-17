# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 13:20 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint. Do not reconstruct strategy state from memory when checkpoints exist.

## User operating preferences
- Respond in Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file.
- Never call stale/web proxy prices executable/live. Refresh exact symbol before current entry/hold/cut decisions.
- Keep cash indices separate from NQ/ES futures.
- Structure defines SL first; size/RR follows.
- Avoid excessive indicators; each indicator must have a distinct role.

## Immediate active task
Forex analysis quality and selective live execution.

Crypto research style remains frozen at the current practical framework. Do not restart rejected crypto V25/V26/V27 ideas or force every coin into a live trade.

## Forex current state
Universe: 28 liquid pairs formed from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.

### Minimal technical core
Use only:
- EMA20/50 for trend/value/slope;
- RSI14 for momentum/exhaustion;
- ATR14 for SL/chase normalization;
- ADX14 for trend-vs-chop quality;
- 6h/24h/72h cross-currency strength from the 28-pair network.

M15 universe data is enough to derive H1/H4 locally. M5 is fetched only for finalists; M1/latest only immediately before execution.

### Currency-specific live macro profiles
- USD: Fed/rate path, PCE/CPI, labour/NFP, US yields.
- EUR: ECB, HICP/core, wages/services, energy/growth.
- GBP: BoE, CPI/services, wages, UK growth.
- JPY: BoJ, wages/core CPI, JGB yields, carry and MOF intervention risk.
- CHF: SNB, Swiss inflation, risk-off and SNB FX intervention risk.
- CAD: BoC, CPI/jobs, oil and US trade/growth.
- AUD: RBA, trimmed inflation, labour/capacity, China/commodities/risk.
- NZD: RBNZ OCR, CPI, spare capacity/labour, dairy/global rates.

Historical tests do not reconstruct old macro/news after the fact; live macro is a gate layered on the price-side engine.

## Research progression

### F1 — rejected naive strongest-score selection
July fully covered block at RR1.5:
- forced: 55 TP / 81 SL from 136 resolved, 40.44%, +0.011R;
- naive Top3 MARKET: 4 TP / 11 SL, -0.333R;
- fixed Top3 LIMIT: 2 TP / 11 SL among 13 fills, -0.451R.
Conclusion: raw strongest trend/score is not the best entry.

### F2 — promising but tiny sample
Blind Aug04/05/06/10/11:
- forced RR2.1: 38 TP / 88 SL from 126 resolved, -0.065R;
- selective MARKET: 4 signals, 3 TP / 1 SL, 75% WR, +1.325R;
- selective LIMIT: 3 fills, 2 TP / 1 SL, avg effective RR 3.133, +1.756R.
Critical caveat: four trades are far too few to claim stable 75% WR.

### F3 — currency-profile + ADX blind holdout
Rules were frozen before outcomes. New holdout cutoffs had no exact repo hits before creation:
- Jul31, Aug03, Aug07, Aug12, Aug14 at 08:00 UTC.

Baseline RR1.8:
- all 28 pairs evaluated on all five dates = 140 forced benchmark signals;
- forced: 128 resolved, 44 TP / 84 SL, 34.38% WR, -0.037R;
- strict selective gate produced only 3 signals;
- selective MARKET: 1 TP / 1 SL + 1 timeout, 50% resolved WR, +0.400R;
- selective LIMIT: all 3 filled, 1 TP / 1 SL + 1 timeout, avg effective RR 3.445, +0.899R among resolved;
- selective HYBRID: 1 TP / 1 SL + 1 timeout, +0.400R.

Predeclared RR2.1 comparison:
- forced: 39 TP / 89 SL from 128 resolved, -0.055R;
- selective MARKET: 1 TP / 1 SL + 1 timeout, +0.550R;
- selective LIMIT: avg effective RR 3.921, +1.103R among resolved.

F3 date notes:
- Jul31 EURNZD SELL MARKET TP; LIMIT also TP.
- Aug03 EURGBP BUY classified LIMIT; both executions timed out.
- Aug07 NO TRADE while forced benchmark was only 3 TP / 22 SL.
- Aug12 NO TRADE while forced benchmark was 7 TP / 21 SL.
- Aug14 EURAUD SELL LIMIT SL.

## Current conclusion
- F3 did NOT confirm F2's apparent 75% WR. The next untouched block fell to 50% among only two resolved selective trades.
- Therefore no stable Forex win-rate claim is justified yet.
- LIMIT improves payoff geometry but has not shown a reliable hit-rate advantage.
- Forcing every pair remains negative expectancy at both 1.8R and 2.1R.
- The correct path remains selective quality gate + `NO TRADE`, not adding more indicators or flipping bias formulas.
- Current research baseline RR is 1.8R; 2.1R is allowed only when real structure/liquidity supports it.

## F3 per-currency forced diagnostic
Pair-involvement diagnostic only, not independent currency-model WR:
- AUD 54.55%
- NZD 45.45%
- GBP 40.62%
- JPY 40.62%
- USD 37.50%
- EUR 24.24%
- CHF 20.00%
- CAD 9.68%

Do not tune these percentages on the same revealed sample. CAD/CHF/EUR especially need stronger live macro/context confirmation rather than looser technical gates.

## Forex practical style from now on
1. Build 6h/24h/72h currency strength across all 28 pairs.
2. Apply the currency-specific live macro driver set.
3. H4/H1 structure + EMA slope establish tradable direction.
4. ADX only rejects chop; RSI only checks momentum/exhaustion; ATR only normalizes risk/chase.
5. M15 must show a real setup and structural invalidation.
6. M5 confirms live execution.
7. Rank quality with currency-correlation control; output 0–3 trades.
8. MARKET for clean continuation near value.
9. LIMIT only for a structurally expected pullback with expiry/cancel conditions.
10. Structure defines SL first; require roughly >=1.5R room, baseline around 1.8R, stretch ~2.1R only when supported.
11. Refresh exact M1/latest immediately before executable entry.

Retained Forex evidence:
- `scripts/blind_backtest_forex_f2.py`
- `data/blind_backtest_forex_f2.json`
- `scripts/blind_backtest_forex_f3.py`
- `data/blind_backtest_forex_f3.json`
- `docs/checkpoints/FOREX_STATE.md`

## Twelve Data efficiency
- universe scan: one M15 time-series per pair = 28 symbol credits;
- derive H1/H4, EMA/RSI/ATR/ADX and 6h/24h/72h strength locally;
- fetch M5 only for up to 3 finalists;
- fetch M1/latest only for executable finalists;
- target roughly 34 symbol credits for a full scan with three finalists.

## Crypto state — frozen
Keep current selective crypto framework: BTC/market regime, D1/H4/H1 + short momentum, M15/M5, fresh order flow only when available, structural SL, MARKET/LIMIT by setup, `NO TRADE / CHAOS` allowed.

## Other markets
- Metals remain separate XAUUSD/XAGUSD workflow.
- Cash indices are never silently substituted with futures.
- NQ/ES futures remain separate MNQ/MES workflow.

## Infrastructure
Repo: `hanlinh227-ship-it/trading-api`.
Crypto live route: Binance -> OKX -> Bybit.
Forex/metals/cash indices: Twelve Data/Worker route subject to entitlement.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`
