# FUTURES NQ / ES STATE — SEPARATE FROM CASH INDICES

Updated: 2026-08-17 UTC+7

## Scope and instrument separation
This checkpoint is only for CME equity-index futures.

- MNQ = Micro E-mini Nasdaq-100 Futures.
- MES = Micro E-mini S&P 500 Futures.
- NQ/ES may be analyzed as reference contracts.
- User execution preference for this system is MNQ/MES.

Never use NDX/NAS100/SPX/US500 cash prices as a silent substitute for NQ/ES/MNQ/MES futures, and never report a cash quote as a futures quote.

## Data-source hierarchy
1. Exact current MNQ/MES/NQ/ES price supplied by the user's trading platform immediately before execution.
2. A verified authoritative futures feed with exact contract/front-month identity, exchange and timestamp.
3. Twelve Data Grow 55 only when the exact futures instrument/contract mapping is explicitly verified.

Twelve Data can be useful for broader futures/commodity context, but an ambiguous symbol, continuous contract or cash proxy is not sufficient for MARKET execution.

If exact contract/feed identity cannot be verified, return `DATA_BLOCK` for a claimed live MARKET price rather than substitute another instrument.

## Core method
Integrated ICT / futures workflow:
- HTF draw on liquidity;
- liquidity sweeps;
- MSS / displacement;
- FVG / IFVG;
- breaker / unicorn where structurally valid;
- premium/discount;
- SMT divergence between Nasdaq and S&P;
- Silver Bullet / macro windows / NDOG / NWOG where relevant;
- VWAP;
- Volume Profile;
- order flow when a reliable feed is available;
- economic calendar/news gate.

## Analysis order
1. Resolve exact contract and market state.
2. Compare NQ/ES or MNQ/MES HTF structure and SMT.
3. D1/H4 draw-on-liquidity and regime.
4. H1 intraday structure.
5. M15 setup/location.
6. M5 trigger/confirmation.
7. Refresh exact execution price from the preferred futures source.
8. Define structural SL.
9. Calculate MNQ/MES contract count from dollar risk.
10. Set TP from structure/liquidity; never manufacture a target solely to force RR.

## Risk framework
Current user framework for this micro-futures system:
- intended maximum total SL approximately USD 500 per trade;
- target profit approximately USD 1,500 when structure genuinely allows it;
- target RR approximately 1:3.

Critical rule: **structural SL first, position size second**. Never move the stop closer merely to force the dollar/RR target.

## Session and news context
European-session opportunities and later US-session opportunities may both be considered. Resolve session times in Vietnam time and account for US daylight-saving changes.

Always check major US macro events relevant to NQ/ES, especially Fed/FOMC, CPI/PCE, NFP/jobs, Treasury yields, major risk shocks and material mega-cap/tech context for Nasdaq.

## Output standard
For a final futures setup report:
- exact symbol/contract;
- MARKET / LIMIT / DATA_BLOCK as applicable;
- exact current/reference price + source + timestamp semantics;
- structural SL;
- MNQ/MES contract count from dollar risk;
- TP levels and estimated USD P/L;
- ICT/SMT/VWAP/VP reasoning;
- high-impact news/session risk.

Normally choose the single stronger MNQ/MES setup rather than forcing both.
