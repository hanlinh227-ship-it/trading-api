# Crypto Agent Skills — Research-Only Setup

Setup date: 2026-09-12

Status: **GITHUB REGISTRY INTEGRATED / RESEARCH-ONLY**

This workspace is intentionally configured as a documentation, routing, and safety layer for crypto-market research. It does **not** activate live-trading credentials, wallet authentication, withdrawals, swaps, bridges, transaction broadcasting, payments, or automated order placement.

## GitHub Brain integration

The repository-level skill registry is integrated on branch `crypto-agent-registry-v4`:

- `AI_SKILL_LIBRARY/checkpoint.json` exposes the current registry, provider-registry, conflict-policy, source-registry and validator pointers.
- `AI_SKILL_LIBRARY/skills/registry/index.yaml` is the small lookup surface consulted by `task_router` for every request.
- `AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml` normalizes Binance, OKX, Bybit, Gate, KuCoin and Coinbase provider capabilities.
- `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml` prevents majority-vote/averaging conflicts and applies authority/freshness/semantic reconciliation.
- `AI_SKILL_LIBRARY/sources/crypto_agent_official.yaml` records official provider sources as reference-only, training disabled.
- `AI_SKILL_LIBRARY/validate_skill_registry.py` and `.github/workflows/crypto-skill-registry-validate.yml` enforce safety and regression invariants.

Provider capabilities are metadata/evidence adapters only. They do not become independent reasoning authorities and do not replace the existing one-primary-skill + bounded-supporting-skills route.

## Workspace

- `docs/` — official-source notes and capability references.
- `config/` — explicit research allowlist and HIGH-RISK blocklist.
- `notes/` — operator notes/checkpoint area; no secrets allowed.
- `INSTALLED_SKILLS_REPORT.md` — provider/capability status matrix.
- `AGENT_USAGE_GUIDE.md` — Vietnamese research workflows and prompt templates.
- `SETUP_ERRORS.md` — unresolved local-runtime checks and setup errors.
- `SAFETY_RULES.md` — mandatory operating rules.

## Current preparation state

| Provider | GitHub registry | Research scope prepared | Live execution |
|---|---|---|---|
| Binance | integrated | market rank, token info, token audit, address info, signal research | disabled |
| OKX CEX | integrated | public market data and read-only analysis | disabled |
| OKX OnchainOS | integrated | DEX/on-chain research metadata; auth-read-only gated | wallet/action paths disabled |
| Bybit | integrated | public Market module separated from mixed write modules | spot/derivatives/account/earn/actions disabled |
| Gate | integrated | public market, info, news, docs and research skills | exchange/DEX action endpoints disabled |
| KuCoin | integrated | current GET/read-only Skills Hub + future write guard | write actions quarantined if upstream changes |
| Coinbase | integrated | query reference metadata | wallet/auth/send/trade/pay/onchain actions disabled |

`installed` is reserved for a package/skill that has actually been installed and verified in the user's local agent runtime. Repository registry integration does not imply local CLI/package installation. Local-runtime components remain `prepared` until verified on the actual Mac/Windows/Linux host.

## Conflict handling

The system does not combine contradictory provider opinions by voting. It first normalizes token identity, chain, venue, instrument type, quote currency, price semantics, timestamps/windows and units. Then it applies current runtime/project authority and current first-party evidence precedence. Material unresolved conflict is disclosed and blocks dependent high-consequence conclusions.

A credible security/risk warning is asymmetric: a benign result from another provider does not automatically cancel the warning.

## Credential policy

No real API key, API secret, private key, seed phrase, passphrase, OAuth token, session token, or wallet credential has been added by this setup.

If authenticated read-only data is required later, use the minimum possible permissions, preferably a dedicated sub-account/API key with **no withdrawal permission**. Live trading remains a separate HIGH-RISK activation that requires a new explicit authorization.

## Verification

GitHub Actions regression CI validates:
- skill-registry safety tests;
- provider registry invariants;
- Brain validator;
- router validator;
- V4 validator;
- authority validator.

Local environment/version checks remain documented in `SETUP_ERRORS.md` because a hosted ChatGPT session cannot prove the user's actual local CLI installation state.
