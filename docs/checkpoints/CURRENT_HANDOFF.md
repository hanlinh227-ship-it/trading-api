# CURRENT HANDOFF — BTCUSDT BYBIT ONLY

Updated: 2026-09-04 UTC+7

## SINGLE TRADING AUTHORITY
The repository is now targeted at one production strategy only: **BTCUSDT Linear Perpetual on Bybit**.
Source target: `BYBIT-BTC-STATEFLOW-2.1`.
All legacy multi-coin Bybit, Forex, Meme, Signal V10/V11 and AI-council strategy/execution authority is retired.

## KEEP — LIVE INFRASTRUCTURE
Do not remove or replace these capabilities without an explicit migration:
- Bybit LIVE credential lookup (`BYBIT_AUTO_API_KEY` / `BYBIT_AUTO_API_SECRET` with existing fallback names).
- Bybit V5 signing primitive.
- VPS signed private proxy contract `/bybit/private`.
- Cloudflare VPC/service binding used by the private proxy.
- Bybit readonly health/control/deployment verification.
- Existing BTC state KV key so open BTC tranche state is not casually reset.

## STRATEGY AUTHORITY
Indicators are not primary entry authority. Use state-first evidence:
`market structure -> sweep/reclaim or break/retest -> executed flow -> near-touch L2 liquidity/microprice -> OI/funding/premium/crowding context -> liquidation context -> volatility/regime -> risk -> execution`.

A single indicator, funding value, OI change, book imbalance, liquidation print, AI opinion or candle pattern cannot independently authorize a trade.

## SCALE / RISK
- Continuous equity compounding.
- Unlimited strategic trade count; actual entries are constrained by risk/margin/market state, not a daily quota.
- Normal/Strong/A+ risk: 0.75% / 1.00% / 1.25%; hard single entry 1.50%.
- Active risk 6% normal, 8% temporary A+.
- Margin cap 65%, target reserve >=25%.
- Winner pyramiding ON; risk recycling ON.
- Add-to-loser OFF; martingale OFF; grid rescue OFF.
- DD governor: 5% x0.80, 10% x0.55, 15% x0.30, 20% new-risk lock.

## MICROSTRUCTURE
Preferred source is the BTC-only VPS WebSocket collector (`orderbook.50`, `publicTrade`, `allLiquidation`). REST snapshots remain a fail-safe fallback until/when the collector is deployed and healthy.

## LIVE SWITCH
LIVE requires BOTH:
- `BYBIT_AUTO_LIVE=true`
- `BYBIT_BTC_LIVE_ACK=true`

Never report a source commit as LIVE. Require successful worker validation/deploy plus `/bybit/health` runtime-revision/version alignment and authenticated account access.

## CANONICAL CHECKPOINT
Read `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md` for the migration and strategy details.
