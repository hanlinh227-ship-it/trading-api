# V11 DIRECT 5AI FAST RESEARCH CHECKPOINT

Updated: 2026-08-24 UTC+7
Repository: `hanlinh227-ship-it/trading-api`
Purpose: canonical checkpoint for the current V11 research/backtest phase.

## 0. SOURCE OF TRUTH

1. Fresh-read GitHub `main` before any substantive continuation.
2. GitHub `main` + current source/evidence outrank stale chats/checkpoints.
3. This checkpoint describes the owner-authorized **direct research/backtest mode** only.
4. Signal V11 production remains separate, protected and `SIGNAL_ONLY`.

Checkpoint starting head at creation: `bf19563d5c5f3cceaa8a7aeec5a075e4ca2bad6a`.

## 1. WHY THIS CHECKPOINT EXISTS

The previous V11 research path became too slow because research was repeatedly blocked by orchestration work: Issue creation, PR creation, reviewer gates, workflow-token permissions, duplicate-PR checks, structured-output transport, monitor jobs and job retries.

Owner decision: **stop using PR/Issue/job-gated orchestration as the normal V11 backtest loop.**

AI exists here to accelerate research, compare hypotheses and learn from evidence. AI infrastructure must not become the main workload.

## 2. CANONICAL RESEARCH MODE

Use the normal direct backtest style used in earlier research versions:

`fresh main -> 5AI research council -> deterministic direct backtest -> 5AI evidence review -> bounded method change -> direct backtest again`

Do NOT insert a mandatory sequence like:

`Issue -> implementer job -> PR -> reviewer job -> merge -> another job -> backtest`

for ordinary research iteration.

PR/review workflow remains appropriate for protected production changes, not for routine isolated research backtests.

## 3. FIVE AI ARE ACCELERATORS, NOT BACKTEST ENGINES

Required research council lanes:
- Claude
- Codex
- DeepSeek
- Qwen
- OpenRouter

All five must contribute to a compliant final five-AI research round, but they should not each replay the same OHLC dataset independently five times.

Correct usage:
- all five independently study historical methods/current engine;
- all five propose hypotheses, identify leakage/overfit risks and failure clusters;
- one deterministic backtest engine replays the common frozen dataset;
- fresh deterministic evidence is returned to all five;
- all five compare the evidence and propose the next bounded method change;
- deterministic replay remains the performance authority.

This preserves five independent viewpoints without multiplying market-data replay cost by five.

## 4. AI FAILURE / JOB FAILURE POLICY

Research must not sit idle solving orchestration jobs.

If one AI lane, gateway call, transport wrapper, PR bot, reviewer connector or GitHub job fails transiently:
- record the failure factually;
- do not fabricate that AI participated;
- continue the deterministic research/backtest work that can run safely;
- retry the missing AI review in parallel or after fresh evidence exists;
- do not spend repeated research cycles creating replacement Issues/PRs solely to repair orchestration;
- do not declare a **compliant five-AI final round** until all five have actually contributed.

In other words: **AI availability can make a final council incomplete, but should not stop safe deterministic research from progressing.**

A hard external blocker is only something that makes honest backtest evidence impossible, such as unavailable exact market history for a required symbol with no valid exact source, corrupted deterministic engine, or inability to execute the direct runner at all.

## 5. DIRECT WORKFLOW

Canonical research workflow:
`.github/workflows/v11-fiveai-direct-backtest.yml`

Canonical direct research files:
- `scripts/v11_mtf_data_cache.py`
- `scripts/v11_backtest_mtf.py`
- `scripts/v11_backtest_mtf_run.py`
- `scripts/v11_direct_backtest.py`

Current design:
- frozen dataset window for a research round;
- reusable immutable raw-data cache;
- feature cache where schema is unchanged;
- four deterministic symbol shards in parallel;
- 5AI pre-research starts alongside deterministic backtest work where possible;
- 5AI post-review consumes fresh FAST evidence;
- FINAL remains sealed until FAST candidate criteria and five-AI participation requirements are satisfied.

No continuous-watch monitor is required. No recurring AUTO_TASK research job is required.

## 6. SPEED POLICY

The slow operation should be **data acquisition/cache population**, ideally once per frozen dataset snapshot.

After the cache exists:
- do not refetch unchanged raw history;
- do not rebuild unchanged features;
- rerun only affected method logic/shards when possible;
- use parallel shards across independent symbols;
- use FAST DEV/VALIDATION rounds for method rejection;
- use full FINAL only after the candidate/profile is frozen.

Target: ordinary strategy-iteration rounds should be measured in minutes where compute/data permit, not multi-hour orchestration cycles.

Do not weaken evidence quality just to make runtime shorter.

