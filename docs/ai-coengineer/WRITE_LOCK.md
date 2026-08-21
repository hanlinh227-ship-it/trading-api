# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V10-CRYPTO-OPPORTUNITY-DEPLOY-HARDENING
ACQUIRED: 2026-08-21

## Allowed scope

- `cloudflare-worker/signal-v10-scheduled-v2.js`
- `.github/workflows/deploy-cloudflare-worker.yml`
- `.github/workflows/v10-signal-validation.yml`
- `cloudflare-worker/DEPLOY_REVISION.txt`
- `docs/checkpoints/V10_SIGNAL_ONLY_MASTER.md`
- `docs/ai-coengineer/WRITE_LOCK.md`

## Objective

Increase Crypto opportunity coverage without weakening quote integrity, Entry Intelligence, RR/quality or 3-AI consensus. Fix deployment validation so production deploy follows the actual Unified V10 V2 entry path. Preserve Binance Auto separation.

## Protocol

- Fresh-read `main` before each write.
- Crypto scan cadence may be increased, but data/risk gates remain fail-closed.
- Do not modify Binance Auto execution authority.
- Validate source and deployment invariants before releasing lock.
