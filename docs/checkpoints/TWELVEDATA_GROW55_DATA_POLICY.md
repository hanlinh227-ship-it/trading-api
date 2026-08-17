# TWELVE DATA GROW 55 — MARKET DATA POLICY

Updated: 2026-08-17 UTC+7

This policy supplements V74 and does not alter frozen V73.

## CANONICAL DATA PATH

Supported non-crypto instruments use **direct Twelve Data REST from GitHub Actions**:
- client: `scripts/twelvedata_market.py`;
- client version: `V3-TWELVEDATA-DIRECT-STRICT`;
- secret: `TWELVEDATA_API_KEY`;
- shared concurrency group: `twelvedata-api`.

The old Cloudflare Worker is deprecated and must not be used for canonical live market decisions.

## HARD DATA RULES

1. Resolve only through an explicit canonical registry inside `twelvedata_market.py`.
2. Every `/time_series` response must match the exact canonical `meta.symbol` and expected `meta.type`.
3. EMA/RSI/ATR and V74 technical context use **closed candles only**.
4. `/quote` proves identity and supplies `last_quote_at`.
5. `/price` is called only after identity is proven and supplies the latest aggregated price value.
6. Current `/price` must remain reasonably close to the validated `/quote` reference; large drift is `DATA_BLOCK`.
7. If `last_quote_at` is more than **65 seconds old**, return `DATA_BLOCK` even when the symbol is correct.
8. V74 still uses a stricter **<=30 seconds** Forex quote-age target before MARKET review.
9. Twelve Data does not supply an executable broker bid/ask in this integration; never invent spread.
10. Unsupported or ambiguous cash indices/futures are `DATA_BLOCK`, never proxied.

## GROW55 FOREX BUDGET

Canonical workflow: `.github/workflows/scan-forex.yml`.

Current staged budget:
- 28 H1 broad scans = 28 credits;
- Top 3 × D1/H4/M15/M5, reusing H1 = 12 credits;
- Top 3 × (`/quote` + `/price`) = 6 credits;
- normal total = **46/55**;
- reserve = **9 credits**.

No routine Basic-plan `sleep 65` batching remains.

## FOREX

Example mapping: `EURUSD -> EUR/USD`, expected provider type `Physical Currency`.

Current value semantics:
- `currentPrice` = latest `/price` result after exact identity has been validated;
- `currentPriceTime` = `/quote.last_quote_at` provider timestamp;
- `priceFetchedAt` = when our GitHub job fetched `/price`;
- bid/ask/spread = null/unverified unless an execution venue supplies them.

These times must never be conflated.

## CRYPTO

Crypto execution data remains exchange-native through `scripts/fetch_crypto.py` using Binance / OKX / Bybit where available.

Requirements:
- exact token / quote currency;
- exact venue;
- exchange timestamp;
- real bid/ask;
- target quote age <=10 seconds.

Twelve Data may enrich analysis but must not replace an exchange-specific execution quote.

## SPOT METALS / COMMODITIES

Verified canonical mappings include:
- `XAUUSD -> XAU/USD`, type `Precious Metal`;
- `XAGUSD -> XAG/USD`, type `Precious Metal`;
- `WTIUSD -> WTI/USD`, type `Energy Resource`;
- `BRENTUSD -> XBR/USD`, type `Energy Resource`.

Correct identity alone is not enough. If the provider timestamp is stale, the output is `DATA_BLOCK`. Spot metals/energy remain separate from GC/SI/CL futures.

## CASH INDICES

Diagnostics on 2026-08-17 proved that shorthand ticker calls are unsafe:
- plain `NDX` resolved to Nordex SE ADR in Frankfurt at a price near 19.4;
- plain `SPX` resolved to Stellar AfricaGold on TSXV near 0.085.

Current Grow55 diagnostics also showed no safe usable core-endpoint path for NAS100/NDX, US500/SPX, DAX/GDAXI or N225-family cash indices in this account/plan combination.

Therefore those aliases return `DATA_BLOCK`. Never substitute NQ/ES futures, CFDs, ETFs or same-text securities silently.

## FUTURES

Current Grow55 catalog/search did not expose exact provable CME/COMEX/NYMEX contracts for NQ/MNQ/ES/MES/GC/SI/CL.

Those symbols therefore return `DATA_BLOCK` from Twelve Data. Use an authoritative futures feed or the user's platform price until an exact contract feed is integrated. Never substitute cash index or spot commodity data.

## AUDIT

Permanent cross-market audit:
- `.github/workflows/audit-market-data.yml`;
- `scripts/audit_market_data.py`;
- `data/market-data-audit.json`.

It verifies:
- exchange-native BTC/ETH/SOL;
- supported Forex;
- supported spot metals;
- stale-feed rejection;
- expected cash-index blocks;
- expected exact-futures blocks.

## FAILURE RULE

If symbol/type/contract identity, quote timestamp, freshness or required execution fields cannot be verified, return `DATA_BLOCK` or require execution-venue confirmation. Never label stale, ambiguous or proxied data as live.
