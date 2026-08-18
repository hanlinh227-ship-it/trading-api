# Trading Cloudflare Worker

Current production target: **V77.7.0**.

Worker name: `trading-v77-scanner`.

## Single-source architecture

`GitHub main -> Cloudflare Worker -> Twelve Data / exact crypto venues -> TRADING_V77_STATE KV -> Telegram`

GitHub is the canonical source. After Git Builds is connected, do not maintain a separate hand-edited production logic in Cloudflare.

## Runtime configuration

Required Cloudflare Secrets:

- `TWELVE_DATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Recommended:

- `TELEGRAM_WEBHOOK_SECRET`

Optional future automatic news service:

- `NEWS_GATE_URL`

Cloudflare KV binding:

- binding: `TRADING_STATE`
- existing namespace: `TRADING_V77_STATE`

Do not create a replacement KV namespace. V77.7.0 keeps the existing `v775:books` key so current books/state remain readable.

## Trading authority

- V73 frozen JSON is imported directly from `data/nocut_intraday_allpass_v73.json` at build time.
- V74 evidence order is implemented in the runtime gate.
- V76 R2 remains research-only and authorizes no order.
- Broad ranking is candidate discovery only; it cannot authorize MARKET/LIMIT.

Canonical progression:

`D1/H4/H1 -> V73 prior -> M15 location -> M5 MSS + displacement + retest -> current news/context -> structural risk/room -> final execution quote`

RR1 is default. RR2 requires >=2.2R clean room. Estimated spread must be <=0.10R.

### News/context

Twelve Data does not provide the complete live macro/crypto news layer required by V74. V77.7.0 therefore never fabricates clearance.

A setup that reaches this point becomes `WATCH / NEWS_CONTEXT_REQUIRED`. Telegram then exposes `✅ Tin OK <symbol>`. A manual clearance is valid for 30 minutes. If a real news service is connected later through `NEWS_GATE_URL`, this can be automated without changing the entry engine.

### Forex

Twelve Data is the analysis/reference feed. V77.7.0 does **not** fabricate broker bid/ask. Without a broker/venue execution quote, a qualified Forex setup remains `WATCH / EXECUTION_QUOTE_REQUIRED` rather than a new MARKET/LIMIT order.

### Crypto

Twelve Data provides standardized analysis candles. Exact execution confirmation uses Bybit, OKX, then Binance fallback. MARKET/LIMIT requires current news clearance plus a fresh exact-venue bid/ask and estimated spread <=0.10R.

### Metal

Twelve Data is the analysis/reference feed for XAUUSD/XAGUSD. As with Forex, new executable orders require an actual broker/venue bid/ask quote; Twelve Data reference price alone does not authorize MARKET/LIMIT.

## Twelve Data / Cloudflare efficiency

Twelve Data batch requests are used to maximize Grow55 while keeping Cloudflare subrequests low:

- Forex: all 28 H1 symbols in one batch; Top3 deep analysis uses five timeframe batches. Credits remain about 43 per on-demand scan.
- Crypto: 61 canonical identities use exchange bulk discovery; 30 rotating symbols receive one H1 Twelve Data batch; Top3 deep analysis uses five timeframe batches. Credits remain about 45 per scan.
- Metal: both XAUUSD/XAGUSD share one H1 batch and five deep timeframe batches.
- Batch requests reduce HTTP calls, not Twelve Data credits per symbol.
- A shared KV run lock prevents simultaneous manual scans from competing for the same Grow55 minute budget.

## Telegram

Telegram is the single user-facing control surface. Buttons trigger on-demand Forex/Crypto/Metal scans.

Normal Telegram output shows books, coverage and canonical WATCH stages. Raw provider errors stay in `/run-now` diagnostics and Worker logs and are not dumped into normal Telegram messages.

Webhook endpoints:

- `/telegram/setup-webhook`
- `/telegram/webhook-info`
- `/telegram/webhook`
- `/telegram/menu`

Cron is lifecycle-only: TP/SL plus pending LIMIT fill/expiry. Cron never starts discovery scans.

## Cloudflare Git integration

Connect the existing Worker under **Settings -> Builds**.

Use:

- repository: `hanlinh227-ship-it/trading-api`
- production branch: `main`
- root directory / Path: `cloudflare-worker`
- build command: empty
- deploy command: `npm run deploy`

In **Advanced settings**, add one encrypted build variable:

- variable name: `TRADING_KV_NAMESPACE_ID`
- variable value: the ID of the existing `TRADING_V77_STATE` namespace

`prepare-wrangler.mjs` validates that build variable and generates `wrangler.jsonc` only inside the Cloudflare build workspace immediately before deploy. The account-specific KV ID is therefore not committed to GitHub, and automatic KV provisioning is not used.

Keep Worker name exactly `trading-v77-scanner`. Keep runtime secrets in Cloudflare Worker Settings, never in GitHub or build logs.

Cloudflare treats Wrangler configuration as deployment source-of-truth. The generated config explicitly binds `TRADING_STATE` to the existing namespace, preserves dashboard variables with `keep_vars`, and keeps the one-minute lifecycle Cron.

## Post-deploy validation

- `/status` -> `V77.7.0`, V73 loaded, KV online, strict news gate.
- `/run-now?group=forex` -> 28 requested.
- `/run-now?group=crypto` -> 61 requested.
- `/run-now?group=metal` -> 2 requested.
- `/telegram/setup-webhook` then `/telegram/webhook-info`.
- Telegram FOREX / CRYPTO / METAL each finishes with a result message.
- Qualified technical candidates must stop at `NEWS_CONTEXT_REQUIRED` until clearance.
- Forex/Metal do not create new executable orders without broker bid/ask.
- Crypto MARKET/LIMIT can only appear after news clearance and exact venue execution confirmation.
