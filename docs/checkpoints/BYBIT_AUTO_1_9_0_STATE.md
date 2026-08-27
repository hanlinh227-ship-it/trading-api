# BYBIT AUTO 1.9.0 STATE

Date: 2026-08-27
Version: BYBIT-AUTO-1.9.0

## Release intent
BYBIT-AUTO-1.9.0 consolidates the current live scalp tuning into one production version without weakening final execution quality.

## Current production design
- Continuous equity-curve sizing.
- Target risk around 6% on small-equity curve; hard single-trade cap 6.5%, declining with scale.
- Total managed open-risk ceiling: 36% equity.
- Unlimited position-count sentinels; portfolio risk, margin, correlation and exchange constraints remain authoritative.
- Portfolio margin allocation ceiling: 100%; per-position margin uses equity-aware slot decay.
- Fixed free-reserve floor: 0%; runtime `PORTFOLIO_MARGIN_HEADROOM` is authoritative.
- Score bounds: 66–84, with scalp-tuned symbol profiles.
- Correlation defaults: soft 0.86 / hard 0.95.
- Minimum RR: 1.5; preferred RR: 1.8.
- Structural anti-sweep SL/TP remains deterministic.
- Native trailing hard floor: 1.70R; default trigger: 1.85R.
- Smart CUT remains multi-signal, age/confirmation gated and reduce-only.
- Claude + Codex strict unanimous 2/2 final-entry review remains fail-closed.
- Post-AI live quote revalidation remains mandatory.
- Adaptive learning remains bounded and `autoPromote:false`; existing KV/history is preserved.

## Scan coverage
- Bybit USDT Linear Perpetual instruments are discovered dynamically.
- Production universe minimum target: 80 symbols.
- Default minimum turnover: $750,000 per 24h.
- Default scan concurrency: 12.
- Symbol-level liquidity/spread, ATR, regime, structure and cost-aware filters remain mandatory.

## Runtime
- Scheduler cadence: 60 seconds.
- Execution authority: BYBIT_AUTO_TRADE_ONLY.
- Private and market transport remain VPS Bybit proxy routes.
- Telegram HUB is user-facing status/control UI only; trading authority remains in the Bybit Auto runtime.

## Deployment rule
Do not call 1.9.0 LIVE until `validate-worker.mjs`, learning validation, unified deploy and `/bybit/health` production verification all pass with matching runtime revision and version.
