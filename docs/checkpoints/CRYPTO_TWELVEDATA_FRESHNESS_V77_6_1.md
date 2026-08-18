# CRYPTO TWELVE DATA FRESHNESS — V77.6.1

Updated: 2026-08-18 UTC+7

## Observed Telegram evidence

V77.6.0 reached 54/61 broad OK and produced CRVUSDT WATCH, proving the unified Crypto pipeline is operational. AAVEUSDT and ATOMUSDT were incorrectly DATA_BLOCKed as `Giá stale` from the Twelve Data analysis quote even though Crypto execution freshness should be validated separately at the exchange-native quote stage.

## Root cause

`getTwelveCryptoQuote()` reused `normalizeQuotePayload()`, whose `fresh` field is based on the strict generic quote-age threshold. That field was then used by `deepAnalyze()` before D1/H4/H1/M15/M5 were fetched. For Crypto, Twelve Data is analysis-only and must not be treated as the executable quote freshness authority.

Twelve Data `/time_series` candle datetime represents the bar OPEN timestamp. Therefore analysis freshness for a closed M5 candle must be measured from bar close (`open timestamp + 5 minutes`) rather than comparing the open timestamp directly with an execution-quote threshold.

## V77.6.1 fix

- Forex and Metal keep the existing strict initial quote freshness gate.
- Crypto skips the initial Twelve Data `/quote` execution-style freshness gate.
- After closed M5 candles are fetched, Crypto analysis freshness is based on the latest closed M5 candle end time.
- Maximum accepted closed-M5 analysis delay is 900 seconds.
- If the latest closed M5 is older, return `DATA_BLOCK / Dữ liệu M5 phân tích stale`.
- Twelve Data remains analysis-only for Crypto.
- MARKET/LIMIT Crypto still requires a final fresh exact exchange-native bid/ask/timestamp from Binance/Bybit/OKX.
- No execution gate is weakened.

## Canonical architecture unchanged

V73 frozen prior -> V74 live authority -> V75 data -> V76 R2 research-only. V77.6.1 is an operational freshness correction only.
