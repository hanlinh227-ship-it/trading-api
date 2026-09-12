# Crypto Agent Skill Registry Integration Design

## Goal
Integrate the newly prepared official crypto-agent skill sources into the GitHub-first Brain so every request continues through `task_router`, GitHub is consulted as the skill-routing authority, and crypto provider capabilities are selected lazily without creating competing reasoning authorities.

## Non-goals
- Do not preload every provider skill on every request.
- Do not make provider-specific skills independent reasoning authorities.
- Do not enable live trading, wallet actions, transfers, withdrawals, swaps, bridges, signing, broadcasting, payments, or DeFi/earn execution.
- Do not write API keys, private keys, seed phrases, passphrases, OAuth/session tokens, or exchange credentials into the repository.
- Do not mutate immutable files that are hash-pinned in the current Stable release bundle.

## Existing authority constraints
The current Brain already requires `task_router`, one primary domain, at most two supporting skills, lazy loading, project authority before memory, and release-bundle integrity. Trading has its own current project authority and must remain subordinate to that authority. Provider skills are capability/evidence adapters only.

## Architecture

### 1. Global GitHub skill lookup
Every request continues through the existing global `task_router`. The router reads a small registry index before choosing provider-specific capability context. The index is intentionally tiny and only contains pointers and policies; it does not preload provider details.

Flow:

```text
request
  -> checkpoint.json
  -> task_router
  -> registry index lookup
  -> primary domain
  -> project authority if required
  -> primary skill + <=2 supporting skills
  -> domain/provider registry if relevant
  -> relevant source/tool
  -> security gate
  -> evidence reconciliation
  -> answer
```

### 2. Registry index
Create `AI_SKILL_LIBRARY/skills/registry/index.yaml`.

Responsibilities:
- declare that registry lookup happens for every request;
- point to the canonical skill catalog;
- point to domain-specific provider registries;
- state that provider registries are capability metadata, not reasoning authority;
- enforce lazy loading after domain classification;
- cap provider candidates to avoid context explosion;
- fail closed if a provider entry is ambiguous or conflicts with security policy.

### 3. Crypto provider registry
Create `AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml`.

Each provider row records:
- provider and official repository;
- upstream skill/module path or provider bundle;
- normalized capability id;
- use cases and trigger phrases;
- mode: `RESEARCH_SAFE`, `AUTH_READ_ONLY`, or `HIGH_RISK`;
- API-key requirement;
- whether the capability can affect real funds;
- routing authority flag;
- source role;
- fallback behavior;
- notes about upstream changes.

Provider-specific skill documents do not become primary Brain skills. Existing reasoning skills such as `trading_router`, `market_analysis`, `risk_execution`, `research`, and `verification` remain responsible for reasoning and answer construction.

### 4. Risk classes

#### RESEARCH_SAFE
May be selected automatically after domain routing when no credentialed write capability is needed. Examples: public market data, K-line, ticker, orderbook, funding, open interest, token metadata, token audit, public address analysis, macro/news, sentiment, and public smart-money research.

#### AUTH_READ_ONLY
May be selected as a candidate but cannot run until a restricted read/query-only credential is separately authorized. It must never assume a credential exists. No withdrawal permission is permitted.

#### HIGH_RISK
Recorded for discoverability and correct classification only. `routing_authority=false` and `auto_activate=false`. Includes trading/order writes, wallet authentication or creation, transfer/withdrawal, swap/bridge, transaction signing/broadcast, payments, fund movement, leverage/account mutation, earn purchase/redeem, and DeFi investment actions.

### 5. Conflict harmonization
Create `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml`.

Provider outputs are evidence inputs, not votes. The system must never average conflicting provider claims or choose by majority vote.

Resolution order:
1. current runtime evidence;
2. current project authority;
3. current first-party source from the relevant venue/provider;
4. fresher equal-authority source;
5. approved reference source;
6. scoped verified memory;
7. model background.

Before declaring a material conflict, normalize:
- symbol/contract identity;
- spot vs perpetual vs delivery futures vs index/CFD venue;
- quote currency and unit;
- timestamp/timezone;
- candle interval;
- mark/index/last/mid price semantics;
- OI/funding aggregation window;
- chain/network for on-chain tokens.

If material conflict remains unresolved, disclose it and block any high-consequence conclusion that depends on the disputed fact. For live entry analysis, unresolved price/source divergence must not be silently converted into an entry.

