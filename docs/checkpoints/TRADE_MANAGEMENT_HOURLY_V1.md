# HOURLY MANAGED-ENTRY V1 — FOREX + CRYPTO

Updated: 2026-08-17 15:30 UTC+7
Status: RESEARCH PROTOCOL. NO SCHEDULE/AUTOMATION.

## Objective
Every filled MARKET or LIMIT entry is treated as a managed position. In future live/research captures, the trade is reviewed at H+1, H+2, H+3... until TP, SL, CUT or expiry.

## Statistics
Outcomes are separated into:
- TP
- SL
- CUT
- UNRESOLVED/EXPIRED

User-facing win rate is defined as `TP / (TP + SL)`; CUT is excluded from this win-rate denominator as requested.

To prevent artificial inflation, every report MUST ALSO show:
- CUT count and CUT rate;
- average CUT P/L in R;
- total managed expectancy including CUT;
- TP/SL RR and effective realized R distribution.

A method cannot be promoted merely because CUT exclusion pushes displayed WR above 80%.

## Hourly review inputs
At every review, only information observable at that hour may be used.

### Common
1. exact price/time;
2. latest structure/path on H1/M15/M5;
3. current momentum/trend/volatility state using the existing minimal stack;
4. distance to original structural invalidation and realistic target;
5. new material news since previous review;
6. scheduled event risk inside the remaining holding horizon;
7. whether the original thesis is strengthening, unchanged, weakening, or invalidated.

### Forex
Technical core remains F8:
- EMA20/50, RSI14, ATR14, ADX14;
- 3h/6h/12h/24h/72h cross-currency factor coherence;
- dispersion/rank separation;
- 8h session state;
- pair archetype;
- H4/H1 structure, M15 setup, M5 execution.

Macro/news profiles:
- USD: Fed/rates, PCE/CPI, labour/NFP, US yields.
- EUR: ECB, HICP/core, wages/services, growth/energy.
- GBP: BoE, CPI/services, wages, activity.
- JPY: BoJ, CPI/wages, JGB yields, carry/intervention.
- CHF: SNB, inflation, risk-off, intervention.
- CAD: BoC, CPI/jobs, oil, US trade/growth.
- AUD: RBA, trimmed inflation, labour, China/commodities/risk.
- NZD: RBNZ, CPI, labour/spare capacity, dairy/global rates.

Economic-calendar logic:
- calendar is a risk modifier, not automatic BUY/SELL;
- major event within holding horizon reduces tolerance for weak structure;
- do not open a marginal setup immediately before a high-impact release;
- an existing trade may HOLD through an event only if structure/current edge remains strong enough under the account rules;
- a new event/news shock that materially invalidates the thesis is a valid CUT trigger.

### Crypto
State priority:
1. BTC direction/relative strength;
2. market breadth/regime;
3. D1/H4/H1 structure;
4. 6h/24h/72h momentum;
5. M15/M5 location and anti-chase;
6. fresh order flow only when genuinely available;
7. material exchange/regulatory/security/project-specific news;
8. macro calendar capable of shocking risk assets.

## Entry execution
### MARKET
Use only for fresh continuation/displacement with acceptable location and realistic liquidity room. Do not chase an already extended move.

### LIMIT
Use only when a structural pullback/retest is expected. Do not place a universal fixed-R pullback.

## TP/SL
- Structural invalidation first; ATR is only buffer/normalizer.
- Do not widen SL after entry to rescue an invalid thesis.
- TP is based on liquidity/range/structure.
- New managed-entry research target: planned/effective RR typically 1.0–1.5. RR may exceed 1.5 only when structure provides genuine room; do not compress or extend TP just to manufacture statistics.

## HOLD
HOLD when original thesis remains valid and at least two independent supports remain: HTF/current-state bias, structure/path, macro/news/calendar context, momentum/strength/regime.

## CUT
CUT before original SL only when observable evidence materially invalidates the original edge, e.g.:
- opposite structure break + failed reclaim;
- factor/market regime flip against position;
- failed breakout/displacement;
- pullback thesis invalidates instead of merely retracing;
- fresh news/event materially changes expected distribution;
- correlation/factor evidence collapses.

Do NOT CUT solely because the position is red or close to SL.

## Historical-data limitation
Existing committed Forex/Crypto blind result JSONs usually contain entry-time features and final TP/SL outcome but do NOT preserve full hour-by-hour price + indicator + point-in-time news/calendar snapshots for every trade. Therefore:
- entry methodology can be re-audited offline;
- a true historical H+1/H+2 CUT/HOLD validation cannot be reconstructed honestly from all old blocks without fetching/reconstructing missing point-in-time data;
- outcome-derived fields must never be used to pretend an hourly CUT was observable;
- any oracle/upper-bound CUT analysis is diagnostic only, never validation.

## Required capture schema going forward
Every filled position should persist:
- entry timestamp/price/side/SL/TP/plannedRR;
- entry state snapshot;
- hourlyReviews[] containing timestamp, price, H1/M15/M5 state, relevant indicator values, factor/breadth/BTC state, news/calendar summary, decision HOLD/CUT, reason;
- finalOutcome TP/SL/CUT/EXPIRED;
- realizedR;
- if CUT: cutPrice, cutR, cutReason.

## Promotion target
Report success only when a genuinely blind/held-out dataset with observable review snapshots reaches BOTH:
- displayed TP/SL WR >=80%;
- average planned/effective RR between 1.0 and 1.5;
AND managed expectancy including CUT remains positive on a non-trivial sample.
