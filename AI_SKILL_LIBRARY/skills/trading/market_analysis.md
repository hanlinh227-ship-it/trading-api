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

## Forex / OTC FX evidence
- Identify the exact broker/provider, symbol mapping, instrument type (spot reference, CFD, or other contract), quote currency, source timestamp, receive timestamp, and data entitlement. A recent fetch time does not make delayed source data live.
- Read the broker's per-symbol specification for digits, point size, tick size/value, pip convention, contract size, and volume step. Never hard-code a universal pip size or infer money-at-risk from price distance alone; normalize units before comparing symbols.
- Keep bid, ask, mid, last, candle close, and side-of-bar semantics separate. For a broker-specific quote, a long is entered at ask and marked/closed against bid; a short is entered at bid and marked/closed against ask. If only midpoint/close data is available, label levels reference-only.
- Align timeframes and sessions. Use closed bars for confirmed structure; label the forming bar provisional. Preserve source timezone, daylight-saving/session context, and broker rollover behavior where relevant.
- MT5/OTC FX tick volume and quote-update counts describe the observed provider feed. Do not call them global traded volume, executed buy/sell flow, a consolidated tape, or a market-wide order book. Report depth/footprint/order flow only when the named source actually supplies suitable, timestamped trade-level data.
- Describe trend/range, swing structure, momentum, nearby levels, and a price-based invalidation condition. Indicators can corroborate; they cannot substitute for price evidence. Distinguish observed facts from inference and state material gaps.

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
