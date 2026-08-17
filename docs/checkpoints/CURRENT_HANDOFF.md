# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 UTC+7

Read `MASTER_TRADING_STATE.md` first, then:
- `FOREX_V15_PRE_AUG_LOCK.md`
- `FOREX_V15_FINAL1_PASS.md`
- `CRYPTO_V36B_PRE_AUG_LOCK.md`
- `CRYPTO_V36B_FINAL1_PASS.md`
- `TRADE_MANAGEMENT_HOURLY_V1.md`
- `CRYPTO_SYMBOL_PROFILES_V1.md`
- `data/final_target_80wr_validation_2026-08-17.json`

# Current global status
**RESEARCH TARGET ACHIEVED** under the selective full-universe scanner protocol:
- all configured symbols are scanned;
- NO TRADE is permitted for non-qualified symbols;
- displayed WR = TP/(TP+SL);
- CUT tracked separately but included in managed expectancy;
- promoted planned RR = 1:1 for both systems;
- final parameters were frozen before untouched August holdouts were fetched.

# Promoted Forex — V15
Universe: **28/28 Forex pairs scanned**.

Frozen execution:
- LIMIT;
- RR1:1;
- structural SL + 0.65 ATR floor;
- swing lookback 6h;
- limit offset0.35 ATR;
- expiry4h;
- max hold12h;
- H+2 management CUT only if R<=-0.45 and H1 close breaks EMA20 against thesis.

Frozen selector:
- cross-currency factors 3/6/12/24/72h + coherence/rank;
- H1/completed-H4 structure + ADX/RSI/session path;
- ExtraTrees depth7, leaf25;
- threshold0.70;
- BUY/SELL margin0.08;
- Top1 qualifying setup/day.

Pre-Aug expanding walk-forward:
- **55 selected**;
- **35TP / 7SL / 13CUT**;
- **WR83.33%**;
- **+0.491R/trade** including CUT.

Untouched Final1 Aug03–07:
- 840 full-universe pair/time scans;
- **5 selected = 5TP / 0SL / 0CUT**;
- **WR100.00%**;
- **+1.000R/trade**;
- workflow run `32019229044`;
- `finalTargetMet=true`.

# Promoted Crypto — V36b
Universe: **61/61 loaded/scanned** from frozen 4H snapshots.
Sources: OKX57 + Gate2 + Kraken2.

Frozen execution:
- LIMIT;
- RR1:1;
- structural SL +0.65 ATR floor;
- swing lookback5x4H;
- offset0.70 ATR;
- expiry1x4H;
- max hold4x4H;
- no early management CUT in the locked candidate; unresolved -> timeout CUT.

Frozen selector:
- BTC24/72 + breadth/dispersion + relative strength vs BTC;
- H4/completed-D1 + ADX/RSI/momentum;
- symbol/family context;
- HistGradientBoosting depth3, leaf8;
- threshold0.66;
- BUY/SELL margin0.16;
- Top1 qualifying setup/day.

Pre-Aug expanding walk-forward:
- **92 selected**;
- **66TP / 15SL / 11CUT**;
- **WR81.48%**;
- **+0.553R/trade** including CUT.

Untouched Final1 Aug01–07:
- 2,562 requested scan slots; 2,562 eligible;
- **7 selected = 4TP / 1SL / 2CUT**;
- **TP/SL WR80.00%**;
- **+0.657R/trade** including CUT;
- CUTs were +0.965R and +0.630R;
- workflow run `32019086571`;
- `finalTargetMet=true`.

# Important interpretation
This validates the **research/backtest scanner target**, not a guaranteed future/live win rate and not an assertion that each individual symbol separately has >=80% WR. Every symbol is scanned; only qualified entries are traded.

Live/forward operation must additionally use fresh exact prices and point-in-time news/economic-calendar context, then log post-fill HOLD/CUT reviews without hindsight.

# Do not regress integrity
- Do not retune Aug Final1 and call it blind again.
- Do not replace structural SL with arbitrary tight stops merely to preserve WR.
- Do not omit CUT P/L from economic expectancy.
- Do not mix Forex and Crypto feature architectures.

## New-chat instruction
`Tiếp tục Trading từ MASTER_TRADING_STATE.md. Target research 80% đã đạt: Forex V15 scans28/28, RR1:1, pre-Aug55 trades WR83.33%, untouched Aug03-07 5TP/0SL=100%; Crypto V36b scans61/61, RR1:1, pre-Aug92 trades WR81.48%, untouched Aug01-07 4TP/1SL/2CUT=80%, +0.657R incl CUT. Final parameters were locked before August fetch. Không retune final holdouts.`
