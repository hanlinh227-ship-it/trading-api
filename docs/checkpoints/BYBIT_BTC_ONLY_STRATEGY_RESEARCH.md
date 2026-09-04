# BTCUSDT Strategy Research Direction

The BTC-only bot must not use indicator crosses as primary trade authority. The production research stack should combine:

1. Market structure: HH/HL, LH/LL, break of structure, failed break, acceptance/rejection.
2. Liquidity: prior highs/lows, sweep/reclaim, clustered stop zones, range extremes.
3. Order flow: top-of-book/depth imbalance, trade-flow delta, absorption, liquidity vacuum.
4. Volatility regime: compression, expansion, shock, transition.
5. Price action: pullback quality, reclaim/rejection, breakout/retest, failed auction.
6. Derivatives context: funding/open-interest as context only, never standalone direction authority.
7. Execution quality: spread, slippage, chase distance, quote freshness, post-order reconciliation.

Strategy router:
- TREND_UP/TREND_DOWN -> pullback/continuation.
- BREAKOUT_UP/BREAKOUT_DOWN -> breakout/retest with stronger confirmation.
- RANGE -> mean reversion only at validated range edge.
- SQUEEZE -> wait for break; no blind pre-break positioning.
- HIGH_VOL_SHOCK/TRANSITION -> reduce or block new risk.

Risk architecture:
- unlimited strategic trade count, bounded by active-risk/margin budgets.
- no martingale or averaging-down rescue.
- winner pyramiding only after previous tranche risk has been reduced/protected and a fresh setup exists.
- continuous equity compounding and asymmetric drawdown scale-down.

Research objective is robustness after fees/slippage across walk-forward/random windows, not maximizing one in-sample equity curve.
