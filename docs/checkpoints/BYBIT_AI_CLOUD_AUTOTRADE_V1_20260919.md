# BYBIT AI CLOUD AUTOTRADE — VPS-FREE ARCHITECTURE V1

Updated: 2026-09-19 UTC+7

## Objective

Run the existing BTCUSDT Bybit StateFlow continuously without a VPS or a personal computer.

Canonical path:

```
Bybit public WebSocket
  -> Cloudflare Durable Object market stream
  -> StateFlow 2.1 deterministic candidate
  -> AI Legion evidence gate
  -> deterministic Risk Governor
  -> direct Bybit V5 REST
  -> fill / native SL-TP / reconciliation
  -> position management
  -> journal / evaluation
  -> repeat
```

The Bybit API keys are intentionally NOT required during architecture/build work. They are attached only after CI, deployment, market-stream health and demo-safe preflight are green.

## Transport

### Public market data

Canonical public stream:

`wss://stream.bybit.com/v5/public/linear`

Topics:
- `orderbook.50.BTCUSDT`
- `publicTrade.BTCUSDT`
- `allLiquidation.BTCUSDT`
- `tickers.BTCUSDT`

The public stream is shared by mainnet and Demo Trading. The market stream runs inside the `BybitMarketStream` Durable Object.

The stream object:
- maintains an L50 snapshot + delta book;
- retains rolling 1s/3s/5s/15s/60s trade windows;
- retains rolling liquidation notional;
- reconnects through a Durable Object alarm after disconnect;
- emits a bounded trading evaluation only after a meaningful market-state change;
- never emits one AI call for every book update.

### Private/account/execution API

LIVE REST:
`https://api.bybit.com`

DEMO REST:
`https://api-demo.bybit.com`

Canonical private transport:
- Cloudflare Worker -> Bybit V5 REST directly.
- No VPS signed proxy.
- HMAC signing remains local to the Worker.
- Order, leverage, position, wallet and native trading-stop calls remain signed and fail closed.

Demo and Live execute through the same StateFlow/Risk/Execution code path. Only credentials and endpoint differ.

## AI Legion

AI is not a second strategy engine. The deterministic StateFlow produces the candidate first.

### Fast candidate council

1. `structure_regime_agent`
   - structure progression
   - break/retest
   - sweep/reclaim
   - regime coherence

2. `flow_liquidity_agent`
   - taker flow
   - flow acceleration
   - L2 imbalance
   - microprice
   - liquidation context

3. `derivatives_risk_agent`
   - OI
   - funding
   - premium/basis
   - crowding
   - execution cost
   - volatility risk

4. `independent_checker`
   - contradiction
   - stale evidence
   - unsupported assumptions
   - provider/model disagreement

Required new-risk admission:
- minimum 3 distinct healthy Model Mesh workers;
- structure and flow must SUPPORT;
- any required VETO blocks;
- optional independent checker may veto;
- no majority vote.

AI can:
- block an entry;
- reduce risk multiplier.

AI cannot:
- increase risk;
- change leverage;
- place/cancel orders;
- mutate credentials;
- widen BTCUSDT authority;
- change hard risk limits;
- override native-stop verification.

### Background intelligence council

Not on the sub-second execution path.

Roles can refresh asynchronously:
- `research_scout`: exchange/API/changelog context.
- `quant_researcher`: setup performance and regime statistics.
- `data_rag_analyst`: journal aggregation and evidence retrieval.
- `security_reviewer`: credential/runtime/config drift.
- `deployment_verifier`: deployed revision/runtime contract.
- `independent_checker`: challenge any promotion recommendation.

Background outputs are evidence only and cannot authorize an order.

### Post-trade learning council

Runs after closed trades / batches:
- outcome attribution;
- slippage/cost audit;
- setup-family expectancy;
- role calibration;
- stale-data incidents;
- false-positive/false-negative review.

