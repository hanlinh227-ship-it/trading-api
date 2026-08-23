# AI WRITE LOCK

LOCKED: true
OWNER: DEEPSEEK
SCOPE: V11 production quality/runtime + protected trading authority
ACQUIRED: 2026-08-22

Signal V11 is the sole public signal authority on GitHub `main` and remains SIGNAL_ONLY.

## Owner-authorized direct research mode (2026-08-23)

The owner explicitly cancelled the PR/Issue/job-gated orchestration for V11 backtest research and requested the normal direct-backtest workflow used in earlier research versions, with all five AI lanes participating.

For **research-only backtest files and evidence** (`scripts/v11_backtest_mtf.py`, `scripts/v11_backtest_mtf_run.py`, `scripts/v11_mtf_data_cache.py`, `data/v11_mtf_*`, and the dedicated direct research workflow), ChatGPT/orchestrator may make bounded direct changes on current GitHub `main` and run deterministic backtests without opening an implementation PR or waiting for an Issue gate. The five AI lanes Claude, Codex, DeepSeek, Qwen and OpenRouter must participate in the research council for a compliant five-AI round; deterministic replay/evidence remains the performance authority. This exception exists to remove orchestration latency, not to weaken evidence standards.

This direct-research exception does **not** authorize production deployment or changes to Signal V11 execution authority, Telegram signal activation, exchange execution, Cloudflare production trading runtime, TRADING_STATE, risk gates, quote freshness, lifecycle rules, or secrets. Those remain protected and fail-closed.

## Production/orchestration authority

- DeepSeek remains the default source writer for protected production strategy/runtime changes.
- Codex/Claude remain independent review lanes for protected production changes where required.
- Qwen/OpenRouter remain advisory/adversarial lanes.
- Deterministic validation remains mandatory for all trading evidence and production changes.
- Research backtest evidence may never be promoted to production merely because a direct run finishes or reports a high win rate.

## Scheduling invariants

- no repository-wide writer queue;
- direct V11 research backtests do not require PR/Issue scheduling;
- unrelated protected production tasks serialize only where paths overlap;
- stale output is never force-overwritten;
- provider/data failure is surfaced explicitly;
- no secrets in source/comments/logs.

## Research backtest invariants

- all current catalog symbols remain present and independently evaluated;
- required win rate is inclusive >=80.00% per symbol;
- RR is exactly 1:1 or 1:2;
- every eligible symbol/day must contain 1-3 real actual executions; zero or >3 is FAIL;
- closed-market days are excluded explicitly;
- missing exact history is a surfaced data failure, never silently made non-eligible;
- no pooling, symbol deletion, fabricated trade, blind last-bar fill, proxy promotion, lookahead/future leakage, silent eligible-day deletion, or repeated final-holdout tuning;
- DEV/VALIDATION learning may be reused; untouched final-holdout outcomes may not tune later parameters;
- full multi-timeframe research should derive higher frames from the finest exact practical base feed with closed-bar alignment.

## Hard production trading invariants

Preserve `TRADING_STATE`, V11 native scheduler, VPC AI bridge, SIGNAL_ONLY authority, canonical quote freshness, structural/volatility-aware SL, deterministic market gates, max-five-open-per-market enforcement, weekend market closures, and 4/5 AI confirmation for discretionary CUT.

New-entry state must be evaluated by the single V11 entry-eligibility authority. A `LIMIT`/`LIMIT_PLAN` may be promoted to MARKET only when canonical LIVE price has actually reached the configured symbol/market near-entry threshold and drift/chase gates pass. A `MARKET_PLAN` may be actionable only under the same fresh-price and deterministic execution gates. `WATCH`, stale quotes, invalid geometry, hard news blackout, volatility shock, extreme chase, and price-source divergence must never be promoted.

An already-open signal must never be CUT merely because a later scan relabels it `LIMIT`, `LIMIT_PLAN`, `MARKET_PLAN`, or `WATCH`. TP/SL are deterministic; discretionary CUT requires the current hold-invalidation logic plus the configured 4/5 AI confirmation path.

For a symbol that has independently passed the current four-month calibration gate, target RR is locked to exactly 1:1 or 1:2 as recorded by its generated backtest profile. Do not fabricate backtest, quote, deployment, or performance evidence. Do not restore Futures Signal or Hyro/TK2 execution, merge Binance Auto authority into V11, or commit secrets/private keys.

ChatGPT is orchestrator/controller and may maintain direct research methodology/routing under explicit owner authorization; current GitHub `main` is authoritative.
