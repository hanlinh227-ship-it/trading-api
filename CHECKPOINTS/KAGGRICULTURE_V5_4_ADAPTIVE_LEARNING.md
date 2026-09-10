# Kaggriculture V5.4 Adaptive Learning Checkpoint

Status date: 2026-09-10
Branch: `research/kaggriculture-v5-4-rank-livestock`
PR: #219 `[KAGGLE-V5.4] Profit-First Rank Livestock Challenger`

## Current objective
Build a conflict-safe, profit-first Kaggriculture challenger that learns from every local match outcome (win/loss/tie/invalid), improves the next candidate population, and remains fail-closed before any Kaggle submission.

## Implemented
- `reward-hunter/kaggriculture-v3/learning_rank.py`
  - persistent deterministic learning from local evaluation telemetry only
  - records wins, losses, ties, invalid games, opponent families, seats, parameter values and failure signals
  - penalizes invalid actions/no-ops, catastrophic losses and terminal unsold inventory
  - preserves exploration for untested parameter values
  - generates outcome-guided mutations from surviving elites
  - atomic state write via temporary file + replace
- `search_rank.py`
  - consumes learning state
  - every candidate evaluation contributes both positive and negative evidence
  - learned variants are injected between search stages
  - duel/holdout/final evidence is retained for future rounds
  - exports learning summary and learned parameter patch
- `tests/test_learning_rank.py`
  - verifies wins and losses both affect learning
  - verifies invalid/no-op/inventory penalties
  - verifies persistent-state round trip
  - verifies learned variants remain valid and unique
- `.github/workflows/kaggriculture-v5-4-rank-livestock.yml`
  - one serialized research-state writer via `kaggriculture-v54-learning-single-writer`
  - `cancel-in-progress: false`
  - learning memory restored/saved with GitHub Actions cache
  - learning state stored outside Git worktree, preventing learning-memory merge conflicts
  - no Kaggle submission action
- `.github/workflows/reward-kaggriculture-v3.yml`
  - fixed brittle V5 engine detection
  - detects pinned `kaggle-environments==1.32.7` from the evaluator instead of policy docstring

## Verified CI
Latest V5.4 validation after adaptive-learning changes passed:
- 33 tests: PASS
- self-contained package/raw-exec: PASS
- official loader: PASS
- both-seat smoke: PASS
- no unit no-ops in smoke

Generic PR validation also passed after fixing the 1.32.4/1.32.7 engine mismatch, including full-horizon endgame contract.

## Active research
Adaptive learning push run: `34496666630`
- validation: PASS
- adaptive match memory restore/init: PASS
- profit-first livestock challenger league with win/loss learning: running at checkpoint time

## Conflict policy
- Never mutate `main` or the Kaggle incumbent from an unvalidated research run.
- Learning state is not committed by the research loop.
- Only one learning-state writer may run at a time.
- Promotion remains fail-closed on current-engine, both-seat, incumbent duel, unseen holdout/final, runtime/package equivalence and economic safety gates.
- Do not auto-submit to Kaggle.

## Next action
When run `34496666630` finishes, inspect `learning_state_after.json`, best learned patch, duel/holdout/final and promotion reasons. If not promotion-ready, use the learned state to seed the next V5.4 challenger round rather than resetting search memory.
