# MASTER TRADING STATE

Updated: 2026-08-22 UTC+7
Purpose: single canonical state for the Trading project.

## CURRENT CANONICAL VERSION — SIGNAL V11

GitHub `main` is authoritative. Signal V11 is the sole public signal authority.

Current production contract:
- `publicSignalAuthority = V11_ONLY`;
- runtime = `CLOUDFLARE_NATIVE`;
- scheduler = `V11_NATIVE`;
- execution authority = `SIGNAL_ONLY`;
- canonical markets = Forex, Crypto, Metal, Index Cash;
- Hyro/Futures legacy execution remains removed;
- Binance Auto remains separate execution authority.

## AUTOMATED PRODUCTION TOPOLOGY

`GitHub main -> GitHub Actions preflight/deploy -> Cloudflare Worker trading-v77-scanner -> TRADING_STATE KV -> Telegram`

Automatic runtime behavior:
1. Cloudflare V11 scheduler scans markets continuously;
2. only upstream `MARKET` / `MARKET_SIGNAL` may reach automatic V11 approval;
3. LIMIT/WATCH/MARKET_PLAN are never promoted into immediate MARKET;
4. new stored `APPROVED_SIGNAL` sends Telegram automatically;
5. TP / SL / EXPIRED lifecycle transition sends Telegram automatically;
6. duplicate OPEN market/symbol/side signals are blocked;
7. retained legacy non-market approvals are invalidated into history without resetting KV.

Telegram dashboard exposes LIVE, WATCH, market scans, V11 official signals, history, statistics and on-demand 3-AI MARKET hunter.

## V11 NATIVE SIGNAL FUNNEL

Primary files:
- `cloudflare-worker/v11/native-runtime.js`
- `cloudflare-worker/v11/entry-plan.js`
- `cloudflare-worker/v11/market-policies.js`
- `cloudflare-worker/v11/store.js`
- `cloudflare-worker/v11/manual-market-hunter.js`
- `cloudflare-worker/v11/ai-gateway.js`
- `cloudflare-worker/engine-v77168.js`
- `cloudflare-worker/hub-v11.js`

Hard behavior:
- real M5/M15/H1/H4/D1 ATR14 + close evidence;
- fresh provider timestamp required;
- deterministic structure/risk/quality gates;
- fail closed on stale/unverified evidence;
- `reason`, `gateReasons`, `planReason` remain distinct;
- XPL/executable crypto MARKET output retains timeframe evidence;
- native runtime reuses already-fresh run-now analysis before any unnecessary re-analysis.

## MANUAL THREE-AI HUNTER

Review-only and on-demand.
- DeepSeek: API-native when configured;
- Claude: VPC/VPS bridge;
- Codex: VPC/VPS bridge;
- all three required for positive consensus;
- any WAIT, error, unavailable provider, conflict or hard risk prevents a positive result;
- `automaticSignalAuthority = false`.

VPC service: `v11-ai-bridge`.
VPS systemd service: `v11-manual-ai-bridge`.

## TELEGRAM AUTOMATION

Automatic signal message includes:
- market + side + symbol;
- Entry / SL / TP / RR;
- quality;
- quote freshness/source;
- setup and concise WHY NOW;
- explicit SIGNAL ONLY notice.

Automatic lifecycle messages are emitted on TP / SL / EXPIRED.

WATCH remains informational and is available from Telegram/dashboard without being promoted to MARKET.

## CI / DEPLOYMENT

Production deploy workflow: `.github/workflows/deploy-cloudflare-worker.yml`.
Validation workflow: `.github/workflows/v11-signal-validation.yml` runs on `main` and checks V11 source, syntax, market-ready guard, auto Telegram signal/lifecycle hooks, duplicate prevention and three-AI fail-closed invariants.

Deployment preparation must preserve:
- existing `TRADING_STATE` KV;
- `AI_BRIDGE` VPC binding;
- `keep_vars:true`;
- minute V11 cron;
- `npm run check` before deploy.

## PERMANENT INVARIANTS

Never:
- reset `TRADING_STATE`;
- fabricate provider values, ATR, bid/ask, spread, P/L or execution state;
- weaken freshness, structural SL, RR or deterministic market gates merely to increase trade count;
- promote LIMIT/WATCH into MARKET;
- restore Futures Signal or Hyro/TK2 execution;
- merge Binance Auto execution authority into Signal V11;
- let AI review bypass deterministic gates;
- commit secrets/API tokens/private keys.

V73 remains an exposed-development prior, not untouched OOS proof. V76 Forex R2 remains research-only.

## NEXT PHASE

Infrastructure/plumbing is considered complete unless new runtime evidence proves otherwise.
Future work is evidence-driven signal-quality refinement:
- monitor funnel distributions and actual lifecycle outcomes;
- improve market-specific ranking/discrimination without weakening hard gates;
- verify provider freshness behavior during active market sessions;
- tune Telegram presentation only when it improves clarity and does not alter signal authority.

## STARTUP / HANDOFF ORDER

1. fresh-read GitHub `main`;
2. read `MASTER_TRADING_STATE.md`;
3. read `CURRENT_HANDOFF.md`;
4. read `SHARED_STATE.md`;
5. read `WRITE_LOCK.md`;
6. inspect current V11 source before any write.
