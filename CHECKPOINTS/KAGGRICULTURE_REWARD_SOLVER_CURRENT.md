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
- Latest checked state:
  - validate: SUCCESS
  - optimize: SUCCESS
  - Prepare isolated environment: SUCCESS
  - Baseline gate: SUCCESS
  - Search and holdout gate: SUCCESS
  - Final holdout verification: SUCCESS
  - Package champion: SUCCESS
  - Commit improved champion state: SUCCESS
  - Artifact upload: SUCCESS
  - submit job: QUEUED at last check
- Current V1 champion file reports holdout win_rate=1.0, mean_margin=18429 and duel vs previous incumbent 6/6 wins.
- Current V1 champion params include target_hands=11 and sell_floor_ratio=0.75991; these match the self-contained V1 currently accepted by Kaggle.
- Important: V1 branch main.py still contains the old `Path(__file__)` runtime loader. The existing submit job packages `submission.tar.gz`, so it should not be treated as a new distinct champion unless raw-exec compatibility is fixed first.

## Lane V2 FAST — parallel, isolated, non-conflicting
- Branch: reward-solver-kaggriculture-v2-fast
- Workflow run: 34447831809
- validate: SUCCESS
- search: SUCCESS
- Parallel successive-halving search: SUCCESS
- Independent final holdout: SUCCESS
- Package V2 candidate: SUCCESS
- V2 candidate final holdout vs starter: 8/8 wins, mean_margin=12271.75, worst_margin=7676.
- However V2 candidate did NOT clear the direct V1 promotion gate:
  - duel_vs_v1 win_rate=0.25
  - mean_margin=-728.5
  - therefore improved_vs_v1=false and no champion commit was made.
- Artifact produced: kaggriculture-v2-fast-lane, artifact ID 10140604526.
- Conclusion: V2 FAST completed successfully as a search experiment, but V1 remains the stronger incumbent.

## Kaggle submission status
### Submission 56139515 — first quick-submit attempt
- File: submission.tar.gz
- Description: Reward Solver V1 validated quick submit
- Final status: ERROR
- Validation episode: 107391264 completed.
- Root cause from Kaggle agent logs: `NameError: name '__file__' is not defined` inside `_load_submission_params()` when Kaggle raw-executed main.py.
- This was an execution-environment compatibility issue, not a Kaggle API/auth failure.

### Fix applied
- Quick-submit branch was changed so `main.py` no longer depends on `__file__`/champion.json at Kaggle runtime.
- A raw-exec compatibility gate was added and passed: `RAW_EXEC_GATE_OK`.
- Submission path changed to a self-contained `main.py`.

### Submission 56139689 — current live baseline
- File: main.py
- Description: Reward Solver V1 raw-exec fix
- Quick-submit workflow run: 34449193248
- GitHub submit job: SUCCESS
- Kaggle CLI confirmation: `Successfully submitted to Kaggriculture`.
- Latest confirmed Kaggle status at 2026-09-10T07:24:39Z: `SubmissionStatus.COMPLETE`.
- publicScore: 600.0
- privateScore: blank at that instant.
- Validation episode: 107394181, COMPLETED at 2026-09-10T07:21:58Z.
- Meaning: corrected V1 is now accepted and activated by Kaggle; 600.0 is the first confirmed live baseline score.

## Status checker
- Workflow: `.github/workflows/reward-kaggriculture-status-check.yml`
- It now points to current submission 56139689.
- Latest status-check run: 34449786623
- Result: SUCCESS
- It confirmed submission 56139689 is COMPLETE with publicScore 600.0.

## Architecture rule going forward
Three lanes are intentionally isolated:
1. CURRENT KAGGLE BASELINE = 56139689, self-contained V1, COMPLETE, publicScore 600.0.
2. V1 DEEP = optimization completed successfully; its current champion params match the accepted V1 baseline, and its queued old tar submit path still has known raw-exec risk.
3. V2 FAST = completed, but failed V1 duel promotion gate and must not replace V1.
Do not submit V2 merely because its starter-benchmark is strong; V1 remains incumbent until a candidate beats it robustly.

## What the next chat should do first
1. Treat submission 56139689 / score 600.0 as the real Kaggle baseline.
2. Check V1 run 34446634238 submit job before allowing another Kaggle submission; avoid wasting a slot on the same champion or the known old tar/raw-exec path.
3. Start the next isolated upgrade lane focused on stronger opponent-aware/meta play rather than more small parameter tuning.
4. Compare every new candidate against V1 on holdout + direct duel before considering a submission.
5. Keep updating this checkpoint after material changes.

## Safety/handling
- Never expose KAGGLE_API_TOKEN or private credentials.
- Keep secrets only in GitHub Actions secrets.
- Do not manipulate accounts, submission limits, or competition rules.
- Do not claim a Kaggle leaderboard improvement until Kaggle confirms it.
