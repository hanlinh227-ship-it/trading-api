# Trading Cloudflare Worker

Current production target: **V77.8.0 Unified Canonical Hub**.

Worker: `trading-v77-scanner`.

## Single-source architecture

`GitHub main -> Cloudflare Builds -> Worker -> Twelve Data / exact crypto venues -> TRADING_V77_STATE KV -> Telegram Hub`

GitHub is the only production code source. Do not hand-edit a different Worker implementation in Cloudflare after Git Builds is connected.

## Canonical authority

- V73 = frozen prior, imported from `data/nocut_intraday_allpass_v73.json`.
- V74 = live analysis/execution authority.
- V75 = data-integrity rules.
- V76 R2 = research-only; retained `[]`, promoted Forex `0/28`; it authorizes no live order.
- V77.8.0 = runtime/Telegram Hub only; broad ranking is discovery, never execution authority.

Canonical gate:

`exact identity -> closed/fresh data -> D1/H4/H1 -> V73 prior -> M15 location -> M5 MSS + >=0.50 ATR displacement + retest -> current news/context -> structural SL -> clean room -> final execution quote/cost`

RR1 is default. RR2 requires >=2.2R clean room. Estimated execution cost must be <=0.10R.

## Market routing

### Crypto

Crypto is now exchange-native for both deep analysis and execution. Broad discovery uses exact spot instruments from Bybit / OKX / Binance. Each Top candidate must obtain D1/H4/H1/M15/M5 closed candles and the final bid/ask from one exact venue before it can create MARKET/LIMIT. If no venue can provide the exact instrument plus sufficient five-timeframe history, the candidate is DATA_BLOCK/WATCH rather than remapped.

Crypto no longer consumes Twelve Data credits for normal universe/deep scans.

### Forex

Twelve Data Grow55 supplies H1 broad + D1/H4/M15/M5 deep data. H1 broad is reused in deep analysis, so a full 28-pair scan plans roughly 40 credits instead of refetching H1. Twelve Data reference price is not fabricated into broker bid/ask; a fully qualified Forex setup stops at `EXECUTION_QUOTE_REQUIRED` until a real broker execution feed is connected.

### Metal

XAUUSD/XAGUSD use Twelve Data analysis. H1 broad is reused, so the two-symbol full scan plans roughly 10 credits. New executable Metal orders also require a real broker/venue bid/ask feed.

## Telegram Hub

Telegram is the primary user interface.

Buttons:

- `🧭 HUB TOP SETUPS` scans Crypto -> Forex -> Metal and ranks the best canonical stages.
- `💱 FOREX`, `🪙 CRYPTO`, `🥇 METAL` scan one market.
- `📊 STATUS` shows runtime state.
- `📚 BOOKS` shows current books.
- `✅ Tin OK <symbol>` appears only for a setup that reached `NEWS_CONTEXT_REQUIRED`.

WATCH messages show the exact canonical stage. When a setup has already reached the news/execution portion of the gate, Telegram also shows indicative planned Entry/SL/TP. MARKET/LIMIT appears only after every required gate passes.

Manual news clearance is valid for 30 minutes. Optional `NEWS_GATE_URL` can automate that step later without weakening the entry engine.

## Twelve Data budget guard

Before Forex/Metal scans the Worker reads current minute quota. If remaining credits are insufficient, it returns `RATE_BUDGET_WAIT` instead of overspending and producing partial DATA_BLOCK results. The Hub budget is designed so Forex (~40) + Metal (~10) remains inside Grow55 with headroom for quota checks.

## State / lifecycle

Existing KV continuity is preserved:

- binding `TRADING_STATE`
- existing namespace `TRADING_V77_STATE`
- book key `v775:books`

Cron is lifecycle-only. Because Crypto has exact execution quotes, V77.8.0 automatically manages Crypto pending LIMIT fills and Crypto TP/SL. Forex/Metal are analysis-only until a broker execution feed is connected, so Twelve Data reference prices are not used to auto-close executable positions.

## Cloudflare runtime configuration

Required Worker secrets:

- `TWELVE_DATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Recommended:

- `TELEGRAM_WEBHOOK_SECRET`

Optional:

- `NEWS_GATE_URL`

Cloudflare Build configuration remains:

- repository `hanlinh227-ship-it/trading-api`
- branch `main`
- Path `cloudflare-worker`
- deploy command `npm run deploy`
- encrypted build variable `TRADING_KV_NAMESPACE_ID` = existing `TRADING_V77_STATE` namespace ID

`prepare-wrangler.mjs` generates account-specific `wrangler.jsonc` only in the build workspace. Do not commit secrets or create a replacement KV namespace.

## Validation

GitHub workflow `.github/workflows/validate-cloudflare-v77.yml` syntax-checks the Worker, verifies V77.8 canonical locks and runs a Wrangler dry-run.

Post-deploy checks:

- `/status` -> V77.8.0, KV/Twelve Data/Telegram configured, Hub enabled.
- `/hub` -> unified result across all three markets.
- `/run-now?group=crypto` -> 61 canonical identities, exact exchange-native deep analysis.
- `/run-now?group=forex` -> 28 pairs.
- `/run-now?group=metal` -> XAUUSD/XAGUSD.
- `/telegram/setup-webhook` and `/telegram/webhook-info` -> webhook healthy.
- Telegram `🧭 HUB TOP SETUPS` -> final Hub message, never stuck on scanning.
