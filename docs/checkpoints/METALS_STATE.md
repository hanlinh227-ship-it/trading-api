# METALS STATE — XAUUSD / XAGUSD

Updated: 2026-08-17 (UTC+7)

## Scope
Primary metals: XAUUSD (Gold) and XAGUSD (Silver). XPTUSD may exist in broader bot universes but is not part of the default gold/silver discretionary workflow unless requested.

## Timeframe workflow
- H4/H1: main bias, regime, major structure/liquidity.
- M15: setup construction and key intraday levels.
- M5: trigger/confirmation.
- M1: final timing and live-price refresh only.

## Core technical toolkit
Use structure first, indicators second:
- support/resistance and swing structure;
- EMA20/50/200 for trend/pullback context;
- RSI14 for momentum/exhaustion;
- ATR14 for volatility and SL buffer;
- VWAP where reliable intraday data is available;
- Volume Profile: POC, VAH, VAL and value-area acceptance/rejection when available;
- liquidity sweep, displacement, break/retest/reclaim as entry triggers.

## Gold-specific context
For XAUUSD, always consider:
- DXY;
- US Treasury yields, especially US10Y and real-yield direction when available;
- Fed expectations/rates;
- US CPI/PCE/NFP/jobs/retail/growth data;
- geopolitical safe-haven demand;
- major risk-on/risk-off shifts.
Do not infer direction from one macro variable alone; combine with price structure.

## Silver-specific context
XAGUSD shares precious-metal drivers with gold but has stronger industrial/cyclical sensitivity and can be more volatile. Use a wider structure/ATR allowance when the chart requires it. Gold/silver relative behavior may be useful context but is not a standalone signal.

## MARKET entry preference
Strong MARKET setup generally requires:
1. H4/H1 bias not materially conflicting;
2. price at a meaningful M15/M5 location, not chased far from structure;
3. trigger such as sweep-reclaim, rejection, breakout-retest or displacement-pullback;
4. no immediate high-impact event that invalidates the timing;
5. exact current symbol price refreshed immediately before execution.

## SL / TP
- SL must be beyond the structure that invalidates the thesis; ATR is only a minimum buffer/floor.
- Do not place the same fixed-point SL on every gold/silver setup.
- TP should target the next meaningful liquidity/SR/VAH-VAL/POC-related objective or measured continuation area.
- RR must be reported after structure-defined SL and target are known, not reverse-engineered.

## Existing scalp workflow context
A prior MT5 scalp project used XAUUSD and BTCUSD with M15/M5/M1 and separate symbol-specific methods. When discussing that EA, keep its rules separate from discretionary metal analysis and do not silently merge bot settings with live discretionary entries.

## Risk
Use position sizing from USD/% risk and SL distance. For prop-firm accounts, current firm-specific daily/max drawdown constraints override generic risk suggestions.

## Cross-chat continuation
At a new chat, read `MASTER_TRADING_STATE.md`, this file, the current data/feed status, then refresh XAUUSD/XAGUSD before any live entry or hold/cut decision.