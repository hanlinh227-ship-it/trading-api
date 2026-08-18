# UNIFIED RUNTIME V77.7.0

Updated: 2026-08-18 UTC+7
Status: canonical production-runtime shell over V73/V74/V75; V76 remains research-only.

## Purpose

V77.7.0 removes the accumulated V77.5/V77.6 patch-stack from production and replaces it with one GitHub-owned Cloudflare Worker entrypoint:

`cloudflare-worker/index.js`

Runtime topology:

`GitHub main -> Cloudflare Workers Builds -> trading-v77-scanner -> Twelve Data / exact crypto venues -> TRADING_V77_STATE KV -> Telegram`

GitHub is the only code source. Cloudflare must not keep a separately edited production logic once Git Builds is enabled.

## Canonical trading authority

- V73 remains frozen and is imported from `data/nocut_intraday_allpass_v73.json` at Worker build time.
- V74 remains live decision authority.
- V75 data-integrity rules remain in force.
- V76 R2 remains locked research-only, retained archetypes `[]`, promoted Forex `0/28`; V76 cannot authorize orders.
- Broad ranking is discovery only and cannot authorize MARKET/LIMIT.

V77.7.0 deep gate:

1. exact canonical symbol;
2. closed candles;
3. D1/H4/H1 directional alignment;
4. frozen V73 prior loaded where applicable;
5. M15 location = liquidity sweep/reclaim, breakout-retest, or clean EMA reclaim;
6. M5 MSS + >=0.50 ATR displacement + retest;
7. structural SL first;
8. H1 room >=1R;
9. RR1 default; RR2 only when room >=2.2R;
10. final execution-quality gate; estimated spread <=0.10R.

## Market-specific execution

### Forex

Twelve Data is analysis/reference data, not a fabricated broker quote. New Forex orders remain `WATCH / EXECUTION_QUOTE_REQUIRED` until a real broker/venue bid/ask feed is connected.

### Crypto

Twelve Data supplies standardized analysis candles. Exact execution confirmation routes Bybit -> OKX -> Binance. MARKET/LIMIT requires a fresh exact-venue bid/ask (target <=10s) and spread <=0.10R.

### Metal

XAUUSD/XAGUSD use Twelve Data for analysis/reference. New executable orders require a real broker/venue bid/ask feed; Twelve Data reference price alone cannot authorize MARKET/LIMIT.

## Data-budget design

Grow55 is used intentionally:

- Forex: all 28 pairs H1 broad + Top3 x D1/H4/H1/M15/M5 = about 43 Twelve Data credits.
- Crypto: 61 exact identities use exchange bulk discovery; 30 rotating symbols receive Twelve Data H1 enrichment + Top3 five-TF analysis = about 45 Twelve Data credits.
- Metal: both XAUUSD/XAGUSD deep-analyzed.
- KV run lock prevents overlapping manual scans from competing for the same credit minute.

## Telegram

Telegram is the only user-facing control/notification surface.

- FOREX / CRYPTO / METAL buttons start on-demand discovery.
- raw provider errors remain in `/run-now` diagnostics and Worker logs, not normal Telegram messages;
- WATCH displays canonical stage/reason, not legacy score;
- Cron handles lifecycle only: TP/SL and pending LIMIT fill/expiry;
- webhook supports `TELEGRAM_WEBHOOK_SECRET` verification when configured.

## State continuity

V77.7.0 keeps existing KV binding and book key:

- binding `TRADING_STATE`
- namespace `TRADING_V77_STATE`
- book key `v775:books`

Existing books are therefore readable after migration. Do not create a new namespace during Git deployment.

## Git / Cloudflare deployment

Production directory: `cloudflare-worker/`.

Files:

- `index.js` — canonical Worker source;
- `package.json` — Wrangler build/deploy package;
- `wrangler.example.jsonc` — template requiring the existing KV namespace ID;
- `README.md` — deployment and validation instructions.

Validator:

- `.github/workflows/validate-cloudflare-v77.yml`.

Cloudflare existing Worker must be connected under Settings -> Builds to repository `hanlinh227-ship-it/trading-api`, branch `main`, root directory `cloudflare-worker`.

The Worker name must remain exactly `trading-v77-scanner`.

Before activating Git deploy, copy the example Wrangler config to `wrangler.jsonc` and replace its KV placeholder with the **existing** `TRADING_V77_STATE` namespace ID. Do not allow automatic provisioning to create a new namespace.

## Required runtime secrets

- `TWELVE_DATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_WEBHOOK_SECRET` recommended

Secrets stay in Cloudflare, never GitHub.

## Post-deploy validation

1. `/status` = V77.7.0; KV online; V73 loaded.
2. `/run-now?group=forex` requests 28 pairs.
3. `/run-now?group=crypto` requests 61 identities.
4. `/run-now?group=metal` requests 2 symbols.
5. `/telegram/setup-webhook` then `/telegram/webhook-info`.
6. Telegram FOREX/CRYPTO/METAL each finishes with a result message.
7. Forex/Metal do not create new MARKET orders without execution venue bid/ask.
8. Crypto MARKET/LIMIT can only appear after exact venue execution verification.
