# INSTALLED_SKILLS_REPORT

Report date: 2026-09-12

Interpretation of status:
- **installed** — installed and verified in the actual local agent runtime.
- **prepared** — official source and safe routing/configuration have been prepared in this repository, but local runtime installation has not been verified from this hosted session.
- **skipped** — intentionally not prepared because the requested capability/name is obsolete, unavailable, or unsafe for this phase.
- **requires confirmation** — a later step would require authenticated access or activation of a higher-risk capability.

| Provider / skill or source | Official source | Status | Use case | Risk | API key needed? | Can affect real funds? | Notes |
|---|---|---|---|---|---|---|---|
| Binance `crypto-market-rank` | https://github.com/binance/binance-skills-hub | prepared | market data / smart money | LOW | No/depends on upstream endpoint | No | Research routing only. |
| Binance `query-token-info` | https://github.com/binance/binance-skills-hub | prepared | token research / market data | LOW | No/depends on upstream endpoint | No | Token metadata + dynamic market data. |
| Binance `query-token-audit` | https://github.com/binance/binance-skills-hub | prepared | risk check | LOW | No/depends on upstream endpoint | No | Contract/scam/honeypot risk research. |
| Binance `query-address-info` | https://github.com/binance/binance-skills-hub | prepared | smart money / wallet observation | LOW | No/depends on upstream endpoint | No | Public-address holdings snapshot; no wallet action. |
| Binance `binance-trading-signal` | https://github.com/binance/binance-skills-hub | prepared | signal research / watchlist | MEDIUM | Depends on signal functions | No when constrained to analysis | Strategy/signal research only; no wallet/trading module routing. |
| Binance broad CEX/wallet/trading capabilities | https://github.com/binance/binance-skills-hub | requires confirmation | trading / wallet | HIGH | Yes for private actions | Yes | Not activated. Payment, transfer, wallet and execution paths remain blocked. |
| OKX `okx-cex-market` | https://github.com/okx/agent-skills | prepared | market data / futures data | LOW | No | No | Public prices, ticker, order book, candles, funding, OI, indicators. |
| OKX `okx-sentiment-tracker` | https://github.com/okx/agent-skills | requires confirmation | sentiment / news | MEDIUM | Current README says auth required | No if strictly query-only | Requires a later restricted-auth decision. |
| OKX `okx-cex-smartmoney` | https://github.com/okx/agent-skills | requires confirmation | smart money | MEDIUM | Yes | No if strictly query-only | Authenticated analytics; no execution activation. |
| OKX requested `okx-cex-news` | https://github.com/okx/agent-skills | skipped | news | LOW | N/A | No | Not found as a current standalone skill in the verified upstream `agent-skills` repo; current Agent Trade Kit exposes a `news` module instead. |
| OKX Agent Trade Kit `market` module | https://github.com/okx/agent-trade-kit | prepared | market data / futures data | LOW | No | No | Upstream supports `--modules market` and `--read-only`; package not locally installed/verified here. |
| OKX Agent Trade Kit `news` module | https://github.com/okx/agent-trade-kit | prepared | sentiment / news | LOW to MEDIUM | Depends on endpoint | No when read-only | Use query tools only. |
| OKX `okx-dex-market` | https://github.com/okx/onchainos-skills | prepared | token research / smart money / on-chain market | MEDIUM | Current upstream says OnchainOS skills require OKX API credentials; sandbox may exist | No when constrained to read-only market functions | Read-only path only; no wallet handoff. |
| OKX `okx-agentic-wallet` | https://github.com/okx/onchainos-skills | requires confirmation | wallet / swap / bridge / broadcast | HIGH | Yes | Yes | Disabled. Includes fund-moving and transaction capabilities. |
| OKX `okx-defi` / payment actions | https://github.com/okx/onchainos-skills | requires confirmation | DeFi / payment | HIGH | Yes | Yes | Disabled. |
| Bybit Market module | https://github.com/bybit-exchange/skills | prepared | market data / futures data | MEDIUM | Public market calls do not require private key | No for market calls | Only ticker/K-line/orderbook/funding/OI/volatility research is allowed. Full skill is mixed read/write. |
| Bybit Spot / Derivatives / Account / Earn / Strategy / Bot / Copy / Alpha Trade / Pay / Fiat | https://github.com/bybit-exchange/skills | requires confirmation | trading / wallet / account | HIGH | Yes | Yes | Disabled; no API credentials configured. |
| Gate public Market MCP | https://github.com/gate/gate-mcp | prepared | market data / futures data | LOW | No | No | Public MCP endpoint only. |
| Gate Info MCP + `gate-info-*` research skills | https://github.com/gate/gate-mcp ; https://github.com/gate/gate-skills | prepared | token research / risk check / macro | LOW | No for public Info endpoint | No | Includes coin analysis, compare, risk check, macro impact, research. |
| Gate News MCP + `gate-news-*` skills | https://github.com/gate/gate-mcp ; https://github.com/gate/gate-skills | prepared | sentiment / news | LOW | No | No | Briefing, community scan, event explanation. |
| Gate Docs MCP | https://github.com/gate/gate-mcp | prepared | research / documentation | LOW | No | No | Public research/docs surface. |
| Gate `gate-dex-market` | https://github.com/gate/gate-skills | prepared | on-chain market data / risk | MEDIUM | Depends on selected read-only path | No when market-data-only | DEX trade/wallet routes are blocked. |
| Gate `/mcp/exchange`, `gate-dex-trade`, wallet, transfer, pay, futures execution | https://github.com/gate/gate-mcp ; https://github.com/gate/gate-skills | requires confirmation | trading / wallet | HIGH | Yes / OAuth | Yes | Not activated. |
| KuCoin `spot` | https://github.com/Kucoin/kucoin-skills-hub | prepared | market data | LOW | Public data no; private order-query data yes | No | Current Skills Hub is GET-only. |
| KuCoin `margin-trading` | https://github.com/Kucoin/kucoin-skills-hub | prepared | market data / risk | MEDIUM | Some account queries require API key | No in current GET-only hub | No write operations in current hub. |
| KuCoin `futures-trading` | https://github.com/Kucoin/kucoin-skills-hub | prepared | futures data | MEDIUM | Public data no; private query data yes | No in current GET-only hub | GET-only current upstream. |
| KuCoin `assets` | https://github.com/Kucoin/kucoin-skills-hub | requires confirmation | account/assets query | MEDIUM | Yes for private account data | No in current GET-only hub | If enabled later, use restricted read-only key with no withdrawal permission. |
| KuCoin `earn`, `convert`, `broker` | https://github.com/Kucoin/kucoin-skills-hub | prepared | product/account research | MEDIUM | Some private queries require API key | No in current GET-only hub | Query-only current upstream. |
| Coinbase Agentic Wallet Skills | https://github.com/coinbase/agentic-wallet-skills | requires confirmation | wallet / trading / payment | HIGH | Wallet auth/CDP depending on action | Yes | Documentation only. No wallet creation/login/send/trade/pay. |
| Coinbase AgentKit | https://github.com/coinbase/agentkit | requires confirmation | wallet / on-chain actions | HIGH | Yes for wallet/provider use | Yes | Documentation only. AgentKit itself warns that wallet actions can move funds; not activated. |

## Research-ready categories

Prepared without live trading credentials: public market data, token information, token/security research, public wallet/address observation, macro/news/sentiment sources that require no auth, funding/open-interest/futures-market data, and plan drafting.

## Authenticated read-only categories

Not activated yet: OKX authenticated sentiment/smart-money endpoints, KuCoin private account/order/position query endpoints, and any other capability whose upstream requires a key even for reads. If enabled later, the credential must be scoped to read/query only and have no withdrawal permission.

## HIGH RISK categories

Not activated: any live trading, order management, leverage/account-mode changes, wallet authentication or creation, transfers/withdrawals, swaps/bridges, transaction signing/broadcasting, payments, staking/DeFi investment, earn purchase/redeem, and agentic wallet actions.
