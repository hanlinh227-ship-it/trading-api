# DATA / INFRA STATE

Updated: 2026-08-17 UTC+7
Repo: `hanlinh227-ship-it/trading-api`

## PURPOSE

Current live-data infrastructure only. Historical research engines remain outside the active runtime.

## CANONICAL SINGLE-SYMBOL PATH

Trigger: `request.json`
Workflow: `.github/workflows/fetch-market.yml`
Outputs:
- `data/status.json`
- `data/latest.json`

### Crypto
- `scripts/fetch_crypto.py`
- exchange-native Binance / OKX / Bybit fallback;
- direct last price + bid + ask + exchange timestamp;
- D1/H4/H1/M15/M5 + M1 reference;
- strict execution target quote age <=10s.

### Supported non-crypto
- `scripts/twelvedata_market.py`
- direct Twelve Data API using GitHub Actions secret `TWELVEDATA_API_KEY`;
- explicit canonical symbol/type registry;
- `/quote` for current aggregated price and `last_quote_at` timestamp;
- `/time_series` metadata validation for every timeframe;
- closed candles only for technical calculations;
- D1/H4/H1/M15/M5 + M1 reference;
- no fabricated bid/ask/spread.

### Unsupported / ambiguous instruments
Return `DATA_BLOCK`. Do not substitute a same-text ticker, ETF, CFD, cash index, spot commodity or futures proxy.

## FOREX UNIVERSE PATH

Trigger: `scan-request.json`
Workflow: `.github/workflows/scan-forex.yml`

Direct Grow55 staged budget:
- 28 H1 broad scans ~28 credits;
- Top 3 × D1/H4/M15/M5 while reusing H1 ~12 credits;
- Top 3 `/quote` ~3 credits;
- normal total ~43 credits;
- reserve ~12 credits.

All Twelve Data workflows share `concurrency.group=twelvedata-api`.

## CRYPTO UNIVERSE PATH

Trigger: `data/live_scan_request.txt`
Workflow: `.github/workflows/live-crypto-v74-scan.yml`

Exchange-native data remains primary.

## CROSS-MARKET AUDIT

Workflow: `.github/workflows/audit-market-data.yml`
Script: `scripts/audit_market_data.py`
Evidence: `data/market-data-audit.json`

Audit covers:
- exchange-native BTC/ETH/SOL;
- direct Twelve Data Forex;
- direct Twelve Data XAU/XAG spot metals;
- expected DATA_BLOCK for unsafe cash indices;
- expected DATA_BLOCK for exact futures unavailable through current Grow55 catalog.

## PRICE INTEGRITY MODEL

Keep these separate:
1. provider fetch time;
2. underlying quote timestamp;
3. executable bid/ask spread.

### Crypto
Exchange timestamp and bid/ask are normally available and must be verified.

### Twelve Data supported non-crypto
`/quote.last_quote_at` is the current provider quote timestamp. This is materially better than treating API fetch time as quote time.

Twelve Data still does not provide an executable broker bid/ask through this path, so `executionReady` remains false where spread verification is required for MARKET execution.

### Closed candles
D1/H4/H1/M15/M5/M1 indicators are computed only from closed candles. An in-progress candle must not leak into closed-bar technical calculations.

## INSTRUMENT COLLISION DEFENSE

The old shorthand Worker mapping produced demonstrably wrong cash-index data:
- NDX request path returned ~19.4;
- SPX request path returned ~0.085.

Those were unrelated instruments with colliding ticker text. Canonical live logic therefore no longer trusts shorthand ticker identity.

Direct-client checks include:
- exact canonical provider symbol;
- expected provider `type` in time-series metadata;
- quote symbol;
- quote timestamp;
- explicit supported-market registry.

## MARKET-TYPE ROUTING

### Forex
Direct Twelve Data strict client.

### Crypto
Exchange-native REST.

### Spot metals
Direct Twelve Data strict client for verified XAU/USD and XAG/USD; never conflate with GC/SI futures.

### Cash indices
Currently `DATA_BLOCK` in the Twelve strict client because exact Grow55/core-endpoint access is not proven. Use another authoritative cash-index source rather than proxy futures.

### Futures
NQ/MNQ/ES/MES/GC/CL currently `DATA_BLOCK` through Twelve strict client because exact CME/COMEX/NYMEX contracts are not proven in current Grow55 catalog/search. Use an authoritative futures feed or user's platform.

## ACTIVE FILE POLICY

Keep only current runtime/checkpoint/audit files. The redundant standalone fast-Forex workflow and trigger were removed. Temporary secret-check files were also removed after diagnosis.

Legacy optimizer generations, blind tests, calibration suites, provider snapshot collectors and probe jobs remain in Git history only.

## FAILURE RULE

If exact instrument/type/venue/contract, quote timestamp, required freshness or executable spread cannot be verified, return `DATA_BLOCK`. A live system must prefer no price over a wrong price.
