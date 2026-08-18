# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-18 UTC+7

Read in this order:
1. `MASTER_TRADING_STATE.md`
2. `UNIFIED_RUNTIME_V77_8.md`
3. `ENTRY_EXECUTION_V76.md`
4. relevant market checkpoint.

## CURRENT MODE

- **V73** = frozen statistical prior. Never rebuild or retune during live use.
- **V74** = live analysis/execution authority.
- **V75** = data-integrity / fast collection layer.
- **V76 R2** = locked research-only result; retained archetypes `[]`, promoted Forex `0/28`; it authorizes no live order.
- **V77.8.0** = unified GitHub-owned Cloudflare/Twelve Data/exchange/Telegram Hub runtime. It is a runtime shell over V73/V74/V75 and does not revive rejected legacy scoring.

## SINGLE PRODUCTION TOPOLOGY

`GitHub main -> Cloudflare Builds -> trading-v77-scanner -> Twelve Data / exact crypto venues -> TRADING_V77_STATE -> Telegram Hub`

Canonical production source is `cloudflare-worker/index.js`. Cloudflare is a deployment target, not a second hand-edited codebase.

## ENTRY AUTHORITY

Broad ranking is discovery only.

Canonical gate:
1. exact canonical identity;
2. fresh/closed data;
3. D1/H4/H1 directional structure;
4. frozen V73 prior where applicable;
5. M15 tradable location;
6. strict M5 MSS + >=0.50 ATR displacement + retest;
7. structural SL first;
8. clean room >=1R;
9. RR1 default; RR2 only if room >=2.2R;
10. current news/context;
11. final execution quote and estimated cost <=0.10R before executable order.

## MARKET ROUTING

### Crypto

Crypto deep analysis is exchange-native. The runtime scans the 61 canonical identities against exact Bybit/OKX/Binance spot instruments, then Top candidates must obtain closed D1/H4/H1/M15/M5 candles and final bid/ask from one exact venue. No token remapping is allowed. Normal Crypto scanning uses no Twelve Data credits.

Only Crypto currently has an executable venue feed, so only Crypto may create new MARKET/LIMIT orders after every gate passes.

### Forex

Twelve Data provides 28-pair H1 broad data plus Top3 D1/H4/M15/M5 deep data; the H1 broad candle set is reused in deep analysis. Planned budget is about 40 Grow55 credits per scan. Twelve Data reference price is not broker bid/ask, so a qualified Forex setup stops at `EXECUTION_QUOTE_REQUIRED` until a real broker execution feed is connected.

### Metal

XAUUSD/XAGUSD use Twelve Data H1 broad plus deep D1/H4/M15/M5 with H1 reuse, about 10 Grow55 credits. New Metal executable orders also require a real broker/venue bid/ask feed.

## TELEGRAM HUB

Telegram is the primary interface.

- `🧭 HUB TOP SETUPS` scans Crypto -> Forex -> Metal and ranks the strongest canonical stages.
- Individual FOREX / CRYPTO / METAL buttons remain available.
- WATCH reports the exact missing gate, not a legacy score.
- Setups that reached the news/execution portion include indicative planned Entry/SL/TP.
- `✅ Tin OK <symbol>` records a 30-minute manual news/context clearance.
- `NEWS_GATE_URL` is optional for future automated news clearance.
- `📚 BOOKS` shows current order/watch state.

MARKET/LIMIT must never be shown as a new signal merely because broad/technical scoring is high.

## QUOTA / RUNTIME SAFETY

- Crypto universe/deep scans are exchange-native and do not consume Grow55 credits.
- Forex planned cost ~=40 credits.
- Metal planned cost ~=10 credits.
- Before non-Crypto scans, the Worker checks current Twelve Data quota and returns `RATE_BUDGET_WAIT` instead of overspending.
- Shared KV run lock blocks overlapping manual scans.
- All external providers use hard fetch timeouts.
- Cron is lifecycle-only and does not start discovery scans.
- Crypto exact-exchange positions may be auto-managed for LIMIT fill / TP / SL.
- Forex/Metal reference prices are not used to auto-manage new executable positions without a broker feed.

## STATE CONTINUITY

- KV binding: `TRADING_STATE`
- namespace: existing `TRADING_V77_STATE`
- book key remains `v775:books`
- GitHub/Cloudflare Builds path: `cloudflare-worker`
- deployment command: `npm run deploy`

Secrets remain in Cloudflare, not GitHub.

## VALIDATION

`.github/workflows/validate-cloudflare-v77.yml` must PASS syntax, canonical token checks and Wrangler dry-run before V77.8 changes are trusted.

Post-deploy runtime checks:
- `/status` -> V77.8.0 and Hub enabled;
- `/hub` -> combined three-market result;
- `/run-now?group=crypto` -> 61 canonical identities, exchange-native deep;
- `/run-now?group=forex` -> 28 pairs;
- `/run-now?group=metal` -> 2 symbols;
- `/telegram/setup-webhook` and `/telegram/webhook-info` healthy;
- Telegram Hub returns a final result rather than remaining on “Đang quét”.

## NEW CHAT INSTRUCTION

`Continue Trading from MASTER_TRADING_STATE.md + UNIFIED_RUNTIME_V77_8.md + CURRENT_HANDOFF.md. Current state = V73 frozen prior + V74 live authority + V75 data integrity + V76 R2 locked research-only + V77.8.0 Unified Hub. GitHub cloudflare-worker/index.js is the only production code source. Crypto deep is exact exchange-native 5TF + bid/ask. Forex/Metal use Twelve Data analysis but require broker execution bid/ask before new executable orders. Broad ranking never authorizes trades. Require D1/H4/H1, V73 prior, M15 location, strict M5 MSS/displacement/retest, structural SL, clean room, news/context and final execution quote. Never restore legacy score authority, proxy instruments or fabricate spread.`
