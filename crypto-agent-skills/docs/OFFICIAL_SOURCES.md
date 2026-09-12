# Official Sources

Verified during the 2026-09-12 setup work cycle.

## Binance

- Skills Hub: https://github.com/binance/binance-skills-hub
- Current README requirement: Node.js 22+ for the Skills Hub installer.
- Official install command documented upstream: `npx skills add https://github.com/binance/binance-skills-hub`
- Research skills verified in the repository:
  - `crypto-market-rank`
  - `query-token-info`
  - `query-token-audit`
  - `query-address-info`
  - `binance-trading-signal`

## OKX

- CEX Agent Skills: https://github.com/okx/agent-skills
- Agent Trade Kit: https://github.com/okx/agent-trade-kit
- OnchainOS Skills: https://github.com/okx/onchainos-skills
- CEX public market skill: `okx-cex-market`.
- Agent Trade Kit documents `--read-only` and `--modules market` modes.
- OnchainOS current upstream consolidates read-only DEX research primarily under `okx-dex-market`; wallet/execution flows are under `okx-agentic-wallet` and remain disabled here.

## Bybit

- Skills: https://github.com/bybit-exchange/skills
- Current skill contains a Market module for ticker, K-line, order book, funding rate, open interest and volatility, but the same skill also contains write-capable trading/account modules. This workspace therefore treats Bybit as documentation/market-module preparation only until a safe local routing boundary is verified.

## Gate

- Skills: https://github.com/gate/gate-skills
- MCP: https://github.com/gate/gate-mcp
- Public/no-auth MCP surfaces documented upstream:
  - `https://api.gatemcp.ai/mcp` — public market data
  - `https://api.gatemcp.ai/mcp/info` — info/analysis
  - `https://api.gatemcp.ai/mcp/news` — news/sentiment/events
  - `https://api.gatemcp.ai/mcp/docs` — research/docs
- Private exchange and DEX action endpoints are not activated by this setup.

## KuCoin

- Skills Hub: https://github.com/Kucoin/kucoin-skills-hub
- Official docs: https://www.kucoin.com/docs-new/kucoin_skills_hub
- Current upstream states that the skills support GET/read-only endpoints only; placing/cancelling orders and transfers are not supported by the current Skills Hub.
- Official full-depth installer documented upstream: `npx skills add https://github.com/Kucoin/kucoin-skills-hub --full-depth`

## Coinbase

- Agentic Wallet Skills: https://github.com/coinbase/agentic-wallet-skills
- AgentKit: https://github.com/coinbase/agentkit
- Agentic Wallet MCP docs: https://docs.cdp.coinbase.com/agentic-wallet/mcp/welcome
- These projects include wallet authentication, sending assets, trading and payment/on-chain actions. They are HIGH RISK in this workspace and are documentation-only until separately authorized.

## Source precedence

When a capability changes upstream, re-read the current official README/SKILL documentation before enabling it. Official upstream capability documentation does not override this workspace's safety blocklist or the repository's current Brain/security authority.
