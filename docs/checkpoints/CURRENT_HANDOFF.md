# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 15:17 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then `CROSSMARKET_80WR_OFFLINE_AUDIT.md`, then the relevant market checkpoint. Do not reconstruct strategy state from memory when checkpoints exist.

## Immediate active state
The latest task was a **zero-provider-credit full historical re-audit of Forex + Crypto** with a requested promotion target of **>=80% held-out/walk-forward WR and average RR >=1.0 (preferred >=1.5)**.

The target was **NOT validated**. It is forbidden to manufacture 80% by hindsight, cherry-picking revealed dates, tiny TP, or outcome-derived filters.

Full audit checkpoint:
`docs/checkpoints/CROSSMARKET_80WR_OFFLINE_AUDIT.md`

Pre-audit recovery marker:
`docs/checkpoints/archive/2026-08-17_1507_PRE_80WR_OPTIMIZATION.md`
Recovery commit: `de58e0a0ea2a6054b9c5839736be0efa80d01dce`.

## Provider usage
The latest optimization/audit used **0 Twelve Data credits and 0 exchange market-data API calls**. It read only already committed result JSONs.

## Forex — canonical state
**F8 remains the frozen research baseline. Do not replace it with an 80%-optimized hindsight model.**

F8 architecture:
- EMA20/50, RSI14, ATR14, ADX14 only;
- 3h/6h/12h/24h/72h currency-factor coherence;
- dispersion/rank separation;
- 8h session state;
- five pair archetypes;
- horizon-matched structural SL/TP/expiry;
- MARKET vs LIMIT by setup.

Four consecutive frozen 5-day validation blocks:
- May18–22: MARKET +0.111R;
- May25–29: MARKET +0.338R;
- Jun01–05: MARKET +0.247R;
- Jun08–12: MARKET +0.251R.

Combined 20 days / 560 forced signals:
- MARKET: 489 resolved, **248 TP / 241 SL = 50.72% WR**, weighted expectancy ~**+0.233R**;
- LIMIT: 403 resolved, 169 TP / 234 SL, weighted expectancy ~**+0.246R**;
- recommended: 487 resolved, 247 TP / 240 SL, weighted expectancy ~**+0.237R**.

Main remaining Forex weakness: **common-factor/date-regime catastrophe**, not a single consistently bad pair group. Jun04 remains the key example: 5 TP / 22 SL, -0.565R, 19/22 SL true bias errors.

Latest 80WR audit could not legitimately form a held-out >=80% pair gate from compatible pair-level historical tables. F8 therefore remains unchanged.

## Crypto — canonical state
No validated forced all-coin live engine.

Recovered committed audit set:
- 640 resolved trades / 12 dates;
- 229 wins / 411 losses;
- **35.78% WR**;
- mean **-0.057R**;
- average RR **1.639**.

Zero-credit V1 walk-forward selector:
- 48 trades / 9 dates;
- **27.08% WR**;
- -0.268R;
- avg RR 1.685.
Best direct in-sample ceiling in that rule family: **54.24% WR**, +0.433R, avg RR 1.669 — diagnostic only.

Regime-aware V3 audit with inherited day breadth/state:
- walk-forward 27 trades / 5 dates;
- **25.93% WR**;
- -0.304R;
- avg RR 1.735.
Best direct in-sample rule: **59.26% WR**, +0.569R, avg RR 1.679 — not promotable.

Therefore the 80% target is not supported by existing Crypto evidence. Static symbol reputation and historical winner lists must not be the main gate. Current BTC + breadth/regime + HTF structure + M15/M5 path dominate live evaluation.

## Surviving cross-market improvements
1. Regime/bias -> structure -> setup -> execution -> structural SL -> realistic TP.
2. Separate bias error from entry/barrier error.
3. Never shrink TP solely to inflate WR.
4. MARKET for fresh continuation only; do not chase exhausted movement.
5. LIMIT only for a real structural pullback/retest.
6. Forced all-symbol trading is research stress only; live may output NO TRADE.
7. Forex pair history = confidence modifier, not primary direction engine.
8. Crypto symbol history = weak gate; market state dominates.
9. A future >=80% claim requires genuinely independent validation, not retuning these revealed blocks.

## Latest research files
- `docs/checkpoints/CROSSMARKET_80WR_OFFLINE_AUDIT.md`
- `scripts/offline_crossmarket_optimizer_80wr.py`
- `.github/workflows/offline-crossmarket-optimizer-80wr.yml`
- `scripts/offline_crypto_regime_optimizer_v2.py`
- `.github/workflows/offline-crypto-regime-optimizer-v2.yml`
- `scripts/offline_crypto_regime_optimizer_v3_fast.py`
- `.github/workflows/offline-crypto-regime-v3-fast.yml`

Completed evidence runs:
- `32009158360` — Crossmarket 80WR offline optimizer, success.
- `32009450389` — Crypto regime V3 fast, success.

## Live entry rule
Historical research does not authorize stale execution. For any live Forex/Crypto entry:
- refresh exact symbol/current price;
- verify current market regime and relevant news/macro;
- use HTF structure and lower-timeframe setup;
- define structural invalidation first;
- choose MARKET/LIMIT/NO TRADE based on path, not desired WR.

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md, docs/checkpoints/CURRENT_HANDOFF.md và docs/checkpoints/CROSSMARKET_80WR_OFFLINE_AUDIT.md trước, sau đó đọc checkpoint thị trường liên quan. Không được nói mục tiêu 80% đã đạt.`
