# Skill: risk_execution

Covers risk management, SL/TP, position sizing, leverage, portfolio exposure, and execution checks.

- Size from explicit loss-at-invalidation, not desired profit alone.
- Check leverage, liquidation/margin headroom, total open risk, correlation, and venue constraints.
- Place invalidation where the thesis is wrong; do not widen stops merely to avoid normal noise unless the thesis and risk budget still justify it.
- Recompute actual RR after current execution price/slippage.
- Protect live positions with verified venue-native protection when required by project authority.
- Do not add to losers, martingale, or bypass a hard risk governor unless a separately approved design explicitly changes that invariant.

## FX position review (read-only)
- For a supplied FX position, separate broker-observed direction, lots/contracts, entry/current quote, floating P/L, SL/TP, swap/commission, and timestamp from analysis. Preserve the broker symbol and contract specification.
- Flag a missing stop and any unusually concentrated base/quote currency exposure when the complete relevant position set is available. Do not calculate account-level loss, margin, or exposure without contract size, tick value, account currency, conversion rates, and the necessary account/position data.
- State conditional alternatives and invalidation criteria. A risk review does not place, modify, close, or suggest a specific order; the current project authority and explicit execution gates remain decisive.
