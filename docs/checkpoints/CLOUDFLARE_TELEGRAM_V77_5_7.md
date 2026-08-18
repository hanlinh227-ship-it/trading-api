# CLOUDFLARE / TELEGRAM V77.5.7

Updated: 2026-08-18 UTC+7
Status: operational shell fix after V77.5.6 handoff. This checkpoint does NOT replace V73/V74/V75/V76 canonical trading authority.

## Root causes found

1. V77.5.6 Crypto universe did not match the canonical V74/V75 61-token identity set. Several canonical tokens were missing while unrelated symbols were present.
2. Crypto data depended on Binance Spot only. An exact canonical token unavailable on Binance could therefore look like “coin not found” even when an exact USDT spot instrument existed on OKX.
3. `v775BuildCandidates()` promoted only broad-directional symbols. For Metal, XAUUSD/XAGUSD could both be fresh but neutral in the broad 24h heuristic, producing zero deep analyses and making the METAL button look broken.
4. Deep-analysis exceptions were swallowed with `catch {}`. Telegram could report 0 analyzed / 0 new without showing the actual provider or symbol error.
5. Cron called `v775CheckGroupPositions(...)`, but that function does not exist in V77.5.6. The exception was caught by the Cron wrapper, so the Worker stayed online while lifecycle management failed silently every scheduled run.
6. V77.5.6 still exposed stale internal version labels (`V77.5.5`) and RR2 room threshold 2.0R instead of the V74 canonical >=2.2R clean-room rule.

## V77.5.7 operational fixes

- Runtime label: `V77.5.7`.
- Crypto universe aligned to the canonical 61 identities from V74.
- Crypto market data routing: exact Binance USDT spot first; exact OKX USDT spot fallback. Never remap one token to another.
- Crypto quote freshness target: <=10 seconds.
- Binance candles: closed candles only.
- OKX candles: `confirm=1` only.
- Metal discovery: always deep-check every fresh exact XAUUSD/XAGUSD candidate; broad score is discovery only and may not hide the market.
- Crypto discovery: when broad direction is neutral, fill unused deep slots from the strongest fresh exact symbols so the market still returns WATCH/NO_ENTRY/ERROR instead of looking missing.
- Telegram diagnostics now expose broad errors, deep errors, provider/source and per-symbol outcomes.
- Cron lifecycle call corrected to the existing `v775ManageGroup(...)` function.
- RR2 room threshold changed from 2.0R to 2.2R.

## Canonical safety lock

V73 remains frozen. V74 remains live-analysis/execution authority. V75 remains the fast-data layer. V76 R2 remains locked research-only with zero promoted Forex symbols.

V77.5.7 is an operational Telegram/Cloudflare/data-routing repair. Its legacy `deepAnalyze()` scoring is not allowed to become a new canonical authority merely because this shell is operational. The next entry-engine task is still to replace the legacy V77 scoring authority with a V74-compliant `canonicalEntryGate()`.

## Cloudflare runtime requirements

Worker name currently used by the project: `trading-v77-scanner`.

Runtime secrets:
- `TWELVE_DATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

KV binding:
- binding: `TRADING_STATE`
- namespace: existing `TRADING_V77_STATE`

Discovery remains Telegram on-demand:
- FOREX button -> Forex scan
- CRYPTO button -> Crypto scan
- METAL button -> XAUUSD/XAGUSD scan

Cron performs lifecycle/state management only; it must not start background discovery scans.

## Required post-deploy checks

1. `/status` reports V77.5.7, KV online, Telegram configured and Crypto provider `Binance exact spot + OKX exact spot fallback`.
2. `/quote/BTCUSDT` returns a fresh exact Binance/OKX quote.
3. Test at least one canonical token missing from Binance but present on OKX; it must resolve exact instrument or return an explicit exact-instrument error.
4. `/run-now?group=metal` must scan exactly XAUUSD and XAGUSD and report provider errors explicitly if either fails.
5. Telegram CRYPTO/METAL buttons must return `broad OK / fresh / deep` diagnostics and no longer silently show zero because an exception was swallowed.
6. Cron logs must not contain `v775CheckGroupPositions is not defined`.
