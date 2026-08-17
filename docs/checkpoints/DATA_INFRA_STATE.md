# DATA / INFRA STATE

Updated: 2026-08-18 UTC+7
Repo: `hanlinh227-ship-it/trading-api`

## Purpose

Current live-data infrastructure plus isolated V76 research plumbing. V73 research history/legacy optimizers are not active runtime.

## Single-symbol V75

Trigger: `request.json`.
Workflow: `.github/workflows/fetch-market.yml`.
Fast output: `data/decision.json`; detailed evidence: `data/status.json`, `data/latest.json`.

Crypto uses `scripts/fetch_crypto.py`, exchange-native exact instrument, D1/H4/H1/M15/M5 in parallel, final venue ticker refresh, real bid/ask and timestamp. M1 is not mandatory.

Supported non-crypto uses `scripts/twelvedata_market.py` (`V4-TWELVEDATA-FAST-STRICT`) directly from GitHub Actions. It validates exact symbol/type metadata, uses closed candles, `/quote.last_quote_at` for provider time, and `/price` only after identity proof. Quote >65 seconds is `DATA_BLOCK`; broker bid/ask is never fabricated.

## Forex-universe V75

Trigger: `scan-request.json`.
Workflow: `.github/workflows/scan-forex.yml`.
Engine: `scripts/scan_forex_v75.py`.
Fast output: `data/forex-fast.json`.

Pipeline: 28 H1 broad → Top3 deep D1/H4/M15/M5 + quote/price. Normal Grow55 budget is 46/55 credits, reserve 9.

## Crypto-universe V75

Trigger: `data/live_scan_request.txt`.
Workflow: `.github/workflows/live-crypto-v75-scan.yml`.
Engine: `scripts/scan_crypto_v75.py`.
Fast output: `data/crypto-fast.json`.

Exchange-native OKX staged scan is primary; missing exact USDT instruments are not substituted.

## V76 research — isolated from live

Trigger: `data/v76_research_request.txt`.
Workflow: `.github/workflows/research-v76-entry.yml`.
Core: `scripts/research_v76_entry_forex.py`.
Canonical quota-safe runner: `scripts/run_v76_entry_research.py`.
Outputs after successful research: `data/v76_entry_research.json`, `data/v76_entry_methods.json`.

Research fetches historical M5 separately from live scans, resamples M15/H1/H4 locally and fetches D1 separately. Raw history is not committed. Research pauses/quota usage never sits in the live decision path.

## Price integrity

Keep separate:
1. provider/venue market timestamp;
2. our fetch time;
3. latest aggregated/reference price;
4. executable bid/ask spread.

Crypto normally supplies venue timestamp + bid/ask. Forex/spot metals through Twelve Data can be suitable for analysis but still require execution-venue spread confirmation before MARKET.

## Market routing

Forex: direct strict Twelve Data Grow55.
Crypto: exchange-native REST; Twelve Data optional enrichment only.
Spot metals/energy: exact canonical Twelve Data mapping only when identity/freshness pass.
Cash indices: current Grow55 path cannot safely prove NAS100/US500/DAX/N225 families → `DATA_BLOCK`.
Futures: current Grow55 cannot prove exact NQ/MNQ/ES/MES/GC/SI/CL contracts → `DATA_BLOCK`; no cash/spot proxy.

## Permanent audit

`.github/workflows/audit-market-data.yml` + `scripts/audit_market_data.py` → `data/market-data-audit.json`.

## Active-file policy

Keep only current runtime, isolated research, validation, audit and checkpoints. Temporary diagnostics/probes are removed after conclusions are captured. Git history is the archive.

## Failure rule

If exact identity/contract, freshness or required execution fields cannot be verified, return `DATA_BLOCK`/`NO_ENTRY`. Neither V73 nor V76 research can authorize fabricated live data.
