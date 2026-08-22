# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-22 UTC+7

## READ FIRST
1. fresh-read GitHub `main`;
2. `docs/checkpoints/MASTER_TRADING_STATE.md`;
3. this file;
4. `docs/ai-coengineer/SHARED_STATE.md`;
5. `docs/ai-coengineer/WRITE_LOCK.md`;
6. current V11 source files relevant to the task.

GitHub `main` outranks stale checkpoint/version wording.

## CURRENT CANONICAL STATE

Signal V11 is the sole public signal authority.

Current production contract:
- runtime: `CLOUDFLARE_NATIVE`;
- scheduler: `V11_NATIVE`;
- public signal authority: `V11_ONLY`;
- execution authority: `SIGNAL_ONLY`;
- manual whole-market hunter: enabled, review-only;
- legacy public signal endpoints: disabled;
- legacy engine role: internal data-adapter compatibility only;
- active markets: Forex, Crypto, Metal, Index Cash;
- Hyro execution is removed from active architecture;
- Binance Auto remains separate.

Checkpoint lineage includes source commit `e814802c6a0382c222e3541793892207ab7cfc9c` for the V11 funnel/hunter alignment. Later documentation synchronization commits may follow it; fresh-read source before assuming this is the current HEAD.

## WHAT WAS JUST FIXED

### 1. ATR / timeframe contract
`engine-v77168.js` now exposes real timeframe ATR14 + close metrics to V11 for M5/M15/H1/H4/D1.

Do not derive ATR from `riskATR` and do not fabricate missing volatility.

### 2. Native funnel normalization
`v11/native-runtime.js` consumes real timeframe ATR evidence when building structural entry plans.

### 3. Funnel diagnostics
`v11/store.js` now separates:
- effective `reason`;
- `gateReasons`;
- `planReason`.

This prevents a valid plan label such as `STRUCTURE_GEOMETRY_VALID` from masking the actual deterministic policy rejection.

### 4. Manual AI Hunter safety
`v11/manual-market-hunter.js` no longer turns `LIMIT_PLAN`, `MARKET_PLAN` or `WATCH` into an immediate MARKET candidate.

Only genuine upstream `MARKET` / `MARKET_SIGNAL` candidates may be reviewed for immediate MARKET suitability.

The hunter preserves upstream risk evidence and does not create a second conflicting entry/SL plan.

### 5. DeepSeek visibility
The hunter preserves DeepSeek provider status (`OK` / `ERROR` / `UNAVAILABLE`) instead of silently reducing a failed/unavailable DeepSeek review to `null`.

Three-AI positive consensus remains fail-closed: DeepSeek + Claude + Codex must all be healthy, aligned to the candidate direction and free of hard risk.

## VPC AI BRIDGE

Cloudflare Worker binding:
- binding: `AI_BRIDGE`;
- VPC service: `v11-ai-bridge`.

VPS bridge:
- systemd: `v11-manual-ai-bridge`;
- local health: `http://127.0.0.1:8789/health`;
- Claude: enabled;
- Codex: enabled;
- mode: on-demand only.

Last point-in-time runtime evidence showed bridge health PASS and systemd active/enabled.

## DEPLOYMENT

Worker: `trading-v77-scanner`.

Use:
`cd cloudflare-worker && npm run deploy`

The deploy path must run:
1. `npm run check`;
2. `prepare-wrangler.mjs`;
3. Wrangler deploy with generated `wrangler.jsonc`.

Generated config must retain:
- existing `TRADING_STATE` KV;
- `AI_BRIDGE` VPC binding;
- `keep_vars:true`;
- V11 native minute cron.

Cloudflare token needs sufficient Workers/KV permissions plus Connectivity Directory access needed to discover/bind `v11-ai-bridge`.

Never commit the Cloudflare API token.

## CURRENT FAIL-CLOSED BEHAVIOR

These are valid outcomes and must not be weakened merely to increase trade count:
- `WATCH`;
- `FORWARD_TARGET_RR_TOO_LOW`;
- quality gate rejection;
- stale/unverified quote rejection;
- `NO_MARKET_ENTRY`;
- `NO_3AI_CONSENSUS`.

Historical funnel rows may retain earlier errors. Diagnose current failures using newly-created rows/timestamps rather than treating old retained KV history as present runtime behavior.

## PERMANENT INVARIANTS

- V73 remains a frozen exposed-development prior, not untouched OOS proof.
- V76 Forex R2 remains research-only with 0/28 promoted.
- Never reset `TRADING_STATE`.
- Never fabricate ATR, quote, bid/ask, P/L or execution state.
- Never weaken structural SL, freshness or deterministic market-policy gates.
- Never restore Futures Signal.
- Never restore Hyro/TK2 execution into Signal V11.
- Never merge Binance Auto execution authority into Signal V11.
- Never let manual/AI review bypass deterministic gates.

## NEXT ENGINEERING WORK

The core V11 runtime repair is complete at this handoff. Next work should be incremental and evidence-driven:
- observe current V11 production funnel by market;
- investigate recurring *new* fresh-quote failures if they remain reproducible;
- improve market-specific candidate discrimination without weakening hard gates;
- validate DeepSeek provider health when a genuine upstream MARKET candidate reaches the manual hunter;
- maintain Telegram signal clarity and lifecycle correctness.

Do not resume old V78/V10 signal-authority methods when they conflict with current V11 source.

## NEW CHAT PROMPT

`Continue the Trading project from current GitHub main. Read MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, SHARED_STATE.md and WRITE_LOCK.md first. Signal V11 is the sole public signal authority and is SIGNAL_ONLY. Preserve TRADING_STATE, V11 native scheduler, VPC v11-ai-bridge, real timeframe ATR evidence, deterministic market gates and fail-closed three-AI review. Never promote LIMIT/WATCH into MARKET, never restore Hyro/Futures legacy execution, and fresh-read main before modifying source.`
