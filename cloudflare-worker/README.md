# Trading Cloudflare Worker

Current operational target: **V77.5.7**.

Worker currently used by the project: `trading-v77-scanner`.

## Runtime configuration

Cloudflare runtime Secrets:

- `TWELVE_DATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Cloudflare KV binding:

- binding name: `TRADING_STATE`
- bind it to the existing namespace `TRADING_V77_STATE`

Do not commit API keys or Telegram tokens to GitHub.

## Intended architecture

GitHub is the source/history layer. Cloudflare Worker is the single runtime. Telegram is the user-facing control/notification surface.

Discovery is on-demand from Telegram only:

- `FOREX` -> scan Forex
- `CRYPTO` -> scan canonical Crypto universe
- `METAL` -> scan XAUUSD + XAGUSD

Cron performs lifecycle/state checks only. It must not run background discovery scans.

## V77.5.7 data routing

- Forex/Metal: Twelve Data exact symbol mapping.
- Crypto: exact Binance USDT Spot first, exact OKX USDT Spot fallback.
- Never remap one token identity to another.
- Crypto quote target age <=10 seconds.
- Closed candles only.
- Futures and unsupported cash indices remain DATA_BLOCK unless an authoritative exact feed is added.

## Why Crypto/Metal previously looked broken

See `docs/checkpoints/CLOUDFLARE_TELEGRAM_V77_5_7.md`.

The important fixes are: canonical Crypto identities, Binance->OKX exact fallback, XAU/XAG always deep-checked when fresh, visible provider/deep errors in Telegram, and the broken Cron call replaced by the existing lifecycle function.

## Cloudflare Git integration

When Git deployment is enabled, set the Worker/Build root directory to the directory containing the active `wrangler.jsonc`. The Worker name in `wrangler.jsonc` must match the existing Cloudflare Worker name (`trading-v77-scanner`).

Do not activate `wrangler.example.jsonc` until its KV namespace ID has been replaced with the ID of the existing `TRADING_V77_STATE` namespace. Otherwise you risk deploying with a different/new KV namespace and losing continuity of the current order books/state.

After each deployment test:

- `/status`
- `/debug/routes`
- `/quote/BTCUSDT`
- `/run-now?group=crypto`
- `/run-now?group=metal`
- `/telegram/webhook-info`
- Telegram `CRYPTO` and `METAL` buttons
