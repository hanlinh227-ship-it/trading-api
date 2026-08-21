# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V10-CRYPTO-SCALP-OPPORTUNITY-TUNING
ACQUIRED: 2026-08-21

## Allowed scope

- `cloudflare-worker/signal-v10-council.js`
- `cloudflare-worker/signal-v10-scheduled-v2.js`
- `.github/workflows/deploy-cloudflare-worker.yml`
- `.github/workflows/v10-signal-validation.yml`
- `cloudflare-worker/DEPLOY_REVISION.txt`
- `docs/checkpoints/V10_SIGNAL_ONLY_MASTER.md`
- `docs/ai-coengineer/WRITE_LOCK.md`

## Objective

Tune Signal-Only Crypto for frequent scalp opportunities. Crypto should not be rejected by duplicate V10 advisory strictness after the compatibility engine has already produced a structurally valid actionable plan. Keep verified-fresh quotes, valid Entry/SL/TP geometry, engine structural RR, and three-AI no-opposition consensus. Do not modify Binance Auto execution authority or real-capital hard-risk controls.

## Protocol

- Fresh-read `main` before each write.
- Changes here affect Signal V10 advisory admission only unless explicitly documented.
- Missing/stale price or invalid plan still fails closed.
- Preserve `TRADING_STATE`, `v775:books`, lifecycle history and Binance Auto separation.