## 7. MULTI-TIMEFRAME RESEARCH CONTRACT

Research should evaluate the full useful hierarchy, assigning roles rather than blindly mixing all frames:
- W1 / D1: macro regime, long-range structure, major liquidity context;
- H4 / H1: bias, structure, volatility, relative strength / SMT / breadth;
- M30 / M15: location, session, liquidity, setup/archetype;
- M5: trigger, displacement, MSS, FVG/retest confirmation;
- M1: execution refinement only when exact sufficiently deep M1 history exists.

Prefer deriving higher frames from the finest practical exact base feed using only closed bars.
Never fabricate a missing timeframe or expose an HTF candle before close.

## 8. HISTORICAL LEARNING TO PRESERVE

Use previous versions as priors/lessons, not as current proof:
- V62/V63: cross-market strength, candidate ranking, max-trades/day research ideas;
- V73: mandatory-daily research concept may be studied, but exposed-development all-pass evidence is not untouched OOS proof;
- V74: D1/H4/H1 bias + M15/M5 confirmation and structure-first risk;
- V76: strongest prior for M5-derived M15/H1/H4 + D1, session/regime context, objective archetypes and chronological DEV/VALIDATION/OOS discipline.

Shared repository knowledge/evidence should be read before proposing another method so the five AI do not rediscover the same failed ideas every round.

## 9. FIXED USER TARGET

Every current catalog symbol is evaluated independently.

Required final contract:
- current catalog count: 95 symbols unless current `main` changes the catalog;
- every eligible symbol/day must contain **at least 1 and at most 3 real actual executions**;
- zero executions on a valid eligible day = FAIL;
- more than 3 executions on an eligible day = FAIL;
- closed-market days are explicitly excluded;
- exact-data outage is surfaced as a data failure, never silently reclassified as non-eligible;
- RR exactly 1:1 or 1:2;
- per-symbol win rate target inclusive `>=80.00%`;
- positive expectancy;
- exact instrument history;
- no pooling of symbols;
- no symbol deletion;
- no fabricated trades or blind final-bar fills;
- no proxy promotion;
- no lookahead/future leakage;
- no silent eligible-day deletion;
- no repeated tuning against untouched final holdout.

## 10. FAST VS FINAL

### FAST RESEARCH
- chronological historical / DEV / VALIDATION only;
- used to reject weak ideas rapidly;
- may learn failure clusters and method stability;
- may update shared learning registry from historical/DEV/VALIDATION evidence;
- must not use untouched final holdout outcomes to choose future parameters.

### FINAL
- frozen method/profile only;
- untouched holdout;
- deterministic replay;
- no parameter changes after seeing FINAL outcomes;
- only this layer may support a fresh final success claim.

## 11. REPORTING POLICY

Do not proactively report intermediate pass counts, win rates or partial success while the research loop is still running.

Only report final success when **all current catalog symbols simultaneously pass every required deterministic gate** and the required five-AI participation evidence is genuine.

Never convert an AI opinion into a backtest result.

## 12. PRODUCTION REMAINS LOCKED

Direct research authorization does NOT authorize:
- production deployment;
- Telegram signal activation/unlock;
- exchange execution;
- Cloudflare trading-authority changes;
- `TRADING_STATE` reset/modification outside existing runtime behavior;
- weakening quote freshness, structural SL, lifecycle/risk gates;
- merging Binance Auto authority into Signal V11;
- secrets/API tokens/private keys in source or logs.

Signal V11 remains `SIGNAL_ONLY`.

## 13. WHAT TO DO WHEN A NEW CHAT STARTS

1. Fresh-read GitHub `main`.
2. Read `docs/checkpoints/MASTER_TRADING_STATE.md`.
3. Read `docs/checkpoints/CURRENT_HANDOFF.md`.
4. Read this checkpoint.
5. Read `docs/ai-coengineer/WRITE_LOCK.md`.
6. Inspect current direct workflow + direct runner + latest evidence.
7. Continue the direct five-AI research/backtest loop; do not rebuild PR/Issue/job-gated research orchestration unless the owner explicitly asks for it.

## 14. NEW CHAT PROMPT

