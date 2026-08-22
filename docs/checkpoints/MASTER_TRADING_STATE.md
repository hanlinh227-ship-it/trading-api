# MASTER TRADING STATE

Updated: 2026-08-22 UTC+7
Purpose: single canonical state for the Trading project.

## CURRENT CANONICAL VERSION — SIGNAL V11

GitHub `main` is authoritative. Current source-of-truth commit at this checkpoint lineage: `e814802c6a0382c222e3541793892207ab7cfc9c` (`fix(v11): align native signal funnel and manual market hunter`). If source advances beyond this commit, fresh-read `main` before making decisions.

Signal architecture is **V11 ONLY** for public signal authority.

Current production contract:
- `publicSignalAuthority = V11_ONLY`;
- runtime = `CLOUDFLARE_NATIVE`;
- scheduler = `V11_NATIVE`;
- execution authority = `SIGNAL_ONLY`;
- Hyro execution is removed from the active architecture;
- legacy public signal routes are disabled; legacy engine code is internal data-adapter compatibility only;
- canonical Signal markets: Forex, Crypto, Metal, Index Cash;
- Futures Signal remains removed;
- Binance Auto is a separate project and must not be merged into Signal V11 authority.

## V11 PRODUCTION TOPOLOGY

`GitHub main -> Cloudflare Worker trading-v77-scanner -> TRADING_STATE KV -> Telegram`

Additional on-demand AI review path:

`Cloudflare Worker -> VPC Service v11-ai-bridge -> VPS manual AI bridge -> Claude + Codex`

DeepSeek remains API-native through `cloudflare-worker/v11/ai-gateway.js` when its API secret is configured.

VPC bridge invariants:
- service name: `v11-ai-bridge`;
- local bridge health endpoint: `http://127.0.0.1:8789/health`;
- systemd service: `v11-manual-ai-bridge`;
- bridge is on-demand only;
- AI review is not automatic execution authority.

## V11 NATIVE SIGNAL FUNNEL

Primary files:
- `cloudflare-worker/v11/native-runtime.js`
- `cloudflare-worker/v11/entry-plan.js`
- `cloudflare-worker/v11/market-policies.js`
- `cloudflare-worker/v11/store.js`
- `cloudflare-worker/v11/manual-market-hunter.js`
- `cloudflare-worker/v11/ai-gateway.js`
- `cloudflare-worker/engine-v77168.js`

Current funnel behavior:
1. native market scan;
2. fresh symbol re-analysis;
3. canonical candidate normalization;
4. structural entry plan using real ATR/structure evidence;
5. market-specific deterministic policy gate;
6. only approved signals enter V11 accepted/lifecycle state;
7. manual whole-market AI hunter is a review-only second opinion and never creates execution authority.

### ATR contract repair

`deepAnalyze()` now exposes real calculated timeframe metrics in its payload:
- M5 ATR14 + close;
- M15 ATR14 + close;
- H1 ATR14 + close;
- H4 ATR14 + close;
- D1 ATR14 + close.

V11 normalizers consume these real ATR values. Do not substitute `riskATR` for ATR and do not fabricate ATR from plan risk.

Observed production validation after repair showed positive ATR values on representative Crypto, Metal and Forex symbols. Historical funnel rows containing `MISSING_SIDE_ENTRY_ATR` remain history and must not be treated as current failures merely because they are retained in KV.

### Funnel reason semantics

`recordV11()` now preserves deterministic rejection semantics separately:
- `reason` = effective rejection/watch reason;
- `gateReasons` = market-policy rejection reasons when present;
- `planReason` = entry-plan state such as `STRUCTURE_GEOMETRY_VALID`.

Never interpret `STRUCTURE_GEOMETRY_VALID` by itself as a rejection reason when `gateReasons` exists.

## MANUAL WHOLE-MARKET AI HUNTER

The manual hunter is review-only.

Hard rule: **never promote `LIMIT_PLAN`, `MARKET_PLAN` or `WATCH` into an immediate MARKET candidate.**

Only upstream statuses already considered market-ready (`MARKET` / `MARKET_SIGNAL`) may enter the immediate-MARKET AI review pool. The hunter must preserve upstream entry/SL/TP/RR evidence and must not create a conflicting second plan merely to obtain a MARKET candidate.

Three-AI review contract:
- DeepSeek: API-native when configured;
- Claude: VPS bridge;
- Codex: VPS bridge;
- all three must be healthy/aligned for a positive three-AI consensus;
- uncertainty or hard risk means WAIT;
- AI disagreement or unavailable provider never authorizes a trade;
- manual AI hunter has `automaticSignalAuthority = false`.

