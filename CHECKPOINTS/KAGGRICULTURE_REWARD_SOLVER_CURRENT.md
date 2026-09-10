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

## Canonical V3 revalidation launched
- To avoid manual workflow dispatch, V3 workflow was extended with an isolated push trigger file. No Kaggle submission job was added.
- Workflow modification commit: 112a288bf4160cce3228ba18f3cd6958fdd38d59
- Research trigger commit: 347cb1f2f1b22b5136d10dc9d6abfc62387e7fb5
- Canonical full-search workflow run: 34453319508
- Event: push on codex/kaggriculture-v3-meta-orchestrator
- Latest checked state: validate IN PROGRESS, installing pinned official simulator; research will run after validate.
- Research uses fresh deterministic study seed = GitHub run ID and search budget 8, both seats, meta opponent suite, unseen holdout/final blocks, raw-exec/package checks and fail-closed promotion.
- If promotion passes, workflow may commit only V3 `champion.json` and generated `main.py`; it never submits to Kaggle.

## Current architecture rule
1. Live incumbent is 56139689 / current confirmed publicScore 337.0.
2. Old tar submissions are invalid and must not be reused.
3. V2 failed the V1 direct-duel promotion gate.
4. V3 is the strongest architectural candidate, but DO NOT submit yet because canonical full-search revalidation run 34453319508 is still running.
5. Submit V3 only if canonical run clears promotion, candidate raw-exec remains PASS, generated candidate hash is identified, and no packaging mismatch remains.
6. Keep PR #216 open until canonical evidence is captured and reviewed.

## What the next chat should do first
1. Fetch jobs for V3 run 34453319508.
2. When research completes, inspect its logs and artifact `kaggriculture-v3-search-34453319508`.
3. If promotion PASS, fetch updated PR #216 head/champion/main and verify the exact candidate hash and raw-exec evidence.
4. If promotion FAIL, keep V1 live and improve V3; do not submit merely on historical study-001 numbers.
5. Recheck Kaggle live score before consuming another submission slot.
6. Never expose KAGGLE_API_TOKEN.

## Safety/handling
- Never expose KAGGLE_API_TOKEN or private credentials.
- Keep secrets only in GitHub Actions secrets.
- Do not manipulate accounts, submission limits, or competition rules.
- Do not claim a Kaggle leaderboard improvement until Kaggle confirms it.
