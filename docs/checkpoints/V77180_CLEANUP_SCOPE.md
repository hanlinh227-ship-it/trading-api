# V77.18.0 cleanup scope

Delete from main:
- legacy auto-promotion workflows matching `.github/workflows/apply-v*.yml`
- legacy migration scripts matching `scripts/apply_v*.js`

Keep:
- audit/validate/research workflows that do not write canonical production code
- `cloudflare-worker/index.js`, `engine-v77168.js`, `hub-v77171.js`, `hyro-scanner.js`, `hyro-execution.js`, `hyro-runtime.js`
- all data/symbol knowledge/checkpoint history
- every Cloudflare KV key and LIVE ORDERS state

Reason: old apply workflows/scripts can rewrite production canonical if GitHub Actions becomes active again.