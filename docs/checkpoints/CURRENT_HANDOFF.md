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
- **V77.7.0** = unified GitHub-owned Cloudflare/Twelve Data/Telegram production runtime implementing the V74 evidence stack without rewriting V73 or promoting V76.

## SINGLE PRODUCTION RUNTIME

Canonical production source:

- `cloudflare-worker/index.js`
- `cloudflare-worker/package.json`
- `cloudflare-worker/wrangler.example.jsonc`
- `.github/workflows/validate-cloudflare-v77.yml`
- `docs/checkpoints/UNIFIED_RUNTIME_V77_7.md`

Topology:

`GitHub main -> Cloudflare Workers Builds -> trading-v77-scanner -> Twelve Data / exact crypto venues -> TRADING_V77_STATE KV -> Telegram`

GitHub is the source of truth. Once Git Builds is connected, do not hand-edit a different production logic in Cloudflare.

## V77.7.0 CANONICAL ENTRY GATE

Broad ranking is discovery only. It cannot authorize an order.

Deep gate:
1. exact canonical symbol;
2. closed candles only;
3. D1/H4/H1 alignment;
4. frozen V73 prior loaded where applicable;
5. M15 tradable location: liquidity sweep/reclaim, breakout-retest, or clean reclaim;
6. M5 MSS + >=0.50 ATR displacement + retest;
7. current news/context clearance;
8. structural SL first;
9. H1 clean room >=1R;
10. RR1 default; RR2 only when room >=2.2R;
11. final execution quality; estimated spread <=0.10R.

## NEWS / CONTEXT

Twelve Data does not provide a complete current macro/crypto news feed suitable for replacing the V74 news gate. V77.7.0 therefore never fabricates clearance.

- Technical-ready setups stop at `WATCH / NEWS_CONTEXT_REQUIRED`.
- Telegram shows `✅ Tin OK <symbol>` only when a candidate reaches this stage.
- Manual clearance is stored in KV for 30 minutes, then the symbol is rechecked through the remaining gates.
- Optional `NEWS_GATE_URL` can automate this later if a real current-news service is connected.

## MARKET-SPECIFIC EXECUTION

### Forex

Twelve Data is analysis/reference data, not an executable broker quote. Until a real broker/venue bid/ask feed is connected, a qualified setup remains `WATCH / EXECUTION_QUOTE_REQUIRED`; no new Forex MARKET/LIMIT may be created from Twelve Data reference price alone.

### Crypto

Twelve Data supplies standardized analysis candles. Exact execution confirmation routes Bybit -> OKX -> Binance. New MARKET/LIMIT requires current news clearance plus fresh exact venue bid/ask (target <=10s) and spread <=0.10R.

### Metal

XAUUSD/XAGUSD use Twelve Data for analysis/reference. New executable orders require a real broker/venue bid/ask feed; otherwise the setup remains WATCH.

## DATA / SUBREQUEST BUDGET

Twelve Data Grow55 is budgeted deliberately and batch requests are used to minimize Cloudflare subrequests without pretending that batch lowers API credits:

- Forex: 28 H1 pairs in one batch + Top3 deep data in five timeframe batches ~=43 Twelve Data credits.
- Crypto: 61 exchange-bulk identities + 30 rotating Twelve Data H1 symbols in one batch + Top3 deep data in five timeframe batches ~=45 Twelve Data credits.
- Metal: XAUUSD/XAGUSD share one H1 batch and five deep timeframe batches.
- Shared KV run lock prevents overlapping Telegram scans from competing for the same minute budget.

Twelve Data provider timestamps are never replaced with fetch time. Closed candles are used for technical calculations. Twelve Data bid/ask is never fabricated.

## STATE / TELEGRAM

State continuity is preserved:

- KV binding `TRADING_STATE` -> existing namespace `TRADING_V77_STATE`;
- book key remains `v775:books` so existing books remain readable during migration.

Telegram is the only user-facing control surface:

- FOREX / CRYPTO / METAL = on-demand discovery;
- WATCH displays canonical stage/reason, never legacy score;
- news clearance happens in Telegram only for candidates that reach that gate;
- raw provider failures remain in `/run-now` diagnostics and Worker logs, not normal Telegram messages;
- Cron performs lifecycle only: TP/SL and pending LIMIT fill/expiry;
- `TELEGRAM_WEBHOOK_SECRET` is supported and recommended.

## V76 R2 — STILL LOCKED

Final V76 R2 remains:

- 28 Forex pairs;
- six objective families A–F;
- 72 variants;
- chronological DEV / validation / untouched OOS;
- retained global archetypes: NONE;
- promoted symbols: 0/28;
- all 28 methods = `RESEARCH_ONLY`.

Do not retune V76 R2 from OOS and do not let it authorize live orders.

## DATA INTEGRITY LOCK

1. exact canonical identity;
2. exact provider symbol/type metadata;
3. closed candles for technical calculations;
4. provider timestamp != fetch time;
5. aggregated/reference price != executable quote;
6. no fabricated bid/ask/spread;
7. cash/futures/spot never interchangeable.

Cash NAS100/US500/DAX/N225-family and exact NQ/MNQ/ES/MES/GC/SI/CL remain `DATA_BLOCK` until authoritative exact feeds exist.

## CLOUDFLARE MIGRATION REQUIREMENT

Before Git Builds is activated, the existing `TRADING_V77_STATE` KV namespace ID must be copied into an active `cloudflare-worker/wrangler.jsonc` based on `wrangler.example.jsonc`.

Do **not** deploy the placeholder and do not allow Wrangler automatic provisioning to create a replacement namespace.

Required Cloudflare secrets:

- `TWELVE_DATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Recommended:

- `TELEGRAM_WEBHOOK_SECRET`

Optional:

- `NEWS_GATE_URL`

Worker name must remain exactly `trading-v77-scanner`.

## POST-DEPLOY VALIDATION

1. `/status` reports V77.7.0, KV online, V73 loaded and strict news gate.
2. Forex requests 28 symbols.
3. Crypto requests 61 identities.
4. Metal requests 2 symbols.
5. `/telegram/setup-webhook` then `/telegram/webhook-info` succeeds.
6. Telegram FOREX / CRYPTO / METAL each returns a final result.
7. Technical-ready candidates stop at `NEWS_CONTEXT_REQUIRED` until clearance.
8. Forex/Metal create no new executable order without broker execution bid/ask.
9. Crypto MARKET/LIMIT appears only after news clearance + exact venue execution verification.

## NEW CHAT INSTRUCTION

`Continue Trading from MASTER_TRADING_STATE.md + UNIFIED_RUNTIME_V77_7.md + CURRENT_HANDOFF.md. Current state = V73 frozen prior + V74 live authority + V75 data integrity + V76 R2 locked research-only + V77.7.0 unified GitHub/Cloudflare/Twelve Data/Telegram runtime. GitHub cloudflare-worker/index.js is the only production code source. Twelve Data batch is used to maximize Grow55 while controlling Cloudflare subrequests. Broad ranking is discovery only. Require D1/H4/H1, V73 prior where applicable, M15 location, strict M5 MSS/displacement/retest, current news/context clearance, structural SL, clean room and final execution quote. Twelve Data Forex/Metal reference prices never authorize executable MARKET/LIMIT without broker bid/ask. Crypto execution requires exact Bybit/OKX/Binance quote. Never proxy cash/futures, fabricate spread, bypass the news gate, or restore legacy V77 scoring authority.`
