# Crypto Trading Method V5

## Goal
Use a hierarchical, regime-aware multi-timeframe process. Do not stack redundant indicators. Price structure is primary; EMA/RSI/volume/ATR are supporting tools. Derivatives and news are context, not standalone triggers.

## 1. Data quality
- Direct exchange price, bid/ask, timestamp, fresh M1.
- D1/H4/H1/M15/M5 candles from the same venue when possible.
- For perpetual context, collect funding, open interest and long/short ratio from a public derivatives venue when available.
- Never call stale or fallback web price an execution price.

## 2. Regime first
Classify each symbol as TREND, RANGE or TRANSITION using D1/H4 structure, EMA50/EMA200 slope/position, ATR expansion and optional ADX.
- TREND: favor continuation/pullback; do not fade RSI extremes by default.
- RANGE: favor mean reversion at range edges; avoid breakout entries without volume expansion.
- TRANSITION: require M15/M5 confirmation and lower confidence.

## 3. Multi-timeframe roles
- D1: macro structure, 50/200 EMA, major support/resistance, ATR regime.
- H4: operational trend, swing highs/lows, range boundaries, volatility expansion.
- H1: intraday bias and pullback quality.
- M15: setup zone, breakout/retest, sweep/reclaim, volume confirmation.
- M5: market-entry trigger only.
- M1: final price/spread refresh, not bias reversal.

## 4. Core indicators
Use one tool per job.
- Trend: EMA50/EMA200 plus structure.
- Momentum: RSI14.
- Conviction: volume ratio versus 20-bar average.
- Risk/volatility: ATR14.
- Regime helper: ADX14, optional and secondary.
Do not add MACD/Bollinger/oscillators unless they add a distinct decision variable.

## 5. Strategy selector
### Trend continuation
Use when H4/H1 align and structure is directional. Enter only after pullback/retest or renewed M5 displacement. Avoid chasing if price is >~1.3-1.6 ATR from H1/M15 EMA20.

### Breakout-retest
Require closed breakout beyond a meaningful M15/H1 level, volume expansion, and retest/hold. A raw breakout without confirmation is not enough.

### Range mean reversion
Only when H4/H1 are genuinely ranging. Buy lower range after rejection/reclaim; sell upper range after rejection. RSI extremes are confirmation, not the reason for entry.

### Liquidity sweep reversal
Require sweep of a prior swing, reclaim/MSS, and M5 confirmation. Do not reverse merely because RSI is overbought/oversold.

## 6. Market context
For alts, compare relative strength against BTC and ETH over H1/H4. Stronger alts receive long preference in risk-on conditions; weaker alts receive short preference in risk-off conditions. This is a tiebreaker, not a hard trigger.

## 7. Derivatives context
When available:
- Funding: extreme positive funding can warn against late longs; extreme negative funding can warn against late shorts.
- Open interest: price+OI rising can confirm participation; price move with OI falling can indicate covering/deleveraging.
- Long/short ratio: sentiment context only; never use alone.
Do not reject a setup solely because one derivatives metric disagrees.

## 8. Coin classes
- Majors (BTC/ETH/SOL/XRP): tighter spreads, more weight on D1/H4 structure, smaller ATR stop multiplier.
- Liquid alts: add BTC/ETH relative-strength filter.
- Memes/high-volatility: require stronger volume confirmation, wider ATR buffer, lower size, and stricter anti-chase rules.

## 9. Entry score for live ranking
Recommended 100-point model:
- Regime + HTF structure: 30
- H1/M15 setup quality: 25
- M5 trigger quality: 15
- Volume/volatility quality: 10
- BTC/ETH relative strength/context: 10
- Funding/OI/sentiment confirmation: 5
- Event/news/tokenomics risk: 5

For live trading, prioritize A/A+ setups. Forced-market blind tests may still force BUY/SELL for research, but that is not a live rule.

## 10. Stop and target
- Stop is structure-first, then ATR floor.
- Typical ATR floor: majors ~1.1-1.3 M15 ATR; alts ~1.2-1.4; memes ~1.4-1.7.
- Do not shrink stop to manufacture RR.
- Target nearest liquidity/structure first; use R-multiple only as validation.

## 11. Blind-test protocol
- Freeze all rules before selecting test windows.
- Use only fully closed candles before cutoff.
- Hide all future candles until side/entry/SL/TP are frozen.
- Use new timestamps after each rule revision.
- Report TP/SL, MFE, MAE, win rate and expectancy.
- Keep forced-market stress test separate from realistic live test with NO TRADE allowed.

## 12. Rejected lesson from V4
Do not blend trend and mean-reversion scores indiscriminately. A mean-reversion component can flip a strong momentum market into a countertrend trade. Use a strategy selector based on regime first, then score only the strategy appropriate to that regime.
