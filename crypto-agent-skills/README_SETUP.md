# Crypto Agent Skills — Zero-Local Research Runtime

Setup date: 2026-09-12

Status: **GITHUB BRAIN + CLOUD RUNTIME / RESEARCH-ONLY**

Normal crypto research does **not** require Node, npm, Python, provider skill packages, exchange CLIs, or a local MCP server on the user's computer.

## Runtime path

```text
User / ChatGPT
  -> GitHub checkpoint
  -> skill registry + task_router
  -> canonical reasoning skill
  -> approved RESEARCH_SAFE capability
  -> Railway crypto-research-gateway
  -> public first-party provider API
  -> normalized evidence + conflict policy
  -> answer
```

GitHub remains the canonical control plane. Railway is execution only. Provider output is evidence, not independent reasoning authority.

## Canonical files

- `AI_SKILL_LIBRARY/checkpoint.json` — discovery root.
- `AI_SKILL_LIBRARY/skills/registry/index.yaml` — lightweight lookup for every request.
- `AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml` — provider capability identity/risk metadata.
- `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml` — semantic normalization and conflict handling.
- `AI_SKILL_LIBRARY/skills/registry/runtime_policy.yaml` — zero-local execution precedence.
- `AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml` — cloud runtime manifest.
- `crypto-research-gateway/` — read-only Node.js 22 cloud gateway.

## Provider execution state

| Provider | GitHub registry | Default cloud research |
|---|---|---|
| Binance | integrated | public market data enabled |
| OKX | integrated | public CEX market data enabled |
| Bybit | integrated | public market data enabled only where the cloud region is permitted by Bybit; regional 403 is reported explicitly and is never bypassed |
| Gate | integrated | public market data enabled |
| KuCoin | integrated | public market data enabled |
| Coinbase | integrated | reference/query metadata only until a clearly isolated credentialless read adapter is approved |

## Cloud capabilities

Executable default research surface:
- market snapshot;
- candles/K-line;
- order book;
- derivatives funding/open-interest context where the provider exposes it publicly.

The remote MCP surface exposes only read-only tool names. Token/news/risk tools that do not yet have a safe public adapter return `capability_not_available` rather than simulated data.

## Restrictions

`AUTH_READ_ONLY` remains disabled until separate credential authorization. If enabled later, secrets must live only in cloud secret storage with read/query scope and no withdrawal/write permission.

`HIGH_RISK` has no executable zero-local route. This includes live orders, cancel/amend/close, leverage/account mutation, wallet actions, transfers, withdrawals, swaps, bridges, transaction signing/broadcasting, payments and DeFi/earn financial actions.

## Conflict handling

Provider results are not votes. The gateway preserves venue/instrument/price semantics/timestamps, and the Brain applies `conflict_policy.yaml`. Spot/perpetual and last/mark/index are never silently merged. Material unresolved divergence blocks the dependent high-consequence conclusion.

## Credentials

Default public research uses no exchange API key. No API secret, private key, seed phrase, OAuth token or wallet credential belongs in GitHub.

## Local installation

**Required for normal research: NO.**

Local diagnostics in older setup notes are developer troubleshooting only and are not part of the runtime path.
