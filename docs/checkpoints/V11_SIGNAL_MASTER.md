# SIGNAL V11 — MASTER CHECKPOINT

STATUS: FOUNDATION IMPLEMENTED
BRANCH: signal-v11
BASE_MAIN_COMMIT: 2a5f02d6e364fb814325525cb9dba2fbd0110ebb
UPDATED: 2026-08-21

## Canonical direction
V11 is a clean Signal-only architecture. V10 on main remains rollback/reference. V77/V78 may not regain scheduler, council, lifecycle or signal-decision authority.

## Platform split
- Cloudflare: single runtime/scheduler authority, shared cache/state, orchestration, Telegram/lifecycle/learning target, API gateway.
- Twelve Data Grow 55: 55 credits/min baseline, structured Forex/Metal/Index data; shared cache and quota admission; reserve lifecycle/verification credits.
- GitHub: source, branch, validation, deploy, rollback and checkpoint control plane.
- DeepSeek API: unattended API-native critic through Cloudflare.
- Claude AI Max: context/research/manual review; not falsely treated as API.
- ChatGPT Plus: logic/code/consistency/manual review; not falsely treated as API.

## Implemented V11 foundation
- `cloudflare-worker/v11/config.js`: isolated V11 market policies, Grow-55 budget and cadences.
- `cloudflare-worker/v11/data-hub.js`: shared memory/KV cache abstraction, candle-boundary TTL, quota allocator, verified-fresh evidence envelope.
- `cloudflare-worker/v11/market-policies.js`: separate Crypto/Forex/Metal/Index scalp gates and strategy families.
- `cloudflare-worker/v11/ai-gateway.js`: Cloudflare-native DeepSeek API reviewer; Claude Max/ChatGPT Plus explicitly human-assisted until API entitlement exists; no VPS/CLI dependency in V11 module.
- `cloudflare-worker/v11/orchestrator.js`: one Cloudflare scheduler authority and canonical candidate→market gate→AI review→approved signal path.
- `.github/workflows/v11-signal-validation.yml`: V11 syntax/invariant guards and anti-legacy-authority checks.

## Current market baselines (shadow; tune from outcomes)
- Crypto: scan 60s, Quality 62, RR 1.08, horizon 90m. Broad liquid discovery; momentum pullback, breakout-retest, sweep-reclaim, relative strength. Hard liquidity/chase/freshness safety remains.
- Forex: scan 120s, Quality 68, RR 1.20, horizon 180m. Session sweep/MSS, trend pullback, post-news retest, currency strength; high-impact clearance.
- Metal: scan 120s, Quality 70, RR 1.25, horizon 180m. Session sweep/reclaim, impulse pullback, breakout-retest; US-event/volatility shock protection.
- Index: scan 180s, Quality 68, RR 1.20, horizon 180m. Opening-range, VWAP reclaim, trend pullback, relative/SMT with fresh comparison evidence.

These are opportunity thresholds, not guarantees or forced trade quotas. Verified price, instrument identity, Entry/SL/TP geometry, liquidity/execution sanity, duplicate protection and lifecycle idempotency remain hard gates.

## Data policy
Scanner cadence is decoupled from expensive data refresh. Closed candles are cached to timeframe boundaries and shared by scanner/entry/AI evidence. Live quote is refreshed immediately before signal admission and lifecycle decisions. Grow 55 is used actively, but discovery may not consume lifecycle/verification reserves.

## AI policy
Production V11 must never depend on a local/VPS CLI. DeepSeek API is currently the unattended provider. Claude Max and ChatGPT Plus contribute through development/manual review until actual API credentials exist. Provider outage never becomes silent approval; missing optional evidence never gets fabricated.

## Separation
Signal V11 remains separate from Binance Auto execution authority.

## Next implementation phase
1. Wire V11 data hub to existing provider adapters without importing legacy decision authority.
2. Implement four scanner/context adapters behind clean V11 interfaces.
3. Add persistent Cloudflare state (KV/D1/Queues/Workflows according to deployed bindings) for dedupe, lifecycle and funnel telemetry.
4. Build Telegram V11 shadow UX.
5. Shadow-run V11 against V10; collect per-market candidate→gate→AI→signal→outcome funnel.
6. Promote only after CI + Cloudflare runtime evidence; do not overwrite main beforehand.
