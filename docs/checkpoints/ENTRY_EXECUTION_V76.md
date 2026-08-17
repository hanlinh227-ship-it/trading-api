# ENTRY / EXECUTION V76

Updated: 2026-08-18 UTC+7
Status: R2 Forex research protocol locked; final R2 result pending canonical research output.

## Scope

V76 researches objective Forex entry/execution rules after V75 has produced a candidate. It does not modify, rebuild or optimize V73. It does not replace V74 market-data, news, freshness or execution-spread gates. It does not change V75 live-data architecture.

Forex is researched first across all 28 major-cross pairs. Crypto research is deferred until Forex V76 is locked. Futures research remains blocked until exact authoritative futures-contract history exists; NAS100/SPX cash data is never used as NQ/ES proxy.

## Objective setup families

A `A_SWEEP_MSS`: M15 sweeps prior 8-bar liquidity and closes back inside; within six M5 bars a displacement body >=0.50 ATR closes beyond the prior 5-bar M5 swing in the reversal direction.

B `B_H1_PULLBACK_RECLAIM`: H1 close/EMA20/EMA50 trend; closed M15 touches EMA20 and closes back with trend; M5 displacement closes beyond prior 5-bar swing.

C `C_SWEEP_FVG`: M15 liquidity sweep as A followed within six M5 bars by a same-direction three-candle FVG >=0.05 M5 ATR.

D `D_BREAK_RETEST_CONT`: H1 trend; M15 closes beyond prior 12-bar range by >=0.05 M15 ATR; within four M15 bars price retests breakout level and closes on breakout side; M5 displacement confirms continuation.

E `E_FAILED_BREAK_REV`: M15 exceeds prior 12-bar extreme by >=0.15 ATR but closes back inside prior range and beyond its midpoint; M5 displacement confirms reversal within six M5 bars.

F `F_IFVG_RECLAIM`: a prior opposite-direction M5 FVG >=0.05 ATR is invalidated by a displacement close through the far edge; the inverted gap becomes reclaim/retest zone.

## Variants

Each family tests:
- entry: `CLOSE`, `RETEST`, `LIMIT_FVG`;
- stop: `STRUCTURE`, `STRUCTURE_ATR`;
- target: RR1 and RR2.

That is 12 variants per family, 72 variants total.

## Research protocol R2

- Chronological 60% DEV / 20% VALIDATION / 20% untouched OOS.
- DEV ranks variants.
- VALIDATION gates variants and determines retained global archetypes.
- OOS is used once only to promote/reject a locked method; OOS never changes thresholds or ranking.
- Minimum selected-method sample targets: DEV 60, VALIDATION 20, OOS 20.
- Same-bar TP+SL = SL.
- `LIMIT_FVG` fill candle is scored conservatively: any stop touch = SL; a TP on the fill candle counts only if the candle close also crosses TP.
- Maximum holding period = 36 M5 bars.
- Historical round-trip execution cost = fixed 0.05R because historical broker bid/ask is not available in the canonical feed.
- Metrics: n, WR, expectancy R, PF, average win/loss R, max losing streak, max DD R, MFE, MAE, hit1R, hit2R, TIMEOUT.
- Context breakdown: session, London/NY overlap, D1/H4/H1 alignment, volatility regime, H1/M15 liquidity room and direction.

## Historical data

Canonical history path:
- `scripts/fetch_v76_history.py`;
- four parallel groups × seven Forex pairs;
- 5,000 M5 bars/symbol/chunk;
- 28 symbol credits/chunk with quota-window separation;
- six R2 chunks target ~30,000 M5 bars per pair;
- M15/H1/H4 resampled locally;
- D1 fetched separately;
- raw historical candles are not committed to GitHub.

This grouping stays below the observed Twelve Data batch guard and keeps research independent of V75 live scans.

## News limitation

The canonical data feed does not provide a complete timestamped historical macro calendar such as NFP/ISM suitable for honest before/after-news backtesting. V76 therefore does not fabricate historical news labels from price volatility. Historical news-window performance is not claimed. V74 current-news refresh remains mandatory before live execution.

## Promotion gates R2

Global archetypes are retained from validation evidence only. Per-symbol live promotion additionally requires:
- DEV n>=60, expectancy >0R, PF>=1.10;
- VALIDATION n>=20, expectancy >0R, PF>=1.05;
- OOS n>=20, expectancy >0.05R, PF>=1.15;
- OOS max DD <=10R;
- OOS max losing streak <=10.

No method that fails these gates can authorize live V76 entry.

## Live V76 flow

`V75 data -> V74 HTF/context -> locked V76 symbol method -> M15 location -> M5 strict trigger -> current news -> final venue quote/spread -> MARKET / LIMIT / NO_ENTRY -> structural SL -> RR1/RR2`.

`scripts/entry_v76.py` is a post-V75 gate. It never fetches data. It blocks any methods file except `V76-ENTRY-METHODS-R2`, blocks non-promoted methods, blocks RR2 with <2.2R H1 room, requires current execution venue bid/ask/timestamp and current-news clearance before an executable order.

## Canonical files

- `scripts/research_v76_entry_forex.py` — objective setup primitives/metrics.
- `scripts/evaluate_v76_entry_forex.py` — conservative R2 evaluator.
- `scripts/fetch_v76_history.py` — grouped historical fetcher.
- `scripts/run_v76_entry_research.py` — canonical full research runner.
- `scripts/entry_v76.py` — live post-V75 gate.
- `scripts/summarize_v76.py` — compact result reader.
- `.github/workflows/research-v76-entry.yml` — explicit research only.
- `.github/workflows/validate-entry-v76.yml` — code/protocol/method validator.
- `.github/workflows/summarize-v76.yml` — compact summary generator.
- `data/v76_entry_research.json` — research evidence after successful run.
- `data/v76_entry_methods.json` — locked per-symbol method file.
- `data/v76_entry_summary.json` — compact method/OOS summary after R2.

## Validation

V76 validator run `32053848686` = SUCCESS before final R2 output. It compiles modules, checks 6 setup families/72 variants, grouped history geometry, overlap classification, conservative fill-bar SL behavior and V73 frozen integrity.

## Important status rule

Pilot R1 evidence is not accepted for live execution. R1 showed examples where DEV/VALIDATION strength did not persist OOS, so live gate explicitly rejects `V76-ENTRY-METHODS-R1`. Only final R2 methods may be evaluated for promotion.

Final retained/eliminated archetypes, 28-pair mapping and OOS results must be filled from the successful R2 output without subsequent OOS retuning.
