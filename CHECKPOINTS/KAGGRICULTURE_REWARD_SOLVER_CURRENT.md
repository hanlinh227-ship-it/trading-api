# KAGGRICULTURE REWARD SOLVER — CURRENT CHECKPOINT

Updated: 2026-09-11 +07

## Project / integrity
- Repository: `hanlinh227-ship-it/trading-api`.
- Competition: Kaggle Kaggriculture.
- Canonical simulator: `kaggle-environments==1.32.7`.
- `KAGGLE_API_TOKEN` remains only in GitHub Actions secrets; never request, print or commit it.
- No forced matchmaking, quota bypass, multi-accounting, duplicate/re-roll spam, hidden-state exploitation or copied private opponent traces.

## Live Kaggle
- V1 submission `56139689`: last confirmed COMPLETE; recheck before quoting a current score/rank.
- V5.4 live-shadow `56148022`: last confirmed PENDING; recheck before a current status claim.
- Kaggle controls live matchmaking frequency. Local/self-play workflows cannot force individual Kaggle episodes.
- Guarded promotion on main requires composite strict + monotonic promotion evidence, a new candidate hash, and a six-hour cooldown; duplicate descriptions/hashes are skipped.

## Historical anchors
- V1 PR #215 merged at `0624e73c079b3097b1b97f69279ea625bd77ec53`.
- V5 PR #218 merged at `6435be98d2196f3765f0a07ac6f797d0eec02560`.
- PR #219 `[KAGGLE-V5.7] Adaptive Agro-Economic Learning Rank Engine` is MERGED into `main`; merge commit `219a10c9c9c6c5d932e79e57f9aa6bc6da9be85d`.
- Latest verified V5.7 old-lineage research artifact before the conflict-free cutover: run `34543115864`, artifact `10180135630`. Its learning snapshot is the bootstrap source for the canonical main lineage.

## ACTIVE CANONICAL CHAIN — V5.7 Conflict-Free Continuous Learning
The only authoritative writer is now `main`.

### Conflict elimination / state ownership
- Main workflow commit: `8c2c78712aac506bd79725e4614b7bddcb3b3c00` (`Make main the single conflict-free Kaggriculture learning writer`).
- Main trigger commit: `357013356973daa40eded640526f6548c69f3f9a` (`Start canonical conflict-free Kaggriculture learning chain on main`).
- Research is permitted only when `github.ref == refs/heads/main`.
- Concurrency group: `kaggriculture-v57-main-canonical-single-writer`, `cancel-in-progress: false`.
- Canonical state paths are isolated under `/tmp/kaggriculture-v57-main-learning/`.
- Canonical cache namespace is `kaggriculture-v57-main-learning-*`; legacy branch caches cannot interleave with main.
- First canonical run imports the last verified learning snapshot from artifact `10180135630` atomically. If the snapshot cannot be validated, the workflow fails safe to a clean state rather than accepting partial/corrupt memory.
- Kaggle live ledger is updated atomically only after a submitted candidate becomes visible.
- Queue-next logic allows exactly one successor: if another canonical main run is already queued/in-progress/pending, the current run emits `NEXT_ROUND_DEDUPED` instead of creating fan-out.

### Legacy branch retirement
- Former writer branch `research/kaggriculture-v5-4-rank-livestock` is archived at commit `b55a73c59a43e3ef187eace3463727023b0851a6`.
- Its workflow is read-only/no-op: no research, no cache/state writes, no Kaggle submission, no recursive next-round dispatch.
- An already-started legacy run may finish using its historical workflow snapshot, but it cannot share the new main cache namespace; any successor created from the archived branch is no-op. This extinguishes the old lineage without corrupting canonical state.

## Learning / promotion doctrine
- Every local win/loss/tie/invalid result updates adaptive evidence; losing candidates are learned from but cannot replace the accepted champion.
- `monotonic_rank.py` maintains accepted-capital high water and rejected/taboo strategy evidence.
- `agro_reasoning.py` attributes failures such as fourth-quadrant overreach, poor land utilization, excessive movement, labor drag, feed stress, herd capital not converted, weak price capture, terminal inventory and failure to compound.
- Candidate selection combines accepted champion, archived personal champions, learned patches, failure-derived recovery hypotheses, public-top priors and exploratory mutations.
- Public high-Elo structures such as 3Q / COW+SHEEP are priors only; personal benchmark evidence decides acceptance.
- Candidate promotion is fail-closed: strict gate and monotonic capital gate must both pass; a lower-money or tail-regressing candidate never replaces the incumbent.

## Current performance problem to solve
- Continuous games are not the bottleneck: the previous learning history already contained roughly 14.7k matches.
- Latest analyzed V5.7 challenger was stuck in a local optimum: roughly 56–58k money versus the stronger incumbent around 74.5k.
- The weak challenger leaned toward 4Q + cow-only, while the stronger incumbent used 3Q + COW/SHEEP; movement idle was about 65% and productive utilization only about 46–48%.
- Next algorithmic objective is a breakthrough search around structurally different farm families, not merely more repetitions of the same configuration. Do not lower gates to manufacture progress.

## Latest canonical run
- Canonical main run: `34549835117`.
- `validate`: SUCCESS.
- `Canonical lineage guard`: SUCCESS.
- `Restore canonical adaptive memory and live ledger`: SUCCESS.
- `Bootstrap or validate conflict-free memory`: SUCCESS.
- `Adaptive agro-economic challenger league`: IN PROGRESS at last check.
- Promotion, state save and exactly-one next-round queue occur only after the challenger league completes successfully.

## Next action
1. Let run `34549835117` finish; do not manually create redundant canonical research runs.
2. Inspect its `PROMOTION`, `MONOTONIC`, `CAPITAL_REGRESSION`, `DUEL`, `HOLDOUT`, `FINAL`, `AGRO_REASONING`, `ROUND_PLAN`, `NEXT_ROUND`, and queue-dedup result.
3. Confirm exactly one successor on `main`; legacy branch must remain no-op.
4. If candidate regresses, keep incumbent and use failure evidence to expand a materially different 3Q/COW+SHEEP-centered breakthrough family rather than replaying the losing 4Q/cow-only pattern.
5. Never weaken strict/monotonic gates merely to create a promotion.
