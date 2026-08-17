# DATA / INFRA STATE

Updated: 2026-08-18 UTC+7
Repo: `hanlinh227-ship-it/trading-api`

## Purpose

Current V75 live-data infrastructure plus isolated V76 research plumbing. V73 legacy research/optimizers are not active runtime.

## V75 live data

Single symbol: trigger `request.json` → `.github/workflows/fetch-market.yml` → `data/decision.json` first, with `status.json` / `latest.json` as deeper evidence.

Supported non-crypto uses `scripts/twelvedata_market.py` (`V4-TWELVEDATA-FAST-STRICT`): exact symbol/type validation, D1/H4/H1/M15/M5 parallel fetch, closed candles, `/quote.last_quote_at` provider time, `/price` only after identity proof, >65s hard stale block, no fabricated bid/ask.

Crypto uses `scripts/fetch_crypto.py`: exchange-native exact instrument, 5 TF parallel, final venue ticker refresh, real bid/ask + exchange timestamp. M1 is not mandatory.

Forex universe: `scan-request.json` → `scan-forex.yml` → `scripts/scan_forex_v75.py` → `data/forex-fast.json`. Pipeline is 28 H1 broad → Top3 deep D1/H4/M15/M5 + quote/price. Normal Grow55 budget 46/55, reserve 9.

Crypto universe: `data/live_scan_request.txt` → `live-crypto-v75-scan.yml` → `scripts/scan_crypto_v75.py` → `data/crypto-fast.json`. Missing exact OKX USDT instruments are never substituted.

## V76 research — isolated from live

Explicit trigger: `data/v76_research_request.txt`.
Workflow: `.github/workflows/research-v76-entry.yml`.
Canonical full runner: `scripts/run_v76_entry_research.py`.
Primitives: `scripts/research_v76_entry_forex.py`.
R2 evaluator: `scripts/evaluate_v76_entry_forex.py`.
Historical fetcher: `scripts/fetch_v76_history.py`.
Live post-V75 gate: `scripts/entry_v76.py`.
Validator: `.github/workflows/validate-entry-v76.yml`.

Historical M5 uses four parallel groups × seven pairs × 5,000 bars = 35,000 points per HTTP batch, below the observed Twelve Data 100,000 batch-page guard. A complete chunk still consumes 28 symbol credits; chunks are quota-window separated. Final R2 is configured for six chunks (~30,000 M5 bars/pair target). M15/H1/H4 are resampled locally and D1 fetched separately. Raw history is never committed.

Outputs:
- `data/v76_entry_research.json` — compact research evidence;
- `data/v76_entry_methods.json` — locked per-symbol methods;
- `data/v76_entry_summary.json` — compact read summary after R2.

Research/API pauses never sit in the V75 live path. Pilot R1 methods are explicitly blocked by `entry_v76.py`; only `V76-ENTRY-METHODS-R2` can even be considered for live use, and non-OOS-promoted R2 methods still return `NO_ENTRY`.

## Price integrity

Keep distinct: provider/venue market timestamp, our fetch time, latest aggregated/reference price, executable bid/ask spread.

Crypto normally supplies venue timestamp + bid/ask. Forex/spot metals through Twelve Data can support analysis but still require execution-venue spread confirmation before MARKET.

## Routing

Forex: direct strict Twelve Data Grow55.
Crypto: exchange-native REST; Twelve Data optional enrichment only.
Spot metals/energy: exact canonical Twelve Data mapping only when identity/freshness pass.
Cash indices NAS100/US500/DAX/N225 families: `DATA_BLOCK` in current Grow55 integration.
Exact futures NQ/MNQ/ES/MES/GC/SI/CL: `DATA_BLOCK`; no cash/spot proxy.

## Audit / cleanup

Permanent market-data audit: `.github/workflows/audit-market-data.yml` + `scripts/audit_market_data.py` → `data/market-data-audit.json`.

Keep only current runtime, isolated research, validation, audit and checkpoints. Temporary diagnostics/probes are removed; Git history is the archive.

If identity/contract, freshness or required execution fields cannot be verified, return `DATA_BLOCK` / `NO_ENTRY`. Neither V73 nor V76 research can authorize fabricated live data.
