# SYMBOL KNOWLEDGE + CALIBRATION ARCHITECTURE

Status: canonical design target after V77.11.x

## Goal
Every supported symbol must have its own knowledge profile, but all outputs normalize to a common Hub readiness model. Flexibility is allowed at the analysis/entry-policy layer; execution/news/freshness/risk gates remain strict. No version may claim a stable win rate without walk-forward/OOS evidence.

## Per-symbol knowledge object
Each symbol should expose at least:
- canonical symbol identity and legacy aliases (aliases only for user input/prior lookup, never market-data identity)
- asset class / ecosystem / benchmark
- V73 historical prior families and source
- allowed regimes: TREND, RELATIVE, MEAN_REVERSION, BREAKOUT, PULLBACK/CONTINUATION as supported
- current dynamic active regime and route scores
- primary context drivers
- session/time-of-day behavior when statistically supported
- volatility/risk ATR prior
- preferred entry styles per regime
- invalidation hierarchy for SL
- target hierarchy for TP1/TP2
- execution authority/source and quote freshness rules
- news/context drivers
- calibration evidence: sample size, walk-forward periods, wins/losses/timeouts, expectancy in R, payoff ratio, max adverse excursion, max favorable excursion, drawdown, calibration date and data source

## Entry policy
TREND: continuation/pullback/break-retest allowed when HTF direction, momentum and structure support it. Do not require a liquidity sweep on every trend setup.
RELATIVE: benchmark-relative strength/context must materially support direction; combine with at least one structural/HTF confirmation.
MEAN_REVERSION: remain stricter; require extension plus reclaim/reversal evidence and clean invalidation.
BREAKOUT: only when closed-candle breakout and usable room/target exist; avoid entering an already exhausted move.
PULLBACK: favor structural/EMA/liquidity retest with invalidation behind real structure.

## SL policy
SL is never chosen to manufacture a desired RR. Order of preference:
1. structural invalidation / liquidity swing
2. higher-timeframe invalidation if local swing is too tight/noisy
3. ATR volatility floor/buffer to prevent micro-noise stops
Reject plans where the resulting stop is absurdly wide relative to available target/volatility.

## TP policy
TP is selected from real forward structure/liquidity/support-resistance. Prefer TP1 at first clean target and TP2 at next clean target. RR is calculated after entry+SL+target are known. Do not force 1:2 or 1:3 by inventing a target.

## RR / expectancy policy
Do NOT optimize raw win rate alone. Promotion should target positive and robust expectancy:
Expectancy_R = win_rate * avg_win_R - loss_rate * avg_loss_R - cost_R.
A lower win-rate method may be superior if payoff is materially better. A high win rate with poor payoff/tail losses must not be promoted.

Minimum research checks before a calibration may influence production confidence:
- enough trades for the symbol/regime to avoid tiny-sample conclusions
- multiple time windows / market regimes
- walk-forward or untouched OOS segment
- spread/slippage/cost assumptions included
- no target-period leakage
- report both win rate and expectancy, not win rate alone

## Production confidence layers
1. STRUCTURAL QUALITY: current setup quality from live market data.
2. REGIME FIT: whether the currently active regime is allowed and supported for this symbol.
3. CALIBRATION CONFIDENCE: only from OOS/walk-forward evidence. If unavailable, mark UNCALIBRATED rather than inventing confidence.
4. EXECUTION QUALITY: quote freshness, spread/cost, exact symbol, venue/broker authority.

Hub score is setup readiness, NOT probability of winning. A future calibrated probability must be separately named and produced only after reliability testing.

## Knowledge source routing
Crypto: exchange-native OHLCV/order/derivatives context + benchmark/ecosystem context; broad discovery sources may rank but not execute.
Forex: multi-pair currency strength + macro/news drivers per currency + session behavior + broker execution quote before MARKET/LIMIT.
Gold/Silver: metal structure plus USD/DXY/rates/macro/news context when trustworthy feeds are connected; broker execution quote required.
Futures NQ/ES/MNQ/MES: CME/Massive contract data, volume, session structure, NQ-ES SMT/relative context, exact contract/front-month resolver, live execution feed entitlement required for executable instructions.
Index cash: use broker-native price for execution; NQ/ES futures may act as leading/context data but must never substitute the cash CFD execution quote.

## Anti-overfitting rules
- Never promote a rule because it made the most recent few trades look better.
- Never tune and score on the same target window without a holdout.
- Prefer simple route features with stable behavior across windows.
- New symbol-specific rules start as RESEARCH_ONLY until validated.
- V73 remains a prior, not proof of future performance.

## Promotion criteria
A future engine change can be called better only if it improves robustness on walk-forward/OOS metrics without creating unacceptable drawdown, execution fragility or coverage regression. Production live smoke tests must still pass after research promotion.