Risk evidence is asymmetric: a credible high-risk/security flag is not canceled by a lower-risk provider opinion. It must be investigated or disclosed.

### 6. Provider precedence
Provider precedence is contextual, not global. A provider is authoritative for its own current first-party venue data, but it does not override current project policy or runtime authority. Cross-venue market comparison is allowed only after semantic normalization.

Provider skills cannot override:
- current trading authority;
- Stable security invariants;
- credential policy;
- live-data freshness requirements;
- user-defined hard risk controls.

### 7. Upstream discovery and freshness
Official provider repositories are registered in `AI_SKILL_LIBRARY/sources.yaml` as RAG/reference sources with provenance and licenses. The registry stores upstream paths instead of vendoring entire third-party repositories.

New upstream skills may be discovered through Evergreen, but they enter quarantine with zero routing authority. Financial/credential-sensitive Class D capability never auto-promotes.

### 8. Canonical integration points
Modify only non-hash-pinned integration surfaces:
- `AI_SKILL_LIBRARY/skills/core/task_router.md`
- `AI_SKILL_LIBRARY/router.yaml`
- `AI_SKILL_LIBRARY/skills/catalog.yaml`
- `AI_SKILL_LIBRARY/v4/skills/core/manifest.yaml`
- `AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml`
- `AI_SKILL_LIBRARY/v4/mesh/domains/trading.yaml`
- `AI_SKILL_LIBRARY/sources.yaml`
- `AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml`

Do not modify current hash-pinned Stable files under the active release manifest unless a separate release-promotion workflow is explicitly undertaken.

### 9. Validation
Add `AI_SKILL_LIBRARY/validate_skill_registry.py` and tests.

The validator must fail on:
- missing registry files;
- duplicate capability ids;
- unknown risk/mode values;
- HIGH_RISK entry with routing authority or auto activation;
- real-funds capability marked LOW risk;
- credential-sensitive capability marked no-auth without an explicit public-only note;
- missing official source repository;
- missing conflict policy;
- registry configured to preload all provider capabilities;
- more than the configured maximum provider candidates;
- provider registry attempting to supersede project authority.

Run existing Brain/router/V4 validators plus the new registry validator.

## Provider coverage

### Binance
Research-safe capability coverage includes market rank, token info, token audit, public address info, and research-only signal analysis. Wallet, payment, transfer, and execution capability is HIGH_RISK.

### OKX
Research-safe coverage includes CEX market data and no-auth market modules. Authenticated sentiment/smart-money/account-query capability is AUTH_READ_ONLY. CEX trade, bot, portfolio mutation, earn action, Agentic Wallet, swap/bridge/broadcast, payments, and DeFi action are HIGH_RISK. OnchainOS names are normalized to the current upstream structure rather than preserving obsolete names.

### Bybit
The single upstream skill is split at registry level into public Market research versus mixed write-capable modules. Market data is allowed as research capability; Spot, Derivatives writes, Account mutations, Earn, Strategy execution, Bots, Copy Trading, Alpha Trade, Pay, and Fiat actions are HIGH_RISK.

### Gate
Public Market, Info, News, Docs and research skills are RESEARCH_SAFE. Authenticated private read-only account information is AUTH_READ_ONLY where applicable. Exchange trading, futures execution, DEX trade/wallet, transfers, pay, earn actions and other fund-moving capability are HIGH_RISK.

### KuCoin
Current Skills Hub is modeled as GET/read-only. Public market queries are RESEARCH_SAFE; private account/order/position queries are AUTH_READ_ONLY. If upstream later adds write operations, those must not inherit read-only trust and must enter quarantine/reclassification.

### Coinbase
Agentic Wallet and AgentKit wallet/fund/send/trade/payment/on-chain actions are HIGH_RISK and documentation-only. Read-only on-chain query references may be cataloged separately when they can be isolated from wallet action providers.

## Success criteria
- Every request still passes through `task_router` and a GitHub registry index.
- Non-crypto requests do not load crypto provider details.
- Crypto requests can discover all prepared official provider capability bundles through GitHub.
- Existing project/trading authority remains unchanged.
- Provider conflicts are reconciled by evidence precedence, semantics, freshness, and risk—not by majority vote.
- HIGH_RISK capability cannot auto-route or auto-activate.
- Existing validators remain green and the new registry validator is green.
- No credential material is introduced.
