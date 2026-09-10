# KAGGRICULTURE V5.7 — ADAPTIVE AGRO-ECONOMIC CHECKPOINT

Updated: 2026-09-11 00:27 +07

## Goal
Use every local win/loss as deeper crop/livestock/economic evidence. Exploration may fail, but accepted capital must remain monotonic. Production volume and realized sale price are optimized together rather than maximizing output while collapsing the shared market.

## Branch / PR
- Repo: `hanlinh227-ship-it/trading-api`
- Branch: `research/kaggriculture-v5-4-rank-livestock`
- PR #219: `[KAGGLE-V5.7] Adaptive Agro-Economic Learning Rank Engine`
- Keep PR draft until a full V5.7 research round is reviewed.
- Canonical V5.7 validation head before trigger: `43a3dc3904b222ebea2aedfab6668774fd306b53`.
- Research trigger commit: `46265eea01e691645bc72a2ccf43423c95e2a910`.

## Canonical runtime / research path
- `economic_reasoning.py`: official-market-aware crop/animal portfolio economics, future town drain/scarcity projection, price-capture logic.
- `policy_v57.py`: runtime production/price coordinator layered over proven base policy; rewrites marginal planting/seed choices, sale timing/batches and uneconomic animal purchases.
- `benchmark_v57.py`: canonical evaluator with economy telemetry and all legacy promotion metrics.
- `package_submission_v57.py`: self-contained V5.7 package.
- `agro_reasoning.py`: persistent failure attribution and recovery hypotheses.
- `search_rank.py`: canonical V5.7 adaptive search; imports `benchmark_v57` and `package_submission_v57`.
- `monotonic_rank.py`: accepted-champion capital non-regression and taboo memory.

The temporary `value_overlay.py` / `agent_factory.py` path is not canonical for V5.7 research; it remains only as a transitional/legacy path until cleanup is safe.

## What each failure now teaches
Failure labels include: invalid execution, action waste, terminal inventory, routing overhead, underutilized land, fourth-quadrant overreach, labor overhead, herd feed pressure, herd capital not converted, premium glut dumping, volume-over-value, crop-only income ceiling, livestock without crop support, idle structure capital, capital starvation, expansion cash drag, hiring cash drag, poor price capture, feed-market dependency, premium supply/price mismatch, capital not compounding and catastrophic economics.

Repeated causes generate materially different next-round hypotheses rather than only changing one numeric parameter. Examples:
- repeated 4Q/cash drag -> 3Q, leaner labor, larger working-capital buffer;
- herd/feed failure -> stronger WHEAT/grains backbone, feed carry 8, smaller/ROI-gated herd;
- poor premium price capture -> demand/ROI crop mode, smaller sell batches, lower premium oversupply;
- low utilization -> higher fill target / better action allocation;
- terminal inventory -> earlier drop/liquidation and smaller, more frequent market realization;
- crop-only income ceiling -> cow/sheep mixed-farm prior;
- failure to compound -> protect cash floor and re-test 3Q + demand-aware mixed farm.

## Top-history lessons integrated as priors, not copies
Public high-Elo evidence repeatedly showed 3-quadrant livestock-heavy structures around 9 cows, 4-5 sheep and 9-10 hands. Public discussion also showed many strong agents were heuristic/fixed-policy lineages, and 4th-quadrant expansion is often a strategic ROI trade-off rather than mandatory. These patterns seed candidate priors only; our accepted champion and failure-derived personal hypotheses are evaluated first and may reject the public prior.

## Production + price coordination
The runtime models the shared market as endogenous: own/opponent selling adds supply and can depress price; town demand and supported market buys remove supply and can create scarcity. Premium goods such as strawberry, melon, milk and wool have much stronger glut curves than staples, so V5.7:
- projects current + future town drain;
- scores crops by marginal yield, seed cost, remaining horizon, demand and projected realizable price;
- scores animals by product value, feed cost, fertilizer value, labor burden, demand and supply pressure;
- uses WHEAT as both revenue and herd-feed backbone;
- holds or clips premium sells when expected scarcity is more valuable, but cash/capacity/endgame pressure overrides waiting;
- prioritizes strong current price/scarcity opportunities;
- avoids late 4Q expansion when the first 3 quadrants are still under-utilized.

## Monotonic accepted-capital rule
Fixed regression seeds: `7319, 29077`, all local opponent families, both seats. A candidate may replace the accepted champion only with a real positive money gain and no paired regression in money, margin, win rate, worst tail, catastrophic rate, terminal inventory or no-op. Failed challengers become learning data and do not replace the champion.

This guarantees non-regression at accepted-champion/promotion level, not that every exploratory stochastic episode must earn more than the previous episode.

## Validation
Canonical V5.7 workflow: `Kaggriculture V5.7 - Adaptive Agro-Economic Challenger`.
Run `34508086126`: VALIDATE SUCCESS.
Passed:
- compile + all regression/monotonic/agro-economic tests;
- V5.7 self-contained package + raw-exec;
- V5.7 economy smoke both seats;
- V5.7 source/package episode equivalence.
Research skipped in that run because it was a pull-request event, as intended.

## Active research
Push run `34508180760` created from trigger commit `46265eea01e691645bc72a2ccf43423c95e2a910` and is queued/starting under the existing non-cancelling single-writer learning concurrency group. It is the first canonical full V5.7 agro-economic cycle.

On completion inspect:
- `AGRO_REASONING` dominant failure causes and strategy-family stats;
- price capture, scarcity, money checkpoints, min/peak money, crop/animal exposure, land/hire/feed purchases;
- direct incumbent duel, unseen holdout/final;
- fixed capital-regression candidate vs accepted champion;
- `MONOTONIC` decision and money high-water mark;
- strict promotion reasons;
- next adaptive candidate budget and whether next round is queued.

## Integrity
- Promotion evidence pinned to `kaggle-environments==1.32.7`.
- No hidden Kaggle state/private opponent data.
- No copied top action tape; public top history is a prior only.
- No forced matchmaking, quota bypass or submission reroll spam.
- `KAGGLE_API_TOKEN` remains secret-only.
- Guarded live promotion requires strict rank gate + monotonic gate + unique hash + cooldown + duplicate check.
