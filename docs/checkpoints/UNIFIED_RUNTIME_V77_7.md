# UNIFIED RUNTIME V77.7.0

Updated: 2026-08-18 UTC+7
Status: canonical production runtime over V73/V74/V75; V76 remains research-only.

## Purpose

V77.7.0 removes the accumulated V77.5/V77.6 patch-stack from production and replaces it with one GitHub-owned Cloudflare Worker entrypoint:

`cloudflare-worker/index.js`

Runtime topology:

`GitHub main -> Cloudflare Workers Builds -> trading-v77-scanner -> Twelve Data / exact crypto venues -> TRADING_V77_STATE KV -> Telegram`

GitHub is the only code source. After Git Builds is enabled, do not maintain a separate hand-edited production logic in Cloudflare.

## Canonical authority

- V73 remains frozen and is imported directly from `data/nocut_intraday_allpass_v73.json` at Worker build time.
- V74 remains live decision authority.
- V75 data-integrity rules remain in force.
- V76 R2 remains locked research-only: retained archetypes `[]`, promoted Forex `0/28`.
- Broad ranking is discovery only; it never authorizes MARKET/LIMIT.

V77.7.0 deep gate:

1. exact canonical symbol;
2. closed candles only;
3. D1/H4/H1 directional alignment;
4. frozen V73 prior loaded where applicable;
5. M15 tradable location: liquidity sweep/reclaim, breakout-retest, or clean reclaim;
6. M5 MSS + >=0.50 ATR displacement + retest;
7. current news/context clearance;
8. structural SL first;
9. H1 room >=1R;
10. RR1 default; RR2 only when room >=2.2R;
11. final execution quote and estimated spread <=0.10R.

## News/context gate

Twelve Data does not supply a complete symbol-specific macro/crypto news feed suitable for replacing V74 current-news review. V77.7.0 therefore does not fabricate news clearance.

Default runtime behavior is strict:

- a setup that passes the technical stack stops at `WATCH / NEWS_CONTEXT_REQUIRED`;
- Telegram shows `✅ Tin OK <symbol>` only for such candidates;
- manual clearance is stored in KV for 30 minutes and then the symbol is rechecked through the remaining canonical gates;
- optional `NEWS_GATE_URL` can automate this later if a genuine current-news service is connected.

## Market-specific execution

### Forex

Twelve Data is analysis/reference data, not an executable broker quote. New Forex orders remain `WATCH / EXECUTION_QUOTE_REQUIRED` until a real broker/venue bid/ask feed is connected.

### Crypto

Twelve Data supplies standardized analysis candles. Exact execution confirmation routes Bybit -> OKX -> Binance. MARKET/LIMIT requires a fresh exact-venue bid/ask (target <=10s) and spread <=0.10R.

### Metal

XAUUSD/XAGUSD use Twelve Data for analysis/reference. New executable orders require a real broker/venue bid/ask feed; Twelve Data reference price alone cannot authorize MARKET/LIMIT.

## Twelve Data / Cloudflare budget

Grow55 is used intentionally while reducing Cloudflare external subrequests through Twelve Data batch requests:

- Forex: 28 H1 symbols in one batch + Top3 deep data in five timeframe batches = about 43 Twelve Data credits, but only six Twelve Data HTTP subrequests before any final quote.
- Crypto: 61 exact identities use exchange bulk discovery; 30 rotating symbols receive one Twelve Data H1 batch + Top3 receive five timeframe batches = about 45 Twelve Data credits.
- Metal: XAUUSD/XAGUSD use one H1 batch + five deep timeframe batches.
- Batch requests reduce HTTP subrequests but do not reduce Twelve Data credits per symbol.
- A shared KV run lock prevents overlapping manual scans from competing for the same Grow55 minute budget.

This design stays comfortably below the Cloudflare Workers Free external-subrequest ceiling in normal operation while still using nearly the full Grow55 analytical budget.

## Telegram

Telegram is the single user-facing control and notification surface.

- FOREX / CRYPTO / METAL buttons start on-demand discovery.
- raw provider failures remain in `/run-now` diagnostics and Worker logs, not normal Telegram messages;
- WATCH displays canonical stage/reason, never legacy score;
- news clearance is handled from Telegram for candidates that actually reach that gate;
- Cron handles lifecycle only: TP/SL and pending LIMIT fill/expiry;
- webhook supports `TELEGRAM_WEBHOOK_SECRET` verification when configured.

## State continuity

V77.7.0 keeps the existing state contract:

- binding `TRADING_STATE`
- existing namespace `TRADING_V77_STATE`
- book key `v775:books`

Existing books remain readable after migration. Do not create a new KV namespace during Git deployment.

## Git / Cloudflare deployment

Production directory: `cloudflare-worker/`.

Canonical files:

- `index.js` — production Worker source;
- `package.json` — Wrangler build/deploy package;
- `wrangler.example.jsonc` — deployment template requiring the existing KV namespace ID;
- `README.md` — deployment instructions;
- `.github/workflows/validate-cloudflare-v77.yml` — syntax/canonical-lock validator.

Cloudflare existing Worker must be connected under Settings -> Builds to repository `hanlinh227-ship-it/trading-api`, branch `main`, root directory `cloudflare-worker`.

Worker name must remain exactly `trading-v77-scanner`.

Before Git deploy is activated, copy the example Wrangler config to `wrangler.jsonc` and replace the KV placeholder with the **existing** `TRADING_V77_STATE` namespace ID. Do not let Wrangler automatic provisioning create a replacement namespace.

## Required Cloudflare secrets

- `TWELVE_DATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Recommended:

- `TELEGRAM_WEBHOOK_SECRET`

Optional future automation:

- `NEWS_GATE_URL`

Secrets stay in Cloudflare, never GitHub.

## Post-deploy validation

1. `/status` = V77.7.0; KV online; V73 loaded; strict news gate shown.
2. `/run-now?group=forex` requests 28 pairs.
3. `/run-now?group=crypto` requests 61 identities.
4. `/run-now?group=metal` requests 2 symbols.
5. `/telegram/setup-webhook` then `/telegram/webhook-info`.
6. Telegram FOREX/CRYPTO/METAL each returns a final result message.
7. Technical-ready candidates stop at `NEWS_CONTEXT_REQUIRED` until clearance.
8. Forex/Metal create no new executable order without broker execution bid/ask.
9. Crypto MARKET/LIMIT appears only after news clearance + exact venue execution verification.
