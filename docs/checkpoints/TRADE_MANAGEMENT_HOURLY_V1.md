# HOURLY ROLLING BLIND MANAGEMENT V2 — FOREX + CRYPTO

Updated: 2026-08-17 15:34 UTC+7
Status: RESEARCH/BACKTEST PROTOCOL. NO SCHEDULE/AUTOMATION.

## Correct objective
This is NOT a live reminder/scheduler. It is a sequential blind-backtest rule applied AFTER a MARKET entry is filled or a LIMIT order actually fills.

For every filled position, the backtest must re-open the decision every 1 hour using only information that would have been observable up to that review timestamp. The position is then classified HOLD or CUT. If HOLD, advance exactly one more hour and repeat. Never expose later candles/news while deciding an earlier review.

## Sequential test clock
1. Generate the original BUY/SELL + MARKET/LIMIT + structural SL + TP at signal time T0 using only data <= T0.
2. MARKET: fill according to the frozen execution rule. LIMIT: remain pending until legitimately filled; no hourly position review before fill.
3. Let Tf = actual fill timestamp.
4. Review #1 at Tf + 1h using only data <= Tf+1h.
5. Decide HOLD or CUT.
6. If HOLD, review #2 at Tf + 2h using only data <= Tf+2h.
7. Repeat at H+3, H+4... until TP, SL, CUT, or frozen expiry/horizon.
8. If TP or SL occurs between two review timestamps, that barrier result happens first; the backtest may not retroactively CUT at the next review.

This means a setup can be valid at entry but later deteriorate. The hourly manager is specifically intended to detect that deterioration before the original SL when it is observable in real time.

## Outcomes and statistics
Final outcomes:
- TP
- SL
- CUT
- EXPIRED/UNRESOLVED

Requested display win rate:
`WR = TP / (TP + SL)`
CUT is recorded separately and excluded from this WR denominator.

To keep the test economically honest every report MUST ALSO show:
- CUT count and CUT rate;
- CUT winners vs CUT losers if cut above/below entry;
- average CUT realized R;
- total managed expectancy INCLUDING CUT;
- average planned RR and effective realized payoff;
- number of positions saved from later SL by a legitimate CUT;
- number of positions CUT that would later have reached TP (false cuts);
- HOLD-to-TP and HOLD-to-SL transitions.

A method is not promoted just because excluding CUT mathematically raises displayed WR.

## Hourly re-analysis — common layer
At each H+N checkpoint recompute from information available at that timestamp:
1. exact current price and path since previous review;
2. whether original structural thesis is intact;
3. H1/M15/M5 structure and displacement/reclaim/failure;
4. EMA20/50 trend/value/slope;
5. RSI14 momentum/exhaustion;
6. ATR14 volatility/invalidation context;
7. ADX14 trend-vs-chop state;
8. distance from price to original SL and TP;
9. whether remaining reward still justifies remaining risk;
10. market/news/calendar state if point-in-time information exists in the tested dataset.

The manager must not widen the original SL to rescue a bad trade. It may CUT early or HOLD the original structure. TP/SL may only be changed in a future explicitly tested trailing/retargeting version; V2 keeps barriers frozen so the effect of HOLD/CUT can be isolated.

# FOREX

## Entry/bias core
Keep frozen F8 as the starting comparator:
- 3h/6h/12h/24h/72h cross-currency factor coherence;
- cross-sectional dispersion/rank separation;
- 8h session state;
- pair archetype;
- H4/H1 structure;
- M15 setup and M5 execution;
- EMA20/50, RSI14, ATR14, ADX14 only for distinct roles.

## Macro/news/economic-calendar layer
At entry and each H+N review, use point-in-time information when available:
- USD: Fed/rates, PCE/CPI, NFP/labour, US yields;
- EUR: ECB, HICP/core, wages/services, growth/energy;
- GBP: BoE, CPI/services, wages, activity;
- JPY: BoJ, CPI/wages, JGB yields, carry/intervention;
- CHF: SNB, inflation, risk-off, intervention;
- CAD: BoC, CPI/jobs, oil, US growth/trade;
- AUD: RBA, trimmed inflation, labour, China/commodities/risk;
- NZD: RBNZ, CPI, labour/spare capacity, dairy/global rates.

