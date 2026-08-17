# CROSS-MARKET 80% WR OFFLINE AUDIT

Updated: 2026-08-17 15:16 UTC+7
Status: **TARGET NOT VALIDATED — DO NOT FORCE 80%**
Provider credits used: **0**

## User target
Improve Forex + Crypto using only already committed historical/blind result data. Desired promotion threshold:
- held-out / chronological walk-forward WR >= 80%;
- average planned/effective RR >= 1.0, preferred >= 1.5;
- non-trivial sample size;
- no provider/API market-data calls;
- preserve old state and Git history.

## Integrity rules applied
1. No Twelve Data calls.
2. No exchange REST calls.
3. Only committed blind/backtest JSONs were read.
4. Outcome-derived fields (future direction, MFE/MAE, first-hit result) were not allowed as entry filters.
5. In-sample fitted ceiling is reported separately from held-out/walk-forward performance.
6. 80% reached only by hindsight/cherry-picking is explicitly rejected.
7. Old canonical state is recoverable from pre-optimization commit `de58e0a0ea2a6054b9c5839736be0efa80d01dce` and archive `docs/checkpoints/archive/2026-08-17_1507_PRE_80WR_OPTIMIZATION.md`.

# FOREX

## Canonical baseline remains F8
The true current Forex comparator is not F4–F6; it is frozen F8.
Four consecutive chronological 5-day blocks, unchanged engine:
- May18–22: MARKET +0.111R;
- May25–29: MARKET +0.338R;
- Jun01–05: MARKET +0.247R;
- Jun08–12: MARKET +0.251R.

Combined 20 trading days / 560 forced signals:
- MARKET: 489 resolved, 248 TP / 241 SL, **50.72% WR**, weighted expectancy about **+0.233R**;
- LIMIT: 403 resolved, 169 TP / 234 SL, **41.94% WR**, weighted expectancy about **+0.246R**;
- recommended execution: 487 resolved, 247 TP / 240 SL, **50.72% WR**, weighted expectancy about **+0.237R**.

Combined chosen-direction accuracy 58.57%; 3h 59.64%; 6h 55.36%; 12h 55.54%; 24h 53.21%.

## Zero-credit selector audit
`Offline Crossmarket Optimizer 80WR` run: `32009158360`.
The automatic pair-table selector could recover the first two F8 holdout pair tables directly:
- 56 pair-block observations;
- 238 resolved;
- 119 wins / 119 losses;
- **50.00% WR**;
- mean expectancy **+0.217R**.

It could not form a legitimate nested 80% gate because only two of the four later files expose compatible pair-level tables; F10/F11 expose block/day comparator summaries rather than the same pair-table schema. Therefore **no 80% Forex claim was produced**.

Important retained evidence from F10/F11:
- Jun01–05 frozen F8: 66 TP / 63 SL, 51.16% WR, +0.247R, avg RR about 1.421.
- Jun01 alone: 19 TP / 6 SL, 76.00% WR, +0.845R; LIMIT 73.91%, +1.182R.
- Jun04 was catastrophic: 5 TP / 22 SL, -0.565R; 19/22 SL were true bias errors.
- F11 day-conflict gate tried predeclared thresholds 0.55/0.65/0.75 on 700 development signals; all activated zero days, so it correctly made zero overrides. Jun08–12 stayed frozen F8 and produced +0.251R MARKET.

### Forex conclusion
**F8 remains frozen.** Existing committed evidence does not support >=80% held-out WR at RR>=1.0. The main problem is common-factor/day-regime failure, not TP size or a single bad pair group. Do not distort F8 to hit 80% on revealed dates.

# CRYPTO

## Full recovered historical set
640 resolved trades across 12 dates from committed V24/V26/V27/Apr16 results:
- 229 wins / 411 losses;
- **35.78% WR**;
- mean **-0.057R**;
- average RR **1.639**.

