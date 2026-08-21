# V4 Adaptive Scalp Research Basis

## Operating objective

- Binance USDT perpetual futures only.
- Scalp-only, 24/7.
- No daily trade-count quota.
- No daily-loss or max-loss quota.
- Every trade still requires a per-trade structural/volatility stop.
- Different symbols may use different strategies as market regime changes.
- Production strategy changes are never promoted solely because an AI suggested them; empirical validation is required.

## Research findings incorporated

1. High-frequency crypto futures display distinct market-microstructure behavior and intraday variation. This supports regime-aware, volatility-aware scalp rules rather than a single fixed threshold for every coin.
   - Borsa Istanbul Review (2025), High-frequency dynamics of Bitcoin futures: https://www.sciencedirect.com/science/article/pii/S2214845025001188

2. Very short-horizon crypto price discovery is strongly associated with algorithmic trading activity. This supports strict freshness, liquidity and execution-quality guards for scalping.
   - Economics Letters (2026), Price discovery in cryptocurrency markets: sub-second evidence: https://www.sciencedirect.com/science/article/pii/S016517652600220X

3. Derivatives and spot order imbalances can have cross-market predictive relationships, depending on market state. This motivates treating funding/open-interest/participation as context rather than unconditional entry signals.
   - British Accounting Review (2025): https://www.sciencedirect.com/science/article/pii/S0890838925001520

4. Futures activity and open interest relate differently to volatility. This supports using derivatives participation as a risk/regime feature rather than a simplistic directional signal.
   - International Review of Financial Analysis: https://www.sciencedirect.com/science/article/abs/pii/S1057521923000133

5. Binance USD-M Futures exchange filters impose tick-size, quantity and minimum-notional constraints. Small accounts must reject trades that cannot be sized correctly rather than silently increasing risk.
   - Binance USD-M Futures common definitions: https://developers.binance.com/zh-CN/docs/products/derivatives-trading-usds-futures/common-definition

## V4 strategy library

- TREND_PULLBACK: 15m + 5m directional alignment, 1m controlled pullback toward EMA/VWAP.
- BREAKOUT: compression followed by range break with volume expansion.
- MOMENTUM: aligned trend plus short-horizon momentum and participation.
- MEAN_REVERSION: neutral higher regime plus large VWAP deviation and short-term exhaustion.

## Dynamic exits

Stops are calculated from structural invalidation plus volatility/noise distance. Targets are expressed in R and vary by strategy. The system does not assume one universal SL/TP percentage for all symbols.

## Continuous learning

`research/learning_engine.py` aggregates closed paper trades by symbol and strategy. Samples below 30 closed trades remain RESEARCH_ONLY. Observed results may trigger research or challenger variants, but they do not automatically rewrite or promote the live strategy.

## Live promotion rule

LIVE remains locked until the new V4 scanner, all three AI lanes, adaptive risk engine, execution guard, position manager and updater pass on the VPS after auto-deployment. A successful GitHub commit is not itself evidence that live trading is ready.
