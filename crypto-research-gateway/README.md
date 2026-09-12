# Crypto Research Gateway

Read-only cloud execution runtime for GitHub Brain crypto research.

## Runtime

- Node.js 22+
- TypeScript
- Fastify
- MCP TypeScript SDK v2 Streamable HTTP
- Railway deployment from GitHub
- no local user installation required

## HTTP surface

- `GET /health`
- `GET /capabilities`
- `POST /research/market`
- `POST /research/token`
- `POST /research/news`
- `POST /research/risk`
- `/mcp` — remote read-only MCP endpoint

`/research/market` currently implements `snapshot`, `candles`, `orderbook`, and `funding_oi`. Unsupported safe research capabilities return `501 capability_not_available` rather than guessed data.

## Providers

Credentialless public adapters:
- Binance
- OKX
- Bybit, subject to Bybit's regional API restrictions
- Gate
- KuCoin

Bybit HTTP 403 from a provider-restricted cloud region is classified as `region_restricted_bybit_cloud_region`; the service never attempts to bypass provider geographic restrictions.

## Safety

The gateway does not expose order placement, cancellation, leverage mutation, account mutation, wallet actions, transfers, withdrawals, swaps, bridges, signing/broadcasting, payments, or DeFi/earn financial actions.

Provider data is evidence only. Canonical reasoning and conflict resolution remain controlled by GitHub Brain policy.

## Secrets

Default public research uses zero exchange credentials. Future authenticated read-only support, if separately authorized, must use Railway secret storage and restricted read-only permissions.
