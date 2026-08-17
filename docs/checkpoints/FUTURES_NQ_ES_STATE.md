# FUTURES NQ / ES STATE — SEPARATE FROM CASH INDICES

Updated: 2026-08-17 UTC+7

## SCOPE

This checkpoint is only for exact CME equity-index futures.

- MNQ = Micro E-mini Nasdaq-100 Futures.
- MES = Micro E-mini S&P 500 Futures.
- NQ/ES may be analyzed as reference contracts.
- execution preference: MNQ/MES.

Never use NDX/NAS100/SPX/US500 cash prices as a silent substitute for NQ/ES/MNQ/MES futures.

## CURRENT TWELVE DATA GROW55 STATUS

Strict direct catalog/search diagnostics on 2026-08-17 did **not** expose exact provable CME contracts for:
- NQ
- MNQ
- ES
- MES

The same policy also blocks GC/CL in the direct Twelve client when an exact COMEX/NYMEX contract cannot be proven.

Therefore `scripts/twelvedata_market.py` intentionally returns:
- `status=DATA_BLOCK`
- reason `TWELVE_DATA_FUTURES_NOT_AVAILABLE`

This is correct behavior. A same-text security, cash index, spot commodity or ambiguous continuous contract must never be reported as the requested futures quote.

## DATA-SOURCE HIERARCHY

1. Exact current MNQ/MES/NQ/ES price from the user's trading platform immediately before execution.
2. A verified authoritative futures feed with exact contract/front-month identity, CME venue and timestamp.
3. Twelve Data only if a future plan/catalog version exposes the exact contract and the integration validates it explicitly.

Until then, Twelve Data may contribute macro/spot context but **not** a claimed live NQ/MNQ/ES/MES execution price.

## CORE METHOD

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
- order flow when a reliable futures feed exists;
- economic calendar/news gate.

## ANALYSIS ORDER

1. Resolve exact contract and market state.
2. Compare NQ/ES or MNQ/MES HTF structure and SMT.
3. D1/H4 draw-on-liquidity/regime.
4. H1 intraday structure.
5. M15 setup/location.
6. M5 trigger/confirmation.
7. Refresh exact execution price from the authoritative futures source.
8. Define structural SL.
9. Calculate MNQ/MES contract count from dollar risk.
10. Set TP from structure/liquidity.

## RISK FRAMEWORK

- intended maximum total SL approximately USD 500 per trade;
- target profit approximately USD 1,500 when structure genuinely allows it;
- target RR approximately 1:3.

**Structural SL first, position size second.** Never move the stop solely to force the dollar/RR target.

## SESSION / NEWS

Consider European and US sessions as appropriate. Always refresh major US macro risk: Fed/FOMC, CPI/PCE, jobs/NFP, Treasury yields, geopolitical shocks and material mega-cap/tech context for Nasdaq.

## OUTPUT STANDARD

A final futures setup must show:
- exact contract;
- MARKET / LIMIT / DATA_BLOCK;
- exact current/reference price + source + timestamp semantics;
- structural SL;
- MNQ/MES contract count;
- TP and estimated USD P/L;
- ICT/SMT/VWAP/VP reasoning;
- high-impact news/session risk.

Normally choose the stronger MNQ/MES setup rather than force both.
