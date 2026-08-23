# AI WRITE LOCK

LOCKED: true
OWNER: MULTI_AI_ORCHESTRATOR
SCOPE: Secure Multi-AI gateway integration, then V11 quality optimization
ACQUIRED: 2026-08-23

Signal V11 is the sole public signal authority on GitHub `main` and remains SIGNAL_ONLY.

## Current orchestration authority

- DeepSeek is the primary source writer for an active implementation branch/path shard.
- Qwen may write only to a disjoint allowed-path shard with its own lock; otherwise it is read-only test/adversarial analysis.
- Codex is the authenticated exact-SHA blocking automated reviewer for ACCEPT/REPAIR in the current GitHub closed-loop workflow.
- Claude is independently requested in parallel for architecture/regression review. User-authored Claude envelopes remain advisory until the secure Multi-AI Gateway supplies independently authenticated provider identity.
- OpenRouter is read-only adversarial/fallback by default.
- ChatGPT is orchestrator/integrator and may maintain task metadata, routing, lock scope, and explicitly authorized non-overlapping integration patches; it is not an independent implementation reviewer.

When authenticated five-provider gateway evidence is available, it may expand reviewer/test participation without weakening exact-SHA or deterministic validation gates.

## Scheduling and writer invariants

- no repository-wide writer queue;
- unrelated tasks/PRs and disjoint path shards run in parallel;
- same task/PR/path writers serialize;
- exactly one writer per overlapping path shard;
- every writer starts from an exact head SHA and CAS-checks the remote head before push;
- stale output is discarded/re-read, never force-overwritten;
- reviewers do not acquire overlapping writer locks;
- no task may create duplicate implementation PRs for the same task id;
- deterministic validation and exact-SHA blocking review remain final dependency barriers;
- provider failure removes only that lane and is surfaced explicitly;
- missing provider evidence fails closed rather than fabricating success;
- no secrets/API keys/private keys may appear in source, browser payloads, comments, or logs.

## Hard trading invariants

Preserve `TRADING_STATE`, V11 native scheduler, private VPC `AI_BRIDGE`, SIGNAL_ONLY authority, quote freshness, structural SL, RR/forward-liquidity, automatic Telegram lifecycle and deterministic market gates. Never promote LIMIT/WATCH/MARKET_PLAN into MARKET, fabricate market/deployment evidence, restore Futures Signal or Hyro/TK2 execution, merge Binance Auto execution authority into V11, or commit secrets/private keys.

GitHub `main` remains authoritative; stale checkpoints do not override current source.
