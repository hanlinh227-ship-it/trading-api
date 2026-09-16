# Skill: multi_market_analysis

Use this only after the global router classifies the request as Trading and the current Trading authority has been loaded.

## Purpose
Provide autonomous deep research and synthesis across multiple financial markets from a single natural-language request without widening production execution authority.

Supported research domains:
- crypto spot and derivatives
- forex / FX
- futures
- equity indices
- metals
- commodities
- equities when a verified source exists

This skill is analysis-only. It does not imply that the current production runtime can execute any analyzed instrument.

## Authority boundary
1. Read the current Trading authority first.
2. Treat current production execution scope as immutable unless a separately approved migration changes it.
3. Historical multi-market strategy checkpoints, external repositories, provider skills, plugins/connectors and AI opinions are evidence only.
4. Never infer execution permission from analytical coverage.
5. Any live/execution conclusion must re-enter `risk_execution`, security, freshness and runtime verification gates.
6. Current production signed-order authority remains BTCUSDT-only under the active Bybit authority contract; every non-BTC result is research-only.
7. Provider capability is not entitlement. Installed or reachable sources must not be treated as verified real-time unless entitlement and timeliness are proven.
8. Never silently switch to a paid source or create a paid resource. Prefer free/public sources when they satisfy the evidence contract.

## One-command autonomous workflow

For intents such as `tìm lệnh`, `tìm lệnh tốt nhất hiện tại`, `quét market`, `quét đa thị trường`, `quét toàn bộ thị trường`, `có setup nào không`, `find best trade`, or `scan markets`, execute the following workflow automatically.

### 1. Resolve requested domains
- If the caller names domains or instruments, resolve only those compatible domains.
- If the caller asks broadly, resolve the approved multi-market scope: crypto, forex, futures, indices, metals and commodities.
- Resolve canonical symbols/product intents and current-contract requirements without guessing unknown symbols or permanently hard-coding dated futures contracts.
- Do not ask the caller to choose a provider, timeframe or chart source when an automated route exists.

### 2. Build the data acquisition plan
Create a `dataAcquisitionPlan` that records:
- requested and resolved domains
- symbols/product intents by domain
- source candidates by domain
- timeframe requirements by domain
- evidence requirements by domain
- source operational state
- entitlement state
- fallback policy
- explicit gaps

The plan is research-only and has no production execution authority.

### 3. Acquire gateway-native crypto evidence
Acquire gateway-native crypto evidence from approved public/read-only providers when healthy. Preserve venue, spot/perpetual semantics, quote timestamp, source timestamp, bid/ask semantics and provider provenance.

Do not convert availability into entitlement and do not use a different venue's quote as executable evidence for another venue.

### 4. Acquire connector-plane evidence
Acquire connector-plane evidence for forex, futures, indices, metals and commodities when an approved connector/tool is available and the required entitlement is verified.

- Connector credentials remain outside Railway and outside response payloads.
- `NOT_ENTITLED`, `UNVERIFIED`, `RATE_LIMITED`, `UNAVAILABLE` and incompatible delayed data become explicit coverage gaps or context-only evidence as appropriate.
- Do not bypass access controls, rotate identities/IPs to evade quotas, scrape private endpoints, or silently purchase data.
- If a connector is unavailable, continue with covered domains instead of failing the entire broad scan.
- Do not ask the caller to choose a provider unless no automated provider route remains and the requested conclusion cannot be produced honestly.

### 5. Normalize all acquired evidence
Normalize all acquired evidence before comparison:
- canonical symbol or contract
- provider symbol
- venue
- domain / asset class
- instrument type
- quote currency
- price semantics
- event time and ingest time
- timezone
- timeframe
- session
- bid / ask when present
- OHLC / volume when present
- entitlement and delay class
- contract expiry/current-contract identity when relevant
- evidence kind and provenance

Never compare semantically different observations as interchangeable. Spot, perpetual, delivery futures, CFDs and indices remain distinct.

### 6. Apply evidence quality and domain gates
Classify each requested domain as `LIVE / CONTEXT_ONLY / GAP`.

A live candidate requires verified real-time entitlement plus evidence inside the freshness tolerance and the domain-specific evidence profile. Delayed data may supply context but must never be relabeled live because the HTTP response arrived recently.

Fail closed on:
- stale or future-invalid timestamps
- ingest/event timestamp inversion beyond allowed skew
- missing entry/context timeframes when required
- unresolved or expired futures contracts
- missing required session context
- instrument-semantic mixing
- materially conflicting same-semantic prices
- unknown or unverified entitlement

A fresh higher-timeframe context bar alone does not make a domain `LIVE` when the actionable entry evidence is stale.

