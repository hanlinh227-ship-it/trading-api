# KAGGRICULTURE REWARD SOLVER CHECKPOINT

Updated: 2026-09-10 20:52 +07

## Project
- Repository: `hanlinh227-ship-it/trading-api`
- Competition: Kaggle Kaggriculture 2026
- `KAGGLE_API_TOKEN` stays only in GitHub Actions secrets. Never request, print, expose or commit it.
- Current promotion evidence must use `kaggle-environments==1.32.7`.
- Future Kaggle candidates must remain self-contained and pass raw-exec + official loader + package/source episode equivalence. Never assume `__file__` exists.

## Live Kaggle incumbent
- Accepted self-contained V1 submission: `56139689`, COMPLETE.
- Last confirmed publicScore: `337.0` from status run `34453161833`.
- Old tar submissions `56139515` and `56139862` are ERROR and must not be reused.

## Historical research lanes
- V1 integration PR #215 merged at `0624e73c079b3097b1b97f69279ea625bd77ec53`.
- V2 Fast failed direct V1 promotion: win rate 0.25, mean margin -728.5.
- V3 PR #216: meta-orchestrator research; an early strong study used mismatched simulator source and is not submission evidence.
- V4 PR #217: rapid four-quadrant expansion/utilization research lane.

## ACTIVE DEPLOYED RESEARCH LANE — V5.3
- PR #218 `[KAGGLE-V5] Mixed-Farm Economy and Cyclic Challenger League` is **MERGED**.
- Squash merge commit: `6435be98d2196f3765f0a07ac6f797d0eec02560`.
- Former feature branch: `codex/kaggriculture-v5-mixed-farm-economy`.
- Dedicated checkpoint: `CHECKPOINTS/KAGGRICULTURE_V5_MIXED_FARM.md`.
- V5 Kaggle submission: **NO**.

### V5 architecture
V5 treats the farm as one capital-allocation engine:
`crop cashflow -> market selling -> working capital -> land/labor/livestock -> feed/care/fertilizer -> harvest -> reinvest`.
It includes dynamic crop ROI, working-capital-aware expansion, dynamic labor, cow/sheep/goose logistics, WHEAT feed reserve, care/feed/harvest, fertilizer use, metered selling, action-efficiency routing and endgame liquidation.

Public top-replay data is OFFLINE research input only. It can generate a challenger prior but cannot bypass local league, direct incumbent duel, unseen holdout/final or runtime/package gates. The submitted agent has no replay/network dependency.

### Strong current-engine V5.2 evidence
Run `34459804967` completed on engine 1.32.7. Best candidate parameter hash prefix `d3dd324477` used approximately: ROI crops, fast expansion, target_hands 11, cow_sheep herd, cow_max 6, sheep_max 4, goose_max 0, livestock_start_day 2, adaptive fertilizer, sell_batch 5.

Results:
- Stage C: 48/48 wins, mean margin +33488.3125, p20 +23825, worst +15643.
- Direct V1 duel: 8/8 wins, mean margin +21765.5, p20 +4976, worst +2546.
- Holdout E: 64/64 valid, 63 wins, mean margin +33243.90625, p20 +26695, worst -2888, catastrophic rate 0.
- Final F: 64/64 wins, mean margin +31518.953125, p20 +22293, worst +3410, catastrophic rate 0.
- raw-exec PASS, official loader PASS, package/source episode equivalence PASS.
- candidate-main.py sha256: `88acdcffe5840f673e4f26edcdf3d03c4b02622c73c73e20f045b475c6027893`.
- artifact: `kaggriculture-v5-research-34459804967`, artifact id `10145994708`.

The V5.2 promotion result was false because the incumbent baseline E/F blocks were invalid from benchmark plumbing: legacy V1 accepted only `obs`, while the tracker called `(obs, configuration)`. This was a benchmark adapter bug, not a V5 candidate runtime failure.

