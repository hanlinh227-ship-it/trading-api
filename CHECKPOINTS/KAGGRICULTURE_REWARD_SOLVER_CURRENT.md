# KAGGRICULTURE REWARD SOLVER CHECKPOINT

Updated: 2026-09-11 00:03 +07

## Project
- Repository: `hanlinh227-ship-it/trading-api`
- Competition: Kaggle Kaggriculture 2026
- `KAGGLE_API_TOKEN` stays only in GitHub Actions secrets. Never request, print, expose or commit it.
- Current promotion evidence must use `kaggle-environments==1.32.7`.
- Every Kaggle candidate must be self-contained and pass raw-exec + official loader + package/source episode equivalence. Never assume `__file__` exists.
- Do not force Kaggle matchmaking, bypass submission quotas, duplicate/reroll submissions, or use hidden/private opponent state.

## Live Kaggle agents
- V1 submission `56139689`, `main.py`, COMPLETE. Latest confirmed publicScore: **402.4** from the 2026-09-10 16:22 UTC Kaggle CLI status captured by live-shadow workflow run `34501308533`.
- V5.4 live shadow `56148022`, `candidate-main.py`, description `V5.4 shadow b113a5da49a5 adaptive livestock`; exact candidate sha256 `b113a5da49a597baaacae7de76041b9702f99881d1e35db02beda4408192996f` from research run `34496666630`.
- Last confirmed V5.4 shadow status: **PENDING** at 2026-09-10 16:22:45 UTC. Recheck before claiming COMPLETE/ACTIVE or a live score.
- Old tar submissions `56139515` and `56139862` are ERROR and must not be reused.
- Kaggle controls live matchmaking/episode frequency. Internal self-play may run continuously, but the repo cannot force arbitrary Kaggle rematches.

## Historical lanes
- V1 PR #215 merged at `0624e73c079b3097b1b97f69279ea625bd77ec53`.
- V2 Fast rejected vs V1: win rate 0.25, mean margin -728.5.
- V3 PR #216 remains a research/meta-orchestrator lane; its old mismatched-simulator study is not submission evidence.
- V4 PR #217 remains the four-quadrant/full-farm campaign lane.
- V5 PR #218 merged at `6435be98d2196f3765f0a07ac6f797d0eec02560`; current-engine V5.2 produced very strong local results but missed strict full-farm/terminal-waste gates. Do not weaken gates just to manufacture PASS.

## Main deployed V5.3 research lane
- Default `main` contains continuous public-meta/challenger research.
- Fast public-meta cycle: every 6 hours; deep cycle: daily.
- Public replay data is offline research input only; submitted agents have no replay/network dependency.
- Main V5.3 workflow itself does **not** auto-submit to Kaggle.
- It remains useful as a broad meta-intelligence lane while the profit-first rank lane evolves independently.

## ACTIVE RANK LANE — PR #219 / V5.6 MONOTONIC CAPITAL LEARNING
- PR #219 title: `[KAGGLE-V5.6] Monotonic Capital Learning Rank Engine`.
- Head branch: `research/kaggriculture-v5-4-rank-livestock`.
- PR is **open + draft + mergeable**. Keep draft until at least one full V5.6 current-engine research round is reviewed.
- Dedicated checkpoint on branch: `CHECKPOINTS/KAGGRICULTURE_V5_6_MONOTONIC_CAPITAL.md`.
- Latest V5.6 research trigger commit: `1e743d4095c59087f063ffba18cb32c5329b6295`.

### V5.6 objective
The new requirement is not merely to run forever. Failed investment configurations must produce permanent learning, the accepted strategy must not move backward, and the next search must use the failure to look elsewhere.

Important interpretation: stochastic exploratory matches can still score lower. It is impossible to guarantee every random match earns more. The enforceable guarantee is at the **accepted research champion / promotion level**: a worse challenger cannot replace the accepted champion and cannot reach Kaggle live promotion.

### V5.6 monotonic loop
`explore -> evaluate -> learn every win/loss -> fixed capital regression panel -> compare with accepted champion -> accept only non-regressing capital improvement -> remember rejected strategy -> penalize repeated losing values -> widen/deepen recovery search -> strict promotion -> next round`.

### Stable capital regression panel
- fixed seeds: `7319`, `29077`;
- all local opponent families in `SUITE`;
- both seats;
- full 720-step horizon;
- candidate train/duel/holdout/final seeds are sampled from `>=100000`, so the fixed panel is separate from candidate selection.

A different challenger can replace the accepted research champion only if it increases paired money by at least `max(1 simulator money unit, 0.1%)` and does not regress paired money, mean margin, win rate, worst-margin tail, catastrophic rate, terminal unsold inventory or no-op rate.

The fixed panel is a regression/high-water check, not the sole promotion evidence. Unseen holdout/final and the existing strict rank gate remain mandatory to reduce fixed-panel overfitting.

### Persistent failure memory
New module: `reward-hunter/kaggriculture-v3/monotonic_rank.py`.

