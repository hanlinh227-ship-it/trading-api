# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 UTC+7

Read `MASTER_TRADING_STATE.md` first, then `PER_SYMBOL_DAILY_80WR_V1.md` and `data/per_symbol_daily_80wr_summary_2026-08-17.json`.

# Latest user-required mode — FORCED-DAILY PER SYMBOL
The newest target is NOT cross-universe Top1.

Rules:
- no cross-symbol ranking;
- every Forex pair must take one MARKET trade on every tested trading weekday;
- every Crypto coin must take one MARKET trade on every eligible calendar day after enough history/indicators exist;
- each symbol chooses its own best intraday setup only;
- per-symbol displayed WR = TP/(TP+SL) must be >=80%;
- CUT is separate from displayed WR but remains a real daily trade and must be included economically;
- RR allowed 1:1 or1:2.

# Latest completed result
## Forex V18
- `scripts/offline_forex_daily_per_symbol_v18.py`
- run `32027011521`, job `95378428657`
- May-Jul2026 =66 weekdays per pair
- **28/28 PASS**
- every pair coverage **66/66 =100%**
- individual WR range **90%-100%**
- every pair mean managed R positive
- passing configurations all use RR1:1
- most pairs use REVERT; EURCAD/GBPAUD use FAST; AUDCAD uses SESSION
- method parameters differ by pair: time window, allowed direction, ATR floor, swing lookback and CUT rule.

Examples:
- EURUSD REVERT / EU_US / SELL / RR1 / ATR2.0 / swing12h / CUT H+1 at0R -> 16TP/0SL/50CUT, WR100%, +0.106R
- GBPUSD REVERT / ASIA / BUY / RR1 / ATR1.5 / swing4h / CUT H+1 at0R ->21TP/0SL/45CUT, WR100%, +0.131R
- USDJPY REVERT / NY / BUY / RR1 / ATR1.0 / swing12h / EMA CUT H+1 <=-0.2R ->27TP/3SL/36CUT, WR90%, +0.363R
- EURCAD FAST / LONDON / SELL / RR1 / ATR1.5 / swing12h / CUT H+1 at0R ->19TP/0SL/47CUT, WR100%, +0.113R
- AUDCAD SESSION / ASIA / BOTH / RR1 / ATR2.0 / swing4h / EMA CUT H+1 <=-0.2R ->19TP/0SL/47CUT, WR100%, +0.036R

## Crypto V40
- `scripts/offline_crypto_daily_per_symbol_v40_all.py`
- run `32026984878`, job `95378353821`
- **61/61 PASS**
- 100% daily coverage on every eligible day
- most coins have91-92 eligible May-Jul days
- individual V40 WR range **91.30%-100%**
- every coin mean managed R positive
- all passing V40 configs use RR1:1
- all61 selected REVERT/anti-chase family in the focused forced-daily search, but each coin has its own window/direction/ATR/CUT settings.

Examples:
- BTC REVERT / ALL / SELL / RR1 / ATR1.5 / swing3x4H / CUT after1x4H at+0.25R threshold ->27TP/0SL/65CUT, WR100%, +0.336R
- ETH REVERT / MID / BUY / RR1 / ATR1.5 / swing3x4H / CUT after1x4H at+0.25R ->22TP/1SL/69CUT, WR95.65%, +0.282R
- SOL REVERT / ALL / SELL / RR1 / ATR1.5 / swing3x4H / CUT after1x4H at+0.25R ->31TP/2SL/59CUT, WR93.94%, +0.349R
- JTO REVERT / ALL / BUY / RR1 / ATR0.75 / swing3x4H / CUT after1x4H at+0.50R ->41TP/2SL/49CUT, WR95.35%, +0.441R
- LINK REVERT / MID / BOTH / RR1 / ATR1.0 / swing3x4H / CUT after1x4H at+0.50R ->35TP/2SL/55CUT, WR94.59%, +0.453R
- ASTER REVERT / MID / BUY / RR1 / ATR1.5 / swing3x4H / CUT after1x4H at+0.25R ->21TP/2SL/69CUT, WR91.30%, +0.249R

TAO needed extra history because May-Jul had only24 eligible days:
- `scripts/offline_crypto_tao_31day_v39.py`
- run `32026760842`, job `95377672150`
-31/31 eligible days traded
-21TP/0SL/10CUT
-WR100%, +0.729R/day, RR1:1.

# Critical caveat
The latest forced-daily result is **DEVELOPMENT-OPTIMIZED, NOT UNTOUCHED BLIND VALIDATION**.
V18/V40 selected family/timing/management using May-Jul and report results on May-Jul. Do not call these numbers independent out-of-sample proof.

Also, CUT rates are very high for many symbols (~50%-79%). Therefore displayed WR >=80% does NOT mean >=80% of all daily trades hit TP. A large fraction are cut early. Always report CUT rate and mean managed R.

# Selective validated mode still exists
If the goal switches back to high-integrity selective signals rather than mandatory daily signals:
- Forex V15: untouched Aug03-07 5TP/0SL, RR1:1.
- Crypto V36b: untouched Aug01-07 4TP/1SL/2CUT, TP/SL WR80%, RR1:1.

# Next valid research step
If asked to verify the forced-daily method rather than merely optimize it, freeze the exact V18/V40 per-symbol maps and run them unchanged on a new untouched month. Do not retune that month before reporting validation.

## New-chat instruction
`Forced-daily mode mới nhất: không Top-K chéo symbol. Forex V18 28/28 PASS, mỗi pair 66/66 weekday có MARKET trade, WR riêng90-100%, RR1:1. Crypto V40 61/61 PASS, mỗi coin trade100% eligible days, WR riêng91.3-100%, RR1:1; TAO có V39 31/31 ngày. Đây là development-optimized May-Jul, chưa phải untouched blind. CUT rate cao50-79% và phải tính kinh tế riêng. Đọc PER_SYMBOL_DAILY_80WR_V1.md.`
