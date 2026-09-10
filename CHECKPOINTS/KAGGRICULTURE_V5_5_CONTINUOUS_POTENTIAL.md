# KAGGRICULTURE V5.5 — CONTINUOUS POTENTIAL CHECKPOINT

Updated: 2026-09-10 23:50 +07

## Goal
Continuously increase challenger potential without resetting useful learning or blindly increasing compute. The controller adapts search breadth/depth from observed local evidence while strict promotion rules stay unchanged.

## Branch / PR
- Branch: `research/kaggriculture-v5-4-rank-livestock`
- PR #219: `[KAGGLE-V5.5] Continuous Potential Rank Engine`
- Keep draft until full research evidence is reviewed.

## Core loop
`match -> learn win/loss/tie/invalid -> identify weak opponent families -> retain elite archive -> detect stagnation/regression -> adapt candidate budget/exploration/mutation -> duel/holdout/final -> strict gate -> queue next round`

## Adaptive controller
- exploit: base requested budget, exploration ~0.16, mutation depth 1;
- recover after regression: >=32 candidates, exploration >=0.26, mutation depth >=2;
- stagnation >=2: >=40 candidates, exploration >=0.32, mutation depth >=3;
- stagnation >=4: >=56 candidates, exploration >=0.42, mutation depth 4;
- every fifth round: periodic deep search >=48 candidates, exploration >=0.34, mutation depth >=3;
- hard limit: 8..64 candidates.

## Learning memory
- Existing V5.4 state is migrated in place; no reset.
- Adds family-conditioned parameter statistics, bounded round history, up to 8 archived champions and controller state.
- Atomic state writes; single writer concurrency group remains non-cancelling.
- Round potential score changes exploration policy only; it does not weaken promotion gates.

## Commits
- `ea85581abd8dfb6453eb419fd5c343d51fe38ee8` — continuous-potential learner.
- `d413cb2db24bb64d373546ddad39c900196ce6cc` — adaptive search integration.
- `3c345e82f4eecc838d7fc84a7f18afaa47c63fef` — continuous-potential regression tests.
- `63f653774a36313c9fdf80303d659c1d57b9dd2f` — adaptive workflow/next-round budget.
- `473c546ab52d296962b0dd6e42377f3c25a3314e` — first V5.5 research trigger.

## Validation
Run `34503967537`: SUCCESS. Compile/regression contracts, self-contained package gate and both-seat smoke all passed.

Push research run `34503963040`: validate SUCCESS; research job `102961627629` was PENDING at last check. This queueing is expected because only one research process may write the persistent learning state at a time.

## Kaggle live
- V1 `56139689`: COMPLETE, latest confirmed publicScore 402.4.
- V5.4 shadow `56148022`: last confirmed PENDING.
- Future V5.5 submission is guarded: strict promotion PASS + new hash + >=6h cooldown + duplicate check. No forced matchmaking or quota bypass.

## Next check
Inspect run `34503963040`, then any newer V5.5 run. On completion inspect `ROUND_PLAN`, `NEXT_ROUND`, weak families, champion count, control/stagnation state, duel/holdout/final and promotion reasons. Verify the following round is dispatched with the adaptive candidate count. Update the central checkpoint after material results.
