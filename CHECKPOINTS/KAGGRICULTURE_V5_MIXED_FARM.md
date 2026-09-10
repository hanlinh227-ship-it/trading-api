# Kaggriculture V5 Mixed-Farm Economy Checkpoint

Updated: 2026-09-10 20:45 +07

## Identity
- Repository: `hanlinh227-ship-it/trading-api`
- Branch: `codex/kaggriculture-v5-mixed-farm-economy`
- PR: #218 `[KAGGLE-V5] Mixed-Farm Economy and Cyclic Challenger League`
- Engine for current evidence: `kaggle-environments==1.32.7`
- Kaggle submission from V5: **NO**
- Live incumbent remains self-contained V1 submission `56139689`; last confirmed publicScore `337.0`.

## Purpose
V5 treats Kaggriculture as one capital-allocation system: crop cashflow -> market sales -> working capital -> land/labor/livestock -> feed/care/fertilizer -> harvest -> reinvest. Full-farm expansion is a research objective but never overrides profitability or evidence gates.

## V5.0 / V5.1 history
V5.0 canonical run `34458086918` exposed a cash deadlock: 16/16 valid, 0 wins, mean margin -2400.625, mean money 0.0. It reserved almost all next-land cash while hiring/building, starving seeds.

V5.1 reordered working capital, bounded hires/animal purchases/structures, reserved feed wheat and diversified crop ROI. Validation run `34458596933`: 16/16 valid, 4 wins, mean money 1392.25, mean margin -889.4375, zero unit no-ops. Progress only; not promotion evidence.

## V5.2 strong canonical research result
Run `34459804967` completed validate + research successfully on 1.32.7. Best candidate parameter hash prefix `d3dd324477`:
- crop_mode `roi`
- expansion_mode `fast`
- land_buffer 180
- target_hands 11
- herd_mode `cow_sheep`
- cow_max 6
- sheep_max 4
- goose_max 0
- livestock_start_day 2
- fertilizer_mode `adaptive`
- sell_batch 5
- seed_scale 1.45

Current-engine evidence from that run:
- Stage C: 48/48 wins, mean margin +33488.3125, p20 +23825, worst +15643.
- Direct V1 duel D: 8/8 wins, mean margin +21765.5, p20 +4976, worst +2546.
- Holdout E: 64/64 valid, 63 wins, mean margin +33243.90625, p20 +26695, worst -2888, catastrophic rate 0.
- Final F: 64/64 wins, mean margin +31518.953125, p20 +22293, worst +3410, catastrophic rate 0.
- candidate raw-exec PASS, official loader PASS, package/source episode equivalence PASS.
- candidate-main.py sha256: `88acdcffe5840f673e4f26edcdf3d03c4b02622c73c73e20f045b475c6027893`.
- research artifact: `kaggriculture-v5-research-34459804967`, artifact id `10145994708`.

The run still returned PROMOTION=false because incumbent baseline holdout/final blocks were invalid (`invalid_4`, `invalid_5`). Root cause was benchmark plumbing, not the candidate: legacy V1 `make_agent()` accepted one argument but `_track()` called tracked baselines with `(obs, configuration)`.

Even after fixing that plumbing, the measured candidate is **not automatically promotion-ready** because the strict campaign requirements still include mean full unlock <= day 12, >=0.60 full-farm productive utilization and <=8 mean terminal unsold units. V5.2 measured roughly day 17.9 unlock, ~0.50-0.53 utilization and ~21-22 terminal unsold units. Do not weaken those gates merely to manufacture PASS.

## V5.3 hardening performed by ChatGPT
- `benchmark_v5.py`: added `_two_arg_adapter()` for the legacy V1 baseline so baseline evidence can be valid without modifying the live V1 agent.
- `tests/test_v5.py`: added a real 1.32.7 regression that evaluates legacy incumbent as a tracked candidate in both seats; expects 2/2 valid games.
- shared PR workflow `.github/workflows/reward-kaggriculture-v3.yml`: now detects the V5 lane, installs 1.32.7, runs V5 contract tests, raw-exec, both-seat smoke and full-horizon incumbent check instead of stale V3-only tests. Latest PR validation run `34484026991` is SUCCESS across every validation step.
- public-meta workflow now samples only the two most recent dated replay Parquet shards instead of scanning aggregate history first, caps parsing at 80 rows/file and 160 seat-records, has a 10-minute parser timeout and writes a preflight artifact.
- public-meta workflow concurrency is non-cancelling so a new scheduled scan cannot kill an in-flight challenger league.
- branch cyclic cadence remains every 6 hours plus one deeper daily run after merge to default branch. No auto-submit.

## V5.3 active runs
Canonical V5.3 run:
- run id `34483998540`
- trigger commit `dfcde4231a7e42ea2ad07eeada3ee13bb9f5c09d`
- current status at checkpoint update: IN PROGRESS.
- purpose: rerun canonical search with valid incumbent baseline blocks.

Public-meta/challenger V5.3 run:
- run id `34484024952`
- trigger commit `3df5f9e043fa8b031398855fb2e3b19b277671dc`
- `analyze-public-meta`: SUCCESS.
- archive download: SUCCESS.
- bounded recent Parquet analysis: SUCCESS (fixes the previous 25-minute timeout).
- `adaptive-local-search`: IN PROGRESS at checkpoint update.

Shared PR validation:
- run id `34484026991`
- conclusion: SUCCESS.
- compile/contracts: PASS.
- generated raw-exec: PASS.
- official both-seat episodes: PASS.
- full-horizon endgame/incumbent check: PASS.

## Public meta architecture
Research-only analyzer: `reward-hunter/kaggriculture-v3/meta/replay_intelligence.py`.
Workflow: `.github/workflows/reward-kaggriculture-v5-meta-intel.yml`.
It reads public replay data offline and converts recent top-play behavior into one search prior. That prior still must survive local candidate screening, incumbent duel, multiple opponent families, unseen holdout/final and runtime/package gates. The submitted agent never uses network/replay files.

## Claude V6 status
Claude reported a local V6 branch/commit (`claude/kaggriculture-v6-adaptive-continuous`, local HEAD `8e223bcc`) and local tests, but its session could not push because of GitHub permission. No V6 branch/PR exists on GitHub and the reported bundle/patch has not been uploaded into this ChatGPT conversation. Therefore V6 is **not integrated** and must not be represented as deployed evidence.

## Promotion / submission rules
- Never submit a candidate merely because it wins local starter/meta games.
- Require exact 1.32.7 engine provenance, complete both-seat coverage, valid incumbent baselines, direct incumbent duel, unseen holdout/final, tail-risk checks, full-farm economics, zero invalid unit actions, low terminal waste, raw-exec, official loader and exact package/source equivalence.
- Kaggle submission is separate and explicit; no scheduled workflow can submit.
- Kaggle controls live matchmaking; this repository may monitor public results but must not force or manipulate matchmaking or submission quotas.

## NEXT CHAT COMMAND
User can type: `check PR kaggle`

Next AI should first:
1. inspect PR #218 and this checkpoint;
2. inspect runs `34483998540`, `34484024952`, and `34484026991`;
3. confirm whether V5.3 baseline blocks are now valid and whether the adaptive challenger completes;
4. if PR #218 has been merged, verify schedules on `main` and inspect the first default-branch scheduled/manual run;
5. do not call any candidate PROMOTION_READY until the strict gate itself passes;
6. never expose `KAGGLE_API_TOKEN`.
