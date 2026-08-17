# TWELVE DATA GROW 55 — MARKET DATA POLICY

Updated: 2026-08-17 UTC+7

This policy supplements V74 and does not alter frozen V73.

## CORE DATA PATH

Supported non-crypto instruments now use the **direct strict Twelve Data client**:
- `scripts/twelvedata_market.py`
- GitHub Actions secret: `TWELVEDATA_API_KEY`
- client version: `V2-TWELVEDATA-DIRECT-STRICT`

The old practice of trusting a shorthand ticker through the Cloudflare Worker is deprecated for canonical live decisions.

Direct-client rules:
1. resolve only through an explicit canonical registry;
2. use Twelve Data `/quote` for current aggregated price;
3. use `last_quote_at` as the provider quote timestamp;
4. validate `/time_series` metadata on every requested timeframe;
5. reject any metadata/symbol/type mismatch;
6. calculate EMA/RSI/ATR locally from closed candles only;
7. never invent bid/ask or spread;
8. return `DATA_BLOCK` when the exact requested instrument cannot be proven.

## GROW55 QUOTA

Operational budget remains 55 API credits/minute. All Twelve Data workflows use the shared `twelvedata-api` concurrency group.

### Forex universe scan
Canonical workflow: `.github/workflows/scan-forex.yml`.

Current staged budget:
- 28 H1 broad scans ≈ 28 credits;
- Top 3 × D1/H4/M15/M5 while reusing H1 ≈ 12 credits;
- Top 3 `/quote` ≈ 3 credits;
- normal total ≈ 43/55;
- reserve ≈ 12 credits.

There is no routine Basic-plan `sleep 65` batching.

## FOREX

Canonical mapping is explicit, e.g. `EURUSD -> EUR/USD`. Time-series metadata must identify `Physical Currency` and the exact pair.

Current price comes from `/quote`; `last_quote_at` supplies the provider timestamp. V74 strict target is quote age <=30 seconds.

Twelve Data does not provide an executable broker bid/ask in this integration. Therefore:
- bid/ask remain null when not supplied;
- spread remains unverified;
- a fresh aggregated price is useful for analysis but is not automatically a broker-executable MARKET quote.

## SINGLE SYMBOL

Canonical workflow: `.github/workflows/fetch-market.yml`.

- Crypto: `scripts/fetch_crypto.py`, exchange-native.
- Supported Forex/metals: `scripts/twelvedata_market.py`, direct Twelve Data.
- Unsupported/ambiguous cash indices or exact futures: explicit `DATA_BLOCK`.

The former standalone fast-Forex refresh workflow was removed to avoid duplicate paths and inconsistent semantics.

## CRYPTO

Execution data remains exchange-native, using Binance / OKX / Bybit where available.

Requirements:
- exact token and quote currency;
- exact venue;
- exchange timestamp;
- real bid/ask;
- V74 target quote age <=10 seconds.

Twelve Data may be used for enrichment, but it does not replace exchange-native execution quotes.

## SPOT METALS / COMMODITIES

Verified strict mappings include:
- XAUUSD -> `XAU/USD`, expected type `Precious Metal`;
- XAGUSD -> `XAG/USD`, expected type `Precious Metal`.

Spot metals remain separate from GC/SI futures.

Energy spot symbols such as WTI may be fetched only when their provider timestamp satisfies the freshness requirement. A stale quote is rejected even if symbol metadata is correct.

## CASH INDICES

Current Grow55 diagnostics showed that shorthand core endpoint requests can collide with unrelated instruments. Examples observed during the 2026-08-17 audit included an `NDX` value around 19.4 and `SPX` around 0.085, neither of which is the requested cash index.

Therefore the strict client currently returns `DATA_BLOCK` for NAS100/NDX, US500/SPX, DAX and N225-family cash-index aliases until the exact cash index is provably available through the plan/core endpoint combination.

Never substitute NQ/ES futures or a CFD for cash index data silently.

## FUTURES

Current Grow55 catalog/search diagnostics did not expose exact provable CME/COMEX/NYMEX contracts for NQ/MNQ/ES/MES/GC/CL.

Therefore the direct strict client returns `DATA_BLOCK` for these exact futures symbols rather than accepting a same-text ticker or using a cash/spot proxy.

For MNQ/MES live analysis, use an authoritative futures feed or the user's platform price until an exact futures feed is integrated.

## AUDIT

Cross-market audit:
- `.github/workflows/audit-market-data.yml`
- `scripts/audit_market_data.py`
- `data/market-data-audit.json`

Audit verifies supported Forex, exchange-native Crypto, supported metals, and expected blocking behavior for cash indices/futures.

## NEWS / CONTEXT

Twelve Data remains a market-data provider, not the sole news source. Live analysis must also refresh applicable macro, central-bank, yields/DXY, geopolitical, sector and crypto-specific context.

## FAILURE RULE

If symbol/type/venue/contract identity, quote timestamp, required freshness, or execution spread cannot be verified, return `DATA_BLOCK` or require execution-venue confirmation. Never call stale, ambiguous or proxied data live.
