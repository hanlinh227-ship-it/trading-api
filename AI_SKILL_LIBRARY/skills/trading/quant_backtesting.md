# Skill: quant_backtesting

Covers quantitative research, backtesting, strategy validation, and statistical robustness.

- Define data universe, timeframe, fees, slippage, funding/carry, latency assumptions, and survivorship rules before interpreting results.
- Separate in-sample optimization from out-of-sample validation.
- Watch for leakage, look-ahead bias, overfitting, data snooping, and repeated-test selection bias.
- Report distributional metrics and drawdown, not win rate alone.
- Prefer walk-forward/stability checks and sensitivity ranges over a single optimized parameter set.
- A backtest is evidence about a historical simulation, never a guarantee of future profitability.

## Forex-specific validation
- Use the exact broker/instrument history and preserve whether bars are bid, ask, midpoint, or last. Model long and short fills on the correct quote side; a midpoint-only result is not an executable FX backtest.
- Include variable spread by session/news regime when data supports it, commission, slippage, gaps, swap/financing and triple-rollover rules, broker-specific digits/point size/tick size/tick value/pip convention/contract size/volume step, account-currency conversion, market hours/holidays, timezone and daylight-saving changes. Never hard-code a universal pip value; normalize distance and volatility across pairs. If a cost or symbol specification cannot be sourced, report a sensitivity range and label the missing assumption; do not silently set it to zero.
- Treat MT5 tick volume as provider-feed activity unless the source establishes executed trade volume. Do not use broker tick volume as a proxy for consolidated FX turnover or aggressor flow.
- Keep chronological train/validation/test windows separate. Add walk-forward tests across pairs and distinct rate/volatility regimes, account for multiple testing and correlated pair exposure, and report stability after realistic costs. Do not tune on the final test period.
- Report trade count, net return after modeled costs, drawdown, expectancy/distribution, exposure and sensitivity to spread/slippage/carry; a high win rate alone is not an edge. Historical research never grants live signal or execution authority.
