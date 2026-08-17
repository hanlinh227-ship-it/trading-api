# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 14:18 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint. Do not reconstruct strategy state from memory when checkpoints exist.

## User operating preferences
- Respond in Vietnamese unless another language is requested.
- For trading code edits where the user needs to copy the result, provide the full updated file.
- Never call stale/web proxy prices executable/live; refresh the exact symbol before current entry/hold/cut decisions.
- Structure defines SL first; size/RR follows.
- Avoid redundant indicators.

## Immediate active task
Forex method development using forced blind testing across all 28 pairs. No Top-3 selection in the research benchmark: every valid pair receives BUY or SELL. Judge the method using direction 6h/12h/24h + TP/SL + expectancy/RR, and separate bias failure from entry/barrier failure.

Crypto practical framework remains frozen separately.

## Forex minimal stack
- EMA20/50: trend/value/slope;
- RSI14: momentum/exhaustion;
- ATR14: volatility/SL normalization;
- ADX14: regime/trend-vs-chop;
- 6h/24h/72h cross-currency strength.
Historical research fetches one Twelve Data M15 series per pair and derives H1/H4 locally.

## Latest evidence
### F4 — near break-even LIMIT, but not robust
Jul17/20/21/22/24 forced 140:
- MARKET: 49 TP / 73 SL, WR 40.16%, avg RR 2.055, expectancy -0.081R;
- LIMIT: 40 TP / 70 SL, avg effective RR 2.699, expectancy -0.018R;
- direction12/24 both 53.57%.
Lesson: modest directional edge only; LIMIT cannot fix bad bias.

### F5 — rejected
Jul27/28 forced 56:
- MARKET 12 TP / 43 SL, WR 21.82%, -0.383R;
- LIMIT 10 TP / 42 SL, -0.362R;
- direction12/24 both 32.14%;
- 36 of 43 SL were also wrong direction24.
This is true bias failure, not mainly tight SL. Do not promote LONGHORIZON/economic-target F5.

### F6 rotation — hypothesis not exercised
May11–15 same-block baseline vs F6, 140 each. Final retained JSON is the source of truth:
- rotation overrides = 0 because the predeclared gate never triggered;
- F6 therefore equals baseline exactly;
- MARKET 35 TP / 73 SL from 108 resolved, WR 32.41%, avg RR 2.413, expectancy -0.084R;
- LIMIT 30 TP / 72 SL from 102 resolved, avg effective RR 3.105, expectancy -0.016R;
- direction12 55.00%, direction24 52.86%;
- 28/73 SL later became correct at 24h.
Do not loosen F6 thresholds on May and call the same block blind.

### Parallel dual-horizon — negative aggregate
Jun24/Jun30/Jul02/Jul07/Jul10:
- MARKET 44 TP / 70 SL from 114 resolved, -0.119R;
- LIMIT 20 TP / 65 SL, -0.254R;
- selected direction 51.43%.
Some pairs looked good individually but aggregate remained negative; no cherry-picking.

### F7 consensus — partial improvement, still NOT profitable
Unseen historical holdout Apr20–24. Same 140 signals for baseline and F7. Note: unseen timestamp holdout, but not pure chronological walk-forward because baseline was developed using later 2026 data.

Direction rule: majority vote across 6h/24h/72h currency strength + H4 trend + H1 trend. Barriers unchanged.

Baseline same block:
- MARKET 27 TP / 100 SL, expectancy -0.258R;
- LIMIT 22 TP / 100 SL, expectancy -0.241R;
- direction12 41.43%, direction24 50.00%, avg signed 24h move -0.420 ATR.

F7:
- 13 direction overrides;
- MARKET 27 TP / 102 SL, WR 20.93%, avg RR 2.661, expectancy -0.150R;
- LIMIT 23 TP / 102 SL, avg effective RR 3.383, expectancy -0.054R;
- direction12 42.14%, direction24 50.71%, avg signed 24h move +0.059 ATR;
- 35/102 SL later correct at 24h; 67/102 remained wrong direction.

Interpretation:
- F7 improves payoff expectancy materially versus the exact same baseline, especially LIMIT (-0.241R -> -0.054R), but does NOT materially improve directional hit rate and remains negative.
- Keep five-vote consensus only as a candidate component, not a validated engine.
- Date instability remains extreme: Apr23 F7 MARKET +0.766R / LIMIT +1.062R, while Apr24 MARKET -0.848R / LIMIT -0.815R.

## Next meaningful research hypothesis
Do NOT add indicators. The next step should be a market-day/common-factor regime layer:
1. measure common USD/risk/carry factor across the 8-currency network;
2. measure cross-sectional breadth/dispersion;
3. identify synchronized trend vs rotation/chop;
4. still force every pair BUY/SELL in benchmark, but let day regime change directional weighting and barrier geometry;
5. compare new method against baseline on the same untouched block;
6. keep SL classification: bias wrong vs later-right path failure.

Do not tune on any revealed F4/F5/F6/F7 date and then call it blind again.

## Twelve Data efficiency
- one M15 history per 28 pairs ≈ 28 symbol credits per full block;
- H1/H4/EMA/RSI/ATR/ADX/strength derived locally;
- model revisions on the same block reuse cached local data;
- workflows share `twelvedata-api` concurrency and use cooldown to avoid HTTP 429.

## Active Forex files
- `scripts/blind_backtest_forex_f4.py`, `data/blind_backtest_forex_f4.json`
- `scripts/blind_backtest_forex_f5.py`, `data/blind_backtest_forex_f5.json`
- `scripts/blind_backtest_forex_f6.py`, `data/blind_backtest_forex_f6.json`
- `data/blind_backtest_forex_f6_dual_horizon.json`
- `scripts/blind_backtest_forex_f7.py`, `data/blind_backtest_forex_f7.json`
- `docs/checkpoints/FOREX_STATE.md`

## Other markets
- Crypto selective practical framework remains frozen.
- Metals remain separate XAUUSD/XAGUSD workflow.
- Cash indices are never silently substituted with futures.
- NQ/ES futures remain separate MNQ/MES workflow.

## Infrastructure
Repo: `hanlinh227-ship-it/trading-api`.
Crypto live route: Binance -> OKX -> Bybit.
Forex/metals/cash indices: Twelve Data/Worker route subject to entitlement.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`
