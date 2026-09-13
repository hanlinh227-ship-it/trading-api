# CURRENT HANDOFF — MULTI-COIN SCAN / BTCUSDT BYBIT EXECUTION

Updated: 2026-09-14 UTC+7

## SINGLE TRADING AUTHORITY ENTRYPOINT
`docs/checkpoints/CURRENT_HANDOFF.md` remains the single Trading authority entrypoint. It now separates scan/research authority from production execution authority.

## SCAN/RESEARCH AUTHORITY
Canonical scanner: `docs/checkpoints/MULTI_COIN_A_PLUS_SCANNER_1_0_20260914.md`
Authority token: `MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0`.

The scanner may dynamically discover and evaluate eligible USDT-margined perpetuals across Bybit, Binance, and OKX. BTC has no built-in ranking priority. Research may return one A+ candidate, a watchlist, or `NO A+ SETUP`.

**Scan/research authority does not grant execution authority.** Scanner venue recommendation, provider consensus, G9 evidence, plugins, external repositories, or AI opinions cannot promote a symbol/venue into live-order permission.

## PRODUCTION EXECUTION AUTHORITY
Production execution remains **BTCUSDT Linear Perpetual on Bybit only**.
Canonical execution checkpoint: `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`.
Execution token: `BYBIT-BTC-STATEFLOW-2.1`.

All legacy multi-coin Bybit execution, Forex execution, Meme execution, Signal V10/V11 execution, and AI-council execution authority remain retired. The new scanner does not revive them.

## KEEP — LIVE INFRASTRUCTURE
Do not remove or replace these capabilities without an explicit execution migration:
- Bybit LIVE credential lookup (`BYBIT_AUTO_API_KEY` / `BYBIT_AUTO_API_SECRET` with existing fallback names).
- Bybit V5 signing primitive.
- VPS signed private proxy contract `/bybit/private`.
- Cloudflare VPC/service binding used by the private proxy.
- Bybit readonly health/control/deployment verification.
- Existing BTC state KV key so open BTC tranche state is not casually reset.

## STRATEGY / EVIDENCE ORDER
Indicators are not primary entry authority. The state-first stack remains:
`market structure -> sweep/reclaim or break/retest -> executed flow -> near-touch L2 liquidity/microprice -> OI/funding/premium/crowding context -> liquidation context -> volatility/regime -> risk -> execution`.

A single indicator, funding value, OI change, book imbalance, liquidation print, AI opinion, candle pattern, or aggregate score cannot independently authorize a trade.

For multi-coin research, gate-first evaluation must fail closed on stale data, insufficient liquidity/history, malformed symbol mapping, unresolved cross-venue divergence, or unclear structural invalidation.

## SCALE / RISK
- Continuous equity compounding.
- Unlimited strategic trade count; actual entries are constrained by risk/margin/market state, not a daily quota.
- Normal/Strong/A+ risk: 0.75% / 1.00% / 1.25%; hard single entry 1.50%.
- Active risk 6% normal, 8% temporary A+.
- Margin cap 65%, target reserve >=25%.
- Winner pyramiding ON; risk recycling ON.
- Add-to-loser OFF; martingale OFF; grid rescue OFF.
- DD governor: 5% x0.80, 10% x0.55, 15% x0.30, 20% new-risk lock.

A+ classification never overrides drawdown, margin, reserve, or live-execution gates.

## MICROSTRUCTURE
For BTC production execution, preferred source remains the BTC-only VPS WebSocket collector (`orderbook.50`, `publicTrade`, `allLiquidation`). REST snapshots remain a fail-safe fallback until/when that collector is deployed and healthy.

For multi-coin research, normalized public evidence from Bybit, Binance, and OKX may be used through the read-only gateway. Such evidence remains research-only.

## LIVE SWITCH
BTC/Bybit LIVE still requires BOTH:
- `BYBIT_AUTO_LIVE=true`
- `BYBIT_BTC_LIVE_ACK=true`

Never report a source commit, scanner candidate, provider quote, or PR as LIVE. Require successful worker validation/deploy plus `/bybit/health` runtime-revision/version alignment and authenticated account access.

## CANONICAL CHECKPOINTS
- Scan/research: `docs/checkpoints/MULTI_COIN_A_PLUS_SCANNER_1_0_20260914.md`
- Production execution: `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`
