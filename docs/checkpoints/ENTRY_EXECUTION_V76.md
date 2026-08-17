# ENTRY / EXECUTION V76

Updated: 2026-08-18 UTC+7
Status: **R2 FOREX RESEARCH LOCKED — NEGATIVE LIVE-PROMOTION RESULT**.

## Final conclusion

V76 R2 completed successfully across all 28 Forex pairs. It tested six objective setup families and 72 entry/stop/RR variants under chronological DEV/VALIDATION/untouched-OOS rules.

**Result:**
- retained global archetypes: **NONE**;
- live-promoted symbols: **0/28**;
- 28/28 methods: `RESEARCH_ONLY`;
- research candidates only: `C_SWEEP_FVG`, `D_BREAK_RETEST_CONT`;
- fully rejected in this R2 hypothesis set: `A_SWEEP_MSS`, `B_H1_PULLBACK_RECLAIM`, `E_FAILED_BREAK_REV`, `F_IFVG_RECLAIM`.

This result is frozen. Do not retune R2 using its OOS results to force a promotion. A new hypothesis requires a separately versioned research generation.

## Scope / architecture

V76 is an optional post-V75 Forex entry gate. It does not rebuild/optimize V73, does not replace V74 news/data/execution integrity, and does not change V75 fast-data architecture.

Current live authority therefore remains **V74 + V75 data**. V76 R2 currently authorizes **no Forex order** because every R2 per-symbol method is non-promoted.

Crypto entry research remains deferred. Futures entry research remains blocked until exact authoritative futures-contract history exists; cash NAS100/SPX is never a proxy for NQ/ES.

## Objective setup families tested

A `A_SWEEP_MSS`: M15 sweeps prior 8-bar liquidity and closes back inside; within 6 M5 bars a >=0.50 ATR displacement closes beyond the prior 5-bar M5 swing.

B `B_H1_PULLBACK_RECLAIM`: H1 trend by close/EMA20/EMA50; M15 touches/reclaims EMA20; M5 displacement confirms.

C `C_SWEEP_FVG`: M15 liquidity sweep followed within 6 M5 bars by a same-direction 3-candle FVG >=0.05 M5 ATR.

D `D_BREAK_RETEST_CONT`: H1 trend; M15 closes beyond prior 12-bar range by >=0.05 ATR; retest within 4 M15 bars; M5 displacement continuation.

E `E_FAILED_BREAK_REV`: M15 exceeds prior 12-bar extreme by >=0.15 ATR but closes back inside and beyond midpoint; M5 displacement reversal.

F `F_IFVG_RECLAIM`: prior opposite M5 FVG >=0.05 ATR is invalidated by displacement through its far edge; inverted gap becomes reclaim/retest zone.

Each family tested `CLOSE / RETEST / LIMIT_FVG` × `STRUCTURE / STRUCTURE_ATR` × `RR1 / RR2` = **12 variants/family, 72 total**.

## R2 research protocol

- chronological 60% DEV / 20% VALIDATION / 20% untouched OOS;
- DEV ranks variants;
- VALIDATION gates variants and retained global archetypes;
- OOS only promotes/rejects a locked method, never changes thresholds/ranking;
- selected-method minimum targets: DEV 60, VALIDATION 20, OOS 20;
- same-bar TP+SL = SL;
- LIMIT_FVG fill candle is conservative: any stop touch = SL; fill-bar TP counts only if close also crosses TP;
- max holding period = 36 M5 bars;
- fixed historical round-trip cost = 0.05R because historical broker bid/ask is unavailable;
- reported metrics: n, WR, expectancy R, PF, avg win/loss, max losing streak, max DD R, MFE, MAE, hit1R, hit2R, TIMEOUT;
- context: session, London/NY overlap, D1/H4/H1 alignment, volatility, H1/M15 liquidity room, direction.

## Historical data actually used

- source: exact Twelve Data `Physical Currency`;
- 30,000 M5 bars per pair;
- common research window approximately **2026-05-05 through 2026-08-17**;
- 6 historical chunks × 5,000 bars/symbol;
- four parallel API groups × seven symbols/group;
- M15/H1/H4 resampled locally from M5;
- D1 fetched separately (500 bars);
- raw historical candles are not committed.

Observed batch constraint required batch-symbol-count × outputsize <=100,000; grouped fetch keeps each HTTP batch at 7×5,000 = 35,000.

## Validation-level archetype result

Across 28 symbols where available:
- A: validation-positive 8/28; median validation expectancy **-0.1254R**;
- B: 3/28; median **-0.2061R**;
- C: 12/28; median **-0.0299R**;
- D: 9/28; median **-0.0625R**;
- E: only 2 symbols had adequate validation samples, 0 positive; median **-0.2593R**;
- F: 4/28; median **-0.0809R**.

