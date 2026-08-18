# Trading Cloudflare Worker

Current production target: **V77.7.0**.

Worker name: `trading-v77-scanner`.

## Single-source architecture

`GitHub main -> Cloudflare Worker -> Twelve Data / exact crypto venues -> KV -> Telegram`

GitHub is the canonical source. Do not maintain a separate hand-edited production logic in Cloudflare after Git Builds is connected.

## Runtime configuration

Cloudflare Secrets:

- `TWELVE_DATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_WEBHOOK_SECRET` (recommended; V77.7.0 verifies Telegram's secret header when configured)

Cloudflare KV binding:

- binding: `TRADING_STATE`
- existing namespace: `TRADING_V77_STATE`

Do not create a replacement KV namespace. V77.7.0 keeps the existing `v775:books` key so current books/state remain readable.

## Trading authority

- V73 frozen JSON is imported directly from `data/nocut_intraday_allpass_v73.json` at build time.
- V74 evidence order is implemented in the runtime gate: D1/H4/H1 alignment -> M15 tradable location -> M5 MSS/displacement/retest -> structural SL -> H1 room -> final execution-quality gate.
- V76 R2 remains research-only and authorizes no order.
- Broad scores rank candidates only; they cannot authorize MARKET/LIMIT.

### Forex

Twelve Data is the analysis/reference feed. V77.7.0 does **not** fabricate broker bid/ask. Without a broker/venue execution quote, a qualified Forex setup remains `WATCH / EXECUTION_QUOTE_REQUIRED` rather than a new MARKET order.

### Crypto

Twelve Data provides standardized analysis candles. Exact exchange execution confirmation uses Bybit, OKX, then Binance fallback. MARKET/LIMIT requires a fresh exact-venue bid/ask and estimated spread <= 0.10R.

### Metal

Twelve Data is the analysis/reference feed for XAUUSD/XAGUSD. As with Forex, new MARKET orders require an actual broker/venue execution quote; Twelve Data reference price alone does not authorize an executable order.

## Universe and Twelve Data budget

- Forex: all 28 pairs are broad-scanned on H1; Top3 receive D1/H4/H1/M15/M5 deep analysis. Approximate Twelve Data use is 43 credits per on-demand scan, inside Grow55 when no overlapping scan is running.
- Crypto: 61 canonical identities are covered by exchange bulk discovery; 30 symbols per scan receive rotating Twelve Data H1 enrichment; Top3 receive five-timeframe Twelve Data analysis. This uses roughly 45 Twelve Data credits plus exchange-native requests.
- Metal: XAUUSD and XAGUSD both receive full analysis.
- A shared KV run lock prevents simultaneous manual scans from competing for the same Grow55 minute budget.

## Telegram

Telegram is the single user-facing control surface. Buttons trigger on-demand Forex/Crypto/Metal scans. Raw provider errors stay in `/run-now` diagnostics and Worker logs; normal Telegram messages show books, WATCH stages, coverage and results without dumping provider error strings.

Webhook endpoints:

- `/telegram/setup-webhook`
- `/telegram/webhook-info`
- `/telegram/webhook`
- `/telegram/menu`

Cron is lifecycle-only; it handles TP/SL and pending LIMIT fills/expiry and never starts discovery scans.

## Cloudflare Git integration

Cloudflare supports connecting an existing Worker to GitHub under **Settings -> Builds**. Use repository `hanlinh227-ship-it/trading-api`, production branch `main`, and root directory `cloudflare-worker`.

Before enabling automatic deploys:

1. Copy `wrangler.example.jsonc` to `wrangler.jsonc`.
2. Replace `REPLACE_WITH_EXISTING_TRADING_V77_STATE_NAMESPACE_ID` with the ID of the existing `TRADING_V77_STATE` namespace.
3. Keep Worker name exactly `trading-v77-scanner`.
4. Keep the four runtime secrets in Cloudflare, not GitHub.
5. Build command can be empty; deploy command is `npx wrangler deploy`.

Cloudflare treats Wrangler configuration as deployment source-of-truth. Never enable the template with the placeholder KV ID, because automatic provisioning could create a different namespace.

## Post-deploy validation

- `/status` -> `V77.7.0`, V73 loaded, KV online.
- `/run-now?group=forex` -> 28 requested; new executable Forex orders should not be created without a broker execution feed.
- `/run-now?group=crypto` -> 61 requested; Top3 canonical deep gate.
- `/run-now?group=metal` -> 2 requested.
- `/telegram/setup-webhook` then `/telegram/webhook-info`.
- Telegram FOREX / CRYPTO / METAL buttons all return a final message instead of remaining at `Đang quét...`.
