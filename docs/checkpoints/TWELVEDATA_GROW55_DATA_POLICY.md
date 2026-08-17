# TWELVE DATA GROW 55 — MARKET DATA POLICY

Updated: 2026-08-18 UTC+7

Supplements V74/V75. V73 remains frozen.

## Canonical live path

Supported non-crypto uses direct Twelve Data REST from GitHub Actions through `scripts/twelvedata_market.py`, version `V4-TWELVEDATA-FAST-STRICT`. The old shorthand Cloudflare Worker is deprecated for canonical decisions.

Hard rules:
1. explicit canonical identity only;
2. every timeframe validates exact `meta.symbol` + `meta.type`;
3. indicators/structure use closed candles only;
4. `/quote.last_quote_at` = provider time;
5. `/price` accepted only after identity proof;
6. provider time, fetch time and aggregated price are distinct;
7. quote >65s => `DATA_BLOCK`;
8. V74 Forex MARKET target <=30s when true timestamp exists;
9. no fabricated broker bid/ask/spread;
10. cash index/futures/spot are never interchangeable.

## V75 live speed

D1/H4/H1/M15/M5 single-symbol calls are parallelized. Full indicator history is processed in memory; compact tails are stored. Preferred artifacts are `data/decision.json` and `data/forex-fast.json`.

28-pair live scan budget remains about 46/55 credits: 28 H1 broad + 12 deep-frame credits + 6 quote/price credits, leaving 9 reserve.

## V76 research history

Research is separate from live V75 latency.

Canonical runner: `scripts/run_v76_entry_research.py`.
Core definitions: `scripts/research_v76_entry_forex.py`.

Observed API guard: `batch symbol count × outputsize <= 100000`. The canonical 28-pair M5 research request therefore uses outputsize 3500 (`28 × 3500 = 98000`) per chunk. M15/H1/H4 are resampled locally from M5; D1 is fetched separately. Raw history is not committed, only compact research evidence and locked methods.

## Market rules

Forex: exact `AAA/BBB`, expected type `Physical Currency`. `currentPrice` is validated `/price`; `currentPriceTime` is `/quote.last_quote_at`; broker spread still requires venue confirmation.

Crypto: execution data remains exchange-native with exact token/venue/timestamp and real bid/ask; target quote age <=10s.

Spot metals/energy: exact mappings such as XAU/USD, XAG/USD, WTI/USD, XBR/USD only when identity/freshness pass. Never substitute GC/SI/CL futures.

Cash indices: NAS100/NDX, US500/SPX, DAX and N225-family remain `DATA_BLOCK` in current Grow55 integration because exact cash identity is not safely provable.

Futures: exact CME/COMEX/NYMEX NQ/MNQ/ES/MES/GC/SI/CL remain `DATA_BLOCK` until an authoritative exact-contract feed exists.

## Audit / failure rule

Permanent audit: `.github/workflows/audit-market-data.yml`, `scripts/audit_market_data.py`, `data/market-data-audit.json`.

If identity, contract, timestamp freshness or required execution fields cannot be verified, return `DATA_BLOCK`/require venue confirmation. Never label stale, ambiguous or proxied data live.
