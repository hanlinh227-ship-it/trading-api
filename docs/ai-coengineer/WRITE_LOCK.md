# AI WRITE LOCK

LOCKED: true
OWNER: DEEPSEEK
SCOPE: V11 quality optimization + non-blocking AI orchestration
ACQUIRED: 2026-08-22

Signal V11 is the sole public signal authority on GitHub `main` and remains SIGNAL_ONLY.

## Current orchestration authority

- DeepSeek is the source writer for the active implementation branch/path shard.
- Codex is the authenticated exact-SHA blocking automated reviewer for ACCEPT/REPAIR in the current GitHub closed-loop workflow.
- Claude remains a mandatory independent advisory architecture/regression review request, but user-authored Claude envelopes cannot authorize ACCEPT or automatic REPAIR because they do not carry an independently authenticated Claude identity.
- Qwen/OpenRouter may run continuously as read-only test/adversarial/fallback lanes.
- The authenticated Multi-AI Gateway may provide independent provider evidence, but deterministic exact-SHA validation remains the final barrier.

This is intentionally explicit: no unauthenticated comment may become merge/repair authority merely to satisfy a nominal dual-review label.

## Scheduling invariants

- no repository-wide writer queue;
- unrelated tasks/PRs run in parallel;
- same task/PR/path writers serialize;
- one writer per overlapping path shard;
- all writer output starts from exact head and CAS-checks remote head before push;
- stale output is discarded, never force-overwritten;
- deterministic validation and exact-SHA blocking review remain final dependency barriers;
- provider failure removes only that lane and is surfaced explicitly;
- no secrets in source/comments/logs.

## Hard trading invariants

Preserve `TRADING_STATE`, V11 native scheduler, VPC AI bridge, SIGNAL_ONLY authority, canonical quote freshness, structural/volatility-aware SL, deterministic market gates, max-five-open-per-market enforcement, weekend market closures, and 4/5 AI confirmation for discretionary CUT.

New-entry state must be evaluated by the single V11 entry-eligibility authority. A `LIMIT`/`LIMIT_PLAN` may be promoted to MARKET only when canonical LIVE price has actually reached the configured symbol/market near-entry threshold and drift/chase gates pass. A `MARKET_PLAN` may be actionable only under the same fresh-price and deterministic execution gates. `WATCH`, stale quotes, invalid geometry, hard news blackout, volatility shock, extreme chase, and price-source divergence must never be promoted.

An already-open signal must never be CUT merely because a later scan relabels it `LIMIT`, `LIMIT_PLAN`, `MARKET_PLAN`, or `WATCH`. TP/SL are deterministic; discretionary CUT requires the current hold-invalidation logic plus the configured 4/5 AI confirmation path.

For a symbol that has independently passed the current four-month calibration gate, target RR is locked to exactly 1:1 or 1:2 as recorded by its generated backtest profile. Do not fabricate backtest, quote, deployment, or performance evidence. Do not restore Futures Signal or Hyro/TK2 execution, merge Binance Auto authority into V11, or commit secrets/private keys.

ChatGPT is orchestrator/controller and may maintain task metadata, routing and lock scope when explicitly authorized by the user; it is not an independent implementation reviewer. Current GitHub `main` is authoritative.
