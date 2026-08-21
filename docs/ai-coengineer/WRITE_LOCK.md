# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: NONE
RELEASED: 2026-08-21
RELEASED_BY: CHATGPT

## Completed scope

V10-CRYPTO-OPPORTUNITY-DEPLOY-HARDENING completed on GitHub `main`.

Implemented:
- Crypto auto-scan cadence increased from 5 minutes to 3 minutes to capture more valid coin opportunities without lowering admission quality.
- Verified-fresh quote requirement remains mandatory before V10 admission and lifecycle TP/SL evaluation.
- Existing market-specific quality/RR, plan geometry, Entry Intelligence and three-AI consensus gates remain intact; no data-integrity bypass was introduced.
- Forex remains 10 minutes, Metal 10 minutes and Index 15 minutes.
- Cloudflare deployment workflow was corrected to validate the actual Unified V10 V2 path (`index.js` -> `hub-v10-unified-entry.js` -> `hub-v10-unified-v2.js` + `signal-v10-scheduled-v2.js`) instead of asserting the superseded direct `hub-v10.js` entry.
- Deployment validation now checks Crypto 3-minute cadence, verified-fresh quote protection, Unified V10 V2 markers and Binance Auto separation.
- V10 static validation now asserts the same cadence and entry-path invariants.
- `DEPLOY_REVISION.txt` was advanced, which matches the Cloudflare deployment workflow push path and requests a production deployment from current `main`.
- Binance Auto execution source was not modified.

Runtime evidence note:
- GitHub source updates are complete.
- The available GitHub connector exposes only pull-request-triggered workflow runs for commit lookup and returned no run for the push commit, so successful Cloudflare deployment cannot be claimed from connector evidence alone.

## Current protocol

- No writer currently owns the repository write lock.
- Fresh-read `main` before future writes.
- Preserve fail-closed quote/data protections and Signal V10 / Binance Auto separation.
