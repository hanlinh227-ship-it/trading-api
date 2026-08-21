# SIGNAL V11 — MASTER CHECKPOINT

STATUS: INTEGRATED BRANCH — VALIDATION/PROMOTION PENDING
BRANCH: signal-v11
BASE_MAIN_COMMIT: 2a5f02d6e364fb814325525cb9dba2fbd0110ebb
UPDATED: 2026-08-22

## Canonical architecture
V11 is the Signal-only successor architecture. V10 main remains rollback until V11 CI/runtime promotion. V77/V78 cannot regain scheduler, lifecycle or signal-decision authority.

DATA/QUOTE → MARKET SCAN → INSTRUMENT PROFILE → ENTRY/SL/TP ROUTER → MARKET HARD GATE → V11 SIGNAL → TELEGRAM → LIFECYCLE → HISTORY/STATS.

3-AI review is deliberately outside this automatic signal pipeline and only runs on explicit Telegram request.

## Platform split
- Cloudflare: V11 native runtime, single scheduler, state, lifecycle, Telegram and orchestration.
- Twelve Data Grow 55: 55 credits/min baseline for structured market data, with cache/reserves.
- Exchange/venue feeds: Crypto live quote/liquidity where available.
- GitHub: source of truth, CI, checkpoint, rollback/deployment control plane.
- DeepSeek API: optional/manual AI critic.
- Claude AI Max: manual context/regime reviewer; never faked as background API.
- ChatGPT Plus/Codex: manual logic/math/consistency reviewer; never faked as background API.

## Implemented
- `v11/config.js`: independent Crypto/Forex/Metal/Index policy and cadence.
- `v11/data-hub.js`: cache, Grow-55 budget allocator and verified quote envelope.
- `v11/instrument-profiles.js`: per-instrument strategy/risk priors, immutable registry and aliases.
- `v11/entry-plan.js`: structure/liquidity invalidation SL + volatility floor; forward-structure TP; no fake TP extension for RR.
- `v11/market-policies.js`: separate hard/quality gates per market.
- `v11/store.js`: persistent accepted/history/funnel state and idempotent lifecycle close.
- `v11/native-runtime.js`: Cloudflare-native V11 scheduling, scan admission, fresh quote re-analysis and lifecycle refresh. Existing engine is compatibility DATA/SCAN adapter only, not V11 decision authority.
- `hub-v11.js`: Telegram V11 owner, live/market/history/stats, per-market manual scan and separate 3-AI review button.
- `index.js`: Signal source-of-truth points to V11 on this branch.
- `.github/workflows/v11-signal-validation.yml`: syntax + authority/freshness/lifecycle/manual-AI separation regression guards.

## Market baselines
- Crypto: 60s opportunity cadence, Quality 62, RR 1.08, horizon 90m.
- Forex: 120s, Quality 68, RR 1.20, horizon 180m.
- Metal: 120s, Quality 70, RR 1.25, horizon 180m.
- Index: 180s, Quality 68, RR 1.20, horizon 180m.

No trade quota is forced. Fresh price, valid Entry/SL/TP geometry and market-specific hard safety remain mandatory.

## AI authority
Automatic Signal V11 does NOT require AI. Telegram `🧠 3 AI ĐÁNH GIÁ` is an independent on-demand review surface. AI output cannot silently alter already-issued signals and cannot execute Binance Auto.

## Separation
Signal V11 and Binance Auto remain separate projects. Compatibility V10 fetch exists only so legacy active/history/Binance surfaces are not destroyed during promotion; V10 scheduler is not called by the V11 hub.

## Promotion rule
Do not call production complete until V11 CI is green and Cloudflare deployment/runtime evidence exists. Promotion to main must preserve rollback and existing active legacy tracking.
