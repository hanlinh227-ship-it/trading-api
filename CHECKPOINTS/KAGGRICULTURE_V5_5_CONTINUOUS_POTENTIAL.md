# KAGGRICULTURE V5.5/V5.6 — CONTINUOUS POTENTIAL + MONOTONIC CAPITAL CHECKPOINT

Updated: 2026-09-11 00:01 +07

## Goal
Continuously increase challenger potential without resetting useful learning, and never allow a weaker capital configuration to replace the accepted research champion. Exploration may discover losing candidates, but losses must become durable learning evidence rather than being repeated.

## Branch / PR
- Branch: `research/kaggriculture-v5-4-rank-livestock`
- PR #219: `[KAGGLE-V5.5] Continuous Potential Rank Engine`
- Current code has advanced to the V5.6 monotonic-capital layer.
- Keep PR draft until full current-head research evidence is reviewed.

## Core loop
`match -> learn win/loss/tie/invalid -> identify weak opponent families -> retain accepted capital high-water champion -> remember failed exact strategy + failed investment thesis -> adapt candidate budget/exploration/mutation -> duel/holdout/final -> fixed capital regression panel -> strict non-regression gate -> promote only if better -> queue next round`

## V5.5 adaptive controller
- exploit: base requested budget, exploration ~0.16, mutation depth 1;
- recover after regression: >=32 candidates, exploration >=0.26, mutation depth >=2;
- stagnation >=2: >=40 candidates, exploration >=0.32, mutation depth >=3;
- stagnation >=4: >=56 candidates, exploration >=0.42, mutation depth 4;
- every fifth round: periodic deep search >=48 candidates, exploration >=0.34, mutation depth >=3;
- hard limit: 8..64 candidates.

## V5.6 monotonic-capital rules
1. The current accepted champion is always retained as the fallback high-water configuration.
2. A challenger may replace it only on paired apples-to-apples evidence and must increase weighted mean money by at least max($1, 0.1% of incumbent money).
3. No replacement is allowed if duel/holdout/final money, margin or win rate regresses; tail risk, catastrophic rate, terminal inventory and no-op rate also cannot worsen.
4. A rejected exact parameter configuration becomes taboo immediately and cannot be generated again.
5. Repeated bad parameter values accumulate a search penalty so losing ingredients are progressively deprioritized.
6. NEW: an investment-thesis fingerprint captures crop mode, expansion mode, land target/buffer, labor target, herd composition/timing/cash buffer, animal ROI threshold, fertilizer policy, sell batch and seed scale. If two independently rejected configurations share the same investment fingerprint, the whole pattern becomes taboo. Future candidates must materially change the investment thesis instead of replaying it with cosmetic routing/priority changes.
7. The accepted champion is explicitly exempt from failure-pattern blocking so recovery cannot accidentally delete the high-water fallback.
8. Rejected challengers are never archived as champions and cannot reach Kaggle live promotion.

## Failure memory
Persistent state now records:
- exact rejected strategy hashes;
- repeated parameter-value failure counts;
- failed investment-pattern fingerprints and representative examples;
- reasons such as money regression, margin regression, tail regression, inventory regression;
- accepted capital high-water mark;
- controller stagnation/regression state.

The memory stays bounded and atomic, and the workflow continues using a single non-cancelling writer.

## Important realism rule
It is impossible to guarantee that every exploratory game or unseen Kaggle episode earns more money than every previous game because seeds/opponents/market paths vary. The enforceable monotonic rule is stronger in the place that matters: **a lower-performing candidate can never replace the accepted champion or be promoted**. Losses are used only as training evidence.

## Commits
- `ea85581abd8dfb6453eb419fd5c343d51fe38ee8` — continuous-potential learner.
- `d413cb2db24bb64d373546ddad39c900196ce6cc` — adaptive search integration.
- `3c345e82f4eecc838d7fc84a7f18afaa47c63fef` — continuous-potential regression tests.
- `63f653774a36313c9fdf80303d659c1d57b9dd2f` — adaptive workflow/next-round budget.
- `1608871163484c01b0741daab994debcdb2f4014` — repeated losing investment-pattern lockout.
- `f8aa1a3ab127d60233b6c8a4e9953835aea42eb8` — regression test proving two independent failures block the same investment thesis while preserving the accepted champion.
- `8da9d1c1952990cc431ae6c58f1d11ef73fc1a6e` — trigger V5.6 monotonic-capital recovery cycle 002.

## Validation / active research
Earlier V5.5 validation run `34503967537`: SUCCESS across compile/regression contracts, self-contained package and both-seat smoke.
Earlier push research run `34503963040`: validation SUCCESS; research job was in progress when V5.6 pattern learning was added. That older run uses its original checked-out commit and is useful historical evidence, but it does not validate the newest investment-pattern guard.

The V5.6 trigger file now requests `v5.6-monotonic-capital-002`. Inspect the newest workflow run for head `8da9d1c1952990cc431ae6c58f1d11ef73fc1a6e` and later heads. Do not start duplicate full research if one is already queued/running under the single-writer concurrency group.

## Kaggle live safety
- Keep competition credentials only in GitHub Actions secrets.
- No forced matchmaking, quota bypass, multi-accounting or reroll/duplicate submissions.
- A live submission is eligible only after strict current-engine promotion + monotonic non-regression + new candidate hash + cooldown/duplicate checks.

## Next chat
If the user asks to continue/tune/check:
1. inspect PR #219 current head first;
2. inspect the newest V5.6 validation/research run and the older in-flight round if still relevant;
3. confirm the new test `test_same_losing_investment_thesis_cannot_repeat_after_two_independent_failures` passes;
4. inspect `money_high_water`, `taboo_exact_count`, `taboo_pattern_count`, top failure reasons, capital regression panel, duel/holdout/final and promotion reasons;
5. confirm a rejected strategy/pattern is not regenerated in the following round;
6. preserve the accepted champion whenever the new candidate is worse;
7. never expose `KAGGLE_API_TOKEN`.
