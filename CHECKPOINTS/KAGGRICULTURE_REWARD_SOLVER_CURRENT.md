# KAGGRICULTURE REWARD SOLVER CHECKPOINT

Updated: 2026-09-10

## Project
- Repository: hanlinh227-ship-it/trading-api
- Competition: Kaggle Kaggriculture 2026
- Main integration PR: #215
- PR #215 merged to main at commit 0624e73c079b3097b1b97f69279ea625bd77ec53
- User joined Kaggriculture and accepted competition rules.
- User reports KAGGLE_API_TOKEN is stored as a GitHub Actions repository secret. Never request, print, or commit the token value.

## Lane V1 — deep/stable solver
- Branch: reward-solver-kaggriculture-v1
- Solver path: reward-hunter/kaggriculture/
- Workflow run: 34446634238
- validate: SUCCESS
- optimize: SUCCESS
- submit command: SUCCESS, but that tar-based submission later failed Kaggle validation.
- V1 local validation: holdout win_rate=1.0, mean_margin=18429; duel vs previous incumbent 6/6 wins.
- Accepted self-contained V1 remains the live incumbent, but live Kaggle performance has degraded from its initial 600 validation baseline.

## Lane V2 FAST
- Branch: reward-solver-kaggriculture-v2-fast
- Workflow run: 34447831809
- validate/search/final holdout/package: SUCCESS
- V2 final holdout vs starter: 8/8 wins, mean_margin=12271.75, worst_margin=7676.
- Direct duel vs V1: win_rate=0.25, mean_margin=-728.5.
- improved_vs_v1=false; no V2 champion promotion.

## Kaggle submissions
### 56139515
- File: submission.tar.gz
- Final status: ERROR
- Root cause: `NameError: name '__file__' is not defined` during Kaggle raw execution.

### 56139689 — canonical live incumbent
- File: main.py
- Description: Reward Solver V1 raw-exec fix
- Status: COMPLETE
- Validation episode: 107394181, COMPLETED
- Fresh check run 34453161833 at 2026-09-10T08:04 UTC shows publicScore: 337.0.
- It has completed at least 9 public episodes after validation.
- Earlier 600.0 was only the initial live baseline immediately after validation; current confirmed live score is 337.0.

### 56139862 — extra V1 deep tar submit
- File: submission.tar.gz
- Description: Reward Solver validated champion
- Fresh check run 34453161833 shows final status: ERROR.
- Do not use it as baseline and do not repeat the old tar/runtime path.

## Status checker
- Branch: reward-solver-kaggriculture-quick-submit
- Workflow: `.github/workflows/reward-kaggriculture-status-check.yml`
- Latest run: 34453161833 — SUCCESS
- Current confirmed live state: 56139689 COMPLETE / publicScore 337.0; 56139862 ERROR.

## V3 Codex meta-orchestrator
- PR: #216
- URL: https://github.com/hanlinh227-ship-it/trading-api/pull/216
- Title: [KAGGLE-V3] Meta Orchestrator and Robust Search System
- Branch: codex/kaggriculture-v3-meta-orchestrator
- PR remains OPEN, DRAFT, mergeable.
- Original implementation commit: b60a93d00765757880d8d928afdb2978374e6ea3
- Canonical-source hardening commit: bf04be16e17605d2158e5079cb64396767785ad8
- V3 final PR validation run 34452492123: SUCCESS.
  - compile/tests: PASS (13 tests)
  - raw exec: PASS
  - official loader: PASS
  - both-seat/multi-seed smoke: PASS as a contract test
  - full-horizon incumbent check: 2/2 wins, mean margin +7899
- Historical study-001 reported D direct V1 duel 8/8 wins, mean +5299.25; E 64/64; F 64/64, but this evidence is NOT sufficient for submission because audit found study-001 used a different simulator source under the same 1.32.4 version label.
- benchmark.py now enforces pinned Kaggle simulator source hash `9741c0470a8db98a70644491d5121ae6295413343d1a08ef9fcee35e0b76f2c5`.
- Committed V3 main.py is self-contained and embeds `harvest_wait=False`; raw-exec passes.
- `package_submission.py` with no `--params` generates the default `harvest_wait=True`, so future submission must use the validated self-contained `main.py` or explicitly pass the validated champion params. Do not submit the default package by mistake.
- V3 has NOT been submitted to Kaggle.

