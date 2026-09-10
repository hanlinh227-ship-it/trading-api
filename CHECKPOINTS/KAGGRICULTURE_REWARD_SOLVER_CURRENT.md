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
- V2 runs on GitHub-hosted ubuntu-latest, not on `trading-vps`, so it can execute while V1 uses the VPS.
- V2 does NOT auto-submit to Kaggle. It searches, validates, packages and promotes a local V2 champion only when it clears the V1 comparison gate.

## Quick-submit acceleration lane — start leaderboard campaign immediately
- Branch: reward-solver-kaggriculture-quick-submit
- Created from the already validated V1 branch so it does not wait for the current 40-iteration optimization run.
- Workflow: .github/workflows/reward-kaggriculture-quick-submit.yml
- Trigger: .github/reward-kaggriculture-quick-submit-trigger
- Trigger commit: fb4834fe99be0e1600948f3a98d9327a7250c5c1
- Workflow run: 34448297489
- Runner: GitHub-hosted ubuntu-latest, so it does not consume the trading VPS.
- Latest checked state:
  - checkout/setup: SUCCESS
  - KAGGLE_API_TOKEN guard: SUCCESS (secret exists; value is never printed)
  - Install Kaggle CLI: IN PROGRESS
  - package / submit / confirm: pending
- Purpose: submit the previous already-validated V1 champion immediately to obtain real Kaggle leaderboard feedback while V1 deep optimization and V2 fast search continue in parallel.
- The quick-submit workflow uses standard Kaggle CLI syntax: `kaggle competitions submit -c kaggriculture ...`.

## V2 FAST changes
- Density control: tunable max_quadrants=1..3.
- Market pacing: tunable sell_batch_limit.
- Opponent-aware selling: separate ahead / neutral / behind sell floors and cash-gap trigger.
- Action efficiency: tunable movement-distance penalty.
- Phase timing: tunable early/mid/late crop boundaries.
- Crop composition mutation: nested crop weights are mutable.
- Strategic seed biases toward wheat + strawberry and away from melon-heavy play.
- Robust objective includes win rate, mean margin, p20 margin, worst margin and final money.
- Honest gate: V2 candidate duels the original V1 agent on both seats.
- Promotion requires holdout robustness and non-negative duel margin vs V1.

## V2 search acceleration
- Default pool: 64 candidates.
- Fast screen: one full 720-turn seed, both seats.
- Successive halving: top 10 advance to full multi-seed evaluation.
- ProcessPoolExecutor uses available CPU cores, auto capped at 8 workers.
- Separate holdout seeds are used after training seeds.

## Architecture rule going forward
Three lanes are intentionally isolated and may run simultaneously:
1. QUICK SUBMIT = get a real leaderboard baseline as fast as possible.
2. V1 DEEP = stable 40-iteration optimization on the VPS.
3. V2 FAST = broad structural search on GitHub-hosted compute.
Do not edit the running V1 lane mid-run. Compare actual leaderboard feedback plus holdout/duel evidence before replacing a champion.

## Next strategic lane after V2 FAST
Livestock/fertilizer/carry logistics (cows/sheep, CARE, FEED, fertilizer use, shed pickup/drop and action-density routing) is the next high-value architecture upgrade. Keep it isolated from V1 while the current run is active.

## What the next chat should do first
1. Fetch run 34448297489 first. If quick submit completed, inspect its job/logs and confirm whether Kaggle accepted the submission.
2. If quick submit failed, repair the exact auth/packaging/CLI error without exposing secrets and retrigger only the quick-submit lane.
3. Fetch V1 run 34446634238 and V2 run 34447831809.
4. If V1 finishes optimize, inspect its submit job.
5. If V2 finishes, compare V2 holdout/duel vs V1 before promotion.
6. Keep updating this checkpoint after material changes.

## Safety/handling
- Never expose KAGGLE_API_TOKEN or private credentials.
- Keep secrets only in GitHub Actions secrets.
- Do not manipulate accounts, submission limits, or competition rules.
- Do not claim a Kaggle submission or leaderboard improvement until GitHub/Kaggle confirms it.
