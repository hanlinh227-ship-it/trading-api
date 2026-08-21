# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V10-SIGNAL-INTEGRITY-OPTIMIZATION
ACQUIRED: 2026-08-21

## Allowed scope

- `cloudflare-worker/hub-v10-unified-v2.js`
- `cloudflare-worker/signal-v10-scheduled-v2.js`
- `cloudflare-worker/signal-v10-council.js`
- `cloudflare-worker/signal-v10-learning.js`
- `.github/workflows/v10-signal-validation.yml`
- `docs/checkpoints/V10_SIGNAL_ONLY_MASTER.md`
- `cloudflare-worker/DEPLOY_REVISION.txt`
- `docs/ai-coengineer/WRITE_LOCK.md`

## Objective

Optimize V10 signal opportunity flow without weakening quality: eliminate false quote rejects, require verified fresh lifecycle quotes, preserve continuous Live -> History state, prevent learning double-count, and strengthen deterministic validation. Binance Auto execution source is out of scope.

## Protocol

- Fresh-read `main` before every write and never overwrite a moved blob SHA.
- Preserve `TRADING_STATE` and `v775:books`.
- Preserve SIGNAL-ONLY V10 and Binance Auto separation.
- Missing/unverified/stale quote must fail closed; never bypass `QUOTE_MISSING`/freshness protections.
- Do not lower RR, quality, hard-news, structural SL, anti-chase, or 3-AI consensus requirements merely to increase signal count.
- No real-capital execution changes.
- No secret may be committed or printed.
- Release this lock only after source validation and final state sync are complete.
