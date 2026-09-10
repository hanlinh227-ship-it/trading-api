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
- Latest checked state:
  - validate: SUCCESS
  - search: IN PROGRESS
  - Parallel successive-halving search: IN PROGRESS
  - final holdout / package / promotion: pending
- V2 runs on GitHub-hosted ubuntu-latest, not on `trading-vps`, so it can execute while V1 uses the VPS.
- V2 does NOT auto-submit to Kaggle. It searches, validates, packages and promotes a local V2 champion only when it clears the V1 comparison gate.

## Quick-submit acceleration lane — leaderboard campaign started
- Branch: reward-solver-kaggriculture-quick-submit
- Workflow: .github/workflows/reward-kaggriculture-quick-submit.yml
- Trigger commit: fb4834fe99be0e1600948f3a98d9327a7250c5c1
- Workflow run: 34448297489
- Job: SUCCESS in about 20 seconds on GitHub-hosted ubuntu-latest.
- KAGGLE_API_TOKEN guard: SUCCESS; secret value was not exposed.
- Packaging: SUCCESS.
- Kaggle submission command: SUCCESS.
- Kaggle confirmation: `Successfully submitted to Kaggriculture`.
- Submission reference: 56139515.
- Description: `Reward Solver V1 validated quick submit`.
- Dedicated status-check workflow added on quick-submit branch:
  - workflow: `.github/workflows/reward-kaggriculture-status-check.yml`
  - run: 34448577621
  - status-check job: SUCCESS
  - latest observed Kaggle state at 2026-09-10T07:09:48Z: `SubmissionStatus.PENDING`
  - publicScore/privateScore still blank at that instant.
- Kaggle CLI reported 4 submissions remaining today after this submit.
- Meaning: Kaggle has accepted the submission, but leaderboard evaluation has not completed yet.

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
1. QUICK SUBMIT = real leaderboard baseline is accepted by Kaggle but still PENDING evaluation.
2. V1 DEEP = stable 40-iteration optimization on the VPS.
3. V2 FAST = broad structural search on GitHub-hosted compute.
Do not edit the running V1 lane mid-run. Compare actual leaderboard feedback plus holdout/duel evidence before replacing a champion.

## Next strategic lane after V2 FAST
Livestock/fertilizer/carry logistics (cows/sheep, CARE, FEED, fertilizer use, shed pickup/drop and action-density routing) is the next high-value architecture upgrade. Keep it isolated from V1 while the current run is active.

## What the next chat should do first
1. Check Kaggle submission ref 56139515 status. Current confirmed state is still PENDING as of status-check run 34448577621.
2. Fetch V1 run 34446634238 and V2 run 34447831809.
3. If V1 finishes optimize, inspect its submit job and avoid unnecessary duplicate submissions if the champion is unchanged.
4. If V2 finishes, compare V2 holdout/duel vs V1 before promotion/submission.
5. Keep updating this checkpoint after material changes.

## Safety/handling
- Never expose KAGGLE_API_TOKEN or private credentials.
- Keep secrets only in GitHub Actions secrets.
- Do not manipulate accounts, submission limits, or competition rules.
- Do not claim a Kaggle leaderboard improvement until Kaggle confirms it.
