# INSTALLED_SKILLS_REPORT

Report date: 2026-09-12

## Status semantics

- **registry-integrated** — capability is normalized in GitHub Brain.
- **cloud-executable** — implemented in the zero-local Railway gateway with no local package requirement.
- **cloud-gated** — known but disabled until separate read-only authorization.
- **cloud-disabled** — HIGH_RISK; no executable cloud adapter exists.
- **region-restricted** — provider policy blocks the current cloud region; the runtime reports this and does not bypass the restriction.

Repository/cloud integration does **not** require installation on the user's Mac/Windows/Linux machine.

| Provider / capability | GitHub | Cloud runtime | Mode | Credential | Real-fund impact |
|---|---|---|---|---|---|
| Binance public market snapshot/K-line/orderbook | registry-integrated | cloud-executable | RESEARCH_SAFE | None | No |
| Binance public derivatives context | registry-integrated | cloud-executable | RESEARCH_SAFE | None | No |
| Binance token/audit/address/signal metadata | registry-integrated | adapter-dependent | RESEARCH_SAFE | endpoint-dependent | No |
| Binance wallet/payment/trading execution | registry-integrated | cloud-disabled | HIGH_RISK | auth | Yes |
| OKX public CEX market/K-line/orderbook/funding/OI | registry-integrated | cloud-executable | RESEARCH_SAFE | None | No |
| OKX private sentiment/smart-money/on-chain analytics | registry-integrated | cloud-gated | AUTH_READ_ONLY | Restricted read-only | No |
| OKX trade/bot/account/wallet/DeFi/payment writes | registry-integrated | cloud-disabled | HIGH_RISK | auth | Yes |
| Bybit public Market V5 | registry-integrated | cloud-executable where provider permits cloud region; otherwise region-restricted | RESEARCH_SAFE | None | No |
| Bybit account/trading/earn/bot/copy/pay writes | registry-integrated | cloud-disabled | HIGH_RISK | auth | Yes |
| Gate public market | registry-integrated | cloud-executable | RESEARCH_SAFE | None | No |
| Gate public info/news/research metadata | registry-integrated | adapter-dependent | RESEARCH_SAFE | None/public | No |
| Gate private account reads | registry-integrated | cloud-gated | AUTH_READ_ONLY | Restricted auth | No |
| Gate financial writes | registry-integrated | cloud-disabled | HIGH_RISK | auth | Yes |
| KuCoin public spot/futures market GET | registry-integrated | cloud-executable | RESEARCH_SAFE | None | No |
| KuCoin private GET queries | registry-integrated | cloud-gated | AUTH_READ_ONLY | Restricted read-only | No |
| KuCoin future writes if upstream changes | guard registered | cloud-disabled | HIGH_RISK | auth | Yes |
| Coinbase isolated read references | registry-integrated | cloud-gated/reference-only | AUTH_READ_ONLY | Depends on approved endpoint | No |
| Coinbase Agentic Wallet / AgentKit actions | registry-integrated | cloud-disabled | HIGH_RISK | auth/wallet | Yes |

## Current executable gateway tools

- `market_snapshot`
- `market_candles`
- `market_orderbook`
- `derivatives_funding_oi`

The MCP registry also reserves read-only names `token_research`, `token_risk_check`, and `crypto_news_research`, but these return explicit `capability_not_available` until a credentialless or separately approved read-only adapter is implemented. They never fabricate results.

## Conflict harmonization

`task_router` remains the reasoning authority. Provider adapters supply evidence only. Evidence is normalized by symbol, venue, instrument, quote currency, price semantic, source timestamp and unit before comparison. No majority vote and no silent price averaging are allowed.

## Bybit regional behavior

Bybit's current official API guidance states that requests from US or Mainland China IP addresses receive HTTP 403. When the cloud host is in a restricted region, the gateway reports `region_restricted_bybit_cloud_region`; it does not use proxies, alternate geography tricks, or other bypasses. Other approved providers remain available as evidence sources.

## AUTH_READ_ONLY

Disabled by default. Any future activation requires separate authorization and cloud-only secret storage with read/query permissions and no withdrawal, transfer, order or other write scope.

## HIGH_RISK

No executable zero-local route exists for live orders, cancel/amend/close, leverage/account mutation, wallet authentication/creation, transfers, withdrawals, swaps, bridges, signing/broadcast, payments or DeFi/earn financial actions.

## Local installation status

**Normal research local installation required: NO.**

No local provider CLI/MCP/package is part of the runtime path, and no live credential has been configured by this project.
