# CURRENT HANDOFF — BTCUSDT BYBIT ONLY

Updated: 2026-09-19 UTC+7

## SINGLE TRADING AUTHORITY
The repository is now targeted at one production strategy only: **BTCUSDT Linear Perpetual on Bybit**.
Source target: `BYBIT-BTC-STATEFLOW-2.1`.
All legacy multi-coin Bybit, Forex, Meme, Signal V10/V11 and AI-council strategy/execution authority is retired.

## KEEP — LIVE INFRASTRUCTURE
Do not remove or replace these capabilities without an explicit migration:
- Bybit LIVE credential lookup (`BYBIT_AUTO_API_KEY` / `BYBIT_AUTO_API_SECRET` with existing fallback names).
- Separate Bybit Demo credential lookup (`BYBIT_DEMO_API_KEY` / `BYBIT_DEMO_API_SECRET`).
- Bybit V5 signing primitive.
- Direct Cloudflare -> Bybit signed REST transport.
- Cloudflare-native public WebSocket collector via `BybitMarketStream` Durable Object.
- Bybit readonly health/control/deployment verification.
- Existing BTC state KV key so open BTC tranche state is not casually reset.

The canonical V1 runtime no longer requires a VPS or VPC/private bridge.

## STRATEGY AUTHORITY
Indicators are not primary entry authority. Use state-first evidence:
`market structure -> sweep/reclaim or break/retest -> executed flow -> near-touch L2 liquidity/microprice -> OI/funding/premium/crowding context -> liquidation context -> volatility/regime -> risk -> execution`.

A single indicator, funding value, OI change, book imbalance, liquidation print, AI opinion or candle pattern cannot independently authorize a trade.


## AI LEGION — CONTINUOUS AUTOTRADE V2 MARKET INTELLIGENCE
The existing StateFlow engine remains the strategy/execution authority. The AI Legion is a subordinate evidence plane attached after deterministic setup selection and before new-risk admission.

Role contract:
- `structure_regime_agent`: structure, sweep/reclaim, break/retest and regime coherence.
- `flow_liquidity_agent`: executed flow, near-touch L2, microprice and liquidation coherence.
- `derivatives_risk_agent`: OI/funding/premium/crowding, cost and execution-risk context.
- `independent_checker`: contradiction/staleness checker when a fourth distinct worker is available.
- All roles use the market-intelligence playbook for structure/flow/derivatives/stop-target coherence. Stops are not treated as unsweepable.

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
`Cloudflare Bybit WebSocket event -> StateFlow setup -> AI Legion evidence gate -> deterministic Risk Governor -> direct Bybit REST execution -> fill/protection reconciliation`.

## SCALE / RISK
- Progressive continuous compounding: dollar risk grows automatically with the capital base and the percentage multiplier increases gradually only at larger realized-capital tiers.
- Scale-up is realized-capital-first. Unrealized profit receives only the bounded capital-base credit already defined by the risk engine, so a temporary floating winner cannot instantly unlock a large risk jump.
- Equity-scale multiplier: $39=0.75x, $50=0.80x, $75=0.88x, $100=0.95x, $150=1.00x, $250=1.05x, $500=1.10x, $1k=1.16x, $2.5k=1.22x, $5k=1.28x, $10k=1.32x, $25k+=1.35x.
- Normal/Strong/A+ base risk remains 0.75% / 1.00% / 1.25%; hard single-entry cap remains 1.50%, so growth cannot widen the absolute per-entry ceiling beyond authority.
- Losses contract risk twice: the capital base falls immediately and the drawdown multiplier reduces percentage risk.
- DD governor: 2% x0.92, 5% x0.80, 8% x0.65, 10% x0.55, 15% x0.30, 20% new-risk lock.
- Active risk 6% normal, 8% temporary A+.
- The full account balance may be used as eligible capital/margin capacity: portfolio margin cap 100%, per-position margin cap 100%, minimum reserve 0%. This does NOT mean 100% stop-loss risk; per-entry and active-risk limits remain enforced.
- No daily loss limit, no daily profit cap, no daily max-trade count, no daily target and no time-based daily lock. The engine may keep trading while valid setups exist.
- Unlimited strategic trade count; actual entries are constrained by per-trade risk, active-risk capacity, drawdown state, market quality, AI evidence and exchange margin—not by a daily quota.
- Winner pyramiding ON; risk recycling ON.
- Add-to-loser OFF; martingale OFF; grid rescue OFF.

## LATENCY PROFILE
- Zero physical/network latency is impossible. The runtime is therefore optimized for minimum internal decision/execution delay while preserving risk and AI gates.
- Cloud market-event debounce default: 150 ms; hard floor: 75 ms.
- Market events arriving during an in-flight evaluation are coalesced and immediately re-evaluated after the current cycle, rather than silently dropped.
- AI Legion refresh is off the critical market-data path when a Durable Object context is available; stale AI evidence still blocks new DEMO/LIVE risk until a fresh cached decision exists.
- Account/capital reconciliation runs in parallel with the trading decision path.
- BTCUSDT instrument metadata is cached in-process for 5 minutes to remove a redundant public REST call from most market events.
- Post-order fill reconciliation polls at 80 ms intervals instead of 200 ms.
- No latency optimization may bypass native protection, freshness, AI veto, risk governor, symbol authority or Demo/Live separation.

## MICROSTRUCTURE
Preferred source is the Cloudflare-native outbound Bybit WebSocket collector (`orderbook.50.BTCUSDT`, `publicTrade.BTCUSDT`, `allLiquidation.BTCUSDT`, `tickers.BTCUSDT`). REST snapshots remain a diagnostic/fail-safe fallback. New autonomous risk requires fresh cloud-stream evidence.

## LIVE SWITCH
LIVE AI-autotrade requires ALL THREE:
- `BYBIT_AUTO_LIVE=true`
- `BYBIT_BTC_LIVE_ACK=true`
- `BYBIT_AI_LEGION_LIVE_ENABLED=true`

Never report a source commit as LIVE. Require successful worker validation/deploy plus `/bybit/health` runtime-revision/version alignment and authenticated account access.

## CANONICAL CHECKPOINT
Read `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md` for the strategy authority.
Read `docs/checkpoints/BYBIT_AI_CLOUD_AUTOTRADE_V1_20260919.md` for the VPS-free cloud runtime, AI Legion roles, Demo/Live activation order and credential handoff.
Read `docs/checkpoints/BYBIT_AI_MARKET_INTELLIGENCE_PLAYBOOK_V1_20260919.md` for evidence hierarchy, stop/target geometry, coin research and bounded self-calibration.
