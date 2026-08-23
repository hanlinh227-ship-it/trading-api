# AI WRITE LOCK

LOCKED: true
OWNER: MULTI_AI_ORCHESTRATOR
SCOPE: Multi-AI gateway/control-center integration, then V11 quality optimization
ACQUIRED: 2026-08-23

## Current baseline

Signal V11 is the sole public signal authority on GitHub `main` and remains SIGNAL_ONLY. Preserve TRADING_STATE, V11 native scheduler, VPC AI bridge, deterministic freshness/structure/RR gates, automatic Telegram lifecycle, and separate Binance Auto authority.

## Concurrent writer policy

The user explicitly authorized maximum safe parallelism across all five providers. Concurrency is now path/task scoped rather than repository-wide.

- DeepSeek: primary implementation/repair writer.
- Qwen: independent implementation/test writer only on a disjoint allowed-path shard.
- Codex: technical/security reviewer; no overlapping source writes while reviewing.
- Claude: architecture/regression reviewer; no overlapping source writes while reviewing.
- OpenRouter: adversarial/fallback reviewer; read-only by default.
- ChatGPT: orchestrator/integrator. It may maintain lock metadata, route work, and apply provider-generated patches when explicitly authorized by the user, but does not count as an independent reviewer.

Required writer invariants:
- only one writer per exact file/path at a time;
- same task/PR/path writers serialize;
- unrelated tasks and disjoint path shards may run concurrently;
- every writer starts from an exact head SHA and must compare-and-swap before push;
- stale output is discarded/re-read, never force-overwritten;
- reviewers never acquire writer locks;
- no task may create duplicate implementation PRs for the same task id;
- review evidence must bind to the exact implementation SHA;
- no workflow may print/commit secrets;
- missing provider evidence fails closed rather than fabricating success.

## Hard trading invariants

Never reset `TRADING_STATE`, weaken freshness/structural SL/RR/forward-liquidity/deterministic gates, promote LIMIT/WATCH/MARKET_PLAN into MARKET, fabricate market data or deployment evidence, restore Futures Signal or Hyro/TK2 execution, merge Binance Auto execution authority into V11, or commit secrets/tokens/private keys.

GitHub `main` remains authoritative; stale checkpoints do not override current source.