`Continue Trading from fresh GitHub main. Read MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, V11_DIRECT_5AI_FAST_RESEARCH_20260823.md and WRITE_LOCK.md. V11 research is in owner-authorized DIRECT 5AI FAST mode: Claude, Codex, DeepSeek, Qwen and OpenRouter are research accelerators before/after one deterministic cached/sharded backtest engine. Do not restore PR/Issue/job-gated research loops. AI/job transport failures must not leave deterministic research idle; continue safe direct backtesting and retry missing AI participation separately, while final five-AI success still requires genuine participation from all five. Preserve 95-symbol independent evaluation, 1-3 real executions per eligible symbol/day, RR 1:1/1:2, >=80.00% per-symbol target, exact data, no leakage and untouched FINAL. Production Signal V11 stays SIGNAL_ONLY and locked. The owner is PROMPT-ONLY: never ask the owner to open Actions, copy logs, send screenshots, run commands, edit GitHub, or perform technical steps. The owner receives final result only. Use the NO-REPAIR GOLDEN PATH: prompt starts requested work immediately; stable research infrastructure is not redesigned or repaired unless a true hard blocker prevents the requested work.`

## 15. OWNER INTERACTION CONTRACT — PROMPT ONLY / FINAL RESULT ONLY

This is mandatory and supersedes any previous request for manual technical help.

The owner will:
- write prompts only;
- perform no GitHub, Actions, VPS, Cloudflare, terminal, log-copy, screenshot or manual technical operation;
- receive only the final outcome of the requested work.

The assistant/orchestrator must handle all available technical operations itself, including:
- fresh-reading GitHub `main` and current evidence;
- running/retrying direct backtests;
- invoking and coordinating all five AI lanes;
- reading Actions jobs/logs/artifacts/evidence through available tools;
- fixing research-only runner/workflow issues within authorized scope;
- comparing results and iterating methodology;
- maintaining checkpoints and research evidence.

Do NOT ask the owner to:
- open GitHub Actions;
- provide a run ID;
- copy/paste logs;
- send screenshots of workflow output;
- press Run/Re-run buttons;
- execute shell/terminal commands;
- edit files or settings;
- perform any troubleshooting step.

If a transient tool/provider/job problem occurs, solve or route around it without involving the owner and continue safe research.

If a true external hard blocker makes the requested result impossible with the available authorized tools, do not convert that into a manual task for the owner. Report only the final blocker after exhausting available compliant alternatives.

For this Trading research program, the owner-facing interaction model is therefore:

`OWNER PROMPT -> ASSISTANT/5AI/TOOLS DO ALL WORK -> OWNER RECEIVES FINAL RESULT ONLY`

## 16. NO-REPAIR GOLDEN PATH — PROMPT MUST START WORK

This rule is mandatory for ordinary research prompts.

The system is treated as a stable appliance, not a software project that must be redesigned every time the owner asks for work.

For each new owner prompt:
1. classify the requested task;
2. use the existing stable tool/runner/data path immediately;
3. start the requested research/backtest/analysis before any optional optimization work;
4. run five-AI research/adversarial review in parallel where useful, never as a serial prerequisite to deterministic work;
5. use cached/frozen data whenever the dataset request is unchanged;
6. change methodology primarily through configuration/parameters/routing, not workflow rewrites;
7. return only the final requested outcome.

### Repair budget

Ordinary prompts have a default infrastructure-repair budget of **zero**.

Do not stop requested work to improve architecture, create Issues/PRs, redesign workflows, refactor helpers, change gateways, alter checkpoint machinery, or optimize infrastructure merely because a cleaner implementation is possible.

Infrastructure repair is allowed only when a **true hard blocker** directly prevents the requested work from producing honest evidence. In that case:
- use the smallest bounded repair;
- do not redesign unrelated components;
- resume the original task immediately after the blocker is removed;
- do not turn the repair itself into a new research project.

### Stable core / variable method split

Keep stable and rarely changed:
- data snapshot/cache layer;
- deterministic backtest engine;
- symbol catalog loader;
- integrity gates;
- evidence format;
- five-AI gateway contract;
- production locks.

Change frequently through configuration/evidence-driven routing:
- setup family;
- timeframe weighting;
- session/regime filters;
- trigger conditions;
- stop geometry within fixed integrity rules;
- RR choice from allowed domain;
- ranking weights;
- per-symbol profiles derived only from permitted historical/DEV/VALIDATION evidence.

The preferred research mechanism is **method-as-config**, not code-as-method. A strategy iteration should normally mean changing a bounded configuration and replaying the same deterministic engine, not writing a new workflow or rebuilding infrastructure.

### Failure containment

A failure in Claude/Codex/DeepSeek/Qwen/OpenRouter, an advisory API, logging, artifact upload, or nonessential orchestration must not stop deterministic work that can still run honestly.

Only failures in required exact data, the deterministic engine, integrity checks, or another component strictly necessary to produce truthful requested evidence may block the task.

### Operating objective

The desired owner experience is:

`PROMPT -> IMMEDIATE WORK -> INTERNAL ITERATION -> FINAL RESULT`

not:

`PROMPT -> REPAIR SYSTEM -> REPAIR JOB -> REPAIR AI -> START WORK LATER`
