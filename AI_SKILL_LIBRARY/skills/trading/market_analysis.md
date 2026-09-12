# Skill: market_analysis

Covers technical analysis, market structure, microstructure/order flow, liquidity, provider-evidence reconciliation, and live-data validation.

## Evidence discipline
- For live decisions, record source and freshness; stale data cannot masquerade as current.
- Use structure and executed market evidence before isolated indicators.
- Distinguish spot, perpetual, delivery futures, options, CFD, and index feeds; do not silently mix prices.
- Distinguish last, mark, index, bid, ask, and mid prices; they are not interchangeable.
- Check spread, volatility/regime, liquidity, and meaningful cross-source divergence when execution depends on them.
- An indicator, funding value, OI change, order-book imbalance, liquidation print, candle pattern, social signal, provider signal, or AI opinion cannot independently prove a trade.
- State invalidation conditions, not only directional bias.

## Provider reconciliation
When crypto provider capabilities are selected from `AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml`:
1. Normalize symbol or contract address, chain/network, venue, instrument type, quote currency, price semantics, timestamp/timezone, interval/window, and units.
2. Apply `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml`.
3. Treat same-venue first-party data as authoritative for that venue, not for all venues.
4. Prefer fresher evidence only when authority and semantics are comparable.
5. Never majority-vote, average away, or hide material provider disagreement.
6. If unresolved divergence affects entry price, funding, OI, liquidity, token identity, or security, disclose it and withhold the dependent high-consequence conclusion.
7. Preserve FACT / INFERENCE / ASSUMPTION separation when provider evidence is incomplete.

## Risk asymmetry
A credible token-security, honeypot, malicious-contract, permission, or fund-movement warning must be escalated for investigation. A benign result from another provider does not automatically cancel it.
