# AI WRITE LOCK

LOCKED: true
OWNER: DEEPSEEK
SCOPE: V11 quality optimization + Telegram signal discrimination under 3-AI review
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

## Optimization scope

DeepSeek may implement only bounded V11 quality/ranking/discrimination improvements supported by current evidence. Required independent reviewers: Codex and Claude on the same implementation SHA.

Hard invariants:
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
- Codex and Claude are reviewers only until DeepSeek completes or the task is released.
- Current GitHub `main` is authoritative; stale checkpoints do not override source.
