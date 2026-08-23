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
- When the secure Multi-AI Gateway is merged, authenticated provider evidence may replace this transitional reviewer boundary without weakening exact-SHA/deterministic checks.

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

Preserve `TRADING_STATE`, V11 native scheduler, VPC AI bridge, SIGNAL_ONLY authority, quote freshness, structural SL, RR/forward-liquidity and deterministic market gates. Never promote LIMIT/WATCH/MARKET_PLAN into MARKET, fabricate market/deployment evidence, restore Futures Signal or Hyro/TK2 execution, merge Binance Auto authority into V11, or commit secrets/private keys.

ChatGPT is orchestrator/controller and may maintain task metadata, routing and lock scope when explicitly authorized by the user; it is not an independent implementation reviewer. Current GitHub `main` is authoritative.
