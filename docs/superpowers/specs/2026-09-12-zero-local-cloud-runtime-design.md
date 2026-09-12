# Zero-Local Cloud Runtime Design

**Date:** 2026-09-12  
**Status:** APPROVAL-PENDING IMPLEMENTATION  
**Repository:** `hanlinh227-ship-it/trading-api`  
**Branch:** `zero-local-cloud-runtime-20260912`

## 1. Goal

Make the crypto research skill system usable without installing Node, npm, Python, MCP servers, exchange skill packages, Claude CLI, Codex CLI, Cursor extensions, or any other runtime on the user's computer.

GitHub remains the canonical brain/control plane. A cloud runtime deployed from GitHub executes approved read-only provider capabilities. The local computer is never required for normal research execution.

## 2. Non-goals

This project does not enable live trading, order placement, cancellation/amendment, wallet authentication, transfers, withdrawals, swaps, bridges, transaction signing/broadcasting, payments, DeFi/earn financial actions, or any other capability that can mutate real financial state.

This project does not store API secrets in GitHub.

This project does not make provider repositories independent reasoning authorities.

## 3. Architectural decision

Use a single GitHub-controlled cloud gateway deployed to Railway.

```text
User / ChatGPT
    -> GitHub checkpoint
    -> skill registry index
    -> task_router
    -> canonical domain skill
    -> provider capability selection
    -> Zero-Local Cloud Gateway
         -> public first-party exchange HTTPS APIs
         -> approved remote read-only MCP/provider adapters
    -> normalize evidence
    -> conflict policy
    -> canonical reasoning skill
    -> answer
```

GitHub is the source of truth for routing, capability metadata, risk classification, validation, deployment configuration, and CI. Railway is the execution runtime only.

## 4. Runtime technology

- Node.js: 22.x
- Language: TypeScript
- HTTP server: Fastify
- Validation: JSON Schema / Zod-compatible runtime validation
- Remote tool surface: Streamable HTTP MCP endpoint where compatible, plus stable read-only HTTP endpoints
- Deployment: Railway from GitHub
- No local runtime dependency

Node 22 is selected because it satisfies the highest known Node requirement among the registered provider ecosystems while remaining compatible with lower Node requirements.

## 5. Repository structure

Create a focused cloud-runtime subsystem:

```text
crypto-research-gateway/
  package.json
  tsconfig.json
  src/
    server.ts
    config.ts
    policy/
      capability-policy.ts
    routing/
      capability-router.ts
    normalization/
      market-normalizer.ts
      conflict-resolver.ts
    providers/
      types.ts
      binance.ts
      okx.ts
      bybit.ts
      gate.ts
      kucoin.ts
    tools/
      market.ts
      token.ts
      news.ts
      risk.ts
    mcp/
      server.ts
    routes/
      health.ts
      capabilities.ts
      research.ts
  test/
    policy.test.ts
    routing.test.ts
    normalization.test.ts
    providers.test.ts
    http.test.ts
  railway.toml
```

Brain policy additions:

```text
AI_SKILL_LIBRARY/
  runtime/
    cloud_runtime.yaml
  skills/registry/
    runtime_policy.yaml
```

The existing provider registry remains canonical for capability identity and risk class.

## 6. Zero-local execution contract

The cloud runtime policy must enforce:

```yaml
local_install_required: false
local_cli_execution: false
local_mcp_server_required: false
cloud_runtime_required_for_provider_execution: true
```

Runtime preference:

1. already-connected cloud plugin/connector when it exactly satisfies the capability;
2. public first-party HTTPS endpoint through the gateway;
3. approved remote read-only MCP/provider surface;
4. fail with an explicit degraded-state message.

There is no fallback to asking the user to install a package locally for normal research execution.

## 7. Capability admission

### RESEARCH_SAFE

May execute automatically in the cloud when the provider adapter is implemented and healthy.

Examples:
- ticker
- K-line/candles
- order book
- funding rate
- open interest
- public instrument metadata
- token metadata
- public token audit/risk signals
- public-address observation when upstream permits it
- public news/macro/sentiment

### AUTH_READ_ONLY

Registered but disabled by default. It can only become active after a separate authorization and only when credentials are stored in Railway secrets/variables, never GitHub.

Credential requirements:
- read/query scope only;
- no withdrawal scope;
- no transfer scope;
- no order/write scope;
- no secret values in logs;
- fail closed if permission scope is ambiguous.

### HIGH_RISK

Must never be implemented as an executable cloud adapter in this project.

The gateway rejects these categories even if an upstream provider exposes them:
- place/cancel/amend/close order;
- leverage or margin-mode mutation;
- wallet creation/auth/export;
- transfer/withdrawal;
- swap/bridge;
- transaction signing/broadcast;
- payment/x402;
- DeFi/earn financial action.

The provider registry may retain these capabilities for classification, but `cloud_execution=false` and `auto_activate=false` are mandatory.

## 8. Provider strategy

The initial executable cloud adapters use public first-party HTTPS APIs directly instead of installing the full upstream skill bundles into the production runtime. The skill repositories remain documentation/capability authorities used by GitHub Brain.

This avoids importing mixed read/write packages into the service and sharply reduces permission surface.

Initial provider adapters:
- Binance public market/research surface
- OKX public CEX market surface
- Bybit public market surface
- Gate public market/info/news surfaces where stable public HTTP/MCP access is available
- KuCoin public GET-only market surface

