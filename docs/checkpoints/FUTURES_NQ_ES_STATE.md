# FUTURES NQ / ES STATE — SEPARATE FROM CASH INDICES

Updated: 2026-08-17 (UTC+7)

## Hard separation
This checkpoint is only for CME equity-index futures. Do not use it when the user asks for NAS100/USTEC/US500 cash indices unless they explicitly request futures.

## Instruments
User preference for execution: Micro Futures only when trading this system.
- MNQ = Micro E-mini Nasdaq-100 Futures.
- MES = Micro E-mini S&P 500 Futures.
NQ/ES may be analyzed as reference/front-month instruments, but execution sizing should be translated to MNQ/MES when following the user's micro-futures plan.

## Core method
Integrated ICT / futures workflow:
- HTF draw on liquidity;
- liquidity sweeps;
- MSS / displacement;
- FVG / IFVG;
- breaker / unicorn concepts where valid;
- premium/discount;
- SMT divergence between Nasdaq and S&P;
- Silver Bullet / macro windows / NDOG / NWOG where relevant;
- VWAP / Volume Profile;
- order flow when feed is available;
- economic calendar/news gate.

## Time and session context
Preference has included European session opportunities and US-session/night opportunities. If no high-quality Europe entry exists, a later US-session setup may be considered. Exact session timing should be interpreted in Vietnam time and checked against daylight-saving changes.

## Risk framework
Target framework from the user's micro-futures plan:
- maximum intended total SL approximately USD 500 per trade;
- target profit approximately USD 1,500 per trade;
- target RR around 1:3 when market structure genuinely allows it.
Critical rule: define the structural SL FIRST, then calculate MNQ/MES contract quantity so dollar risk stays within the allowed amount. Never move the SL merely to manufacture 1:3.

## Live price rule
Before finalizing any MNQ/MES entry, use a fresh current price supplied by the user/platform or a sufficiently fresh verified futures feed. If the feed is stale/unavailable, do not claim a MARKET price is live.
The user's realtime MNQ/MES platform price takes priority for execution decisions when provided immediately before entry.

## Entry output
Compare NQ/ES or MNQ/MES structure as needed, but normally choose the single better setup rather than forcing both.
Report:
- symbol;
- MARKET/LIMIT/NO TRADE as appropriate to the live request;
- exact current/referenced price and timestamp;
- structural SL;
- contract count from dollar risk;
- TP levels and expected USD P/L;
- SMT/VWAP/VP/ICT reasoning;
- high-impact news risk.

## Cross-chat continuation
Read `MASTER_TRADING_STATE.md` and this file only when the user explicitly discusses futures. Never let this checkpoint override `CASH_INDICES_STATE.md` for cash-index requests.