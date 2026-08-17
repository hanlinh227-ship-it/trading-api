# CRYPTO RESEARCH ARCHIVE

Updated: 2026-08-17
Purpose: preserve conclusions from retired crypto research artifacts while keeping the active repository tree lean.

## Retention policy
Active tree keeps only code/results required to reproduce or extend the current V24-Core lineage:
- `scripts/blind_backtest_crypto.py` — base utilities/data loader and earlier V6-style core dependency.
- `scripts/blind_backtest_crypto_v17.py` — short-horizon momentum/structure core dependency.
- `scripts/blind_backtest_crypto_v22.py` — actual OKX taker-flow extension dependency.
- `scripts/blind_backtest_crypto_v24.py` — current V24-Core diagnostic research engine.
- `data/blind_backtest_v17.json`, `data/blind_backtest_v22.json`, `data/blind_backtest_v24.json`, `data/blind_backtest_v24_validation.json` — key evidence/results.
- `.github/workflows/blind-backtest-v24.yml` — retained V24 runner.

Retired one-off workflows, diagnostics, raw probe outputs and rejected-version result files are removed from the current tree after their conclusions are checkpointed. Git history still preserves old commits if forensic recovery is ever needed.

## Research history retained as conclusions
- V3: forced-MARKET baseline around 37.5% win at ~1.5R; slightly negative expectancy.
- V4: increased complexity/indicator stacking materially worsened performance; rejected.
- V5/V6: regime-first simplification recovered performance; V6 achieved positive expectancy on some old/new samples and became a useful baseline.
- V7: pushed win rate above 50% on a sample by moving TP too close; average RR around 0.76R and expectancy negative; rejected because higher win rate alone was misleading.
- V8/V9: attempts to restore RR / add breadth did not robustly improve results; rejected.
- V10–V14 family: barrier grids, diagnostics, direction/robustness searches and time-series-momentum experiments informed later simplification, but did not become the final architecture.
- V15: historical funding/OI derivatives experiments had effectively unusable coverage in the current pipeline; derivatives must not be credited as an active edge until reliable historical coverage exists.
- V16: development comparison favored short 6h/24h/72h momentum over longer weekly horizons.
- V17: true-blind sample achieved roughly 43.4% win at ~1.5R with positive expectancy; became the surviving short-horizon price/structure core.
- V18–V21: higher-RR, regime, reversal/fade and per-coin persistence variants were unstable across dates; not promoted.
- OKX public taker-trade probe validated that historical trade-side data can be collected and converted into order-flow imbalance; the standalone probe script/workflow/raw JSON became redundant after V22 integrated the capability.
- V22: first-5m actual taker flow improved the same price-core baseline on two blind dates (Jul12 and Jul10), though overall expectancy remained around/slightly below zero. This remains evidence that microflow adds information.
- V23: raising RR without fixing direction did not improve expectancy; rejected.
- V24 initial evidence: kept V22 core and added market price-breadth + flow-breadth/regime context. Jul04 = 41 TP / 15 SL, 73.21% win, avg RR 1.679, +0.956R. Jul02 = 24 TP / 10 SL among 34 resolved, 70.59% resolved win, avg RR 1.641, +0.865R. Both were `normal`, so they did not validate the regime guard.

## V24 locked June validation — concluded
A separate harness froze the exact V24 engine and ran five previously uninspected June 2026 cutoffs without changing scoring weights, regime thresholds, first-5m flow logic, structural SL or RR.

Aggregate across Jun30/27/24/21/18:
- 278 trades, 262 resolved;
- 112 TP / 150 SL;
- 42.75% resolved win rate;
- average planned RR 1.647;
- expectancy +0.132R;
- flow coverage 62.2%.

Per-date results:
- Jun30: 4 TP / 51 SL among 55 resolved = 7.27% WR, -0.807R expectancy, `normal` regime.
- Jun27: 18 TP / 36 SL among 54 resolved = 33.33% WR, -0.126R, `distribution_reversal`.
- Jun24: 45 TP / 9 SL = 83.33% WR, +1.228R, `normal`.
- Jun21: 28 TP / 27 SL = 50.91% WR, +0.338R, `normal`.
- Jun18: 17 TP / 27 SL among 44 resolved = 38.64% WR, +0.018R, `normal`, 11 unresolved.

Important lessons:
- The exceptional Jul04/Jul02 results do not generalize consistently. V24 is not promoted as a final/main engine.
- The first locked non-normal `distribution_reversal` sample (Jun27) was negative, so the V24 regime guard is not validated as a reliable protective edge.
- Microflow remains informative but incremental: macro/micro agreement produced 44.87% WR and +0.235R expectancy at avg 1.759R, versus conflict at 38.55% WR and essentially flat +0.002R at 1.6R.
- Profile dispersion was large: majors/memes were positive, while DeFi and AI/high-beta were negative. These are diagnostic observations, not permission to retrofit filters and reuse June as blind evidence.
- Jun30 is the critical failure sample: V24 classified it `normal` despite price breadth 0.214, flow breadth 0.317 and median OFI -0.374, then suffered 51 SL from 55 resolved trades. Diagnose this failure before designing V25; do not simply move thresholds to fit it.

## Current direction after V24 validation
V24-Core remains a **diagnostic baseline**, not a validated live engine:
6h/24h/72h momentum + H4/H1 structure + H4 EMA context + BTC relative strength + M15 location/anti-chase + first-5m OKX taker OFI + market breadth/flow context + structural SL + dynamic RR roughly 1.6–2.0 when justified.

The June dates are now development/diagnostic data. Next correct research sequence:
1. diagnose Jun30 and Jun27 row-level directional failures;
2. formulate a minimal theory-driven V25 change without cosmetic RR manipulation or generic indicator stacking;
3. freeze V25 before seeing outcomes on a completely untouched block, preferably May 2026;
4. promote only if multiple unseen dates show materially better robustness, not merely a stronger aggregate driven by one exceptional day.

## Cleanup rule going forward
For each new research generation:
1. keep the current engine and only the dependency chain needed to reproduce it;
2. keep key validation result files, not every temporary grid/probe/raw dump;
3. summarize rejected versions and lessons here or in `CRYPTO_BREAKOUT_STATE.md`;
4. delete one-off workflow files once the experiment is concluded;
5. never delete live data pipeline files (`fetch-market.yml`, `fetch_crypto.py`, `request.json`, `data/status.json`, `data/latest.json`) during research cleanup.