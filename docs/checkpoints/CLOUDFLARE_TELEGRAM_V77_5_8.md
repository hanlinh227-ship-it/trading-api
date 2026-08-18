# CLOUDFLARE / TELEGRAM V77.5.8

Updated: 2026-08-18 UTC+7
Status: Crypto broad-scan subrequest fix on top of V77.5.7.

## Root cause fixed

V77.5.7 broad Crypto discovery called one external quote request per symbol across the 61-token canonical universe. Cloudflare Workers Free allows only 50 external subrequests per invocation, so a Telegram Crypto scan could terminate before broad discovery completed while Metal (2 symbols) remained healthy.

## V77.5.8 fix

- Keep all 61 canonical Crypto identities.
- Replace per-symbol broad quote fetches with bulk market snapshots:
  - Binance `/api/v3/ticker/24hr` bulk snapshot.
  - OKX `/api/v5/market/tickers?instType=SPOT` bulk snapshot.
- Exact symbol matching only; no token remapping.
- Binance exact row has priority; exact OKX USDT spot row is fallback.
- Deep analysis remains limited to selected Top candidates and continues to use exact venue quote/candles.
- Metal and Forex behavior from V77.5.7 remains unchanged.
- Runtime version = `V77.5.8`.

## Why this matters

The broad Crypto phase now needs only a small fixed number of external market-data requests instead of at least 61 requests before deep analysis. This is designed to remain below Cloudflare Workers Free's 50 external-subrequest ceiling for the whole Telegram scan.

## Canonical safety

V73 remains frozen. V74 remains live-analysis/execution authority. V75 remains the fast-data layer. V76 R2 remains research-only. V77.5.8 is an operational data-routing/scanner repair and must not promote legacy V77 scoring into a new live authority.

## Post-deploy checks

1. `/status` => `V77.5.8`.
2. `/run-now?group=crypto` should return `broadScanned: 61` instead of terminating during broad scan.
3. Diagnostics should show `broadOk`, `freshEligible`, `deepRequested`, `deepOk`, and any exact-instrument errors.
4. Telegram CRYPTO button should return a completed scan summary rather than hanging or returning no result.
