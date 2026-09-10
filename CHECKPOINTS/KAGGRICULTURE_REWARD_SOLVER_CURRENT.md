# KAGGRICULTURE REWARD SOLVER CHECKPOINT

Updated: 2026-09-10 23:50 +07

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

## ACTIVE RANK LANE — PR #219 / V5.5 CONTINUOUS POTENTIAL
- PR #219: `[KAGGLE-V5.5] Continuous Potential Rank Engine`.
- Head branch: `research/kaggriculture-v5-4-rank-livestock`.
- PR is **open + draft + mergeable**. Do not merge until a full current-engine research round is reviewed.
- Latest feature trigger commit: `473c546ab52d296962b0dd6e42377f3c25a3314e`.
- Validation run `34503967537`: SUCCESS. Compile/regression continuous-potential contracts, self-contained package gate and both-seat rank-livestock smoke all passed.
- Push research run `34503963040`: validation SUCCESS; research job `102961627629` was **PENDING** at last check because the non-cancelling single-writer research queue serializes learning. Pending here is intentional and is not a merge conflict.

### V5.5 continuous-potential architecture
The loop is now:
`match telemetry -> win/loss/tie/invalid learning -> opponent-family weakness model -> persistent elite archive -> stagnation/regression detector -> adaptive search budget -> challenger league -> duel/holdout/final -> strict promotion -> next adaptive round`.

Learning state remains outside the Git worktree, cached between rounds and atomically replaced. One concurrency group, `kaggriculture-v54-learning-single-writer`, is the only learning-state writer at a time with `cancel-in-progress:false`.

New V5.5 learning features:
- global and opponent-family-conditioned parameter evidence;
- `weak_families()` identifies the currently weakest opponent families and focuses part of candidate selection on them;
- persistent champion archive keeps up to 8 strong parameter lineages so one noisy round cannot erase a useful strategy;
- bounded round history tracks progress, regression and stagnation;
- adaptive search controller changes candidate count, exploration and mutation depth instead of staying fixed forever;
- normal exploitation uses the base budget; regression recovery raises breadth; stagnation >=2 expands to >=40 candidates and deeper mutation; stagnation >=4 expands to >=56; every fifth round forces a periodic deep search of >=48 candidates;
- all candidate budgets remain hard-bounded to 8..64;
- round potential score guides exploration only and **never replaces strict promotion gates**.

Key implementation commits:
- `ea85581abd8dfb6453eb419fd5c343d51fe38ee8` — family-conditioned learning, champion archive, stagnation/regression controller.
- `d413cb2db24bb64d373546ddad39c900196ce6cc` — challenger search driven by adaptive potential state.
- `3c345e82f4eecc838d7fc84a7f18afaa47c63fef` — migration/family/stagnation/deep-round regression contracts.
- `63f653774a36313c9fdf80303d659c1d57b9dd2f` — workflow uses adaptive next-round budget and allows deeper rounds up to 300 minutes.
- `473c546ab52d296962b0dd6e42377f3c25a3314e` — starts first V5.5 continuous-potential research cycle.

### Strict live-promotion guard
The rank workflow may submit a **new** candidate to Kaggle only when all of these are true:
1. strict `promotion.pass_gate` is true;
2. exact candidate sha differs from the last live candidate;
3. at least 6 hours have elapsed since the previous guarded live submission;
4. the candidate description/hash is not already present in Kaggle submissions;
5. Kaggle credential exists only through the Actions secret.

If any condition fails, submission is skipped/deferred and the current live agents remain unchanged. This is controlled promotion, not submission spam or rating rerolling.

## V5.4 source fixes retained in V5.5
- real fertilizer base price 100 and real fertilizer market ratio;
- opponent crop/animal counts and livestock classification;
- 3Q/4Q land target is performance-driven rather than always forcing the fourth quadrant;
- horizon-aware animal ROI, wheat/feed cost, action cost, fertilizer credit and opponent saturation;
- working-capital-aware livestock/crop/fertilizer choices;
- locked central shed tiles cannot be used for DROP/PICKUP;
- endgame planting is forbidden;
- both-seat smoke, invalid/no-op and terminal inventory checks remain active.

## Local promotion gate remains strict
The profit-first rank gate still requires current engine 1.32.7, both seats, exact coverage/identity, unseen seeds, valid incumbent baselines, strong money/margin edge, tail protection, catastrophic-rate cap, zero unit no-ops, movement-efficiency cap, terminal-inventory cap, broad opponent-family coverage, direct incumbent performance and runtime/package equivalence.

## Claude V6
Claude previously reported a local `claude/kaggriculture-v6-adaptive-continuous` branch, but no V6 branch/PR or bundle is available in GitHub/this conversation. It is not integrated. If a V6 bundle appears later, inspect it independently before importing anything.

## NEXT CHAT COMMAND
If user says `check`, `xong chưa`, `tối ưu tiếp`, `leo rank`, or asks about continuous potential:
1. inspect PR #219 latest head;
2. inspect push run `34503963040` and any newer `Kaggriculture V5.5 - Continuous Potential Challenger` runs;
3. if research completed, inspect `ROUND_PLAN`, `NEXT_ROUND`, `learning.control`, weak families, champion archive count, duel, holdout, final, promotion reasons and runtime/package gates;
4. verify that the next round was actually queued with the controller-selected candidate budget;
5. recheck Kaggle submissions `56139689` and `56148022` before stating live status/rank;
6. update this checkpoint after any material result;
7. never expose `KAGGLE_API_TOKEN`.
