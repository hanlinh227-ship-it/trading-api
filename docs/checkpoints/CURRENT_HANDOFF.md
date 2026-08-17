# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 14:30 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint. Do not reconstruct strategy state from memory when checkpoints exist.

## Immediate active task
Forex method development. Research benchmark still forces BUY/SELL on all 28 pairs; no Top-3 selection. Current strongest baseline is **F8 factor-coherence + session + pair-archetype**, now positive on two consecutive chronological holdouts without retuning between them.

## F8 status — promoted research baseline candidate
Minimal indicators remain EMA20/50, RSI14, ATR14, ADX14. The improvement came from non-indicator state and pair-specific archetypes, not more indicators:
- 3h/6h/12h/24h/72h currency-factor coherence;
- cross-sectional dispersion/rank separation;
- 8h session position/breakout/sweep;
- five pair archetypes;
- horizon-matched SL/TP/expiry.

Frozen archetype models:
- USD_MAJOR -> FACTOR_BAL
- JPY_CROSS -> SESSION_SWEEP
- EUROPE_CROSS -> FACTOR_BAL
- COMMODITY_CROSS -> FACTOR_FAST
- MIXED_CROSS -> FACTOR_BAL

### Holdout 1 — May18–22
140 forced signals:
- MARKET: 58 TP /69 SL from 127 resolved, WR 45.67%, **+0.111R** expectancy;
- LIMIT: 35 TP /66 SL from 101 resolved, **+0.030R**;
- direction 6h 67.14%, 12h 66.43%, 24h 61.43%;
- avg RR 1.448.

### Holdout 2 — May25–29, no retuning after holdout1
140 forced signals:
- MARKET: 61 TP /50 SL from 111 resolved, WR **54.95%**, **+0.338R**;
- LIMIT: 45 TP /48 SL from 93 resolved, **+0.435R**;
- recommended: 60 TP /50 SL from 110 resolved, **+0.333R**;
- chosen-direction accuracy 68.57%; 3h 71.43%;
- avg RR 1.447.

### Combined F8 evidence — 10 chronological holdout days / 280 forced signals
MARKET:
- 238 resolved;
- 119 TP /119 SL = 50.00% WR;
- weighted expectancy ~**+0.217R**.
LIMIT:
- 194 resolved;
- 80 TP /114 SL = 41.24% WR;
- weighted expectancy ~**+0.224R**.
Recommended execution:
- 237 resolved;
- 118 TP /119 SL = 49.79% WR;
- weighted expectancy ~**+0.214R**.

Combined direction:
- chosen horizon 60.36%;
- 3h 61.79%;
- 6h 60.36%;
- 12h 60.00%;
- 24h 57.50%.

This is the strongest evidence so far, but F8 is still a research baseline candidate, not guaranteed and not an instruction to live-trade all 28 pairs.

## Group diagnosis
Holdout2:
- COMMODITY_CROSS: +0.679R MARKET, 66.67% WR, dir24 86.67%.
- MIXED_CROSS: +0.474R.
- JPY_CROSS: +0.394R.
- EUROPE_CROSS: +0.420R after a weak holdout1; do not change it yet.
- USD_MAJOR remains weakest/most consistent improvement target: holdout1 -0.131R, holdout2 +0.006R MARKET. LIMIT improved USD_MAJOR holdout2 to +0.229R, suggesting execution also matters, but do not globally force LIMIT.

## Next legitimate improvement
Freeze all successful F8 groups. Improve **USD_MAJOR only** with one interpretable USD-specific component, then compare modified engine vs frozen F8 on the same untouched June holdout while still forcing all 28 pairs.

Already repo-searched and absent before any new test: June 1–5, 2026 at 08:00 UTC are available candidate holdout timestamps. Do not reveal or use them before the modification is frozen.

## Research principles
- Do not add indicators just to improve fit.
- Do not tune on May18–29 and re-label those days blind.
- Do not optimize WR with tiny targets.
- Keep direction and TP/SL diagnostics separate.
- MARKET vs LIMIT is setup-dependent. F8 holdout1 favored MARKET; holdout2 LIMIT had higher expectancy on filled/resolved trades but only 2 trades were actually LIMIT-eligible by the frozen classifier.

## Twelve Data efficiency
- one M15 history per 28 pairs ≈28 symbol credits/block;
- H1/H4/features derived locally;
- model comparisons reuse downloaded data;
- workflows share `twelvedata-api` concurrency + cooldown.

## Active Forex files
- `scripts/blind_backtest_forex_f8.py`
- `data/blind_backtest_forex_f8.json`
- `scripts/blind_backtest_forex_f8_holdout2.py`
- `data/blind_backtest_forex_f8_holdout2.json`
- `docs/checkpoints/FOREX_STATE.md`

## Other markets
Crypto practical framework remains frozen. Metals, cash indices and NQ/ES futures remain separate systems.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan. Tiếp tục đúng trạng thái mới nhất, không quay lại phương pháp đã loại.`
