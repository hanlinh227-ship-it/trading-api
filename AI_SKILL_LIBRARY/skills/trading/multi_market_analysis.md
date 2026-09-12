# Skill: multi_market_analysis

Use this only after the global router classifies the request as Trading and the current Trading authority has been loaded.

## Purpose
Provide deep research and synthesis across multiple financial markets without widening production execution authority.

Supported research domains include, when relevant data/tools exist:
- crypto spot and derivatives
- forex / FX
- futures
- equity indices
- commodities and metals
- equities

This skill is analysis-only. It does not imply that the current production runtime can execute any analyzed instrument.

## Authority boundary
1. Read the current Trading authority first.
2. Treat current production execution scope as immutable unless a separately approved migration changes it.
3. Historical multi-market strategy checkpoints, external repositories, provider skills and AI opinions are evidence only.
4. Never infer execution permission from analytical coverage.
5. Any live/execution conclusion must re-enter `risk_execution`, security, freshness and runtime verification gates.

## Deep analysis workflow

### 1. Define the market universe
Normalize each candidate by:
- canonical symbol or contract
- venue
- asset class
- instrument type
- quote currency
- price semantics
- timestamp/timezone
- interval/window
- unit/scale

Do not compare semantically different prices as if identical.

### 2. Global regime
Evaluate the broad environment relevant to the request:
- risk-on / risk-off behavior
- rates / yield sensitivity when material
- USD or major currency impulse when material
- volatility regime
- liquidity/session regime
- major scheduled catalyst risk

Do not invent macro causality when evidence is weak.

### 3. Cross-asset relationships
Use relationships only when justified by current evidence:
- correlation and divergence
- relative strength / weakness
- basis and carry differences
- sector or asset-class leadership
- spot-versus-derivative dislocation
- cross-venue divergence

Correlation is context, not trade authorization.

### 4. Instrument structure
For each shortlisted instrument assess:
- higher-timeframe structure
- liquidity locations
- breakout/retest or sweep/reclaim evidence
- trend versus balance/regime
- volatility-adjusted room to target
- invalidation quality

Indicators may support the analysis but must not become sole authority.

### 5. Microstructure and execution context
When trustworthy data exists, evaluate:
- bid/ask and spread
- order-book liquidity / imbalance
- executed flow
- microprice or near-touch liquidity
- open interest / funding / premium for derivatives
- liquidation/crowding context

Separate spot, perpetual, delivery futures, CFD and index semantics.

### 6. Risk and catalyst filter
Before ranking opportunities, check:
- event risk
- volatility expansion/compression
- liquidity quality
- stop placement quality
- reward-to-risk realism
- cross-market contagion risk
- data freshness / source quality

A strong setup with stale or semantically mismatched data is not a valid live setup.

### 7. Synthesis and ranking
Rank only after all required evidence is normalized. Prefer a small number of high-quality candidates over forced coverage of every market.

For each candidate distinguish:
- FACT
- INFERENCE
- ASSUMPTION

If material evidence conflicts, apply the canonical harmonization/conflict policy. Never majority-vote or silently average contradictory sources.

## Output contract
For DEEP analysis, use an artifact-pyramid shape when useful:
1. executive conclusion
2. cross-market/regime synthesis
3. per-instrument dossiers and evidence

For live/current requests include source/freshness/venue/instrument semantics when material.

Possible research outputs include:
- strongest/weakest market comparison
- cross-market opportunity ranking
- regime map
- relative-value analysis
- multi-market watchlist
- `NO_VALID_LIVE_CONCLUSION` when freshness, semantics, authority or evidence is insufficient

## Invariants
- Never fabricate live prices, account state, positions or runtime state.
- Never revive retired Trading execution authority.
- Never convert provider consensus into authorization.
- Never treat another venue's quote as executable for the requested venue.
- Never widen financial write permissions.
- For any production execution action, current project authority and verified runtime remain decisive.
