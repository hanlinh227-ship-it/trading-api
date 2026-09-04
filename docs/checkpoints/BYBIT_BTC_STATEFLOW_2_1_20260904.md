# BYBIT BTC STATEFLOW 2.1 — NON-INDICATOR BTC-ONLY REPLACEMENT

Date: 2026-09-04 UTC+7

## Authority
- Production strategy target: BTCUSDT Linear Perpetual only.
- Legacy multi-coin Bybit, Forex, Meme, V10/V11 signal and AI-council execution are retired.
- Bybit LIVE credential routing, signed V5 client, VPS private proxy and health/deployment infrastructure are preserved.
- Source version: `BYBIT-BTC-STATEFLOW-2.1`.
- Do not call the version LIVE until deployment and `/bybit/health` revision/version checks pass.

## Why the strategy changed
The bot no longer treats technical indicators as entry authority. The state-first stack is:
1. Price structure and liquidity: swing progression, break/retest, failed break, sweep/reclaim, range compression/expansion.
2. Executed flow: rolling 5s/15s/60s taker imbalance and burst intensity.
3. Near-touch L2 liquidity: depth imbalance inside 2/5/10 bps, distance-weighted imbalance and microprice displacement.
4. Derivatives state: open-interest change, funding, mark-index premium/basis and long/short crowding.
5. Liquidation flow: rolling long/short liquidation notional from Bybit public WebSocket when the VPS collector is available.
6. Realized volatility and directional efficiency for regime classification.

Funding, OI, order-book imbalance or a single liquidation print can never create an entry alone. Resting book data is treated as potentially spoofable; executed flow + structure confirmation is required.

## Setup families
- `TREND_PULLBACK_LIQUIDITY_RECLAIM`
- `TREND_CONTINUATION_FLOW`
- `BREAKOUT_RETEST_FLOW_CONFIRM`
- `RANGE_SELLSIDE_SWEEP_ABSORPTION`
- `RANGE_BUYSIDE_SWEEP_ABSORPTION`
- `LIQUIDATION_EXHAUSTION_RECLAIM`
- `STRUCTURE_TRANSITION_CONFIRM`

## Scale / risk
- Continuous equity compounding.
- Normal entry risk 0.75% equity; strong 1.00%; A+ 1.25%; hard single-entry cap 1.50%.
- Normal active-risk cap 6%; temporary A+ cluster cap 8%.
- Portfolio initial-margin cap 65%; target free reserve at least 25%.
- No strategic daily trade quota.
- Winner pyramiding ON; add-to-loser OFF; martingale OFF; grid rescue OFF.
- A new pyramid tranche is blocked until the newest tranche has released most of its original risk.
- Drawdown governor: 5% DD x0.80 risk, 10% x0.55, 15% x0.30, 20% new-risk lock.

## Execution safety
- LIVE still requires both `BYBIT_AUTO_LIVE=true` and `BYBIT_BTC_LIVE_ACK=true`.
- Existing Bybit API key/secret lookup is preserved.
- Private signed requests continue through `VPS_BYBIT_PRIVATE_PROXY` with direct fallback only when explicitly enabled.
- Every live entry must be reconciled after fill and must have a verified native stop; failed protection verification triggers emergency reduce-only flattening.
- Smart cut remains multi-signal structure+flow invalidation and reduce-only.

## Microstructure transport
A new source folder `bybit-live-bridge/` contains a BTC-only bridge that preserves `/bybit/private` and adds `/bybit/microstructure`. The collector subscribes to:
- `orderbook.50.BTCUSDT`
- `publicTrade.BTCUSDT`
- `allLiquidation.BTCUSDT`

The Worker treats the WebSocket collector as optional enhancement: if it is not yet installed/healthy, state construction falls back to Bybit REST order-book and recent-trade snapshots so the private LIVE API path is not broken by the migration.

## Legacy cleanup
Execution code under old V10/V11 runtime trees and unused AI/indicator provider modules is removed. Historical research/checkpoint documents can remain as non-executable evidence; they have zero production authority.