Coinbase remains query/reference-only unless a clearly isolated non-wallet read-only endpoint is proven during implementation.

## 9. Canonical cloud tool surface

The gateway exposes normalized, provider-neutral tools instead of one tool per upstream skill.

### HTTP

- `GET /health`
- `GET /capabilities`
- `POST /research/market`
- `POST /research/token`
- `POST /research/news`
- `POST /research/risk`

### Remote MCP

Expose equivalent read-only tools through `/mcp` when the client supports Streamable HTTP MCP.

Canonical tools:
- `market_snapshot`
- `market_candles`
- `market_orderbook`
- `derivatives_funding_oi`
- `token_research`
- `token_risk_check`
- `crypto_news_research`

No financial-write MCP tool is registered.

## 10. Request routing

Every provider request carries:
- canonical capability id;
- symbol/token identifier;
- venue preference when specified;
- instrument type;
- quote currency when material;
- timeframe/window;
- freshness requirement.

The router chooses at most three provider candidates, consistent with the current GitHub registry contract.

Selection order:
1. exact capability match;
2. RESEARCH_SAFE only;
3. healthy provider;
4. first-party/public endpoint preferred;
5. freshness and semantic compatibility;
6. deterministic fallback order.

Provider selection never changes the canonical reasoning skill selected by `task_router`.

## 11. Evidence normalization and conflict control

Every returned market observation must normalize:
- provider/venue;
- symbol/contract;
- chain/network where relevant;
- instrument type;
- quote currency;
- price semantic: last/mark/index/bid/ask/mid;
- source timestamp;
- gateway receipt timestamp;
- timeframe/window;
- unit and scale.

Conflicting provider outputs are evidence, not votes.

Rules:
- never majority-vote for truth;
- never silently average conflicting prices;
- prefer fresher data only when authority and semantics are equivalent;
- never treat spot/perpetual/delivery futures/index prices as identical;
- unresolved material live-price divergence blocks a dependent entry conclusion;
- credible security warnings use worst-credible-flag pending investigation.

This reuses the existing `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml` contract rather than introducing a competing consensus mechanism.

## 12. Health and reliability

`GET /health` returns only non-sensitive operational state:
- service version;
- registry version/commit;
- runtime mode;
- provider adapter health;
- last successful public probe timestamp;
- degraded providers.

Health must never return secret values or private account data.

Provider failures use bounded retry and circuit-breaker semantics. Failure of one provider does not fabricate freshness or promote cached data to live state.

If all eligible providers fail, the gateway returns a structured degraded response and the Brain discloses that live evidence is unavailable.

## 13. Secrets

Initial RESEARCH_SAFE deployment must require zero exchange credentials whenever technically possible.

If AUTH_READ_ONLY is added later:
- secrets live only in Railway environment variables/secrets;
- variable values are never committed to GitHub;
- logs redact credential-like fields;
- startup rejects credential sets with unknown/write permissions when scope metadata can be verified;
- credentials are not echoed through `/health`, `/capabilities`, exceptions, or tool results.

## 14. GitHub integration

Add checkpoint pointers for:
- `cloud_runtime_policy_path`
- `cloud_runtime_manifest_path`

Update registry metadata so each executable capability declares a runtime target such as `cloud_gateway` and a `cloud_execution` boolean.

`AGENTS.md` remains version-agnostic and resolves these pointers from `checkpoint.json`.

No immutable Stable hash-pinned release file is edited directly unless the release process explicitly requires a new validated release.

## 15. Deployment model

Railway deploys from the GitHub repository with root directory `crypto-research-gateway`.

Required runtime configuration:
- Node 22
- start command for compiled TypeScript service
- `/health` health check
- restart-on-failure
- continuous service, not cron
- deployment from the canonical GitHub branch only after PR/CI approval

No computer-side daemon is required.

## 16. CI / verification

Behavior changes follow RED -> GREEN.

Required tests:
1. HIGH_RISK capabilities cannot route to executable adapters.
2. RESEARCH_SAFE capabilities can route without local installation metadata.
3. unknown capabilities fail closed.
4. provider failures produce degraded responses, not fabricated live data.
5. spot/perp and last/mark semantics cannot be silently merged.
6. secret-like values cannot appear in health/capability output.
7. cloud policy explicitly forbids local-runtime dependency.
8. existing Brain/registry/authority/V4 validators remain green.

CI stages:
- TypeScript typecheck
- unit tests
- HTTP integration tests
- registry/cloud-policy validator
- existing Brain validators
- build
- optional deployment smoke test against `/health`

## 17. Deployment acceptance criteria

The project is complete only when all are true:
- GitHub `main` contains the zero-local runtime contract;
- Railway service is deployed from GitHub;
- `/health` is healthy;
- `/capabilities` exposes only read-only executable tools;
- at least Binance, OKX, Bybit, Gate, and KuCoin public market adapters pass live public probes;
- no exchange credential is needed for the default research path;
- no HIGH_RISK executable route exists;
- GitHub CI and post-merge verification are green;
- normal documentation no longer instructs the user to install provider skills locally for research.

## 18. Important product boundary

Zero-local means the user's computer needs no runtime installation. It does not mean GitHub repository files execute by themselves.

The execution runtime is Railway/cloud. A ChatGPT or other agent client still needs an authorized remote connector/MCP relationship to invoke private/custom cloud tools directly. This is a cloud connection, not a local installation.

Public HTTPS research endpoints can remain independently health-checkable even before the remote MCP connection is attached to a client.
