# Claude AI prompt — Kaggriculture V5 crop engine + cyclic challenger audit

Copy the prompt below into Claude AI with GitHub access if available.

---

You are a senior autonomous Python/game-systems engineer auditing a live Kaggle Kaggriculture research branch.

Repository: `hanlinh227-ship-it/trading-api`
Base branch to inspect: `codex/kaggriculture-v5-mixed-farm-economy`
Current checkpoint: `CHECKPOINTS/KAGGRICULTURE_V5_MIXED_FARM.md`
Competition engine target: `kaggle-environments==1.32.7`

Use a large reasoning/coding budget. Do not stop at a conceptual review. Inspect the real repository, reproduce failures, simplify the implementation where possible, run tests, and if your GitHub permissions allow, commit your improvements to a NEW isolated branch:

`claude/kaggriculture-v5-crop-cycle-audit`

Open a PR back into:
`codex/kaggriculture-v5-mixed-farm-economy`

PR title must begin:
`[KAGGLE-V5-CLAUDE]`

Do not merge it yourself.

## Mission
Make the V5 system smaller, safer and economically stronger while preserving its strict promotion gates. Focus on two areas:

1. Crop/economy engine
2. Continuous public-meta -> challenger -> rematch loop

The goal is not maximum code volume. The goal is the fewest moving parts that reliably make good economic decisions and are hard to break.

## Known facts you must respect
- Kaggriculture runtime must be self-contained and stdlib-only after packaging.
- Do not depend on `__file__`, local files, network access or pip packages inside the submitted agent.
- A prior Kaggle raw-exec failure already happened because `__file__` was assumed.
- Kaggriculture 1.32.7 can omit `obs['step']` for seat 1. The branch now derives its clock from `day * turnsPerDay + hour`; do not regress this.
- Public top replay archives downloaded by the research workflow are Parquet, not only JSON/JSONL.
- Public replay analysis is OFFLINE research input only. It must never create runtime network dependence.
- Do not copy private competitor code or use hidden/private competition data.
- Do not bypass Kaggle matchmaking, rate limits or submission limits.
- Do not expose `KAGGLE_API_TOKEN`.
- Do not automatically submit anything to Kaggle.

## Files to audit first
- `reward-hunter/kaggriculture-v3/features.py`
- `reward-hunter/kaggriculture-v3/policy.py`
- `reward-hunter/kaggriculture-v3/benchmark_v5.py`
- `reward-hunter/kaggriculture-v3/search_v5.py`
- `reward-hunter/kaggriculture-v3/promotion_v5.py`
- `reward-hunter/kaggriculture-v3/package_submission.py`
- `reward-hunter/kaggriculture-v3/raw_exec_test.py`
- `reward-hunter/kaggriculture-v3/meta/replay_intelligence.py`
- `.github/workflows/reward-kaggriculture-v5-mixed-farm.yml`
- `.github/workflows/reward-kaggriculture-v5-meta-intel.yml`
- `reward-hunter/kaggriculture-v3/tests/test_v5.py`
- `CHECKPOINTS/KAGGRICULTURE_V5_MIXED_FARM.md`

## Crop engine objectives
Audit the economics instead of assuming the current formulas are correct.

For each crop, reason from the current engine mechanics and verify with simulation:
- seed cost
- first harvest timing
- maturity/harvest cycle
- expected units
- current market price/base price
- shop demand
- market inventory/scarcity
- water/action burden
- fertilizer interaction
- travel burden
- time remaining
- need for fast cash before land unlock
- WHEAT feed reserve required by livestock

The crop chooser should optimize MARGINAL value, not create monoculture. Make sure it can distinguish:
- fast liquidity phase
- expansion-capital phase
- stable production phase
- feed-security phase
- scarcity-opportunity phase
- endgame/no-payback phase

Prefer compact functions with explicit units/meaning. Remove magic multipliers when a simpler economic comparison works as well.

Check whether crop allocation should be based on:
- profit/day
- profit/action
- discounted payback before next land deadline
- marginal portfolio saturation
- expected sellability

You may redesign the scoring if evidence supports it.

## Livestock + crop integration
Do not let livestock starve crops of cash/actions.
Do not let crops starve livestock of feed.

Audit:
- COW/SHEEP/GOOSE purchase timing
- payback horizon
- structure build timing
- pasture/coop forward capacity
- pickup/place routing
- FEED/CARE/HARVEST priority
- WHEAT reserve
- fertilizer collection/use
- late-game animal purchase cutoffs

A public high-Elo prior around 9 cows / 4 sheep / 10 hands may be tested, but it is only a prior and must not be hard-coded as truth.

