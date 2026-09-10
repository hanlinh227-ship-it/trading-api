# Kaggriculture V5 Mixed-Farm Economy Checkpoint

Updated: 2026-09-10

## Identity
- Repository: `hanlinh227-ship-it/trading-api`
- Branch: `codex/kaggriculture-v5-mixed-farm-economy`
- Base: `codex/kaggriculture-v4-full-farm-expansion`
- Current engine target: `kaggle-environments==1.32.7`
- Kaggle submission: **NO**

## Mission
Build a resilient mixed-farm economy that converts crops, market sales, livestock, fertilizer and labor into working capital, opens land without bankrupting production, and only promotes a candidate that beats the incumbent on current-engine unseen games. Public replay intelligence is research input only; it can never bypass local promotion gates.

## V5.0 failure and V5.1 recovery
Canonical run `34458086918` exposed an economic deadlock: 16/16 valid but 0 wins, mean margin -2400.625, mean money 0.0. Root cause was reserving almost the full next-land cost while continuing to hire/build, starving the seed engine.

V5.1 fixed working-capital ordering, limited hires, limited animal pipeline, synchronized structures with actual/queued livestock, reduced duplicate shed pickups, diversified crop ROI and preserved feed wheat. Run `34458596933` then passed the economic smoke: 16/16 valid, 4 wins, mean money 1392.25, mean margin -889.4375, mean peak animals 12.0625, no unit no-ops. It is improved but not yet a champion.

## V5.2 hardening
V5.2 adds failure-prevention and the cyclic challenger loop:
- `features.py` now derives the canonical clock from `day * turnsPerDay + hour`; it no longer trusts `obs['step']`, which can be absent for seat 1 in 1.32.7. A compatibility shim injects the derived step for older routing helpers.
- `benchmark_v5.py` uses the same seat-safe clock for full-unlock telemetry so seat 1 cannot report false day-zero unlocks.
- regression tests cover missing-step seat behavior and JSON-encoded replay cells.
- `meta/replay_intelligence.py` now reads JSON, JSONL and Parquet archives, including JSON-like string/binary cells, with bounded row/file limits, deduplication and schema diagnostics.
- `.github/workflows/reward-kaggriculture-v5-meta-intel.yml` installs PyArrow, retries public archive download, fails closed on empty/stale replay parsing, uploads diagnostics even on failure, and runs a cyclic local challenger league.
- cyclic cadence after merge to default branch: fast public-meta + challenger run every 6 hours; one deeper daily challenger run. No automatic Kaggle submission.
- every challenger still runs staged screening, multiple opponent families, direct incumbent duel, unseen holdout/final, raw-exec and package/source equivalence before `PROMOTION_READY` can be written.

## Public-meta input
Public Kaggle top replay archive notebook output currently contains Parquet files such as `episodes.parquet`, dated `replays_YYYY-MM-DD.parquet` shards and `top10_history.parquet`. The original analyzer only read JSON/JSONL and therefore parsed 0 records in run `34458096559`; that specific failure is now fixed in code and being re-tested.

Research notes: `reward-hunter/kaggriculture-v3/meta/PUBLIC_META_RESEARCH.md`
Analyzer: `reward-hunter/kaggriculture-v3/meta/replay_intelligence.py`

## Current workflows / runs
- Canonical V5.2 research: run `34459804967`, trigger commit `2037eb40919517484a88d71a1b978d0aaa55f1f4`.
- Public-meta V5.2 loop: run `34459819333`, trigger commit `392f84984a76f31260c1b09d88cf201348730900`.
- Previous V5.1 canonical run: `34458596933`.
- Previous public-meta run with JSON-only parser: `34458096559` FAILED because the downloaded archive was Parquet; superseded by V5.2.

Do not claim V5.2 is complete until both new runs have been inspected. If either fails, repair the exact failing step and rerun before considering merge/submission.

## Promotion/submission rule
Acreage, local money, similarity to a top replay, or one smoke win are not sufficient. V5 may be considered promotion-ready only when current 1.32.7 evidence passes all validity, seat symmetry, incumbent duel, meta-opponent, unseen holdout/final, tail-risk, full-farm/utilization, terminal inventory, raw-exec and package-equivalence gates. Kaggle submission remains explicit/manual and must never be triggered by schedule or push.

## Continuous improvement semantics
“Continuous rematch” means continuous **local challenger-league evaluation** against incumbent and distinct opponent families plus periodic public-meta refresh. Kaggle itself controls live ladder matchmaking; the repository must not try to force/bypass matchmaking or submission limits.

## NEXT CHAT COMMAND
User can type: `check PR kaggle`

The next AI should:
1. find the open PR beginning `[KAGGLE-V5]`,
2. read this checkpoint from the PR head branch,
3. inspect runs `34459804967` and `34459819333` first,
4. if public-meta parsing still fails, inspect the emitted Parquet schema diagnostics and adapt the parser rather than guessing,
5. if canonical research fails, fix the exact test/economy/runtime error and rerun,
6. compare V5 evidence with incumbent/live Kaggle baseline only after current-engine gates finish,
7. never expose `KAGGLE_API_TOKEN`,
8. never auto-submit a candidate that has not passed promotion/raw-exec/package-equivalence gates.