No family met the pre-locked global retention gate. C and D are merely the two least-weak research candidates for future observation, not live-approved strategies.

## Per-symbol result

Canonical compact table: `data/v76_pair_table.md`.

Distribution:
- C_SWEEP_FVG selected as the best available research candidate for 18 pairs;
- D_BREAK_RETEST_CONT for 10 pairs;
- **all 28 are RESEARCH_ONLY**;
- **promotedSymbols = []**.

Examples showing why no promotion was forced:
- AUDUSD C LIMIT_FVG/STRUCTURE_ATR RR1: DEV +0.0785R, VAL +0.0263R, but OOS -0.0171R / PF 0.964.
- EURUSD C LIMIT_FVG/STRUCTURE_ATR RR2: DEV +0.1259R, VAL -0.0982R; fails validation even though OOS later rebounded.
- GBPCHF C LIMIT_FVG/STRUCTURE RR1: VAL +0.2668R / PF 1.824, but OOS -0.1655R / PF 0.693.
- AUDJPY is one of the closest: VAL +0.031R / PF 1.072 and OOS +0.0596R / PF 1.149, but it still fails the pre-locked OOS PF >=1.15 requirement and no global archetype was retained.
- GBPNZD D CLOSE/STRUCTURE RR1 has OOS +0.1624R / PF 1.608, but DEV expectancy is negative and validation is only marginal; therefore it cannot be promoted.

These examples demonstrate why OOS is not used to rescue a method that failed earlier gates.

## Historical-news limitation

The canonical research feed does not provide a complete timestamped high-impact macro calendar suitable for honest NFP/ISM/CPI-style historical event-window labeling. V76 does not infer/fabricate news labels from price volatility. Historical before/after-news performance is therefore **not claimed**. Current V74 news/context refresh remains mandatory live.

## R2 promotion gates

A symbol would require all of:
- DEV n>=60, expectancy >0R, PF>=1.10;
- VALIDATION n>=20, expectancy >0R, PF>=1.05;
- OOS n>=20, expectancy >0.05R, PF>=1.15;
- OOS max DD <=10R;
- OOS max losing streak <=10;
- and a globally retained validation-backed archetype.

No symbol satisfied the complete R2 promotion framework because no archetype passed global retention.

## Live behavior now

`scripts/entry_v76.py` accepts only `V76-ENTRY-METHODS-R2`; R1/pilot methods are blocked. R2 methods with `liveEligible=false` return `NO_ENTRY / METHOD_NOT_OOS_PROMOTED`.

Even if a future separately-versioned method is promoted, V76 cannot bypass:
`V75 data -> V74 HTF/context -> V76 method -> M15 -> M5 -> current news -> final venue bid/ask/timestamp/spread -> MARKET/LIMIT/NO_ENTRY -> structural SL -> RR1/RR2`.

RR2 also requires >=2.2R clean H1 room and live execution requires current venue confirmation + news clearance.

## Canonical files

- `scripts/research_v76_entry_forex.py` — frozen objective primitives/metrics for this research generation.
- `scripts/evaluate_v76_entry_forex.py` — conservative R2 evaluator.
- `scripts/fetch_v76_history.py` — grouped historical fetcher.
- `scripts/run_v76_entry_research.py` — canonical R2 runner.
- `scripts/entry_v76.py` — live post-V75 safety gate.
- `scripts/summarize_v76.py` — compact summary/table builder.
- `.github/workflows/research-v76-entry.yml` — explicit research workflow.
- `.github/workflows/validate-entry-v76.yml` — R2 validator.
- `.github/workflows/summarize-v76.yml` — compact result generator.
- `data/v76_entry_research.json` — detailed R2 evidence.
- `data/v76_entry_methods.json` — locked methods R2.
- `data/v76_entry_summary.json` — compact result.
- `data/v76_pair_table.md` — all 28 pair methods + DEV/VAL/OOS metrics.

## Evidence / runs

- Final R2 research run **32053656572** = SUCCESS.
- Compact summary run **32054967541** = SUCCESS.
- Post-R2 validator **32055039365** = SUCCESS; it verifies `V76-ENTRY-METHODS-R2`, 28 pairs, `retained=[]`, conservative fill behavior and V73 frozen integrity.

## Next research rule

Do **not** tune thresholds after reading these OOS results and call it V76 R2. Preferred next step is forward logging/observation of C/D plus collection of better historical transaction-cost/news-event data. Any new hypotheses/filters must be pre-registered as a new research generation (e.g. V77) with a new untouched OOS window.
