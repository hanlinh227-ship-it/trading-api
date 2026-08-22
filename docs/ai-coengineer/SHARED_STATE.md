# AI SHARED STATE

Updated: 2026-08-22 UTC+7
Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`

## CURRENT ARCHITECTURE — SIGNAL V11 ONLY

Signal V11 is the sole public signal authority and remains SIGNAL_ONLY.

Current runtime:
- Cloudflare native scheduler;
- TRADING_STATE KV lifecycle state;
- canonical markets: Forex, Crypto, Metal, Index Cash;
- automatic Telegram signal notification for newly stored MARKET-ready approvals;
- automatic Telegram TP / SL / EXPIRED lifecycle notification;
- Telegram dashboard for LIVE, WATCH, scans, history, stats and manual three-AI hunter;
- Binance Auto separate;
- Hyro/Futures legacy execution removed.

## AUTOMATION CONTRACT

Automatic signal admission requires genuine upstream `MARKET` / `MARKET_SIGNAL` plus deterministic V11 gates.
`LIMIT`, `LIMIT_PLAN`, `MARKET_PLAN` and `WATCH` cannot be promoted to automatic MARKET.

Duplicate OPEN market/symbol/side signals are blocked.
Legacy non-market approvals retained in state are invalidated to history without resetting TRADING_STATE.

## DATA INTEGRITY

- real M5/M15/H1/H4/D1 ATR14 + close evidence;
- no fabricated ATR or bid/ask;
- provider freshness remains a hard gate;
- structure SL and forward-liquidity TP remain deterministic;
- funnel keeps effective reason, gateReasons and planReason distinct;
- executable crypto MARKET output retains timeframe evidence;
- native scan reuses a fresh run-now analysis before unnecessary re-analysis.

## THREE-AI REVIEW

Manual/on-demand only:
- DeepSeek API-native when configured;
- Claude through VPC/VPS bridge;
- Codex through VPC/VPS bridge;
- all three required for positive consensus;
- errors, unavailable providers, WAIT, conflicts or hard risk fail closed;
- no automatic signal or execution authority.

VPC Service: `v11-ai-bridge`.
VPS service: `v11-manual-ai-bridge`.

## CI / DEPLOYMENT

- `.github/workflows/v11-signal-validation.yml` validates V11 production invariants on `main`;
- `.github/workflows/deploy-cloudflare-worker.yml` is the canonical Cloudflare deployment workflow for worker changes;
- `npm run check` remains required;
- generated Wrangler config must preserve TRADING_STATE, AI_BRIDGE, keep_vars and minute cron;
- never commit tokens/secrets.

## FAIL-CLOSED OUTCOMES

WATCH, RR insufficiency, quality rejection, stale/unverified quote rejection, NO_MARKET_ENTRY and NO_3AI_CONSENSUS are valid states. Do not weaken gates merely to increase signal count.

## NEXT PHASE

Infrastructure/plumbing is complete unless new runtime evidence proves otherwise.
Work next on evidence-driven signal quality:
1. production funnel distribution by market;
2. closed lifecycle outcomes;
3. ranking/discrimination improvements without weakening hard gates;
4. provider freshness investigation only when reproducible during active sessions;
5. Telegram clarity improvements that do not change authority.

## PERMANENT RULES

- Never reset TRADING_STATE.
- Never fabricate market data/tests/deployment evidence.
- Never restore Futures Signal or Hyro/TK2 execution.
- Never merge Binance Auto authority into V11.
- Never allow AI to bypass deterministic gates.
- V73 remains exposed-development prior, not untouched OOS proof.
- Fresh-read GitHub main before every write and obey WRITE_LOCK.md.
