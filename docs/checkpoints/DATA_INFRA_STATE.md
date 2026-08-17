# DATA / INFRA STATE

Updated: 2026-08-17 UTC+7
Repo: `hanlinh227-ship-it/trading-api`

## PURPOSE

This file describes the current live-data infrastructure only. Historical research engines are not part of the active runtime.

## ACTIVE DATA PATHS

### Single-symbol path
Trigger: `request.json`
Workflow: `.github/workflows/fetch-market.yml`
Outputs:
- `data/status.json` — compact normalized status for decision use;
- `data/latest.json` — full combined provider output.

Non-crypto path:
- Cloudflare Worker `forex-chart-api`;
- Twelve Data Grow 55 behind the Worker;
- D1/H4/H1/M15/M5 analysis;
- latest `/price` fetched separately;
- M1 `/refresh` retained as reference/context only.

Crypto path:
- `scripts/fetch_crypto.py`;
- Binance -> OKX -> Bybit fallback order where available;
- direct exchange last price, bid, ask, timestamp and candles;
- D1/H4/H1/M15/M5 analysis plus M1 reference.

### Forex universe path
Trigger: `scan-request.json`
Workflow: `.github/workflows/scan-forex.yml`

Grow 55 staged budget:
- 28 broad pair scans ~28 credits;
- Top 3 deep 5-timeframe analyses ~15 credits;
- Top 3 latest-price refreshes ~3 credits;
- normal total ~46 credits;
- reserve ~9 credits.

Routine Basic-plan sleeps have been removed. A wait is permitted only when exceptional retry volume would exceed the remaining minute quota.

### Crypto universe path
Trigger: `data/live_scan_request.txt`
Workflow: `.github/workflows/live-crypto-v74-scan.yml`

Exchange-native data remains primary for candidate ranking and final crypto execution context.

## QUOTA COORDINATION

`fetch-market.yml` and `scan-forex.yml` share the `twelvedata-api` concurrency group so a single-symbol non-crypto fetch cannot collide with the 28-pair Forex Grow 55 scan.

Do not create another Twelve Data workflow with an unrelated concurrency group unless its credit budget is explicitly isolated.

## PRICE INTEGRITY MODEL

The repository distinguishes:

1. **provider fetch time** — when our Worker/GitHub job fetched data;
2. **market quote timestamp** — when the underlying venue says the quote occurred;
3. **executable spread** — venue/broker bid and ask.

These fields must never be conflated.

### Crypto
Direct exchange REST usually supplies market timestamp + bid/ask. V74 strict target quote age is <=10 seconds.

### Forex / non-crypto Twelve Data `/price`
The current integration provides latest aggregated price but does not expose a broker-executable bid/ask or verified quote-tick timestamp. Therefore:
- `/price` is valid as the latest aggregated market reference;
- its Worker `generatedAt` is fetch time, not a broker quote timestamp;
- do not invent bid/ask/spread;
- final MARKET execution requires venue/platform confirmation when spread/timestamp verification is materially required.

M1 `/refresh` is useful for recent-candle context and market continuity but its candle close is not substituted for the final `/price` value.

## MARKET-TYPE ROUTING

### Forex
Twelve Data Grow 55 / Worker.

### Crypto
Exchange-native REST for execution precision. Twelve Data may be used as enrichment/cross-check when useful.

### Cash indices
Use actual cash-index mappings only. Never substitute NQ/ES/MNQ/MES.

### Futures
Exact contract/front-month/continuous identity must be verified. If the Worker/provider cannot prove the exact futures instrument, use an authoritative futures feed or the user's platform price. Do not use cash as a proxy.

### Metals
Keep XAUUSD/XAGUSD spot separate from GC/SI futures.

## ACTIVE FILE POLICY

Keep only files required for the current runtime or canonical checkpoint:
- V73 frozen JSON + runtime reader + validator;
- V74 live playbook + validator;
- single-symbol market fetch;
- Forex universe scan;
- crypto universe scan;
- direct crypto fetcher;
- current outputs and request triggers;
- current market/checkpoint documentation.

Old blind tests, calibration systems, provider snapshot collectors, optimizer generations, probe workflows and temporary result summaries are removed from the active tree once conclusions are represented in the frozen checkpoint. Git history remains the archive.

## FAILURE RULE

If exact symbol/instrument, required market state, quote freshness or execution spread cannot be verified, return `DATA_BLOCK`. A forced-daily research rule never authorizes fabricated live data.
