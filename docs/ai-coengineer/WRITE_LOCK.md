# AI WRITE LOCK

LOCKED: true
OWNER: DEEPSEEK
SCOPE: V11 quality optimization + AI orchestration infrastructure repair under mandatory 3-AI review
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

DeepSeek is the only implementation/source writer while this lock is active. Codex and Claude are independent reviewers/advisers and may not modify overlapping source. The active scope now also includes bounded AI orchestration infrastructure repair needed to make the three-AI loop reliable and non-conflicting.

Required infrastructure invariants:
- exactly one source writer at a time;
- all writer entry points share one concurrency group;
- no implementation task may create duplicate PRs for the same task id;
- review evidence is bound to the exact implementation SHA;
- Codex and Claude review independently; neither may silently substitute for the other;
- DeepSeek must never review/approve its own implementation as an acceptance signal;
- stale task/base metadata must fail closed without spawning replacement tasks endlessly;
- workflow failures must surface explicit diagnostics instead of silently stalling;
- no workflow or watcher may print or commit secrets;
- no infrastructure repair may weaken V11 trading safety gates.

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

- OWNER DEEPSEEK is the only source writer while this lock is active.
- Codex and Claude are reviewers/advisers only until DeepSeek completes or the task is released.
- ChatGPT acts as orchestrator/controller and may maintain task metadata, review routing, and lock scope when explicitly authorized by the user; it does not count as an independent implementation reviewer.
- Current GitHub `main` is authoritative; stale checkpoints do not override source.
