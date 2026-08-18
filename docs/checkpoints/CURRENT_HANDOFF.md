# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

Read in this order:
1. `MASTER_TRADING_STATE.md`
2. `UNIFIED_RUNTIME_V77_7.md`
3. `ENTRY_EXECUTION_V76.md`
4. relevant market checkpoint.

## CURRENT MODE

- **V73** = frozen no-CUT statistical prior. Never rebuild/optimize during live use.
- **V74** = live-analysis / execution authority.
- **V75 Fast Data** = canonical data-integrity / collection layer.
- **V76 R2** = locked Forex entry research with negative live-promotion result: retained archetypes `[]`, promoted symbols `0/28`; research-only.
- **V77.7.0** = unified GitHub-owned Cloudflare/Telegram production runtime shell implementing the V74 evidence stack over current data routing. It does not rewrite V73 or promote V76.

## SINGLE PRODUCTION RUNTIME

Canonical production source:

- `cloudflare-worker/index.js`
- `cloudflare-worker/package.json`
- `cloudflare-worker/wrangler.example.jsonc`
- `.github/workflows/validate-cloudflare-v77.yml`
- `docs/checkpoints/UNIFIED_RUNTIME_V77_7.md`

Target topology:

`GitHub main -> Cloudflare Workers Builds -> trading-v77-scanner -> Twelve Data / exact crypto venues -> TRADING_V77_STATE KV -> Telegram`

GitHub is the source of truth. After Git Builds is connected, do not hand-edit a different production logic in the Cloudflare editor.

## V77.7.0 ENTRY AUTHORITY

Broad ranking is discovery only. It cannot authorize a live order.

Deep gate order:
1. exact canonical symbol;
2. closed candles;
3. D1/H4/H1 alignment;
4. frozen V73 prior loaded where applicable;
5. M15 tradable location: liquidity sweep/reclaim, breakout-retest or clean reclaim;
6. M5 MSS + >=0.50 ATR displacement + retest;
7. structural SL first;
8. H1 clean room >=1R;
9. RR1 default; RR2 only when room >=2.2R;
10. final execution quality; spread estimate <=0.10R.

### Forex

Twelve Data is analysis/reference data. It is not a fabricated broker bid/ask. Until a real broker/venue execution feed is connected, a qualified Forex setup remains `WATCH / EXECUTION_QUOTE_REQUIRED`; V77.7.0 does not create a new executable Forex MARKET/LIMIT from Twelve Data reference price alone.

### Crypto

Twelve Data supplies standardized analysis candles. Exact execution confirmation routes Bybit -> OKX -> Binance. New MARKET/LIMIT requires fresh exact venue bid/ask (target <=10s) and spread <=0.10R.

### Metal

XAUUSD/XAGUSD use Twelve Data analysis/reference data. New executable orders require a real broker/venue bid/ask feed; otherwise the setup remains WATCH.

## DATA BUDGET

Twelve Data Grow55 is budgeted deliberately:

- Forex: 28 H1 broad + Top3 x 5TF deep ~=43 credits per on-demand scan.
- Crypto: 61 exchange-bulk identities + 30 rotating Twelve Data H1 enrichment + Top3 x 5TF deep ~=45 Twelve Data credits.
- Metal: both XAUUSD and XAGUSD analyzed.
- Shared KV run lock prevents overlapping Telegram scans from competing for the same minute budget.

Twelve Data provider timestamps are never replaced with fetch time. Closed candles are used for technical calculations. Twelve Data bid/ask is never fabricated.

## STATE / TELEGRAM

Existing state continuity is preserved:

- KV binding `TRADING_STATE` -> existing namespace `TRADING_V77_STATE`;
- book key remains `v775:books` so existing books remain readable during migration.

Telegram is the only user-facing control surface:

- FOREX / CRYPTO / METAL = on-demand discovery;
- WATCH displays canonical stage/reason instead of legacy score;
- raw provider failures remain in `/run-now` diagnostics and Worker logs, not normal Telegram messages;
- Cron performs lifecycle only: TP/SL and pending LIMIT fill/expiry;
- `TELEGRAM_WEBHOOK_SECRET` is supported and recommended.

## V76 R2 — STILL LOCKED

Research run `32053656572` remains the final V76 R2 result:

- 28 Forex pairs;
- six objective families A–F;
- 72 entry/stop/RR variants;
- chronological DEV / validation / untouched OOS;
- retained global archetypes: NONE;
- promoted symbols: 0/28;
- all 28 methods = `RESEARCH_ONLY`.

Do not retune V76 R2 from its OOS result and do not let it authorize live orders.

## DATA INTEGRITY LOCK

Rules remain:
1. exact canonical identity;
2. exact provider symbol/type metadata;
3. closed candles for technical calculations;
4. provider timestamp != fetch time;
5. aggregated/reference price != executable quote;
6. no fabricated bid/ask/spread;
7. cash/futures/spot never interchangeable.

Cash NAS100/US500/DAX/N225-family and exact NQ/MNQ/ES/MES/GC/SI/CL remain `DATA_BLOCK` until authoritative exact feeds exist.

## CLOUDFLARE MIGRATION REQUIREMENT

Before Git Builds is activated, the existing `TRADING_V77_STATE` KV namespace ID must be copied into an active `cloudflare-worker/wrangler.jsonc` based on `wrangler.example.jsonc`. Do **not** deploy the placeholder or allow a new KV namespace to replace the existing state.

Cloudflare runtime secrets:

- `TWELVE_DATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_WEBHOOK_SECRET` recommended

Worker name must remain exactly `trading-v77-scanner`.

## POST-DEPLOY VALIDATION

1. `/status` reports V77.7.0, KV online and V73 loaded.
2. Forex requests 28 symbols.
3. Crypto requests 61 identities.
4. Metal requests 2 symbols.
5. `/telegram/setup-webhook` then `/telegram/webhook-info` succeeds.
6. Telegram FOREX / CRYPTO / METAL each returns a final result.
7. Forex/Metal create no new executable order without broker execution bid/ask.
8. Crypto MARKET/LIMIT appears only after exact venue execution verification.

## NEW CHAT INSTRUCTION

`Continue Trading from MASTER_TRADING_STATE.md + UNIFIED_RUNTIME_V77_7.md + CURRENT_HANDOFF.md. Current state = V73 frozen prior + V74 live authority + V75 data integrity + V76 R2 locked research-only + V77.7.0 unified GitHub/Cloudflare/Telegram runtime. GitHub cloudflare-worker/index.js is the only production code source. Broad ranking is discovery only. Require D1/H4/H1, V73 prior where applicable, M15 location, strict M5 MSS/displacement/retest, structural SL, clean room and final execution quote. Twelve Data Forex/Metal reference prices do not authorize executable MARKET/LIMIT without broker bid/ask. Crypto execution requires exact Bybit/OKX/Binance quote. Never proxy cash/futures, fabricate spread, or restore legacy V77 scoring authority.`
