# METALS STATE — XAUUSD / XAGUSD

Updated: 2026-08-17 UTC+7

## SCOPE / IDENTITY

- XAUUSD = spot gold versus USD.
- XAGUSD = spot silver versus USD.
- XAUUSD is not GC futures.
- XAGUSD is not SI futures.

Never substitute COMEX futures, ETFs or broker CFDs for the requested spot instrument silently.

## DATA POLICY — GROW55 DIRECT STRICT V3

Canonical client: `scripts/twelvedata_market.py`.

Verified mappings:
- `XAUUSD -> XAU/USD`, expected type `Precious Metal`;
- `XAGUSD -> XAG/USD`, expected type `Precious Metal`.

The current single-symbol path:
1. validates exact Twelve Data metadata on D1/H4/H1/M15/M5/M1;
2. excludes unfinished candles from indicator/trigger calculations;
3. uses `/quote` to verify identity and `last_quote_at`;
4. uses `/price` for the latest aggregated price only after identity is proven;
5. rejects quote age >65 seconds as `DATA_BLOCK`;
6. keeps V74 strict MARKET freshness target <=30 seconds;
7. leaves bid/ask/spread unverified when Twelve Data does not supply broker execution fields.

The old Cloudflare Worker is not part of the canonical metals runtime.

## TIMEFRAME WORKFLOW

- D1/H4: macro regime, major structure/liquidity and premium/discount.
- H1: intraday bias and structural leg.
- M15: setup construction and key location.
- M5: close-confirmed trigger/confirmation.
- M1: recent reference only; never a substitute for exact execution quote.

## TECHNICAL TOOLKIT

Structure first, indicators second:
- swing structure / S/R;
- liquidity sweeps;
- displacement / MSS;
- FVG / imbalance / breakout-retest;
- EMA20/50/200;
- RSI14;
- ATR14;
- VWAP / Volume Profile only when reliable data exists.

## GOLD CONTEXT

For XAUUSD consider:
- DXY;
- US Treasury yields / real yields when available;
- Fed/rate expectations;
- CPI/PCE/NFP/jobs/growth;
- geopolitical safe-haven demand;
- broad risk sentiment.

## SILVER CONTEXT

XAGUSD shares precious-metal drivers but has stronger industrial/cyclical sensitivity and typically higher volatility. Do not copy gold point distances mechanically.

## MARKET SETUP STANDARD

A strong setup requires:
1. exact spot identity;
2. fresh provider timestamp;
3. D1/H4/H1 alignment or a clearly defined counter-trend structure;
4. meaningful M15 location;
5. M5 close-confirmed trigger;
6. current macro/news context;
7. final execution-venue spread confirmation when MARKET precision matters.

## SL / TP

- structural invalidation defines SL;
- ATR is a volatility floor only;
- TP follows defensible liquidity / structure;
- RR is calculated after structural SL and target are defined.

For prop-firm trading, firm-specific drawdown/risk rules override generic sizing guidance.
