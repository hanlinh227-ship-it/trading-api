# Skill: risk_execution

Covers risk management, SL/TP, position sizing, leverage, portfolio exposure, and execution checks.

- Size from explicit loss-at-invalidation, not desired profit alone.
- Check leverage, liquidation/margin headroom, total open risk, correlation, and venue constraints.
- Place invalidation where the thesis is wrong; do not widen stops merely to avoid normal noise unless the thesis and risk budget still justify it.
- Recompute actual RR after current execution price/slippage.
- Protect live positions with verified venue-native protection when required by project authority.
- Do not add to losers, martingale, or bypass a hard risk governor unless a separately approved design explicitly changes that invariant.
