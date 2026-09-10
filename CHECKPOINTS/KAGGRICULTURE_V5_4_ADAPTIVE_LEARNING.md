# Kaggriculture V5.4 Adaptive Learning Checkpoint

Status date: 2026-09-10
Branch: `research/kaggriculture-v5-4-rank-livestock`
PR: #219 `[KAGGLE-V5.4] Profit-First Rank Livestock Challenger`

## Current objective
Run a conflict-safe profit-first Kaggriculture system with two linked lanes: continuous local adaptive self-play that learns from every win/loss/tie/invalid game, and Kaggle live evaluation using only validated, deduplicated candidates without submission spam.

## Implemented adaptive learning
- `reward-hunter/kaggriculture-v3/learning_rank.py`
  - persistent deterministic learning from local evaluation telemetry only
  - records wins, losses, ties, invalid games, opponent families, seats, parameter values and failure signals
  - penalizes invalid actions/no-ops, catastrophic losses and terminal unsold inventory
  - preserves exploration for untested parameter values
  - generates outcome-guided mutations from surviving elites
  - atomic state write via temporary file + replace
- `search_rank.py`
  - every candidate evaluation contributes positive or negative evidence
  - learned variants are injected between search stages
  - duel/holdout/final evidence is retained for future rounds
- single learning-state writer via `kaggriculture-v54-learning-single-writer`, `cancel-in-progress: false`
- learning memory uses Actions cache outside the Git worktree, so adaptive state does not create Git merge conflicts
- successful research rounds dispatch exactly one next adaptive round

## Verified CI
Adaptive V5.4 validation:
- 33 tests: PASS
- self-contained package/raw-exec: PASS
- official loader: PASS
- both-seat smoke: PASS
- no unit no-ops in smoke
- smoke: 16/16 wins, mean margin +3214.1875, worst +1467, terminal unsold mean 5.125
- generic PR validation also passed on `kaggle-environments==1.32.7`, including full-horizon endgame

## Completed adaptive round 34496666630
Learning state after the first full adaptive round:
- matches: 584
- wins: 564
- losses: 20
- invalid: 0

Best candidate SHA256:
`b113a5da49a597baaacae7de76041b9702f99881d1e35db02beda4408192996f`

Best structure included 3 quadrants, 10 hands, ROI crops, fast expansion, 8 cow cap, 5 sheep cap, 2 goose cap, day-0 livestock, and profit-first herd economics.

Robust evidence:
- direct V1 duel: 8/8 wins, mean margin +41846.625, worst +5568
- unseen holdout: 64/64 wins, mean margin +54298.125, worst +8419
- unseen final: 64/64 wins, mean margin +59033.03125, worst +16885
- invalid/no-op/catastrophic rate: 0
- raw-exec / official loader / episode equivalence: PASS
- strict PROMOTION_READY: FALSE only because terminal unsold inventory remained above the economic waste gate in holdout/final

## Kaggle live state
Explicitly authorized guarded live shadow workflow:
`.github/workflows/kaggriculture-v5-4-live-shadow.yml`

Live-shadow source is the frozen candidate from run `34496666630`; the workflow verifies the exact SHA256 and robust evidence before upload and deduplicates by description.

Submission created successfully:
- Kaggle submission ref: `56148022`
- file: `candidate-main.py`
- description: `V5.4 shadow b113a5da49a5 adaptive livestock`
- submitted: `2026-09-10 16:19:13 UTC`
- latest confirmed status at `2026-09-10 16:22:45 UTC`: `SubmissionStatus.PENDING`
- duplicate rerun correctly skipped a second submission

Existing V1 submission `56139689` remains COMPLETE; its live publicScore was observed at 402.4 immediately before the V5.4 shadow upload.

## Guarded continuous Kaggle promotion
`.github/workflows/kaggriculture-v5-4-rank-livestock.yml` now contains a guarded live-promotion stage for future adaptive rounds.

Rules:
- local self-play continues every successful round
- Kaggle replacement is considered only when strict `promotion.pass_gate == true`
- exact code hash must differ from the previous live candidate
- minimum six-hour live-submission cooldown
- duplicate descriptions are skipped
- failed/missing Kaggle credentials or a submission failure do not corrupt learning state and do not remove the current live agents
- live ledger is persisted beside learning memory in Actions cache, outside the Git worktree
- no re-roll of identical agents

The first explicitly authorized V5.4 shadow is seeded as the live-ledger baseline with SHA `b113a5da49a5...` and timestamp `2026-09-10T16:19:13Z`.

## Current self-play chain
Next chained run `34499414704` has validation PASS and its adaptive research job is running. Future self-dispatched rounds use the newest workflow definition and therefore inherit guarded Kaggle live promotion.

## Conflict policy
- one learning-state writer at a time
- learning/live ledgers are not committed by the research loop
- broken validation stops a chain rather than propagating it
- research candidates cannot overwrite source/champion files
- Kaggle uploads are deduplicated and rate-controlled
- strict promotion gates remain intact; the live-shadow exception was a one-time, explicitly authorized second-slot probe based on frozen robust evidence

## Monitoring
Hourly `Kaggriculture Climb Watch` tracks V1 `56139689`, V5.4 `56148022`, later guarded promotions, self-play completion/errors, PROMOTION_READY events and meaningful score/rank changes.

## Next action
Wait for Kaggle validation of `56148022`. If COMPLETE, Kaggle's simulation evaluator will place it into the live evaluation pool. Continue adaptive self-play in parallel; only a later strict gate-passed and cooldown-eligible challenger may replace a live V5.4 slot.
