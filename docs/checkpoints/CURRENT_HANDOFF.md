# CURRENT HANDOFF — BYBIT TOP-100 MARKET-CAP STATEFLOW

Updated: 2026-09-19 UTC+7

## SINGLE TRADING AUTHORITY
The repository is now targeted at one production execution family: **up to 100 high-market-cap Bybit USDT Linear Perpetual symbols**, dynamically intersected with the external top-100 market-cap universe and strict Bybit liquidity/execution-quality gates.
Source target: `BYBIT-TOP100-STATEFLOW-3.0`.
Forex, Meme, Signal V10/V11 and AI-council execution authority remains retired. Legacy broad multi-coin execution is not restored blindly; only symbols passing the canonical top-100 market-cap + liquidity + anti-sweep gate may receive new risk.


## TOP-100 EXECUTION UNIVERSE
New-risk admission is fail-closed and requires all of the following:
- CoinGecko public market-cap rank <= 100 with market cap >= USD 250M; cached for 30 minutes, stale cache accepted for at most 24h.
- Active Bybit USDT linear perpetual with valid instrument metadata.
- Listing age >= 30 days when launch metadata is available.
- 24h Bybit turnover >= USD 10M.
- Open-interest value >= USD 3M.
- Spread <= 10 bps at universe admission; per-symbol strategy profile may be stricter.
- Anti-sweep liquidity score >= 0.62 from turnover, OI, spread and listing age.
- Fresh microstructure is required before new risk; the canonical trigger is the Cloudflare-native Bybit WebSocket path. Legacy VPS/VPC mirrors are fallback/diagnostic only and are not execution authority.
- Existing structure-first setup selection, sweep/reclaim or break/retest evidence, flow/near-touch depth, derivatives context, volatility, risk and execution gates remain mandatory.

This reduces stop-sweep exposure but does **not** guarantee that a stop can never be swept. Stops remain outside structural invalidation with volatility/liquidity noise buffers, and dynamic symbols use a wider anti-sweep buffer plus lower default risk/leverage than core symbols.

## KEEP — LIVE INFRASTRUCTURE
Do not remove or replace these capabilities without an explicit migration:
- Bybit LIVE credential lookup (`BYBIT_AUTO_API_KEY` / `BYBIT_AUTO_API_SECRET` with existing fallback names).
- Separate Bybit Demo credential lookup (`BYBIT_DEMO_API_KEY` / `BYBIT_DEMO_API_SECRET`).
- Bybit V5 signing primitive.
- Direct Cloudflare -> Bybit signed REST transport, with a DEMO-only authenticated Deno Deploy egress fallback when Cloudflare receives a Bybit/CloudFront 403.
- Cloudflare-native public WebSocket collector via `BybitMarketStream` Durable Object.
- Bybit readonly health/control/deployment verification.
- Existing BTC state KV key so open BTC tranche state is not casually reset.

The canonical V1 runtime no longer requires a VPS or VPC/private bridge. Demo fallback remains serverless: Cloudflare signs the Bybit request locally, Deno receives only the signed request envelope (never the Bybit API secret), and forwards only an allowlisted set of Bybit Demo V5 private paths.

## STRATEGY AUTHORITY
Indicators are not primary entry authority. Use state-first evidence:
`market structure -> sweep/reclaim or break/retest -> executed flow -> near-touch L2 liquidity/microprice -> OI/funding/premium/crowding context -> liquidation context -> volatility/regime -> risk -> execution`.

A single indicator, funding value, OI change, book imbalance, liquidation print, AI opinion or candle pattern cannot independently authorize a trade.


## AI LEGION — SINGLE EXECUTOR + RESEARCH SWARM

The AI layer is split into one execution commander and research-only specialists.

- `order_risk_architect_agent` is the **sole AI execution commander**. It may authorize `OPEN`, `HOLD` or `CLOSE` intent after reviewing StateFlow plus research evidence.
- `macro_news_agent`, `market_structure_flow_agent` and `independent_adversarial_checker` are **research-only**. They may supply evidence, challenge a setup, or recommend lower risk, but cannot open, close, amend or cancel orders.
- The executor is sticky to one healthy model family and fails over only when that model is unavailable/unhealthy. Research workers rotate across the remaining healthy model pool.
- No model receives Bybit API secrets. The AI execution command is translated into a signed exchange write only after deterministic StateFlow/Risk Governor checks.
- The AI executor may not override symbol authority, freshness gates, exchange limits, risk ceilings, Demo/Live separation, or native-protection requirements.
- The research swarm may never increase risk. Contradictory/stale evidence is passed to the executor, which can HOLD/CLOSE or refuse OPEN.
- Existing position protection remains deterministic and single-writer even if AI is unavailable.

Continuous opportunity mode means the system continuously scans/ranks the top-100 universe and always resolves toward `OPEN`, `HOLD`, `CLOSE`, or no new risk. It does not force a trade when edge is absent.

Final chain:
`Cloudflare Bybit WS -> top-100 universe gate -> research swarm -> sole AI execution commander -> StateFlow + Risk Governor -> single Bybit V5 execution gateway -> native protection/reconciliation -> post-trade evidence`.

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
The canonical market-event authority is the Cloudflare-native Bybit WebSocket collector. Fresh Cloudflare WS evidence is accepted for both entry and position management; legacy VPS/VPC WS sources may be accepted only as compatible fallback evidence. REST snapshots remain diagnostic/fail-safe only and cannot independently authorize new risk.

## LIVE SWITCH
LIVE AI-autotrade requires ALL THREE:
- `BYBIT_AUTO_LIVE=true`
- `BYBIT_BTC_LIVE_ACK=true`
- `BYBIT_AI_LEGION_LIVE_ENABLED=true`

Never report a source commit as LIVE. Require successful worker validation/deploy plus `/bybit/health` runtime-revision/version alignment and authenticated account access.

## CANONICAL CHECKPOINT
Read `docs/checkpoints/BYBIT_TOP100_STATEFLOW_3_0_20260919.md` for the strategy authority.
Read `docs/checkpoints/BYBIT_AI_CLOUD_AUTOTRADE_V1_20260919.md` for the VPS-free cloud runtime, AI Legion roles, Demo/Live activation order and credential handoff.
Read `docs/checkpoints/BYBIT_AI_MARKET_INTELLIGENCE_PLAYBOOK_V1_20260919.md` for evidence hierarchy, stop/target geometry, coin research and bounded self-calibration.
