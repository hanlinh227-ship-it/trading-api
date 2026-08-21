# V5 Multi-Timeframe Adaptive Scalp Research Protocol

## Objective

Operate a 24/7 Binance USDT perpetual SCALP research engine that standardizes entry quality across market regimes while continuously learning from PAPER outcomes. The system must not self-modify live source code from a small sample of recent trades.

## Entry hierarchy

Every trade-eligible candidate must have all eight deep timeframes available:

- 1d / 4h / 1h: macro context and directional pressure.
- 30m / 15m: setup and regime layer.
- 5m / 3m / 1m: execution and trigger layer.

The engine requires at least two of the three execution timeframes to confirm the direction. Strong setup-layer opposition blocks. Strong macro opposition blocks. A neutral macro context does not automatically block a scalp.

## Strategies

- TREND_PULLBACK: macro + setup aligned, execution returns to a reasonable EMA/VWAP area and re-confirms.
- BREAKOUT: compression in setup layer, participation/volume expansion in execution layer, breakout not excessively extended.
- MOMENTUM: aligned context and setup with synchronized execution momentum and participation.
- MEAN_REVERSION: only in genuine range regimes; uses VWAP deviation/exhaustion and must not fight strong higher-timeframe trend pressure.

## Execution quality

Before a trade can reach AI consensus:

- Spread must be within the execution gate.
- TP1 distance must be meaningfully larger than the estimated round-trip fee/slippage cost.
- Stop must clear short-term noise and remain structurally coherent.
- Stale data, incomplete MTF data, strong MTF opposition, or chase conditions block the trade.

## Derivatives context

Funding, open interest, open-interest change, and taker buy/sell ratio are context variables. They are never a standalone direction signal.

## Continuous learning

The system writes a bounded `adaptive_policy.json` from CLOSED PAPER trades.

- Strategy multiplier becomes evaluatable only after >=30 closed trades.
- Symbol multiplier becomes evaluatable only after >=40 closed trades.
- Regime multiplier becomes evaluatable only after >=30 closed trades.
- Maximum learned score adjustment is bounded to +/-15% before combination clamps.
- Historical learning cannot override a current hard execution blocker.
- No automatic source-code rewrite is allowed from recent PnL.

This is champion-policy learning: evidence adjusts ranking modestly; structural market logic remains authoritative.

## Research evidence incorporated

1. High-frequency dynamics of Bitcoin futures: an examination of market microstructure (Borsa Istanbul Review, 2025). Binance BTC/ETH perpetual data show high-frequency market microstructure and intraday volatility/trade-size dynamics are important rather than invariant.
   https://doi.org/10.1016/j.bir.2025.07.016

2. Price discovery in bitcoin spot and futures markets (Journal of International Money and Finance, 2025). High-frequency lead/lag and transaction-size effects support treating derivatives activity and price discovery as contextual evidence.
   https://doi.org/10.1016/j.jimonfin.2025.103415

3. Perpetual Futures Contracts and Cryptocurrency Market Quality (Ruan & Streltsov, revised 2025). Funding cycles affect trading activity and spreads, so funding should be treated as a time-varying market-quality context variable rather than a fixed directional signal.
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4218907

4. Timing Usage of Technical Analysis in the Cryptocurrency Market (Applied Sciences, 2025). Strategy evaluation must avoid selected-period overfitting; the engine therefore keeps learning evidence sample-gated and bounded.
   https://www.mdpi.com/2076-3417/15/23/12802

## Promotion rule

A new idea can be researched and paper-tested continuously, but it must not silently replace the current execution logic. Promotion requires adequate sample size, stable positive expectancy/profit factor, and no material degradation in drawdown/slippage behavior across multiple regimes.