Calendar/news do NOT directly dictate BUY/SELL. They can strengthen, weaken, or invalidate the already-formed thesis. A new high-impact event, surprise, central-bank communication, intervention risk, or yield/risk shift is a valid management input only if it was observable at that H+N checkpoint.

## Forex HOLD examples
HOLD when most of the following remain intact:
- factor differential still favors the trade;
- H1/M15 structure has not failed;
- price pullback remains corrective rather than impulsive against position;
- session/liquidity path still supports the target;
- no new macro/calendar information materially reverses the distribution;
- remaining reward vs original invalidation is still sensible.

## Forex CUT examples
CUT only on observable deterioration, such as:
- opposite H1/M15 MSS/break + failed reclaim;
- base-vs-quote factor spread flips materially and persists;
- breakout becomes confirmed failure rather than a normal retest;
- common-factor/day regime shifts against the trade;
- new macro/news/event information invalidates the original thesis;
- price reaches a state where remaining upside/downside no longer compensates the still-open structural risk.

# CRYPTO

## Entry/bias core
At entry and H+N reviews prioritize:
1. BTC direction/relative strength;
2. market breadth/regime;
3. D1/H4/H1 structure;
4. 6h/24h/72h momentum;
5. M15/M5 structure/location/anti-chase;
6. fresh order flow only when genuinely available;
7. exchange/regulatory/security/project-specific information;
8. macro events capable of moving risk assets.

Static symbol reputation must not override current market state.

## Crypto HOLD examples
HOLD when:
- BTC/regime still supports the side;
- the symbol preserves relative strength/weakness consistent with entry;
- H1/M15 breakout/retest remains structurally valid;
- M5 weakness is only local noise rather than confirmed failure;
- no material new market/project/news shock invalidates the thesis;
- target still has realistic liquidity room.

## Crypto CUT examples
CUT when:
- BTC/regime flips hard against the position;
- market breadth collapses/expands against the thesis together with structural failure;
- relative strength disappears and the symbol loses the key H1/M15 level;
- failed breakout is confirmed by reclaim on the wrong side;
- a material exchange/security/regulatory/project event changes the trade distribution;
- remaining path to TP becomes structurally inferior to remaining downside/upside to invalidation.

# MARKET vs LIMIT inside the rolling test
- MARKET is evaluated only after its actual market fill.
- LIMIT is not considered an active trade until the pending order fills.
- If TP would have been reached before a LIMIT fill, cancel according to the frozen pending-order rule; do not pretend a fill occurred.
- Once a LIMIT fills, it enters the exact same H+1/H+2/... HOLD/CUT engine as MARKET.

# RR and barriers
Initial SL = structural invalidation with ATR only as buffer/normalizer.
Initial TP = realistic liquidity/range/structure target.
Research promotion target uses average planned RR approximately 1.0–1.5.
Do not shrink TP to manufacture WR and do not widen SL after entry.

# Blind-test integrity
For each review H+N:
- freeze all inputs and the HOLD/CUT decision before revealing H+(N+1);
- future outcome, MFE/MAE and later direction are evaluation labels only;
- they may never be entry or management features;
- a revealed historical review becomes development data and cannot later be called untouched blind validation.

# Historical-data limitation
Old committed result JSONs do not uniformly contain complete hour-by-hour candles/features plus point-in-time news/calendar snapshots for every trade. Therefore the corrected research path is:
1. use any committed candle/path data that actually exists to reconstruct sequential H+N reviews without provider calls;
2. where only final outcomes exist, do NOT fabricate hourly decisions;
3. news/calendar can only be included in historical H+N reviews where point-in-time archived context exists;
4. do not use future outcomes as a substitute for missing hourly state.

# Promotion condition
Only report the new managed method as successful when a legitimate sequential blind/held-out sample reaches:
- TP/SL WR >= 80% after excluding CUT from that denominator as requested;
- average planned RR between 1.0 and 1.5;
- positive total managed expectancy INCLUDING CUT;
- non-trivial trade count;
- acceptable false-CUT rate;
- no hindsight leakage.

Until those conditions are met, report the best honest result and continue development; never manufacture the target.
