# CURRENT HANDOFF — BTCUSDT BYBIT ONLY

Updated: 2026-09-19 UTC+7

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


## AI LEGION — CONTINUOUS AUTOTRADE V1
The existing StateFlow engine remains the strategy/execution authority. The AI Legion is a subordinate evidence plane attached after deterministic setup selection and before new-risk admission.

Role contract:
- `structure_regime_agent`: structure, sweep/reclaim, break/retest and regime coherence.
- `flow_liquidity_agent`: executed flow, near-touch L2, microprice and liquidation coherence.
- `derivatives_risk_agent`: OI/funding/premium/crowding, cost and execution-risk context.
- `independent_checker`: contradiction/staleness checker when a fourth distinct worker is available.

Rules:
- One selected Model Mesh worker/model family per role; minimum three distinct workers for autonomous new risk.
- No majority vote. Required structure and flow roles must explicitly SUPPORT; any required VETO blocks the entry; the independent checker may veto.
- AI receives PUBLIC market/candidate evidence only. Account secrets, API keys and hidden reasoning are not sent to the model.
- AI may block a trade or reduce the deterministic risk multiplier; AI may never increase risk, set leverage, submit/cancel orders, mutate credentials, widen symbol authority, or override StateFlow/Risk Governor.
- Stale/missing/invalid AI evidence fails closed for DEMO/LIVE new entries. Existing protected-position management continues under deterministic StateFlow even when AI is unavailable.
- The event-driven path may refresh AI asynchronously and wait for the next market-state event rather than blocking the fast market-data loop on model latency.

Execution modes:
- `PAPER`: produces candidates/shadow AI evidence only; no exchange order.
- `DEMO`: `BYBIT_AUTO_DEMO=true`; uses the same StateFlow + AI Legion + risk + reconciliation path against Bybit Demo REST. Prefer `BYBIT_DEMO_API_KEY` / `BYBIT_DEMO_API_SECRET`; legacy HYRO demo names are fallback only.
- `LIVE`: requires the existing two live switches plus `BYBIT_AI_LEGION_LIVE_ENABLED=true`. The new AI switch is an additional explicit permission for AI-gated live entries, not a replacement for the existing Bybit live acknowledgements.
- DEMO and LIVE requested together is a hard conflict and blocks execution.

The Legion never becomes a second trading authority. Final chain:
`VPS market event -> StateFlow setup -> AI Legion evidence gate -> deterministic Risk Governor -> Bybit execution -> fill/protection reconciliation`.

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
LIVE AI-autotrade requires ALL THREE:
- `BYBIT_AUTO_LIVE=true`
- `BYBIT_BTC_LIVE_ACK=true`
- `BYBIT_AI_LEGION_LIVE_ENABLED=true`

Never report a source commit as LIVE. Require successful worker validation/deploy plus `/bybit/health` runtime-revision/version alignment and authenticated account access.

## CANONICAL CHECKPOINT
Read `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md` for the migration and strategy details.
