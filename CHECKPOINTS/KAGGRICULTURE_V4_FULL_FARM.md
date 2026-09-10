# Kaggriculture V4 Full-Farm Expansion Checkpoint

Updated: 2026-09-10

## Purpose
V4 is an isolated branch created from the V3 meta-orchestrator so the canonical V3 research run can continue without conflict.

Branch: `codex/kaggriculture-v4-full-farm-expansion`
Base snapshot: V3 head `347cb1f2f1b22b5136d10dc9d6abfc62387e7fb5`
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
- Search uses cheap A/B screens before full-horizon C/D/E/F gates to reduce wasted compute.
- Promotion requires 100% full unlock on unseen holdout/final games, mean full unlock <= day 12, full-farm peak utilization >= 68%, zero unit no-ops, strong multi-family performance and positive V1 duel.

## Safety / competition handling
- No Kaggle submission job exists in the V4 workflow.
- No KAGGLE_API_TOKEN is read by V4.
- No public competitor code/replay ingestion is used.
- Candidate is only committed if all promotion gates pass.

## Workflow
`.github/workflows/reward-kaggriculture-v4-full-farm.yml`

The workflow validates against pinned `kaggle-environments==1.32.4`, performs compile/tests/raw-exec, expansion smoke, full staged research and uploads artifacts. A trigger file is used so champion commits do not recursively launch another full run.

## Next action
1. Trigger the V4 workflow.
2. Record workflow run ID.
3. If validation fails, inspect logs and fix before research.
4. If research passes, inspect V4 vs V1 margin plus unlock/utilization metrics.
5. Do not submit to Kaggle until a later explicit review authorizes it.