Learning produces candidates only. It cannot self-edit Stable trading authority or auto-promote risk changes.

## Execution Modes

### PAPER
- public market data: yes
- AI analysis: yes
- exchange order: no

### DEMO
- public market data: mainnet public WebSocket
- account/order API: `api-demo.bybit.com`
- AI Legion: required
- real Bybit Demo order lifecycle: yes

### LIVE
Required operator switches:
- `BYBIT_AUTO_ENABLED=true`
- `BYBIT_AUTO_LIVE=true`
- `BYBIT_BTC_LIVE_ACK=true`
- `BYBIT_AI_LEGION_LIVE_ENABLED=true`

DEMO and LIVE simultaneously requested => hard block.

## Risk Authority

Canonical ceilings:
- Normal: 0.75%
- Strong: 1.00%
- A+: 1.25%
- hard single-entry cap: 1.50%
- active risk: 6%
- temporary A+ active risk: 8%
- portfolio initial-margin cap: 65%
- target reserve: >=25%

DD governor:
- 5% -> x0.80
- 10% -> x0.55
- 15% -> x0.30
- 20% -> new-risk lock

Runtime overrides may tighten these values only.

No martingale.
No add-to-loser.
No grid rescue.

## Continuous Evaluation

The public WebSocket can produce order-book messages at tens-of-milliseconds cadence. The trading engine must not run at message frequency.

The market-stream gate uses:
- one in-flight evaluation maximum;
- minimum evaluation gap;
- significant flow / move / book-imbalance threshold;
- forced evaluation for liquidation events.

The deterministic engine can manage an already-open position even if the AI council is temporarily unavailable. New DEMO/LIVE risk fails closed if required AI evidence is absent/stale.

## Data Freshness

New-risk admission requires:
- live cloud WebSocket connected;
- recent book;
- recent trades;
- current runtime contract;
- no mode conflict;
- required model workers healthy;
- account/auth ready when DEMO/LIVE.

REST orderbook/recent trades remain diagnostic fallback, not preferred autonomous microstructure authority.

## Secrets and credentials

Never commit API keys.

Planned Cloudflare secrets:
- `BYBIT_DEMO_API_KEY`
- `BYBIT_DEMO_API_SECRET`
- `BYBIT_AUTO_API_KEY`
- `BYBIT_AUTO_API_SECRET`
- `BYBIT_DEMO_EGRESS_URL` (Cloudflare variable, only when Demo fallback is needed)
- `BYBIT_DEMO_EGRESS_SHARED_SECRET` (same secret configured on Cloudflare and Deno)

Recommended Bybit key permissions:
- contract trading/account reads needed by the bot;
- no withdrawal permission;
- separate Demo and Live keys;
- rotate immediately if exposed.

No API key is needed to validate public WebSocket, routing, AI Legion contracts or PAPER mode.

## Activation order

1. Source validation and CI.
2. Deploy exact source SHA.
3. Start cloud public WebSocket.
4. Verify `/bybit/cloud-stream/health`.
5. Verify PAPER candidate path.
6. Add Demo API key/secret.
7. Run Demo autonomous orders.
8. Verify fills, native SL/TP, emergency flatten, reconciliation and journal.
9. Run sustained Demo soak.
10. Add separate Live key/secret.
11. Keep LIVE switches OFF.
12. Run live-account read-only health.
13. Operator explicitly arms LIVE switches.
14. Start low-risk live canary.
15. Normal operation only after runtime evidence passes.

## Cost note

Cloudflare supports outbound WebSocket clients, including from Durable Objects. WebSocket hibernation is not available for outgoing WebSocket use cases, so the long-lived public feed may consume Durable Object duration. The architecture must measure this in the Demo/PAPER soak rather than claim zero cost.

## Authority

This architecture does not widen the canonical trading universe. Production execution remains BTCUSDT Linear Perpetual under `BYBIT-BTC-STATEFLOW-2.1`.
