# CRYPTO RESEARCH ARCHIVE

Updated: 2026-08-17
Purpose: preserve conclusions from retired crypto research artifacts while keeping the active repository tree lean.

## Retention policy
Active tree keeps only code/results required to reproduce or extend the current V24-Core lineage:
- `scripts/blind_backtest_crypto.py` — base utilities/data loader and earlier V6-style core dependency.
- `scripts/blind_backtest_crypto_v17.py` — short-horizon momentum/structure core dependency.
- `scripts/blind_backtest_crypto_v22.py` — actual OKX taker-flow extension dependency.
- `scripts/blind_backtest_crypto_v24.py` — current V24-Core research engine.
- `data/blind_backtest_v17.json`, `data/blind_backtest_v22.json`, `data/blind_backtest_v24.json` — key evidence/results.
- `.github/workflows/blind-backtest-v24.yml` — current research runner.

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
- V22: first-5m actual taker flow improved the same price-core baseline on two blind dates (Jul12 and Jul10), though overall expectancy remained around/slightly below zero. This was evidence that microflow adds information.
- V23: raising RR without fixing direction did not improve expectancy; rejected.
- V24: kept V22 core and added market price-breadth + flow-breadth/regime context. Unseen Jul04 sample: 41 TP / 15 SL, 73.21% win, avg planned RR 1.679, expectancy +0.956R. Unseen Jul02 sample: 24 TP / 10 SL among 34 resolved, 22 unresolved, 70.59% resolved win, avg RR 1.641, expectancy +0.865R. Both were classified `normal`, so the results support V24-Core but do not yet prove the regime guard itself or a sustainable 70%+ system.

## Current direction after archive cleanup
Freeze and validate V24-Core on multiple additional untouched dates before promotion:
6h/24h/72h momentum + H4/H1 structure + H4 EMA context + BTC relative strength + M15 location/anti-chase + first-5m OKX taker OFI + market breadth/flow context + structural SL + dynamic RR roughly 1.6–2.0 when justified.

## Cleanup rule going forward
For each new research generation:
1. keep the current engine and only the dependency chain needed to reproduce it;
2. keep key validation result files, not every temporary grid/probe/raw dump;
3. summarize rejected versions and lessons here or in `CRYPTO_BREAKOUT_STATE.md`;
4. delete one-off workflow files once the experiment is concluded;
5. never delete live data pipeline files (`fetch-market.yml`, `fetch_crypto.py`, `request.json`, `data/status.json`, `data/latest.json`) during research cleanup.