Persistent learning state now keeps:
- accepted research champion + signature;
- money high-water;
- accepted/rejected/kept counters;
- exact rejected strategy signatures;
- failure reasons;
- repeated losing parameter-value counts.

Rules:
- exact rejected configurations become taboo and are not generated again;
- one failure does not poison every component value;
- repeated parameter values across independently rejected configurations accumulate bounded search penalties;
- rejected candidates are not put into the champion archive;
- accepted champion remains the first parent in later searches;
- failed configurations still contribute negative telemetry to family-conditioned learning.

### Adaptive recovery remains active
The V5.5 continuous-potential controller is retained and now reacts to monotonic failure:
- ordinary exploit: requested base budget;
- regression recovery: at least 32 candidates, higher exploration, deeper mutation;
- stagnation >=2: at least 40 candidates, mutation depth >=3;
- stagnation >=4: at least 56 candidates, mutation depth 4;
- every fifth round: periodic deep search at least 48 candidates;
- hard candidate bound remains 8..64.

Thus a failed round is not repeated unchanged: it adds negative memory and increases the effort to find a different, stronger replacement.

### V5.6 implementation commits
- `c89bfb839c371e05e0b689db4edd4890f08d4fa6` — monotonic capital/failure-memory module.
- `a9f6cd22aab7b981097479a500a27ecd17885c29` — search integration, taboo filtering and failure penalties.
- `67b1e21402930a6094591eed0972f4149dd6baac` — monotonic regression tests.
- `14ab8defb536ab557b1ec5fab4c8ed7e00b428d5` — fixed stable capital regression panel.
- `29cc966931347eabb32a44ab952aa4885a813046` — V5.6 workflow + fail-closed promotion consistency assertions.
- `1e743d4095c59087f063ffba18cb32c5329b6295` — starts first V5.6 push research cycle.

### Validation / live research queue
- V5.6 PR validation run `34505564513`: **SUCCESS**. Compile/regression/monotonic-capital tests PASS, self-contained package PASS, both-seat smoke PASS.
- V5.6 push run `34505728525`: validation **SUCCESS**; research job `102967528116` was **PENDING** at last check because the non-cancelling single-writer queue is still occupied by the earlier V5.5 research run.
- Earlier V5.5 push research run `34503963040`: research job `102961627629` was still **IN PROGRESS** at last check. Its learning output is useful and the V5.6 run will start after the single-writer slot is released.
- Do not call V5.6 locally superior until `MONOTONIC`, `CAPITAL_REGRESSION`, duel/holdout/final and promotion outputs from a completed V5.6 research run are inspected.

### Fail-closed live promotion
A V5.6 candidate may reach guarded Kaggle submission only when BOTH are true:
1. existing strict current-engine rank promotion gate passes;
2. monotonic capital gate passes.

The workflow independently asserts the composite relationship before the live-promotion step. Existing new-hash, duplicate and >=6h cooldown checks remain. If any condition fails, current live agents remain unchanged.

## V5.4/V5.5 source fixes retained
- real fertilizer base price 100 and real fertilizer market ratio;
- opponent crop/animal counts and livestock classification;
- 3Q/4Q land target performance-driven rather than blindly forcing the fourth quadrant;
- horizon-aware animal ROI including wheat/feed, action cost, fertilizer credit and opponent saturation;
- working-capital-aware livestock/crop/fertilizer choices;
- locked central shed tiles cannot be used for DROP/PICKUP;
- endgame planting forbidden;
- both-seat smoke, invalid/no-op and terminal inventory checks active;
- global + family-conditioned win/loss learning, elite archive and stagnation controller retained.

## Claude V6
Claude previously reported a local `claude/kaggriculture-v6-adaptive-continuous` branch, but no V6 branch/PR or bundle is available in GitHub/this conversation. It is not integrated. If a V6 bundle appears later, inspect it independently before importing anything.

## NEXT CHAT COMMAND
If user says `check`, `xong chưa`, `tối ưu tiếp`, `leo rank`, `học từ thất bại`, or asks about continuous potential:
1. inspect PR #219 latest head;
2. inspect old run `34503963040` and V5.6 push run `34505728525`, then any newer `Kaggriculture V5.6 - Monotonic Capital Challenger` runs;
3. when V5.6 research completes, inspect `MONOTONIC`, `CAPITAL_REGRESSION`, `CAPITAL_INCUMBENT`, `ROUND_PLAN`, `NEXT_ROUND`, failure reasons/taboo count, learning control, duel, holdout, final and strict promotion reasons;
4. verify rejected candidate did not replace/archive the accepted champion;
5. verify accepted candidate raised the stable-panel money high-water and did not regress risk/waste metrics;
6. verify next round is queued with adaptive candidate count after failure/stagnation;
7. recheck Kaggle submissions `56139689`, `56148022` and any later guarded promotion before stating live score/rank;
8. update this checkpoint after any material result;
9. never expose `KAGGLE_API_TOKEN`.