### V5.3 hardening completed
- `benchmark_v5.py`: added a compatibility adapter around legacy V1 baseline only; live V1 code is unchanged.
- `tests/test_v5.py`: added a real 1.32.7 regression requiring tracked legacy incumbent games to be valid in both seats.
- shared PR workflow now recognizes the V5 lane, installs 1.32.7 and runs V5-specific contracts instead of stale V3-only assumptions.
- PR validation run `34484026991`: **SUCCESS** across compilation/contracts, generated raw-exec, official both-seat episodes and full-horizon check.
- public replay workflow now selects only the two newest dated replay Parquet shards, caps parsing to 80 rows/file and 160 seat-records, has a 10-minute parser timeout, writes preflight diagnostics and does not cancel an in-flight challenger run.
- public-meta run `34484024952`: archive download SUCCESS, bounded recent Parquet analysis SUCCESS, then adaptive local challenger league started.
- canonical V5.3 run `34483998540`: validate SUCCESS; full crop/herd/expansion research was IN PROGRESS at last check.

### Strict campaign gates remain unchanged
Even though V5.2 strongly beat V1 locally, its observed economics still missed deliberately strict campaign targets:
- mean full unlock about day 17.9 vs target <=12;
- full-farm peak productive utilization about 0.50-0.53 vs target >=0.60;
- mean terminal unsold inventory about 21-22 vs target <=8.
Do not lower these gates merely to manufacture PASS. Future challengers should improve them while preserving margin/tail performance.

## Continuous challenger deployment on `main`
The V5 public-meta/challenger workflow is now on default branch `main`, so its schedules are actually eligible to run continuously:
- fast cycle: every 6 hours at `17 */6 * * *`;
- deep cycle: daily at `43 2 * * *`.

Main workflow hardening commit: `91765c5734c2b60d20ab69f9d9787061131d0a15`.
Main live-start trigger commit: `520967e79dd25b6ea84292e31c6eed8ef7bf1482`.
Main workflow run: `34485086057`.
At last check it was pending/queued because the branch adaptive challenger run was still using the same non-cancelling concurrency group. This is intentional: do not kill useful in-flight research just to start duplicate compute. When the branch run clears, the main run can proceed.

The cyclic loop is:
`public replay refresh -> bounded meta analysis -> meta prior -> staged candidate search -> local multi-family league -> direct incumbent duel -> unseen holdout/final -> raw-exec/package-equivalence -> PROMOTION_READY only if all gates pass`.

No schedule/push path can submit to Kaggle. Actual Kaggle submission remains a separate explicit action using the exact validated candidate artifact/hash.

## Claude V6 status
Claude reported a local V6 branch `claude/kaggriculture-v6-adaptive-continuous`, local HEAD `8e223bcc`, 32 local tests and candidate `cand-15b4263783d9`, but Claude's session had no GitHub write permission. No V6 branch/PR exists on GitHub and no bundle/patch is attached in this ChatGPT conversation. Therefore V6 is **not integrated or deployed**. If its bundle/patch is later uploaded, inspect/import it separately.

## Operational rule
- V5.3 research/challenger infrastructure is now deployed to `main` and active/queued in GitHub Actions.
- Keep live Kaggle incumbent V1 until a strict current-engine candidate passes all promotion gates.
- Do not force Kaggle matchmaking or bypass quotas.
- Never expose `KAGGLE_API_TOKEN`.

## NEXT CHAT COMMAND
If user says `check PR kaggle`:
1. inspect latest `main` runs for `Kaggriculture V5 - Public Meta Intelligence` first;
2. inspect branch runs `34483998540` and `34484024952` if still relevant;
3. inspect exact promotion reasons and candidate hash before any submission decision;
4. if a candidate is `PROMOTION_READY`, recheck live Kaggle status/remaining submission state and use only the exact validated self-contained artifact;
5. if Claude V6 bundle/patch appears, evaluate it independently rather than trusting reported local metrics;
6. never expose `KAGGLE_API_TOKEN`.
