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
- workflow_dispatch run: 34446634238
- User selected iterations=40 and submit=true.
- validate: SUCCESS
- optimize: SUCCESS
- Baseline/Search-Holdout/Final-Holdout/Package/Artifact: all SUCCESS
- Current V1 champion validation: holdout win_rate=1.0, mean_margin=18429; duel vs previous incumbent 6/6 wins.
- Current V1 champion params include target_hands=11 and sell_floor_ratio=0.75991; these match the self-contained V1 currently accepted by Kaggle.
- submit job also ran and Kaggle accepted another submission command at 2026-09-10T07:26:33Z.
- That old V1 submit path packaged `submission.tar.gz` and the branch main.py still contains the known `Path(__file__)` loader, so this extra submission is not considered the canonical baseline until Kaggle validates it.

## Lane V2 FAST
- Branch: reward-solver-kaggriculture-v2-fast
- Workflow run: 34447831809
- validate/search/final holdout/package: SUCCESS
- V2 final holdout vs starter: 8/8 wins, mean_margin=12271.75, worst_margin=7676.
- Direct duel vs V1: win_rate=0.25, mean_margin=-728.5.
- improved_vs_v1=false; no V2 champion promotion.
- V1 remains incumbent.

## Kaggle submissions
### 56139515
- File: submission.tar.gz
- Final status: ERROR
- Root cause: `NameError: name '__file__' is not defined` during Kaggle raw execution.

### 56139689 — canonical live baseline
- File: main.py
- Description: Reward Solver V1 raw-exec fix
- Status: COMPLETE
- publicScore: 600.0
- privateScore: blank at last check
- Validation episode: 107394181, COMPLETED
- This is the first confirmed working Kaggle submission and is the canonical live baseline.

### 56139862 — extra V1 deep submit
- File: submission.tar.gz
- Description: Reward Solver validated champion
- Submitted by V1 deep workflow after optimize completed.
- Latest confirmed status at 2026-09-10T07:27:13Z: PENDING.
- Kaggle CLI reported 3 submissions remaining today after this submit.
- Because this path still uses the old tar package/runtime loader, do not treat it as valid until Kaggle confirms COMPLETE.

## Status checker
- Workflow: `.github/workflows/reward-kaggriculture-status-check.yml`
- It targets canonical submission 56139689.
- Run 34449786623 confirmed 56139689 COMPLETE with publicScore 600.0.
- Run 34450005641 additionally observed 56139862 PENDING.

## Architecture rule going forward
1. Keep 56139689 as the canonical live baseline.
2. Do not spend another Kaggle submission slot on V1/V2 unless a candidate is materially different and clears raw-exec + holdout + direct-duel gates.
3. V2 FAST failed direct V1 duel, so do not submit it.
4. Start the next isolated upgrade lane focused on opponent-aware/meta play and larger structural improvements rather than more tiny parameter tuning.
5. Every future Kaggle candidate must be self-contained and pass a raw-exec compatibility gate before submission.

## What the next chat should do first
1. Check whether 56139862 becomes COMPLETE or ERROR; do not rely on it meanwhile.
2. Track the live rating/episodes of canonical submission 56139689.
3. Build the next isolated opponent-aware/meta upgrade lane and benchmark it against V1 on both seats with unseen seeds.
4. Submit only if it robustly beats V1 and passes raw-exec validation.
5. Keep updating this checkpoint after material changes.

## Safety/handling
- Never expose KAGGLE_API_TOKEN or private credentials.
- Keep secrets only in GitHub Actions secrets.
- Do not manipulate accounts, submission limits, or competition rules.
- Do not claim a Kaggle leaderboard improvement until Kaggle confirms it.
