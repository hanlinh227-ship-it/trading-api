# V77.6.0 — TWELVE DATA MAX-UTILIZATION CRYPTO LAYER

Updated: 2026-08-18 UTC+7

Status: data/router upgrade only. V73 remains frozen, V74 remains live authority, V75 remains canonical data-integrity baseline, V76 R2 remains research-only.

## Goal
Use the Twelve Data Grow55 plan close to its useful limit without exceeding 55 API credits/minute, while preserving exchange-native execution verification for crypto.

## Architecture
- Full 61-token canonical crypto universe remains unchanged.
- Venue bulk tickers (Binance/Bybit/OKX) remain low-request discovery/coverage sources.
- Twelve Data adds a rotating closed-H1 broad enrichment set of 30 canonical symbols per Crypto scan.
- Top 3 deep candidates use Twelve Data standardized closed candles on D1/H4/H1/M15/M5.
- Candidate analysis quote may use Twelve Data.
- MARKET/LIMIT authorization for crypto still requires a fresh exact exchange-native quote with real bid/ask/timestamp.
- Twelve Data analysis/reference price is never called an executable venue quote.

## Grow55 budget target
Normal Crypto scan target:
- closed H1 broad enrichment: ~30 credits;
- Top 3 analysis quote resolution: ~3 credits when primary pair resolves immediately;
- Top 3 × D1/H4/H1/M15/M5: ~15 credits;
- expected normal total: ~48 credits/minute;
- reserve: ~7 credits for pair fallback/error handling and other calls.

Batch requests reduce HTTP calls but not credit weight: each symbol still consumes its endpoint weight. The code therefore deliberately does not request 61 Twelve Data symbols in the same minute.

## Twelve Data integrity
- `api-credits-used` and `api-credits-left` response headers are captured into runtime telemetry.
- Crypto Twelve Data pair preference is exact BASE/USDT, then the existing exact resolver may fall back to BASE/USD only when actually supported.
- Closed candles only are used for technical calculations.
- Crypto broad H1 rotates through the 61 canonical symbols via KV cursor, so repeated on-demand scans cover the whole universe without exceeding Grow55.
- Exchange-native fallback candles remain available if Twelve Data candles fail for a selected candidate.

## Entry safety
V77.6.0 does not promote the legacy V77 scoring engine into canonical authority. D1/H4 were added to deep data/context, but a future canonicalEntryGate still must fully enforce V74 current-news/context, V73 prior, M15 tradable location, strict M5 close-confirmed MSS/displacement/retest, structural invalidation, clean-room/cost gate and final execution-venue spread.

## Runtime expectations
Telegram Crypto diagnostics should no longer show the entire market missing merely because Binance/OKX are blocked from Cloudflare. Twelve Data may keep part of the universe analyzable; if final venue bid/ask cannot be verified, the result must be WATCH/DATA_BLOCK rather than fabricated MARKET.

Version label: V77.6.0.
