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
- Workflow: Reward Solver - Kaggriculture
- Current workflow_dispatch run: 34446634238
- User selected iterations=40 and submit=true.
- Latest checked state:
  - validate: SUCCESS
  - optimize: IN PROGRESS on self-hosted runner `trading-vps`
  - Prepare isolated environment: SUCCESS
  - Baseline gate: SUCCESS
  - Search and holdout gate: IN PROGRESS
  - Final holdout / package / commit / submit: pending
- Previous validated V1 champion file reports holdout win_rate=1.0, mean_margin=18429 and duel vs previous incumbent 6/6 wins. These are local simulator metrics, not leaderboard proof.

## Lane V2 FAST — parallel, isolated, non-conflicting
- Branch: reward-solver-kaggriculture-v2-fast
- Created from V1 head aa883d99a774f390795f3d0a1ca3d899142f111a.
- Isolated solver path: reward-hunter/kaggriculture-v2-fast/
- Isolated workflow: .github/workflows/reward-kaggriculture-v2-fast.yml
- Trigger file: .github/reward-kaggriculture-v2-fast-trigger
- Trigger commit/head: 0a9fa0e0eec29d9ccc6b1b6fbb452e92bf7baae8
- Workflow run: 34447831809
- Latest checked state: validate IN PROGRESS; official simulator installation running.
- V2 runs on GitHub-hosted ubuntu-latest, not on `trading-vps`, so it can execute while V1 uses the VPS.
- V2 does NOT auto-submit to Kaggle. It only searches, validates, packages and promotes a local V2 champion when it clears the V1 comparison gate. This avoids competing submissions/slots while V1 submit run is active.

## Why V2 was added
Public environment mechanics and current public competition research show that the earlier V1 search space is too narrow if the objective is to catch the leaders quickly. V2 therefore explores structural, easy-to-complete variables before committing to slower RL work.

V2 FAST changes:
- Density control: tunable max_quadrants=1..3 instead of assuming all land should be bought.
- Market pacing: tunable sell_batch_limit so premium goods are metered instead of dumped.
- Opponent-aware selling: separate ahead / neutral / behind sell floors and cash-gap trigger.
- Action efficiency: tunable movement-distance penalty.
- Phase timing: tunable early/mid/late crop phase boundaries.
- Crop composition mutation: search can mutate nested crop weights, not just scalar thresholds.
- Strategic seed biases toward wheat + strawberry and away from melon-heavy play.
- Robust objective includes win rate, mean margin, p20 margin, worst margin and final money.
- Honest gate: V2 candidate is tested against the original V1 agent as an actual opponent on both seats.
- Promotion requires holdout robustness and non-negative duel margin vs V1.

## V2 search acceleration
- Default pool: 64 candidates.
- Fast screen: one full 720-turn seed, both seats.
- Successive halving: top 10 candidates advance to full multi-seed evaluation.
- ProcessPoolExecutor uses available CPU cores (auto, capped at 8 workers).
- Separate holdout seeds are used after training seeds.
- This is intended to explore more strategy variants in less wall-clock time than the sequential V1 tuner.

## V2 files/commits created
- f4f1113bd8ca6b60b34651ac648d15c7d950f768 — isolated V2 agent
- 9344e8e55e2d5c55c1832a8c7a63416d276279c3 — robust benchmark/duel scoring
- 42957dcf335a4cfb5e5d79c57b1039a2a069097c — parallel successive-halving tuner
- 73d06c0246a683013fdb032a63f49e6daebf3aec — V2 strategic seed champion
- 68d38bd42017d30b33c285d08df65efae2eb0420 — isolated submission packager
- de7d202306d1b688f2e353eb7b9797308279d8b7 — V2 fast workflow
- 0a9fa0e0eec29d9ccc6b1b6fbb452e92bf7baae8 — trigger V2 fast run

## Architecture rule going forward
Keep V1 and V2 separate until real evidence says V2 is stronger. Do not edit V1 files while its submit workflow is running. V1 is the stable/deep lane; V2 FAST is the rapid structural-search lane. After both finish, compare holdout + duel + actual Kaggle leaderboard behavior. Only then promote/merge the better ideas.

## Next strategic lane after V2 FAST
The next high-value architecture upgrade is livestock/fertilizer/carry logistics (cows/sheep, CARE, FEED, fertilizer use, shed pickup/drop and action-density routing). Do not bolt this into V1 mid-run. Implement it as another isolated experimental lane after V2 FAST establishes the new search harness, or in parallel on a separate branch if compute allows.

## What the next chat should do first
1. Fetch jobs for V1 run 34446634238 and V2 run 34447831809.
2. If V2 validate/search failed, fetch the failed job logs and repair only the V2 branch/workflow.
3. If V1 reaches submit, inspect submit status/logs; do not claim Kaggle submission success without confirmation.
4. If V2 finishes, read `reward-hunter/kaggriculture-v2-fast/artifacts/tuning-report.json` from the workflow artifact or committed state and compare V2 holdout/duel against V1.
5. If V2 clears its gate, keep it as a candidate but wait for real Kaggle evidence before replacing V1.
6. Continue checkpoint updates after every material branch/run/promotion change.

## Safety/handling
- Never expose KAGGLE_API_TOKEN or private credentials.
- Keep secrets only in GitHub Actions secrets.
- Do not manipulate accounts, submission limits, or competition rules.
- Do not claim a Kaggle submission or leaderboard improvement until GitHub/Kaggle confirms it.