## Land expansion
User wants aggressive expansion and effective use of all four quadrants, but land ownership alone is not a valid objective.

Audit the working-capital logic so that:
- land has a clear economic payback case,
- buying land never destroys the seed/feed/labor engine,
- the agent can still unlock all four quadrants when profitable,
- unused unlocked acreage is penalized,
- early land deadlines do not create cash deadlocks.

## Labor/action efficiency
Hands reset daily and hires consume market actions/cash. Audit whether the current labor target is too aggressive.

Measure:
- useful actions per hand
- PASS rate
- movement rate
- no-op rate
- harvest/water/feed/care backlog
- distance to assigned tasks
- repeated shed trips
- duplicate pickups

Reduce movement and idle churn. Prefer local task assignment and batching.

## Public replay intelligence
The analyzer must successfully consume the actual downloaded archive format, including Parquet.

Requirements:
- bounded memory/time
- schema diagnostics
- deduplicate aggregate + daily shard copies
- prefer recent engine/current-meta data
- do not fail silently to a zero-animal/zero-record prior
- extract at least: opening fingerprints, land timing, herd composition, peak hands, sell cadence, money curve when available
- produce one small `recommended_params` prior
- the prior must enter search only as a candidate, never bypass gates

If the Parquet schema differs from expectations, adapt to the real schema rather than hard-coding one guessed column name.

## Cyclic challenger league
Make the continuous loop robust:

public replay refresh
-> parse + validate
-> generate/update meta prior
-> fast challenger search
-> incumbent direct duel
-> meta-opponent suite
-> unseen holdout/final
-> package/raw-exec equivalence
-> PROMOTION_READY marker only on PASS
-> no Kaggle submission

Recommended cadence after merge to the default branch:
- fast cycle every 6 hours
- deeper cycle once daily

Do not run useless duplicate searches when the replay fingerprint/meta prior has not changed. If practical, add a digest/hash check so an unchanged meta snapshot can skip the expensive deep search.

Workflows must:
- have timeouts
- use concurrency protection
- retry transient Kaggle archive download errors
- upload diagnostics even on failure
- fail closed on empty replay input
- never expose secrets
- never auto-submit

Important GitHub behavior: scheduled workflows execute from the repository default branch. Document this clearly and do not falsely claim a schedule on an unmerged feature branch is already running periodically.

## Evaluation protocol
Do not trust a single smoke score.

Run:
- compile/unit tests
- seat-0 and seat-1 tests
- missing `obs['step']` regression
- raw-exec test
- official loader test
- short economic smoke
- both seats
- multiple deterministic seeds
- starter
- incumbent V1
- expansion opponent
- early-sell opponent
- other distinct local families
- current engine 1.32.7 only for promotion evidence

For promising candidates run full 720-turn:
- staged screen
- incumbent duel
- unseen holdout
- final holdout
- tail-risk metrics
- full-unlock/utilization metrics
- terminal unsold inventory

If V5 remains weaker than incumbent, report FAIL. Do not manipulate thresholds to manufacture PASS.

## Simplification mandate
Look specifically for:
- duplicated logic
- stale V3/V4 naming that causes confusion
- brittle dictionary assumptions
- incorrect market accounting
- action priority contradictions
- worker oversubscription
- structure overbuilding
- inventory overflow
- late harvests that cannot be sold
- low-value fertilizer chains
- stale replay data
- seat asymmetry
- nondeterminism
- process-pool problems
- GitHub Actions conditions that never fire

Refactor only when it reduces risk or improves measured performance.

## Deliverables
If GitHub write access is available:
1. Create branch `claude/kaggriculture-v5-crop-cycle-audit` from the current V5 branch.
2. Implement fixes.
3. Run tests/benchmarks.
4. Open PR with title beginning `[KAGGLE-V5-CLAUDE]` against `codex/kaggriculture-v5-mixed-farm-economy`.
5. Create/update `CHECKPOINTS/KAGGRICULTURE_V5_CLAUDE_AUDIT.md` containing exact commit SHA, PR number, tests, metrics, failures, and recommended merge decision.

If GitHub write access is not available, output a minimal patch plan with exact files/functions/changes and test commands, not generic advice.

## Final response format
Return only:
- branch
- PR number/URL if created
- head SHA
- tests PASS/FAIL
- best V5 candidate vs incumbent metrics
- public replay parser status and number of parsed records
- cyclic challenger status
- simplifications made
- remaining blocker
- merge recommendation: MERGE / DO NOT MERGE

Do not claim a Kaggle rank improvement unless a real submitted agent has actually accumulated live ladder evidence.

---
