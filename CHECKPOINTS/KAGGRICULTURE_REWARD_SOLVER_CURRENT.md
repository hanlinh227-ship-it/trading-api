# KAGGRICULTURE REWARD SOLVER CHECKPOINT

Updated: 2026-09-10

## Project
- Repository: `hanlinh227-ship-it/trading-api`
- Competition: Kaggle Kaggriculture 2026
- Main integration PR #215 merged at `0624e73c079b3097b1b97f69279ea625bd77ec53`.
- `KAGGLE_API_TOKEN` is stored only as a GitHub Actions secret. Never request, print or commit its value.
- Current promotion evidence must use `kaggle-environments==1.32.7`.

## Live Kaggle incumbent
- Accepted self-contained V1 submission: `56139689`, COMPLETE.
- Last confirmed live publicScore: `337.0` from status run `34453161833`.
- Old tar submissions `56139515` / `56139862` are invalid/error paths and must not be reused.
- The first raw-exec failure was caused by assuming `__file__`; every future candidate must remain self-contained and pass raw-exec + official loader + package/source equivalence before submission.

## Historical lanes
- V1: `reward-solver-kaggriculture-v1`, path `reward-hunter/kaggriculture/`.
- V2 Fast: `reward-solver-kaggriculture-v2-fast`; final holdout vs starter 8/8 but direct V1 duel only 25% / mean margin -728.5, so not promoted.
- V3 Codex: PR #216 `[KAGGLE-V3] Meta Orchestrator and Robust Search System`, branch `codex/kaggriculture-v3-meta-orchestrator`; historical strong numbers are not submission evidence because an early study used a mismatched simulator source despite the same version label.
- V4 Full Farm: PR #217 `[KAGGLE-V4] Full-Farm Expansion and Utilization Campaign`, branch `codex/kaggriculture-v4-full-farm-expansion`; research lane for rapid four-quadrant expansion/utilization, no auto-submit.

## ACTIVE LANE — V5 Mixed-Farm Economy
- Branch: `codex/kaggriculture-v5-mixed-farm-economy`
- Draft PR: #218 `[KAGGLE-V5] Mixed-Farm Economy and Cyclic Challenger League`
- PR URL: https://github.com/hanlinh227-ship-it/trading-api/pull/218
- Dedicated checkpoint: `CHECKPOINTS/KAGGRICULTURE_V5_MIXED_FARM.md`
- Claude audit prompt: `CHECKPOINTS/CLAUDE_KAGGRICULTURE_V5_REVIEW_PROMPT.md`
- Kaggle submission from V5: **NO**.

### V5 objective
Treat the farm as one capital-allocation system:
`crop cashflow -> market selling -> working capital -> land/labor/livestock -> feed/care/fertilizer -> harvest -> reinvest`.
Opening four quadrants is a campaign goal but never overrides profitability or promotion evidence.

### V5.0 failure
Canonical run `34458086918` exposed an economic deadlock:
- 16/16 valid
- 0 wins
- mean margin `-2400.625`
- mean money `0.0`
- movement/idle `0.9834`
Root cause: almost the full next-land price was reserved while hiring/building continued, starving the seed income engine; structures also ran too far ahead of the funded herd.

### V5.1 recovery
Run `34458596933` validation/economic smoke after working-capital fixes:
- 16/16 valid
- 4 wins / 16
- mean money `1392.25`
- mean margin `-889.4375`
- mean peak animals `12.0625`
- terminal unsold units `31.75`
- movement/idle `0.6550`
- unit no-op `0`
- raw-exec PASS
- official loader PASS
This is progress, not a champion.

### V5.2 hardening now in branch
- Seat-safe canonical clock: derive turn from `day * turnsPerDay + hour` because 1.32.7 may omit `obs['step']` for seat 1; inject derived step only as a compatibility shim for legacy routing helpers.
- Benchmark full-unlock telemetry uses the same seat-safe clock.
- Regression tests cover missing-step seat 1 behavior and replay JSON decoding.
- Public replay analyzer now supports JSON/JSONL/Parquet, JSON-like string/binary cells, bounded file/row scans, deduplication and schema diagnostics.
- Public-meta workflow installs PyArrow, retries archive download, fails closed on empty/stale data and uploads diagnostics even on failure.
- Cyclic local challenger league: public replay refresh -> meta prior -> staged candidates -> incumbent duel -> multi-family opponents -> unseen holdout/final -> raw-exec/package equivalence -> `PROMOTION_READY` only on PASS.
- No scheduled or push path ever auto-submits to Kaggle.
- Scheduled workflows only recur after the workflow exists on the repository default branch; do not claim feature-branch cron is already continuously active.

### Current V5.2 runs
- Canonical research run: `34459804967`
  - `validate`: SUCCESS
  - `research / Crop-herd-expansion search and unseen gates`: IN PROGRESS at latest check.
- Public-meta/challenger run: `34459819333`
  - replay-analysis dependencies: SUCCESS
  - public top-replay archive download: SUCCESS
  - `Analyze JSON and Parquet public episodes offline`: IN PROGRESS at latest check.
- Previous public-meta run `34458096559` failed because the archive was Parquet and the old parser only read JSON/JSONL; V5.2 explicitly fixes that root cause.

## Current promotion rule
Do not promote or submit because a candidate resembles a top replay, opens all land, or wins one smoke block. Require current 1.32.7 evidence covering:
- all games valid / both seats
- direct incumbent duel
- multiple opponent families
- unseen holdout + final
- tail risk
- full-farm timing + productive utilization
- unit no-op / movement waste
- terminal unsold inventory
- raw-exec + official loader
- exact package/source episode equivalence

## Continuous improvement semantics
“Continuous rematch” means periodic **local challenger-league research** plus public-meta refresh. Kaggle controls live ladder matchmaking. Do not attempt to force matchmaking, bypass submission limits or manipulate ranking infrastructure.

## Claude second-opinion handoff
No Claude/Anthropic connector is available in the current ChatGPT session. The exact audit prompt is committed at `CHECKPOINTS/CLAUDE_KAGGRICULTURE_V5_REVIEW_PROMPT.md`. If the user pastes it into Claude with GitHub access, Claude is instructed to create branch `claude/kaggriculture-v5-crop-cycle-audit`, open a PR titled `[KAGGLE-V5-CLAUDE]...` back into the V5 branch, run evidence-based tests, and leave `CHECKPOINTS/KAGGRICULTURE_V5_CLAUDE_AUDIT.md`.

## What the next chat should do first
If user says `check PR kaggle`:
1. inspect PR #218 and read `CHECKPOINTS/KAGGRICULTURE_V5_MIXED_FARM.md` from its head branch;
2. inspect V5.2 runs `34459804967` and `34459819333` first;
3. if the Parquet analyzer fails, use emitted schema diagnostics and repair the real schema rather than guessing;
4. if canonical search fails, repair the exact runtime/economic issue and rerun;
5. look for a `[KAGGLE-V5-CLAUDE]` PR and evaluate it if the user has run the Claude prompt;
6. do not submit V5 until promotion/raw-exec/package-equivalence pass and the exact candidate hash is identified;
7. never expose `KAGGLE_API_TOKEN`.

## Safety
- Keep secrets only in GitHub Actions secrets.
- No multi-accounting, submission-limit bypass, hidden/private test extraction, collusion or matchmaking manipulation.
- Do not claim leaderboard improvement without real Kaggle ladder evidence.
