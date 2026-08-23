# AI WRITE LOCK

LOCKED: true
OWNER: DEEPSEEK
SCOPE: V11 quality optimization + AI orchestration infrastructure repair under mandatory multi-AI review
ACQUIRED: 2026-08-22

## Current baseline

Signal V11 is the sole public signal authority on GitHub `main` and remains SIGNAL_ONLY.

Completed automation scope:
- automatic Telegram alert for newly stored V11 MARKET-ready approved signals;
- automatic Telegram TP / SL / EXPIRED lifecycle alerts;
- Telegram dashboard LIVE / WATCH / scans / history / stats / manual three-AI hunter;
- automatic duplicate OPEN suppression;
- legacy non-market approvals invalidated without resetting TRADING_STATE;
- CI validation on `main` for V11 automation invariants;
- canonical Cloudflare auto-deploy workflow remains the normal deployment path.

## Active optimization + infrastructure scope

DeepSeek remains the implementation/source writer for a given active implementation branch. Codex and Claude are independent reviewers. Qwen and OpenRouter may run continuously as advisory, test, triage, alternative-patch-planning, and fallback lanes. They must not write to the same active implementation branch while DeepSeek owns it.

The orchestration target is event-driven and non-blocking: independent analysis/review/test lanes start immediately and do not wait for unrelated jobs. Waiting is allowed only for a real dependency such as exact-SHA review, final consensus, or merge/deploy safety gates.

Required infrastructure invariants:
- exactly one source writer per active implementation branch/path scope at a time;
- independent advisory/review/test lanes may run in parallel without a global queue;
- unrelated task/PR orchestration must not share a repository-wide concurrency bottleneck;
- no implementation task may create duplicate PRs for the same task id;
- review evidence is bound to the exact implementation SHA;
- Codex and Claude review independently; neither may silently substitute for the other;
- DeepSeek must never review/approve its own implementation as an acceptance signal;
- Qwen/OpenRouter advisory output is non-authoritative until incorporated by the active writer and revalidated;
- stale task/base metadata must fail closed without spawning replacement tasks endlessly;
- workflow failures must surface explicit diagnostics instead of silently stalling;
- no workflow or watcher may print or commit secrets;
- no infrastructure repair may weaken V11 trading safety gates.

## Scheduling / worker-pool protocol

- Do not serialize the whole AI system behind one global workflow concurrency group.
- Dispatch, review, triage, observability, and unrelated task lanes should execute independently whenever GitHub/VPS capacity permits.
- A worker that has no write-safe task may perform read-only review, testing, log triage, backlog analysis, or alternative repair planning instead of idling.
- Exact-SHA acceptance remains a dependency barrier: final merge/deploy may not use review evidence from an older SHA.
- Overlapping source edits remain serialized at the branch/path level; speed must come from parallel independent lanes, not conflicting writes.

Hard trading invariants:
- preserve TRADING_STATE;
- preserve V11 native scheduler and VPC AI bridge;
- keep SIGNAL_ONLY authority;
- never promote LIMIT/WATCH/MARKET_PLAN into MARKET;
- never weaken quote freshness, structural SL, RR/forward-liquidity or deterministic market gates merely to increase trade count;
- never fabricate market data, ATR, bid/ask, P/L or deployment evidence;
- never restore Futures Signal or Hyro/TK2 execution;
- never merge Binance Auto execution authority into V11;
- never commit secrets/tokens/private keys.

## Lock protocol

- OWNER DEEPSEEK is the active implementation writer on a specific implementation branch unless ownership is explicitly transferred.
- Codex and Claude remain independent acceptance reviewers.
- Qwen and OpenRouter are allowed to stay busy with read-only/advisory work in parallel; they do not become acceptance authorities merely by being available.
- ChatGPT acts as orchestrator/controller and may maintain task metadata, review routing, scheduling policy, lock scope, and non-overlapping orchestration infrastructure when explicitly authorized by the user; it does not count as an independent implementation reviewer.
- Current GitHub `main` is authoritative; stale checkpoints do not override source.
