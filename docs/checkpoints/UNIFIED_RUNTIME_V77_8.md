# UNIFIED RUNTIME V77.8.0

Updated: 2026-08-18 UTC+7
Status: canonical production Hub over V73/V74/V75; V76 remains research-only.

## Purpose

V77.8.0 unifies discovery, canonical gating, state and Telegram output in one Worker: `cloudflare-worker/index.js`.

Topology:

`GitHub main -> Cloudflare Builds -> trading-v77-scanner -> Twelve Data / exact crypto exchanges -> TRADING_V77_STATE -> Telegram Hub`

## Authority locks

- V73 frozen prior is imported at build time and never retuned.
- V74 remains the live authority.
- V75 data-integrity rules remain mandatory.
- V76 R2 remains research-only, retained `[]`, promoted Forex `0/28`.
- Legacy score is not an execution authority.

## Canonical gate

`exact identity -> closed/fresh data -> D1/H4/H1 -> V73 prior -> M15 tradable location -> strict M5 MSS/displacement/retest -> structural SL -> clean room -> news/context -> final execution quote/cost`

RR1 default. RR2 requires >=2.2R clean room. Estimated execution cost must be <=0.10R.

## Crypto

Crypto is exchange-native for deep analysis and execution. Exact Bybit/OKX/Binance spot identities are discovered in bulk. Top candidates must get closed 5m/15m/1h/4h/1d candles plus bid/ask from one exact venue. Missing identities are not remapped. Crypto scans do not consume Twelve Data Grow55 quota.

## Forex / Metal

Forex and Metal use Twelve Data batch analysis with H1 reuse. Planned costs are approximately 40 credits for all 28 Forex pairs and 10 credits for XAUUSD/XAGUSD. Quota is checked before scans. Twelve Data reference price never substitutes for an executable broker quote; therefore new Forex/Metal MARKET/LIMIT orders are blocked until a real broker bid/ask feed is connected.

## Telegram Hub

`🧭 HUB TOP SETUPS` scans Crypto first, then Forex, then Metal, and ranks the strongest canonical stages. Individual market buttons remain available. WATCH output shows the exact missing stage and, once the setup reaches the news/execution portion, indicative planned Entry/SL/TP.

A setup at `NEWS_CONTEXT_REQUIRED` can receive a 30-minute manual `Tin OK` clearance. Optional `NEWS_GATE_URL` can automate that gate later.

Only fully verified execution setups can create MARKET/LIMIT. Current automatic executable lifecycle is Crypto-only because it has exact venue bid/ask.

## State continuity

KV binding `TRADING_STATE` continues to use the existing `TRADING_V77_STATE` namespace and `v775:books` key.

## Validation

`.github/workflows/validate-cloudflare-v77.yml` validates V77.8 tokens, syntax and Wrangler bundle dry-run. Cloudflare auto-deploys `main` through the already connected Builds pipeline.
