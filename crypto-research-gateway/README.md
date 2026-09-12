# Crypto Research Gateway

Read-only cloud execution runtime for GitHub Brain crypto research.

## Runtime

- Node.js 22+
- TypeScript
- Fastify
- MCP TypeScript SDK v2 Streamable HTTP
- Railway deployment from GitHub
- production replica pinned to Railway Southeast Asia
- production source tracks canonical GitHub `main` with automatic deploys; normal operation must not pin a commit SHA
- no local user installation required

## HTTP surface

- `GET /health`
- `GET /capabilities`
- `POST /research/market`
- `POST /research/token`
- `POST /research/news`
- `POST /research/risk`
- `/mcp` — remote read-only MCP endpoint

`/research/market` implements `snapshot`, `candles`, `orderbook`, `funding_oi`, and `execution_quote`. Unsupported safe research capabilities return `501 capability_not_available` rather than guessed data.

## Venue-bound live execution quotes

`execution_quote` is the price-verification surface for market-entry analysis. It is read-only and never places an order.

Request fields:

```json
{
  "action": "execution_quote",
  "symbol": "BTCUSDT",
  "instrument": "perpetual",
  "side": "LONG",
  "executionVenue": "bybit"
}
```

Rules:

- Production-style perpetual execution defaults to **Bybit** when `executionVenue` is omitted, following current Trading authority.
- Explicit `executionVenue: "binance"` binds the executable quote to Binance USD-M.
- MARKET **LONG** uses the execution venue's **ask**.
- MARKET **SHORT** uses the execution venue's **bid**.
- `last`, `mark`, `index`, and `mid` are context only and can never masquerade as the executable market-entry price.
- Spot and Perpetual observations are never mixed.
- The execution venue must supply its own valid executable quote. A secondary venue can cross-check but never silently replaces the requested venue.
- Source and receive timestamps are preserved separately and `quoteAgeMs` is returned.
- Executable freshness target is <=2,000 ms; quotes older than 5,000 ms fail closed as `STALE_PRICE`.
- Contextual mark/index data older than 10,000 ms is omitted from the execution quote.
- Same-semantic cross-venue deviation above 30 bps fails closed as `PRICE_DIVERGENCE`.
- Missing/invalid source timestamps, crossed books, or semantic mismatches fail closed.

A successful response includes `venue`, `symbol`, `instrumentType`, `side`, `executableSemantic`, `executablePrice`, `bid`, `ask`, `mid`, optional `last`/`mark`/`index`, `sourceTimestampMs`, `receivedTimestampMs`, `quoteAgeMs`, `spreadBps`, `fresh`, `executionVerified`, `status`, and same-semantic `crossVenue` evidence.

Fail-closed statuses include:

- `STALE_PRICE`
- `PRICE_DIVERGENCE`
- `SEMANTIC_MISMATCH`
- `VENUE_UNAVAILABLE`

If any of those states is material to a market entry, the caller must not present the disputed price as a verified MARKET entry.

## Providers

Credentialless public adapters:
- Binance
- OKX
- Bybit, subject to Bybit's regional API restrictions
- Gate
- KuCoin

For executable price semantics, Bybit and Binance are first-class venue-bound sources. Generic provider ranking remains available for broader research and does not determine execution venue.

Bybit HTTP 403 from a provider-restricted cloud region is classified as `region_restricted_bybit_cloud_region`. Binance USD-M HTTP 451 from a restricted cloud region is classified as `region_restricted_binance_futures_cloud_region`. The service never attempts to bypass provider geographic restrictions. When the requested execution venue is unavailable, the gateway returns `VENUE_UNAVAILABLE` rather than substituting another venue.

## Safety

The gateway does not expose order placement, cancellation, leverage mutation, account mutation, wallet actions, transfers, withdrawals, swaps, bridges, signing/broadcasting, payments, or DeFi/earn financial actions.

Provider data is evidence only. Canonical reasoning and conflict resolution remain controlled by GitHub Brain policy.

## Secrets

Default public research uses zero exchange credentials. Future authenticated read-only support, if separately authorized, must use Railway secret storage and restricted read-only permissions.

## Deployment verification

Pre-merge verification runs the exact feature-branch build in GitHub Actions. CI validates policy, unit behavior, typecheck/build, Brain/registry/router/V4/authority contracts, public provider health, and live venue-bound execution quotes. GitHub-hosted US runners may classify Bybit or Binance Futures as explicitly region-restricted; only the exact known restriction classifications are accepted, and no proxy or geographic bypass is used.

Railway production is sourced from the canonical repository `main` branch, deploys automatically from GitHub pushes that affect the service root, and runs in Southeast Asia. Manual exact-commit pins are recovery-only and do not satisfy the normal production deployment contract. `/health` exposes the nonsecret `RAILWAY_GIT_COMMIT_SHA` as `deploymentCommitSha`, allowing post-merge CI to wait for the exact GitHub-triggered production revision rather than smoke-testing an older deployment.

After every relevant push to `main`, the production smoke job waits for `deploymentCommitSha == GITHUB_SHA`, confirms the Railway upstream zone is Southeast Asia, verifies `/capabilities` remains read-only, and POSTs live `execution_quote` requests for BTCUSDT and SOLUSDT against both Bybit Linear and Binance USD-M. Both venues must return verified bid/ask execution quotes within the 5-second hard freshness gate.

Completion requires the canonical Railway deployment to report `SUCCESS`, exact-commit production smoke to pass, `/health` to preserve `localInstallRequired: false`, `/capabilities` to expose read-only tools only, the execution-quote path to retain fail-closed semantics, and post-merge GitHub CI to remain green.
