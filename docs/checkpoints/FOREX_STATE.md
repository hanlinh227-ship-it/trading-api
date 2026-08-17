# FOREX STATE

Updated: 2026-08-17 (UTC+7)

## Objective
Maintain a repeatable Forex analysis/signal workflow for the 8 major currencies: USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD. Pair them into liquid crosses and rank the best opportunities.

## Current operating state
- The hourly Top-3 Forex signal concept exists but is PAUSED until the user explicitly re-enables it.
- Historical requirement when active: every hour re-evaluate old positions, remove trades that hit TP/SL, replace weaker setups, maintain the current best Top 3.
- Do not invent a MARKET trade when fresh data is unavailable.

## Data workflow
Primary provider: Twelve Data through the project pipeline.
Required analysis frames: D1, H4, H1, M15, M5.
M1/latest price is used for execution refresh/timing, not for primary bias.
For any current entry/hold question, refresh the exact pair immediately before quoting price.

## Analysis stack
1. Currency-level macro bias first, not only pair chart.
   - central-bank policy and rate expectations;
   - inflation, employment, growth data;
   - DXY/US rates for USD context;
   - risk-on/risk-off when JPY/CHF/AUD/NZD are involved;
   - commodity context when CAD/AUD/NZD are relevant.
2. D1/H4: regime, major structure, higher-timeframe liquidity/direction.
3. H1: intraday directional bias and actionable structure.
4. M15: setup zone, displacement/retest, break/reclaim, liquidity sweep where visible.
5. M5: final confirmation/timing.
6. M1: only execution-price refresh when needed.

## Indicators / tools
Use indicators for distinct roles:
- EMA20/50/200: trend and pullback location.
- RSI14: momentum/exhaustion, not a standalone trigger.
- ATR14: volatility and SL buffer.
- VWAP / volume-based context when provider data is adequate.
- Support/resistance and market structure are primary over indicator crosses.

## Entry rules
MARKET is strongest when H1 and M15 are aligned and M5 confirms rather than contradicts.
Preferred triggers include:
- breakout + retest/hold;
- liquidity sweep + reclaim/rejection;
- displacement followed by controlled pullback;
- structure continuation after macro and HTF alignment.

LIMIT may be used only when the user allows it and a clearly defined zone exists (S/R, FVG/OB, VWAP/EMA pullback, retracement). Always define cancellation/invalidation.

## News gate
Before live entry, check high-impact events relevant to either currency. Avoid blindly opening immediately into red-impact events. CPI, NFP, central-bank decisions/speeches, employment and inflation data require special caution.

## Risk
General default for discretionary Forex signals: approximately 0.25%-0.50% risk per trade, with higher risk only if explicitly allowed and prop-firm rules permit it. Avoid stacked correlated exposure across multiple pairs.
Position size must be calculated from structure SL and allowed USD risk.

## Output format when active
For each ranked signal:
- pair and BUY/SELL;
- current refreshed price/source/time;
- Entry;
- hard SL;
- TP1/TP2/TP3 when appropriate;
- RR;
- setup reason by timeframe;
- macro/news context;
- cancellation/early-exit condition;
- confidence/rank.

## Cross-chat rule
At a new chat, read `MASTER_TRADING_STATE.md`, this file, then live pipeline status before issuing Forex entries.