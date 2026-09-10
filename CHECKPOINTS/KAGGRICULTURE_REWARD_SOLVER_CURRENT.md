# KAGGRICULTURE REWARD SOLVER CHECKPOINT

Updated: 2026-09-10 20:46 +07

## Project
- Repository: `hanlinh227-ship-it/trading-api`
- Competition: Kaggle Kaggriculture 2026
- V1 integration PR #215 merged at `0624e73c079b3097b1b97f69279ea625bd77ec53`.
- `KAGGLE_API_TOKEN` is stored only in GitHub Actions secrets. Never request, print or commit it.
- Current promotion evidence must use `kaggle-environments==1.32.7`.

## Live Kaggle incumbent
- Submission `56139689`, self-contained `main.py`, COMPLETE.
- Last confirmed publicScore: `337.0` from status run `34453161833`.
- Old tar submissions `56139515` and `56139862` are ERROR and must not be reused.
- Every future submission must be self-contained and pass raw-exec + official loader + package/source equivalence; `__file__` cannot be assumed.

## Historical lanes
- V2 Fast failed direct V1 promotion despite strong starter results: direct V1 win rate 0.25, mean margin -728.5.
- V3: PR #216, branch `codex/kaggriculture-v3-meta-orchestrator`; early strong study used a mismatched simulator source and is not submission evidence.
- V4: PR #217, branch `codex/kaggriculture-v4-full-farm-expansion`; isolated research lane for fast 4-quadrant expansion.

## ACTIVE / DEPLOYMENT LANE — V5.3
- Branch: `codex/kaggriculture-v5-mixed-farm-economy`
- PR: #218 `[KAGGLE-V5] Mixed-Farm Economy and Cyclic Challenger League`
- Dedicated checkpoint: `CHECKPOINTS/KAGGRICULTURE_V5_MIXED_FARM.md`
- Kaggle submission from V5: **NO**.

### Architecture
V5 optimizes one mixed economy: crop ROI, market selling, working capital, land, dynamic labor, cow/sheep/goose logistics, WHEAT feed reserve, CARE/FEED/HARVEST, fertilizer, action efficiency and endgame liquidation. Public top replay data is research-only input; it cannot bypass local gates and the submitted runtime has no network/file dependency.

### Strong V5.2 current-engine evidence
Run `34459804967` completed on 1.32.7. Best candidate (`d3dd324477...`) was roughly 6 cows + 4 sheep, ROI crops, fast expansion, adaptive fertilizer, 11 target hands.
- Stage C: 48/48 wins, mean margin +33488.3125.
- Direct V1 duel: 8/8 wins, mean margin +21765.5.
- Holdout: 64 valid, 63 wins, mean margin +33243.90625, p20 +26695, worst -2888.
- Final: 64/64 wins, mean margin +31518.953125, p20 +22293, worst +3410.
- raw-exec PASS, official loader PASS, episode equivalence PASS.
- candidate-main.py sha256 `88acdcffe5840f673e4f26edcdf3d03c4b02622c73c73e20f045b475c6027893`.

V5.2 promotion was false because benchmarked V1 baseline holdout/final blocks were invalid due to a one-argument legacy incumbent being called through a two-argument tracker. V5.3 fixes the benchmark adapter and includes a real regression test. Do not interpret the V5.2 promotion failure as candidate runtime failure.

### Remaining economic blockers
Even with baseline plumbing fixed, the observed candidate does not yet meet the intentionally strict full-farm campaign requirements:
- mean full unlock measured around day 17.9 vs gate <=12;
- full-farm peak productive utilization around 0.50-0.53 vs gate >=0.60;
- terminal unsold mean around 21-22 vs gate <=8.
Do not lower these gates merely to generate PASS; subsequent challenger search should improve the policy.

### V5.3 fixes and active execution
- `benchmark_v5.py`: legacy incumbent two-argument adapter added.
- `tests/test_v5.py`: baseline validity regression added.
- shared PR workflow now detects V5 and validates against engine 1.32.7 rather than stale V3-only assumptions.
- PR validation run `34484026991`: SUCCESS across compilation/tests, raw-exec, both-seat official episodes and full-horizon check.
- public-meta workflow now parses only the two newest dated replay Parquet shards, bounded to 80 rows/file / 160 seat-records with a 10-minute parser timeout and preflight artifact.
- public-meta run `34484024952`: replay download SUCCESS; bounded Parquet analysis SUCCESS; adaptive local challenger search IN PROGRESS.
- canonical V5.3 run `34483998540`: IN PROGRESS; purpose is to rerun full search with valid incumbent baselines.
- cyclic cadence once merged to default branch: every 6 hours plus a deeper daily run. Runs do not auto-submit Kaggle.

## Claude V6 handoff status
Claude reported local branch `claude/kaggriculture-v6-adaptive-continuous`, local HEAD `8e223bcc`, 32 local tests and a local champion candidate, but Claude had no GitHub write permission. No V6 branch/PR is on GitHub and no bundle/patch is attached to this ChatGPT conversation. Therefore V6 has not been integrated or deployed.

## Operational rule
The currently safe action is to deploy/operate the V5.3 research + cyclic challenger infrastructure while V5.3 canonical/adaptive search continues. Actual Kaggle submission remains a separate explicit decision after a candidate passes the strict gate. Kaggle itself controls live ladder matchmaking; never attempt to force matchmaking or bypass quotas.

## NEXT CHAT COMMAND
If user says `check PR kaggle`:
1. inspect PR #218 and `CHECKPOINTS/KAGGRICULTURE_V5_MIXED_FARM.md`;
2. inspect runs `34483998540`, `34484024952`, `34484026991`;
3. if #218 is merged, inspect `main` scheduled workflow state and latest default-branch run;
4. verify baseline validity and promotion reasons before any submission;
5. if Claude V6 bundle/patch is later attached, inspect/import it separately rather than assuming its reported local metrics;
6. never expose `KAGGLE_API_TOKEN`.