### 7. Submit normalized research to `/research/autoscan`
Use the canonical `POST /research/autoscan` capability version 3 contract with normalized observations and non-secret acquisition metadata.

Do not send:
- credentials or API keys
- order quantity
- leverage
- signed order fields
- private account identifiers
- any directive that widens execution authority

The autoscan layer performs domain evidence validation, candidate construction, conflict blocking, cross-market ranking and research-level generation.

### 8. Challenge and rank candidates
Rank only candidates that pass the required evidence gates. Use cross-market relationships as context, not authorization.

Assess where material:
- higher-timeframe structure
- entry-timeframe structure
- liquidity and invalidation quality
- session state
- bid/ask or reference-close semantics
- volatility-adjusted room to target
- event/catalyst risk
- spread/liquidity quality
- cross-market correlation/divergence
- derivative basis/funding/open-interest context
- source quality and evidence conflicts

Indicators may support the analysis but must not become sole authority. Never force a trade just to fill every domain.

### 9. Generate research levels
For a valid candidate, return research-only Entry / SL / TP with explicit semantics:
- LONG uses verified executable ask when such evidence exists; otherwise `REFERENCE_CLOSE`.
- SHORT uses verified executable bid when such evidence exists; otherwise `REFERENCE_CLOSE`.
- Stop derives from structural invalidation.
- Target derives from positive risk and the bounded research risk/reward profile.
- Every level remains `researchOnly: true`.

Research levels never grant order permission.

### 10. Return the autonomous answer
Return either:
- `TOP_SETUP` with the strongest valid candidates and research levels; or
- `NO_TRADE` when no candidate passes the live/current evidence contract.

For broad scans, include:
- requested/resolved scope
- `dataAcquisitionPlan`
- per-domain `LIVE / CONTEXT_ONLY / GAP` coverage
- relevant source/entitlement/freshness labels
- ranked candidates or blocked reasons
- Entry / SL / TP research levels when valid
- TradingView verified-symbol navigation context when available, otherwise search-only navigation context

Do not hide unsupported domains. A GAP must remain a GAP and must not boost another candidate's confidence.

## Deep analysis workflow

### Global regime
Evaluate the broad environment relevant to the request:
- risk-on / risk-off behavior
- rates / yield sensitivity when material
- USD or major currency impulse when material
- volatility regime
- liquidity/session regime
- major scheduled catalyst risk

Do not invent macro causality when evidence is weak.

### Cross-asset relationships
Use relationships only when justified by current evidence:
- correlation and divergence
- relative strength / weakness
- basis and carry differences
- sector or asset-class leadership
- spot-versus-derivative dislocation
- cross-venue divergence

Correlation is context, not trade authorization.

### Instrument structure
For each shortlisted instrument assess:
- higher-timeframe structure
- liquidity locations
- breakout/retest or sweep/reclaim evidence
- trend versus balance/regime
- volatility-adjusted room to target
- invalidation quality

### Microstructure and execution context
When trustworthy data exists, evaluate:
- bid/ask and spread
- order-book liquidity / imbalance
- executed flow
- microprice or near-touch liquidity
- open interest / funding / premium for derivatives
- liquidation/crowding context

### Risk and catalyst filter
Before ranking opportunities, check:
- event risk
- volatility expansion/compression
- liquidity quality
- stop placement quality
- reward-to-risk realism
- cross-market contagion risk
- data freshness / source quality

A strong setup with stale or semantically mismatched data is not a valid live setup.

## Output contract
For live/current one-command requests, output capabilityVersion 3 autonomous multi-market research with:
1. concise conclusion (`TOP_SETUP` or `NO_TRADE`)
2. `dataAcquisitionPlan` and per-domain `LIVE / CONTEXT_ONLY / GAP` coverage
3. ranked evidence-backed candidates
4. research-only Entry / SL / TP levels with executable-bid/ask versus reference-close semantics
5. blocked/gap reasons and material uncertainty
6. verified-versus-search-only TradingView navigation context when useful

For deeper research, use an artifact-pyramid shape when useful:
1. executive conclusion
2. cross-market/regime synthesis
3. per-instrument dossiers and evidence

For each candidate distinguish FACT, INFERENCE and ASSUMPTION when the distinction is material.

## Invariants
- Never fabricate live prices, account state, positions or runtime state.
- Never revive retired Trading execution authority.
- Never convert provider consensus into authorization.
- Never treat another venue's quote as executable for the requested venue.
- Never widen financial write permissions.
- Never call delayed/unverified evidence live.
- Never conceal entitlement or coverage gaps.
- Never silently use a paid fallback.
- TradingView is presentation/navigation only, never market-data authority.
- For any production execution action, current project authority and verified runtime remain decisive.