A result such as `NO_MARKET_ENTRY` or `NO_3AI_CONSENSUS` is valid fail-closed behavior and must not be weakened to increase trade count.

## MARKET DATA / EXECUTION INTEGRITY

Permanent rules:
1. exact canonical instrument identity;
2. fresh provider timestamps;
3. closed candles for technical calculations;
4. no fabricated bid/ask, spread, ATR, P/L or execution state;
5. analysis price is not automatically an executable quote;
6. stale data is never called live;
7. cash indices and futures are never interchangeable.

Market-specific rules:
- Crypto: exchange-native analysis/exact quote evidence where configured; fresh canonical evidence required for signal admission.
- Forex: Twelve Data analysis/reference; MT5/broker execution quote is required for real execution outside this signal-only architecture.
- Metal: Twelve Data analysis/reference; broker execution quote required for real execution outside this signal-only architecture.
- Index Cash: exact authoritative cash-index identity only; fail closed on identity/sanity failure.

## STATISTICAL / RESEARCH INVARIANTS

V73 remains a frozen exposed-development prior, **not untouched OOS proof**. Historical development win rates are descriptive only and never predictive probabilities.

V76 Forex R2 remains research-only with 0/28 promoted. It does not authorize live signals.

Do not retune historical methods after observing OOS and do not restore methods previously rejected simply to increase signal frequency.

## STATE SAFETY — HARD RULE

Never:
- reset `TRADING_STATE`;
- delete/reset `v775:books` without an explicit migration plan;
- fabricate financial data;
- weaken freshness, structural-SL, RR-quality or required context protections;
- restore legacy Futures Signal;
- restore Hyro/TK2 execution paths into the active Signal architecture;
- merge Binance Auto execution authority into Signal V11;
- commit secrets/API tokens/private keys.

## DEPLOYMENT CONTRACT

Worker: `trading-v77-scanner`.

Deployment preparation is generated by `cloudflare-worker/prepare-wrangler.mjs` and must preserve:
- existing `TRADING_STATE` KV namespace;
- VPC binding `AI_BRIDGE` -> `v11-ai-bridge`;
- `keep_vars: true`;
- V11 native cron `* * * * *`;
- deterministic `npm run check` before deployment.

Do not run an unprepared bare deploy when `wrangler.jsonc` has not been generated. Preferred path is `npm run deploy` with a Cloudflare token that can discover/bind the existing KV and Connectivity Directory VPC service.

## LAST VERIFIED RUNTIME EVIDENCE IN THIS CHECKPOINT

- V11 preflight: PASS.
- Cloudflare deployment with `TRADING_STATE` and `AI_BRIDGE` bindings: PASS.
- VPC bridge `/health`: `ok:true`, Claude true, Codex true, onDemandOnly true.
- systemd `v11-manual-ai-bridge`: active + enabled.
- post-repair funnel produced current reasons such as market-policy quality rejection and `FORWARD_TARGET_RR_TOO_LOW` instead of failing solely on missing ATR.
- manual AI hunter after market-readiness repair returned `NO_MARKET_ENTRY` when no genuine upstream MARKET candidate existed, rather than converting LIMIT plans into MARKET.

This evidence is point-in-time. Always fresh-check current source/runtime before claiming present health.

## STARTUP / HANDOFF ORDER

For a new session:
1. fresh-read GitHub `main`;
2. read `docs/checkpoints/MASTER_TRADING_STATE.md`;
3. read `docs/checkpoints/CURRENT_HANDOFF.md`;
4. read `docs/ai-coengineer/SHARED_STATE.md`;
5. read `docs/ai-coengineer/WRITE_LOCK.md`;
6. read `docs/ai-coengineer/OPEN_ISSUES.md` and `DECISIONS.md` when relevant;
7. inspect current V11 source before modifying anything.

## HANDOFF PHRASE

`Continue the Trading project from current GitHub main. Treat Signal V11 as the sole public signal authority. Preserve SIGNAL_ONLY execution authority, TRADING_STATE, V11 native scheduler, VPC manual AI bridge, real ATR/timeframe evidence, deterministic market-policy gates and fail-closed three-AI review. Never promote LIMIT/WATCH into MARKET, never restore legacy Futures/Hyro execution, never fabricate financial data, and fresh-read main before every write.`
