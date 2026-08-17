# DATA / INFRA STATE

Updated: 2026-08-17 UTC+7
Repo: `hanlinh227-ship-it/trading-api`

## PURPOSE

Current live-data infrastructure only. Historical research engines are not part of the active runtime.

## SINGLE-SYMBOL PATH

Trigger: `request.json`
Workflow: `.github/workflows/fetch-market.yml`
Outputs:
- `data/status.json` — compact canonical state;
- `data/latest.json` — full current provider evidence.

### Crypto
- `scripts/fetch_crypto.py`;
- exchange-native Binance -> OKX -> Bybit fallback where available;
- direct last price, bid, ask and venue timestamp;
- D1/H4/H1/M15/M5 analysis plus M1 reference.

### Supported non-crypto
- `scripts/twelvedata_market.py`;
- direct Twelve Data REST from GitHub Actions;
- no Cloudflare Worker in the canonical runtime;
- explicit symbol registry;
- exact `time_series` metadata validation;
- closed candles for technical indicators;
- `/quote` for identity + `last_quote_at`;
- `/price` for latest aggregated value only after identity validation;
- quote >65 seconds old => `DATA_BLOCK`.

## FOREX UNIVERSE PATH

Trigger: `scan-request.json`
Workflow: `.github/workflows/scan-forex.yml`

Grow55 staged budget:
- 28 H1 broad scans = 28 credits;
- Top 3 × D1/H4/M15/M5, H1 reused = 12 credits;
- Top 3 × (`/quote` + `/price`) = 6 credits;
- total = 46/55;
- reserve = 9 credits.

All Twelve Data workflows share concurrency group `twelvedata-api`.

## CRYPTO UNIVERSE PATH

Trigger: `data/live_scan_request.txt`
Workflow: `.github/workflows/live-crypto-v74-scan.yml`

Exchange-native data remains primary for candidate ranking and execution context.

## PRICE INTEGRITY MODEL

The repository distinguishes:

1. **provider market timestamp** — e.g. Twelve Data `last_quote_at` or exchange tick timestamp;
2. **our fetch time** — when GitHub received the response;
3. **latest aggregated price value** — Twelve Data `/price` after identity validation;
4. **executable spread** — venue/broker bid and ask.

These fields are never conflated.

### Crypto
Exchange REST supplies timestamp + bid/ask. V74 target quote age <=10 seconds.

### Forex / spot metals / supported commodities
Twelve Data:
- `/time_series` proves symbol/type per timeframe;
- `/quote` proves identity and gives `last_quote_at`;
- `/price` supplies latest aggregated value;
- hard stale block >65 seconds;
- V74 Forex MARKET freshness target <=30 seconds;
- broker bid/ask are not fabricated.

Therefore a Twelve Data value can be suitable for analysis while still requiring broker/venue confirmation before MARKET execution.

## MARKET-TYPE ROUTING

### Forex
Direct strict Twelve Data Grow55.

### Crypto
Exchange-native REST. Twelve Data is optional enrichment only.

### Spot metals / energy
Use exact canonical Twelve Data mappings only when metadata and freshness pass. XAUUSD/XAGUSD remain separate from GC/SI.

### Cash indices
Current Grow55/core endpoints cannot safely prove NAS100/NDX, US500/SPX, DAX or N225-family cash indices. These return `DATA_BLOCK`. Never use NQ/ES or same-text securities as silent proxies.

### Futures
Current Grow55 catalog/search does not expose exact provable NQ/MNQ/ES/MES/GC/SI/CL contracts. These return `DATA_BLOCK`; use an authoritative futures feed or the user's platform price.

## PERMANENT AUDIT

- workflow: `.github/workflows/audit-market-data.yml`;
- script: `scripts/audit_market_data.py`;
- evidence: `data/market-data-audit.json`.

Audit covers supported Forex/Crypto/metals plus expected index/futures blocks and stale-feed rejection.

## ACTIVE FILE POLICY

Keep only current runtime, audit and checkpoint files. Diagnostic/probe workflows are temporary and must be removed after conclusions are captured. Git history remains the archive.

## FAILURE RULE

If exact symbol/type/contract, quote freshness or required execution fields cannot be verified, return `DATA_BLOCK`. Forced-daily research rules never authorize fabricated live data.
