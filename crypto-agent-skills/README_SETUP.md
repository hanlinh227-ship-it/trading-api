# Crypto Agent Skills — Research-Only Setup

Setup date: 2026-09-12

Status: **PREPARED / RESEARCH-ONLY**

This workspace is intentionally configured as a documentation, routing, and safety layer for crypto-market research. It does **not** activate live-trading credentials, wallet authentication, withdrawals, swaps, bridges, transaction broadcasting, payments, or automated order placement.

## Workspace

- `docs/` — official-source notes and capability references.
- `config/` — explicit research allowlist and HIGH-RISK blocklist.
- `notes/` — operator notes/checkpoint area; no secrets allowed.
- `INSTALLED_SKILLS_REPORT.md` — provider/capability status matrix.
- `AGENT_USAGE_GUIDE.md` — Vietnamese research workflows and prompt templates.
- `SETUP_ERRORS.md` — unresolved local-runtime checks and setup errors.
- `SAFETY_RULES.md` — mandatory operating rules.

## Current preparation state

| Provider | State | Research scope prepared | Live execution |
|---|---|---|---|
| Binance | prepared | market rank, token info, token audit, address info, signal research | disabled |
| OKX CEX | prepared | public market data and read-only analysis | disabled |
| OKX OnchainOS | prepared-docs | read-only DEX market research only | wallet/action paths disabled |
| Bybit | prepared-docs | Market module reference only | spot/derivatives/account/earn/actions disabled |
| Gate | prepared | public market, info, news, docs endpoints | exchange/DEX action endpoints disabled |
| KuCoin | prepared | current GET/read-only Skills Hub | write actions unavailable in current upstream hub |
| Coinbase | prepared-docs | documentation/reference only | wallet/auth/send/trade/pay/onchain actions disabled |

`installed` is reserved for a package/skill that has actually been installed and verified in the user's local agent runtime. This hosted ChatGPT session cannot truthfully assert that state for the user's Mac/Windows/Linux machine, so local-runtime components remain `prepared` until verified there.

## Credential policy

No real API key, API secret, private key, seed phrase, passphrase, OAuth token, session token, or wallet credential has been added by this setup.

If authenticated read-only data is required later, use the minimum possible permissions, preferably a dedicated sub-account/API key with **no withdrawal permission**. Live trading remains a separate HIGH-RISK activation that requires a new explicit authorization.

## Local verification still required

Run the commands documented in `SETUP_ERRORS.md` from the actual machine that hosts Claude Code, Codex CLI, Cursor, OpenClaw, or another agent client. Those commands only inspect versions/availability and do not authenticate or trade.
