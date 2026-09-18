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

## AI Legion addendum — 2026-09-19

The autonomous AI Legion is integrated as a subordinate evidence gate, not as a replacement strategy or execution authority.

- StateFlow selects the BTCUSDT candidate first.
- Three required distinct Model Mesh workers evaluate structure/regime, flow/liquidity and derivatives/risk; a fourth distinct worker is an optional independent checker.
- Required structure and flow roles must SUPPORT. Any required VETO blocks new risk. The optional checker may veto. No majority vote is used.
- AI output can only reduce the deterministic risk multiplier to 0.50..1.00. It cannot increase risk, change leverage, place orders, alter credentials or expand the BTC-only execution universe.
- AI receives public market/candidate evidence only. Secrets and private account state stay outside provider prompts.
- Demo and Live use the same engine, risk, reconciliation and native-protection path. Demo targets Bybit Demo REST; Live retains the existing Bybit production transport.
- Live AI-autotrade requires `BYBIT_AUTO_LIVE=true`, `BYBIT_BTC_LIVE_ACK=true` and `BYBIT_AI_LEGION_LIVE_ENABLED=true`.
- Missing/stale AI evidence fails closed for new DEMO/LIVE risk, while deterministic management of an already-open protected position continues.

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
- Private signed requests are sent directly from Cloudflare Worker to Bybit V5 REST; the canonical runtime no longer requires the VPS private proxy.
- Every live entry must be reconciled after fill and must have a verified native stop; failed protection verification triggers emergency reduce-only flattening.
- Smart cut remains multi-signal structure+flow invalidation and reduce-only.

## Microstructure transport
The canonical collector is now the Cloudflare `BybitMarketStream` Durable Object. It opens an outbound Bybit public linear WebSocket and subscribes to:
- `orderbook.50.BTCUSDT`
- `publicTrade.BTCUSDT`
- `allLiquidation.BTCUSDT`
- `tickers.BTCUSDT`

REST order-book/recent-trade snapshots remain available as diagnostics/fallback data, but fresh cloud WebSocket evidence is required for autonomous new-risk admission. The legacy VPS bridge may remain as historical code/evidence only and has zero canonical runtime authority.

## Legacy cleanup
Execution code under old V10/V11 runtime trees and unused AI/indicator provider modules is removed. Historical research/checkpoint documents can remain as non-executable evidence; they have zero production authority.