## V1 broad offline optimizer
Run `32009158360`, provider credits 0.
Chronological walk-forward selected:
- 48 trades over 9 dates;
- 13 wins / 35 losses;
- **27.08% WR**;
- **-0.268R**;
- average RR **1.685**.

Even the direct in-sample ceiling within that broad interpretable rule family was only:
- 59 trades / 10 dates;
- 32 wins / 27 losses;
- **54.24% WR**;
- **+0.433R**;
- average RR **1.669**.
This is diagnostic only and not validation.

## V3 regime-aware fast audit
Run `32009450389`, provider credits 0.
This corrected inheritance of day-level breadth/regime into each trade and searched state gates using breadth, side alignment, score, macro score, H4/HTF score, regime, and micro agreement.

Chronological walk-forward:
- 27 trades over 5 dates;
- 7 wins / 20 losses;
- **25.93% WR**;
- **-0.304R**;
- average RR **1.735**.

Best direct in-sample rule in this family:
- 54 trades over 6 dates;
- 32 wins / 22 losses;
- **59.26% WR**;
- **+0.569R**;
- average RR **1.679**.
Again, this is not promotable.

Useful date-level evidence preserved:
- 2026-06-24 full universe: **83.33% WR**, +1.228R, avg RR 1.668.
- 2026-06-30 full universe: **7.27% WR**, -0.807R, avg RR 1.687.
- 2026-04-16: 51.92% MARKET WR, +0.350R; 24h direction accuracy 89.09%.
- 2026-04-09: 20.37% WR, -0.470R.
This extreme date dispersion proves that current-state market regime dominates static symbol reputation.

### Crypto conclusion
No static or walk-forward rule family tested on the committed data can honestly deliver >=80% WR at RR>=1.0. Trying to maximize historical precision caused walk-forward deterioration. **Do not use symbol reputation as the main live gate.** BTC/regime/breadth + HTF structure + entry path must dominate.

# Final method changes retained
These are the changes that survived the audit and should inform live analysis, even though the 80% target failed:
1. Keep `regime/bias -> structure -> setup -> execution -> structural SL -> realistic TP`.
2. Separate `bias wrong` from `bias right but entry/barrier wrong`.
3. Never shrink TP merely to manufacture WR.
4. MARKET only for fresh continuation / displacement that has not already been chased.
5. LIMIT only when a real structural pullback/retest is expected; never as a universal better-price rule.
6. Forex pair history is a confidence modifier only; F8 factor/archetype/current-state logic dominates.
7. Crypto symbol history is not a reliable gate; BTC + market breadth/regime + D1/H4/H1 + M15/M5 path dominates.
8. Live is allowed to output NO TRADE. Forced all-symbol trading remains a stress benchmark only.
9. >=80% is a research target, **not a number to force**. Promotion requires new independent evidence, not retuning revealed blocks.

# Files / runs created by this audit
- `docs/checkpoints/archive/2026-08-17_1507_PRE_80WR_OPTIMIZATION.md`
- `scripts/offline_crossmarket_optimizer_80wr.py`
- `.github/workflows/offline-crossmarket-optimizer-80wr.yml`
- `scripts/offline_crypto_regime_optimizer_v2.py`
- `.github/workflows/offline-crypto-regime-optimizer-v2.yml`
- `scripts/offline_crypto_regime_optimizer_v3_fast.py`
- `.github/workflows/offline-crypto-regime-v3-fast.yml`
- workflow run `32009158360` — completed success
- workflow run `32009450389` — completed success

## Cross-chat instruction
A new chat must read:
1. `docs/checkpoints/MASTER_TRADING_STATE.md`
2. `docs/checkpoints/CURRENT_HANDOFF.md`
3. `docs/checkpoints/CROSSMARKET_80WR_OFFLINE_AUDIT.md`
4. the relevant `FOREX_STATE.md` or `CRYPTO_BREAKOUT_STATE.md`.

Do not claim the 80% target has been achieved. Do not discard F8 Forex merely to raise apparent WR on old data. Do not resurrect rejected Crypto gates merely because one historical date was exceptional.
