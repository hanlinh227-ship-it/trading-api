# TWELVE DATA GROW 55 — MARKET DATA POLICY

Updated: 2026-08-18 UTC+7

V73 remains frozen. V74 is the live decision layer; V75 is the fast-data layer; V76 research is isolated from live latency.

## Live path
Supported non-crypto uses direct Twelve Data REST via `scripts/twelvedata_market.py` (`V4-TWELVEDATA-FAST-STRICT`). The old shorthand Cloudflare Worker is deprecated.

Hard rules: exact canonical identity; exact `meta.symbol` + `meta.type`; closed candles for indicators/structure; `/quote.last_quote_at` is provider time; `/price` only after identity proof; quote >65s = `DATA_BLOCK`; V74 Forex MARKET target <=30s when true timestamp exists; never fabricate broker bid/ask/spread; never substitute cash/futures/spot.

V75 single-symbol D1/H4/H1/M15/M5 calls are parallelized. Preferred fast artifacts are `data/decision.json` and `data/forex-fast.json`. The 28-pair live scan remains about 46/55 credits, leaving 9 reserve.

## V76 research history
Canonical entrypoint: `scripts/run_v76_entry_research.py`.
Objective setup primitives: `scripts/research_v76_entry_forex.py`.
R2 evaluator: `scripts/evaluate_v76_entry_forex.py`.
Historical fetcher: `scripts/fetch_v76_history.py`.

Observed API guard: `batch symbol count × outputsize <= 100000`. Final R2 splits 28 Forex pairs into four parallel groups of seven and requests 5,000 M5 points per symbol, so each HTTP batch is `7 × 5000 = 35000`. A complete M5 chunk still consumes 28 symbol credits; chunks are separated by the quota window. Six chunks target about 30,000 M5 bars per pair. M15/H1/H4 are resampled locally; D1 is fetched separately. Raw history is not committed.

The primitive file is not the canonical full runner; active research uses `run_v76_entry_research.py`.

## Market rules
Forex: exact `AAA/BBB`, expected `Physical Currency`; broker spread still requires venue confirmation.
Crypto: exchange-native token/venue/timestamp + real bid/ask, target age <=10s.
Spot metals/energy: exact mapping/freshness only; never substitute futures.
Cash indices NAS100/US500/DAX/N225 families remain `DATA_BLOCK` in current Grow55 integration.
Exact NQ/MNQ/ES/MES/GC/SI/CL futures remain `DATA_BLOCK` until an authoritative exact-contract feed exists.

Permanent audit: `.github/workflows/audit-market-data.yml`, `scripts/audit_market_data.py`, `data/market-data-audit.json`.
If identity, contract, freshness or execution fields cannot be verified, return `DATA_BLOCK`/require venue confirmation.
