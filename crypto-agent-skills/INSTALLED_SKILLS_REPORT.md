# INSTALLED_SKILLS_REPORT

Report date: 2026-09-12

## Status semantics

- **registry-integrated** — capability is normalized in the GitHub Brain registry and can be discovered/routed according to its risk mode.
- **prepared-local** — official install/reference instructions are known, but installation in the user's actual local CLI has not been verified.
- **requires confirmation** — authenticated read-only or HIGH-RISK activation requires a separate explicit authorization.
- **skipped/obsolete-name** — requested legacy name is not a current standalone upstream skill; current replacement is registered instead.

Repository registry integration does **not** mean a package is installed on the user's Mac/Windows/Linux machine.

| Provider / capability | Official source | GitHub status | Mode | Use case | Risk | API key | Real-fund impact |
|---|---|---|---|---|---|---|---|
| Binance `crypto-market-rank` | https://github.com/binance/binance-skills-hub | registry-integrated | RESEARCH_SAFE | market rank / inflow / smart money | LOW | public default | No |
| Binance `query-token-info` | same | registry-integrated | RESEARCH_SAFE | token research / market data | LOW | public default | No |
| Binance `query-token-audit` | same | registry-integrated | RESEARCH_SAFE | token risk / honeypot / scam | LOW | public default | No |
| Binance `query-address-info` | same | registry-integrated | RESEARCH_SAFE | public-wallet observation | LOW | public default | No |
| Binance trading-signal research | same | registry-integrated | RESEARCH_SAFE | signal/watchlist research | MEDIUM | endpoint-dependent | No |
| Binance wallet/payment/trading execution | same | registry-integrated, disabled | HIGH_RISK | wallet / trading / transfer / payment | HIGH | Yes/auth | Yes |
| OKX CEX market | https://github.com/okx/agent-skills | registry-integrated | RESEARCH_SAFE | ticker / orderbook / candle / funding / OI | LOW | No | No |
| OKX Agent Trade Kit market/news | https://github.com/okx/agent-trade-kit | registry-integrated | RESEARCH_SAFE | market / derivatives / news | LOW | endpoint-dependent | No |
| OKX sentiment/smart-money private analytics | https://github.com/okx/agent-skills | registry-integrated, gated | AUTH_READ_ONLY | sentiment / smart money | MEDIUM | Yes | No |
| OKX DEX market research | https://github.com/okx/onchainos-skills | registry-integrated, gated | AUTH_READ_ONLY | on-chain market / holders / whales | MEDIUM | Yes/sandbox | No |
| OKX CEX trade/bot/account mutation | OKX official repos | registry-integrated, disabled | HIGH_RISK | order/account/bot/earn action | HIGH | Yes | Yes |
| OKX Agentic Wallet / DeFi / payments | https://github.com/okx/onchainos-skills | registry-integrated, disabled | HIGH_RISK | send / swap / bridge / broadcast / DeFi / payment | HIGH | Yes | Yes |
| Bybit Market module | https://github.com/bybit-exchange/skills | registry-integrated | RESEARCH_SAFE | K-line / ticker / orderbook / funding / OI | MEDIUM | No for public market | No |
| Bybit Spot/Derivatives writes/Account/Earn/Bot/Copy/Alpha/Pay/Fiat | same | registry-integrated, disabled | HIGH_RISK | trading / account / payment | HIGH | Yes | Yes |
| Gate public Market MCP | https://github.com/gate/gate-mcp | registry-integrated | RESEARCH_SAFE | market / futures data | LOW | No | No |
| Gate Info research/risk/macro/on-chain | https://github.com/gate/gate-skills | registry-integrated | RESEARCH_SAFE | research / risk / macro / flow | LOW | public surfaces | No |
| Gate News research | same | registry-integrated | RESEARCH_SAFE | news / sentiment / event explain | LOW | No | No |
| Gate DEX market | same | registry-integrated | RESEARCH_SAFE | on-chain market / audit | MEDIUM | surface-dependent | No |
| Gate private account queries | Gate official repos | registry-integrated, gated | AUTH_READ_ONLY | balances / positions / assets | MEDIUM | OAuth/restricted auth | No |
| Gate exchange/futures/DEX trade/wallet/transfer/pay/earn actions | Gate official repos | registry-integrated, disabled | HIGH_RISK | financial writes | HIGH | Yes/OAuth | Yes |
| KuCoin public spot/margin/futures GET | https://github.com/Kucoin/kucoin-skills-hub | registry-integrated | RESEARCH_SAFE | market / futures / funding / risk limits | LOW | No for public | No |
| KuCoin private GET queries | same | registry-integrated, gated | AUTH_READ_ONLY | assets / orders / positions / earn / broker | MEDIUM | Yes | No |
| KuCoin future write endpoints if upstream changes | same | guard registered | HIGH_RISK | future order/transfer writes | HIGH | Yes | Yes |
| Coinbase read-only on-chain query reference | https://github.com/coinbase/agentic-wallet-skills | registry-integrated, gated | AUTH_READ_ONLY | on-chain research | MEDIUM | Yes | No |
| Coinbase Agentic Wallet actions | same | registry-integrated, disabled | HIGH_RISK | wallet / send / trade / fund / pay | HIGH | Yes/auth | Yes |
| Coinbase AgentKit wallet/action providers | https://github.com/coinbase/agentkit | registry-integrated, disabled | HIGH_RISK | on-chain/wallet actions | HIGH | Yes | Yes |

## Conflict harmonization

Provider capabilities do not become independent reasoning skills. `task_router` still selects one primary reasoning path and bounded supporting skills. Provider outputs are reconciled through `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml` using semantic normalization, authority and freshness—not majority voting.

Material unresolved conflict is disclosed and blocks dependent high-consequence conclusions. Credible security/risk warnings are not canceled merely because another provider reports a benign result.

## Research-ready in GitHub

Immediately discoverable at repository-routing level without live-trading credentials: public market data, K-line/ticker/orderbook, funding/OI, token info, token audit/risk research, public-address observation, public news/macro/sentiment, public Gate research, current KuCoin GET-only public market data, and Trading Plan research workflows.

## Authenticated read-only

Registered but not auto-activated: OKX authenticated sentiment/smart-money/on-chain research, Gate private account queries, KuCoin private GET queries, Coinbase query-only service references and similar private read endpoints. Any future credential must be separately authorized, restricted to read/query permissions and have no withdrawal permission.

## HIGH_RISK

Registered for correct classification but not activated: live orders, cancel/amend/close, leverage/account mutation, wallet auth/creation, transfer/withdrawal, swaps/bridges, signing/broadcast, payments, DeFi/earn financial actions and agentic wallet actions.

## Local installation status

Local Node/npm/npx/Claude Code/Codex/Cursor/OpenClaw installations remain **prepared-local / unverified** because this hosted session cannot inspect the user's actual machine. No live credential was configured.
