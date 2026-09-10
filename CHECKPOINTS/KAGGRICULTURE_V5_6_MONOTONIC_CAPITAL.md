# KAGGRICULTURE V5.6 — MONOTONIC CAPITAL LEARNING CHECKPOINT

Updated: 2026-09-11 00:02 +07

## Goal
Turn every failed investment configuration into persistent learning while preventing a worse strategy from replacing the accepted research champion.

Exploratory matches are allowed to lose because exploration is necessary. The non-regression guarantee applies to the **accepted champion and promotion path**, not to every stochastic match: a worse challenger is retained only as failure evidence and cannot become the next champion or be promoted live.

## Branch / PR
- Repository: `hanlinh227-ship-it/trading-api`
- Branch: `research/kaggriculture-v5-4-rank-livestock`
- PR #219: `[KAGGLE-V5.6] Monotonic Capital Learning Rank Engine`
- Keep PR draft until a full V5.6 push research round is reviewed.

## New monotonic loop
`explore -> local evaluation -> learn all wins/losses -> fixed capital regression panel -> compare with accepted champion -> accept only improvement -> reject/taboo regression -> increase recovery search -> strict promotion -> next adaptive round`

## Capital high-water rule
Stable capital regression panel:
- seeds: `7319`, `29077`;
- families: all local `SUITE` opponent families;
- both seats;
- full 720-step horizon;
- candidate search/holdout seeds are sampled from `>=100000`, so these regression seeds are separate from candidate selection.

A different challenger replaces the accepted champion only if:
- weighted/paired money is higher by at least max(`$1 simulator unit`, `0.1%` of incumbent money);
- no duel/holdout/final panel money regression;
- no mean-margin regression;
- no win-rate regression;
- no worse worst-margin tail;
- no higher catastrophic rate;
- no higher terminal unsold inventory;
- no higher no-op rate.

The fixed panel creates a comparable capital high-water mark across rounds. Strict unseen holdout/final and the existing promotion gate remain separate so the system cannot promote solely by overfitting the fixed panel.

## Failure memory
New module: `reward-hunter/kaggriculture-v3/monotonic_rank.py`.

Persistent state now also contains:
- `monotonic.accepted`: current accepted research champion;
- `money_high_water`;
- accepted/rejected/kept counters;
- exact failure signatures;
- failure reasons;
- repeated losing parameter-value counts.

Rules:
- an exact rejected parameter set becomes taboo and is not generated again;
- one failed configuration does not poison every individual parameter value;
- parameter-value penalties begin after the same value appears in multiple independently rejected configurations;
- repeated bad values get increasing bounded search penalty;
- rejected challengers are not archived as champions;
- accepted champion is always seeded first in future search.

## Adaptive recovery after failure
The existing V5.5 adaptive controller is retained and now reacts to monotonic rejection:
- rejection increments regression/stagnation state;
- recovery expands to at least 32 candidates;
- stagnation >=2 expands to >=40 and deeper mutation;
- stagnation >=4 expands to >=56 with mutation depth 4;
- every fifth round forces a deep search >=48;
- hard bound stays 8..64 candidates.

Thus a failure cannot simply repeat the same investment configuration. It both creates negative memory and increases the search effort for a better replacement.

## Promotion fail-closed
`promotion.pass_gate` now requires BOTH:
1. the existing strict current-engine rank gate;
2. the V5.6 monotonic capital gate.

The Actions workflow independently asserts this composite relationship before any Kaggle live promotion step. Existing candidate hash, duplicate check and >=6h cooldown remain active. No forced matchmaking, quota bypass or reroll spam.

## Implementation commits
- `c89bfb839c371e05e0b689db4edd4890f08d4fa6` — monotonic capital/failure-memory module.
- `a9f6cd22aab7b981097479a500a27ecd17885c29` — search integration, taboo filtering and rejected-strategy penalties.
- `67b1e21402930a6094591eed0972f4149dd6baac` — monotonic regression tests.
- `14ab8defb536ab557b1ec5fab4c8ed7e00b428d5` — stable fixed capital regression panel.
- `29cc966931347eabb32a44ab952aa4885a813046` — fail-closed V5.6 workflow and live-promotion consistency guard.
- `1e743d4095c59087f063ffba18cb32c5329b6295` — starts first V5.6 push research cycle.

## Validation
PR validation run `34505564513`: **SUCCESS**.
- compile/regression/monotonic-capital contracts: PASS;
- self-contained package gate: PASS;
- both-seat rank-livestock smoke: PASS.

Push research run `34505728525` was started from trigger commit `1e743d4095c59087f063ffba18cb32c5329b6295`. At checkpoint creation its validation job was still running; recheck before claiming research results.

## Live Kaggle safety
- Do not claim the V5.6 candidate is better live until current-engine research and actual Kaggle evidence confirm it.
- Do not expose `KAGGLE_API_TOKEN`.
- Do not force live rematches.

## Next check
1. Inspect push run `34505728525` and any newer V5.6 runs.
2. When research completes, inspect `MONOTONIC`, `CAPITAL_REGRESSION`, `CAPITAL_INCUMBENT`, `ROUND_PLAN`, `NEXT_ROUND`, failure reasons, taboo count, duel, holdout, final and strict promotion reasons.
3. Confirm a rejected candidate did not enter champion archive and the next round widened/deepened appropriately.
4. Confirm an accepted challenger increased the fixed-panel money high-water and did not regress risk/waste metrics.
5. Update central checkpoint after material results.
