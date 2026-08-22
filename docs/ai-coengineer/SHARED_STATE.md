# AI SHARED STATE

Updated: 2026-08-22 UTC+7
Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`

## CURRENT ARCHITECTURE — SIGNAL V11 ONLY

Signal V11 is the sole public signal authority.

Current runtime contract:
- `publicSignalAuthority = V11_ONLY`;
- `executionAuthority = SIGNAL_ONLY`;
- Cloudflare-native runtime;
- V11-native scheduler;
- canonical markets: Forex, Crypto, Metal, Index Cash;
- Hyro execution removed from active architecture;
- legacy public signal routes disabled;
- legacy engine modules may remain only as internal data adapters;
- Binance Auto remains separate and must not inherit Signal V11 authority.

Current source checkpoint lineage includes `e814802c6a0382c222e3541793892207ab7cfc9c` (`fix(v11): align native signal funnel and manual market hunter`). Documentation synchronization commits follow it. Always fresh-read `main` before writing.

## V11 CORE REPAIRS — RESOLVED

### Real timeframe ATR contract
`cloudflare-worker/engine-v77168.js` exposes M5/M15/H1/H4/D1 ATR14 + close metrics to V11. Native candidate normalization uses real calculated ATR evidence.

Do not fabricate ATR and do not substitute `riskATR` for ATR.

### Funnel semantics
`cloudflare-worker/v11/store.js` keeps effective `reason`, `gateReasons` and `planReason` distinct so deterministic market-policy rejection is not hidden by an otherwise valid structure-plan label.

### Manual whole-market hunter
`cloudflare-worker/v11/manual-market-hunter.js` is review-only.

Hard rule: it must never promote `LIMIT_PLAN`, `MARKET_PLAN` or `WATCH` into immediate MARKET. Only genuine upstream `MARKET` / `MARKET_SIGNAL` candidates can enter the immediate-MARKET AI review pool.

The hunter must preserve upstream entry/SL/TP/RR evidence and must not manufacture a second conflicting risk plan.

### Three-AI review
- DeepSeek: API-native when configured;
- Claude: VPS/VPC bridge;
- Codex: VPS/VPC bridge;
- all three are required for positive manual-hunter consensus;
- any unavailable/error provider, WAIT, directional conflict or hard risk prevents positive consensus;
- manual hunter has no automatic signal/execution authority.

DeepSeek provider state must remain visible as `OK`, `ERROR` or `UNAVAILABLE`; do not silently collapse it to null.

## VPC MANUAL AI BRIDGE

Cloudflare binding: `AI_BRIDGE`.
VPC Service: `v11-ai-bridge`.
VPS service: `v11-manual-ai-bridge`.
Local health endpoint: `http://127.0.0.1:8789/health`.
Mode: on-demand only.

Last point-in-time validation showed:
- bridge health `ok:true`;
- Claude true;
- Codex true;
- systemd active;
- systemd enabled.

This is point-in-time evidence, not a permanent health guarantee.

## DEPLOYMENT CONTRACT

Worker: `trading-v77-scanner`.

Canonical deploy path:
`cloudflare-worker/npm run deploy`

`prepare-wrangler.mjs` must preserve:
- existing `TRADING_STATE` KV namespace;
- `AI_BRIDGE` VPC binding to `v11-ai-bridge`;
- `keep_vars:true`;
- minute V11 cron.

Do not bare-deploy without the generated config. Cloudflare credentials/tokens must never be committed.

## FAIL-CLOSED BEHAVIOR

Valid non-entry outcomes include:
- WATCH;
- RR/forward-target insufficiency;
- quality/policy rejection;
- stale/unverified quote rejection;
- `NO_MARKET_ENTRY`;
- `NO_3AI_CONSENSUS`.

Do not weaken deterministic gates merely to create more signals.

Historical funnel records remain retained in KV. Diagnose current behavior using new timestamps/rows rather than assuming old errors are still active.

## PERMANENT SAFETY / INTEGRITY CONSTRAINTS

- Never reset `TRADING_STATE`.
- Never fabricate provider values, ATR, bid/ask, spread, P/L, tests or deployment evidence.
- Never weaken quote freshness, structural SL or RR/market-policy hard gates.
- Never restore legacy Futures Signal.
- Never restore Hyro/TK2 execution into active Signal architecture.
- Never merge Binance Auto execution authority into V11.
- Never let AI review bypass deterministic signal gates.
- V73 remains a frozen exposed-development prior, not untouched OOS proof.
- V76 Forex R2 remains research-only with 0/28 promoted.

## AI CO-ENGINEERING

ChatGPT and Claude may co-engineer through GitHub under `WRITE_LOCK.md`.

Rules:
- fresh-read `main` before analysis/write;
- one writer at a time;
- current source outranks stale documents;
- preserve hard safety/data-integrity rules;
- do not write secrets.

## NEXT PRIORITIES

1. Observe current V11 production funnel per market using only newly-created rows.
2. Reproduce and diagnose any recurring fresh-quote failures before changing quote policy.
3. Improve market-specific ranking/discrimination without weakening hard gates.
4. Verify DeepSeek provider health when a genuine upstream MARKET candidate reaches manual AI review.
5. Keep Telegram output concise and lifecycle-safe.
6. Keep checkpoint/handoff docs synchronized whenever V11 authority changes.

Older V78/V10 architecture text is historical only when it conflicts with current Signal V11 source.
