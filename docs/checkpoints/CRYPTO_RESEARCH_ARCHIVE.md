# CRYPTO RESEARCH ARCHIVE

Updated: 2026-08-17
Purpose: preserve conclusions from retired crypto research artifacts while keeping the active repository tree lean.

## Retention policy
Active tree keeps only code/results required to reproduce or extend the surviving V24-Core diagnostic lineage plus selected key validation evidence:
- `scripts/blind_backtest_crypto.py`
- `scripts/blind_backtest_crypto_v17.py`
- `scripts/blind_backtest_crypto_v22.py`
- `scripts/blind_backtest_crypto_v24.py`
- `data/blind_backtest_v17.json`
- `data/blind_backtest_v22.json`
- `data/blind_backtest_v24.json`
- `data/blind_backtest_v24_validation.json`
- `data/blind_backtest_v26.json` temporarily as decisive negative true-blind evidence / diagnostic source
- `.github/workflows/blind-backtest-v24.yml`

Retired one-off workflows, diagnostics and rejected-version scripts/results are removed after their conclusions are checkpointed. Git history preserves exact historical artifacts.

## Research history retained as conclusions
- V3: forced-MARKET baseline around 37.5% win at ~1.5R; slightly negative expectancy.
- V4: indicator stacking materially worsened performance; rejected.
- V5/V6: regime-first simplification recovered performance; useful baseline lineage.
- V7: >50% WR was achieved by making TP too close; avg RR ~0.76R and expectancy negative; rejected.
- V8/V9: RR/breadth attempts did not robustly improve results; rejected.
- V10–V14: barrier grids, robustness searches and time-series momentum experiments informed later simplification but were not promoted.
- V15: historical derivatives/funding/OI coverage was effectively unusable in the current pipeline; do not credit it as an active edge.
- V16/V17: development favored 6h/24h/72h momentum; V17 one true-blind sample ~43.4% WR at 1.5R with positive expectancy.
- V18–V21: higher-RR/regime/fade/persistence variants unstable; rejected.
- OKX public taker-trade probe proved usable historical trade-side data could be collected.
- V22: first-5m taker flow improved the same price-core baseline on Jul12/Jul10 but aggregate expectancy remained around/slightly below zero; flow adds information but is not universally decisive.
- V23: raising RR without fixing direction failed; rejected.

## V24 — retained diagnostic baseline
Initial untouched evidence:
- Jul04: 41 TP / 15 SL, 73.21% WR, avg RR 1.679, +0.956R.
- Jul02: 24 TP / 10 SL among 34 resolved, 70.59% WR, avg RR 1.641, +0.865R, 22 unresolved.
Both were `normal`, so the regime guard itself was not validated.

Locked June validation on unchanged V24:
- 278 trades, 262 resolved, 112 TP / 150 SL;
- 42.75% WR, avg RR 1.647, +0.132R;
- Jun30 7.27% / -0.807R;
- Jun27 33.33% / -0.126R;
- Jun24 83.33% / +1.228R;
- Jun21 50.91% / +0.338R;
- Jun18 38.64% / +0.018R.
Conclusion: V24 is not robust enough to promote; keep only as diagnostic baseline.

June row-level lessons:
- Jun30 was systemic: 51/56 decisions SELL, SELL 4 TP / 46 SL, BUY 0/5; high-confidence score buckets and macro/flow agreement were still poor.
- Direct V24-vs-V25 barrier comparison changed 51 Jun30 sides; 46 symbols hit SL in BOTH directions, zero V24-SL became V25-TP, and four V24 winners became V25 losers. This is strong evidence of market-quality/timing/barrier failure rather than a simple wrong-direction problem.
- Jun27 flow agreement outperformed conflict and the few V24 regime-driven flips all lost, which motivated testing macro anchoring cleanly.

## V25 development — rejected
V25 development used already-revealed June dates. It anchored direction to macro and added a synchronized same-direction extreme breadth + OFI whole-market climax reversal rule.
Result:
- 278 trades, 263 resolved, 111 TP / 152 SL;
- 42.21% WR, avg RR 1.624, +0.114R;
- Jun30 `sell_climax`: 0 TP / 56 SL = -1R;
- Jun27 improved to 38.89% / +0.019R.
Conclusion: **whole-market climax reversal is rejected.** The macro-anchor component required independent true-blind testing.

## V26 locked true-blind May — rejected
Before V26 creation, repository search found no `2026-05-*` cutoff references. V26 made one clean conceptual change from V24: BUY/SELL side always followed the macro momentum/structure score; flow/regime context could alter confidence/RR but could not flip side. The V25 climax reversal was excluded.

Locked May result:
- 275 trades, 272 resolved;
- 79 TP / 193 SL;
- 29.04% WR;
- avg RR 1.646;
- expectancy -0.235R;
- only 3 unresolved.
Per date:
- May30 32.73% / -0.145R;
- May27 25.93% / -0.311R;
- May24 21.82% / -0.429R (`distribution_reversal`);
- May21 43.64% / +0.163R;
- May18 20.75% / -0.460R.
Four of five dates were negative. **Macro-always-owns-direction is rejected.** The apparent Jun27 development benefit did not generalize.

May diagnostics:
- breadth <=0.10: 23.36% WR / -0.385R;
- breadth 0.30–0.70: 43.64% / +0.163R;
- breadth 0.70–0.90: 32.73% / -0.145R;
- breadth >=0.90: 21.82% / -0.429R.
Treat extreme breadth only as a risk marker; there are too few date-level samples to lock thresholds.
- flow aligned with the macro side: 24.64% / -0.320R;
- flow conflict/neutral: 39.66% / +0.031R;
- flow unavailable: 26.90% / -0.301R.
Thus the June observation that flow agreement was better is not universal.
- overall median SL arrival: ~39 M5 candles; median TP arrival: ~70. May24/May18 median SL arrival was ~23/~21.5 candles. Together with Jun30 two-sided SL behavior, this shifts research away from another bias rule toward market quality, timing and barrier geometry.

## Current direction after V26
Rejected and must not be revived without genuinely new evidence:
- generic indicator stacking;
- tiny-TP win-rate inflation;
- cosmetic RR increases;
- V25 whole-market climax reversal;
- V26 macro-always-owns-direction.

Retain V24-Core only as a diagnostic comparator. Next research should use already-revealed June + May as development data to investigate **pre-entry market quality, entry timing and barrier survival**, without optimizing exact thresholds on those dates. A minimal successor should then be frozen and tested on a completely untouched block, preferably April 2026.

A separate live `CHAOS / NO TRADE` gate is a legitimate future research question because forced-MARKET stress can expose states where both sides are poor. It must never be used inside the forced-MARKET benchmark to inflate results.

## Cleanup rule
1. Keep the surviving comparator/dependency chain and key evidence.
2. Summarize rejected hypotheses here.
3. Remove concluded one-off scripts/workflows/results from active tree when no longer needed.
4. Git history is the forensic archive.
5. Never delete live data-pipeline files (`fetch-market.yml`, `fetch_crypto.py`, `request.json`, `data/status.json`, `data/latest.json`).