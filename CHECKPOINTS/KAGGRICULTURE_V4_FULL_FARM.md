# Kaggriculture V4 Full-Farm Expansion Checkpoint

Updated: 2026-09-10

## Purpose
V4 is an isolated branch created from the V3 meta-orchestrator so the canonical V3 research run can continue without conflict.

Branch: `codex/kaggriculture-v4-full-farm-expansion`
Base snapshot: V3 head `347cb1f2f1b22b5136d10dc9d6abfc62387e7fb5`
PR: #217 — https://github.com/hanlinh227-ship-it/trading-api/pull/217
PR title: `[KAGGLE-V4] Full-Farm Expansion and Utilization Campaign`
PR base: `codex/kaggriculture-v3-meta-orchestrator`
Kaggle submission: **NO**

## User requirement
- Accelerate farm expansion.
- Reach all four quadrants quickly.
- Use the unlocked acreage instead of owning empty land.
- Improve the complete campaign without sacrificing the fail-closed promotion standard.

## Changes
- Added explicit expansion features: unlocked quadrants, locked/owned tiles, next land cost, full-farm state, utilization and workload.
- Added expansion modes `balanced`, `fast`, `max` with early land deadlines and liquidity buffers.
- Market planning is reordered as `SELL -> BUY_LAND -> HIRE -> BUY_SEED` so inventory can fund expansion before seed spending.
- Added dynamic labor scaling up to 14 hands based on acreage and workload.
- Added fast-cash crop bias before full farm to fund the 1000/2000/4000 land costs.
- Increased seed throughput while newly unlocked acreage is under-filled.
- Added high-priority planting/digging while farm utilization is below target.
- Benchmark now measures full-unlock rate, full-unlock day, peak utilization, full-farm peak utilization, action/no-op metrics and profit robustness.
- Search jointly tunes expansion mode, land buffer, crop mode, labor, routing distance, fill target, fill priority and seed throughput.
- Search uses cheap 240/480-step A/B screens before full-horizon C/D/E/F gates to reduce wasted compute.
- Promotion requires 100% full unlock on unseen holdout/final games, mean full unlock <= day 12, full-farm peak utilization >= 68%, zero unit no-ops, strong multi-family performance and positive V1 duel.

## Safety / competition handling
- No Kaggle submission job exists in the V4 workflow.
- No KAGGLE_API_TOKEN is read by V4.
- No public competitor code/replay ingestion is used.
- Candidate is only committed if all promotion gates pass.

## Workflow
Workflow: `Kaggriculture V4 - Full Farm Expansion`
File: `.github/workflows/reward-kaggriculture-v4-full-farm.yml`
Run ID: `34454305004`
Trigger/head SHA: `531467e9428eb17668c6a1254344df4b1a32dc65`

Latest checked state:
- validate: **SUCCESS**
- compile/contracts: **SUCCESS — 16 tests**
- generated raw-exec: **PASS**
- official loader: **PASS**
- expansion smoke: **SUCCESS**
- research: **IN PROGRESS** at `Full-farm staged search and unseen promotion gate`

Smoke block details (240 steps = 10-day partial horizon, contract only, not promotion evidence):
- games: 16/16 valid
- wins: 12/16
- win_rate: 0.75
- mean_margin: +598
- noop_rate: 0.0
- mean_peak_utilization: 1.0 of currently-owned acreage
- full_unlock_rate at 240 steps: 0.0; this is expected to remain a research question because the hard gate is evaluated at full 720 steps.

Smoke artifact: `kaggriculture-v4-smoke-34454305004`, artifact ID `10142813980`.

## Important interpretation
The V4 requirement is not merely to purchase land. A promotion candidate must both acquire all quadrants early and remain economically stronger than V1 across meta opponents. The search is allowed to reject over-aggressive profiles that unlock land quickly but destroy cash generation.

## Next action
1. Fetch workflow run `34454305004`.
2. When research completes, inspect the full search log/artifact.
3. Record the selected expansion profile and exact full-unlock/utilization metrics.
4. Require positive V1 duel plus holdout/final full-farm gates before promotion.
5. Do not submit to Kaggle until a later explicit review authorizes it.