## Canonical V3 revalidation
- Workflow modification commit: 112a288bf4160cce3228ba18f3cd6958fdd38d59
- Research trigger commit: 347cb1f2f1b22b5136d10dc9d6abfc62387e7fb5
- Canonical full-search workflow run: 34453319508
- Event: push on codex/kaggriculture-v3-meta-orchestrator
- V3 runs independently from the new V4 lane and should not be cancelled merely because V4 exists.

## V4 full-farm expansion lane — NEW
- Branch: `codex/kaggriculture-v4-full-farm-expansion`
- Created from V3 snapshot `347cb1f2f1b22b5136d10dc9d6abfc62387e7fb5`, so it cannot disturb the in-flight V3 canonical research run.
- Dedicated checkpoint: `CHECKPOINTS/KAGGRICULTURE_V4_FULL_FARM.md`.
- Dedicated workflow: `.github/workflows/reward-kaggriculture-v4-full-farm.yml`.
- Trigger commit: `531467e9428eb17668c6a1254344df4b1a32dc65`.
- Workflow run: `34454305004`.
- Latest checked state: V4 `validate` IN PROGRESS on GitHub-hosted runner.
- No Kaggle secret or submission command is used by V4.

### V4 design goals
- Mandatory rapid progression to all 4 quadrants rather than treating land unlock as a late optional purchase.
- Explicit 1000/2000/4000 land economics and expansion modes: balanced / fast / max.
- Reordered market capital flow: SELL -> BUY_LAND -> HIRE -> BUY_SEED.
- Liquidity pressure lowers sell floor near an expansion deadline to convert inventory into land capital.
- Dynamic workforce scales with owned acreage/workload, up to 14 hands.
- Fast-cash crop mix before full unlock helps finance the next quadrant.
- Seed throughput and stock targets expand while new acreage is under-filled.
- Plant/DIG priority rises until target utilization is reached.
- Benchmark now measures full unlock rate, mean full-unlock day, peak utilization and full-farm peak utilization in addition to win/margin/tail/no-op metrics.
- Search jointly explores expansion aggressiveness, land buffer, crop mode, labor, distance cost, fill target, fill priority and seed throughput.
- Search stages A/B use shorter horizons to reject weak candidates quickly; C/D/E/F remain canonical full-horizon evidence.
- V4 promotion hard requirements on unseen holdout and final blocks: 100% full unlock, mean full unlock <= day 12, full-farm peak utilization >= 68%, zero unit no-ops, robust multi-family performance and positive direct V1 duel.
- V4 does NOT auto-submit to Kaggle. Even a local PASS must be reviewed before consuming a submission slot.

## Current architecture rule
1. Live incumbent is 56139689 / current confirmed publicScore 337.0.
2. Old tar submissions are invalid and must not be reused.
3. V2 failed the V1 direct-duel promotion gate.
4. V3 canonical research continues as the clean meta baseline.
5. V4 runs in parallel as an aggressive full-farm lane and must prove both performance and expansion/utilization requirements.
6. Do not submit V3/V4 until the relevant canonical run clears promotion, raw-exec remains PASS, exact candidate hash is identified, and packaging matches the validated candidate.
7. Keep PR #216 open while V3 evidence is under review; V4 should remain isolated until its own validation is known.

## What the next chat should do first
1. Fetch V4 workflow run `34454305004` and inspect validation/research status.
2. Fetch V3 run `34453319508` in parallel; do not confuse their results.
3. If V4 validation fails, inspect logs and repair the V4 branch only.
4. If V4 research completes, compare: direct V1 duel, holdout/final margins, full_unlock_rate, mean_full_unlock_day, full_farm_peak_utilization, no-op rate and raw-exec result.
5. Only consider V4 superior if it clears the full promotion gate; opening land faster alone is not enough if expected leaderboard performance collapses.
6. Recheck Kaggle live score before consuming another submission slot.
7. Never expose KAGGLE_API_TOKEN.

## Safety/handling
- Never expose KAGGLE_API_TOKEN or private credentials.
- Keep secrets only in GitHub Actions secrets.
- Do not manipulate accounts, submission limits, or competition rules.
- Do not claim a Kaggle leaderboard improvement until Kaggle confirms it.
