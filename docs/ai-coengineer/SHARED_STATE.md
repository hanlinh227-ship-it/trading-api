# AI SHARED STATE

Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`

Permanent AI coordination:
- GitHub is the communication bus between ChatGPT and Claude.ai.
- ChatGPT is the physical GitHub writer / primary implementer while Claude's connector remains read-only 403.
- Claude is the optimizer / co-architect / patch designer / independent verifier.
- One writer at a time via `/docs/ai-coengineer/WRITE_LOCK.md`.

Current production component versions retained:
- `cloudflare-worker/index.js`: V77.18.43
- `cloudflare-worker/hub-v77171.js`: V77.18.42
- `cloudflare-worker/engine-v77168.js`: V77.16.20
- `cloudflare-worker/hyro-execution.js`: V77.18.46 telemetry-degradation repair retained.

V78 completed foundation:
- V78-001 KV/state registry — RESOLVED.
- V78-002 DecisionEvidence schema doc — RESOLVED.
- V78-003 Hyro news-gate status — RESOLVED; funding is not hard-news clearance.
- V78-004 Binance20 DECISION-005 quarantine — RESOLVED.
- V78-005 execution authority map — RESOLVED.
- V78-006 baseline validation matrix — RESOLVED.
- V78-007 provider capability inventory — RESOLVED.

Wave 1 source progress:

V78-010 — RESOLVED / CLAUDE PASS
- Shared Bybit HMAC primitive: `providers/bybit-signed-client.js:hmacHex`.
- Four Hyro consumers delegate only HMAC primitive.
- Signer semantics/credentials/mode/error/GET-POST behavior unchanged.
- V78-010b remains DEFERRED / NOT STARTED.

V78-011 — RESOLVED / CLAUDE PASS
- Shared Telegram transport: `providers/telegram-client.js`.
- Seven proven-equivalent production consumers migrated.
- `engine-v77168.js` Telegram timeout path untouched, deferred V78-054.
- `verifyTelegram`/webhook-secret untouched, deferred V78-081.
- Final migration commit in chain: `a27bd47c720476410a76ba78161ebc68b0a7aef2`.

V78-012 — RESOLVED / CLAUDE PASS
- Shared ATR only: `providers/indicators.js:atrFromHLC`.
- `engine-v77168.js` and `hyro-scanner.js` delegate ATR to shared primitive.
- Source commit: `c60cfe8532fdd10b9eca1f7bbefe5024b1d3da70`.
- EMA/RSI remain local because executed equivalence testing proved their current semantics differ.

V78-013 — IMPLEMENTED / VALIDATED / AWAITING CLAUDE FRESH-HEAD REVIEW
- Shared Anthropic transport: `providers/anthropic-client.js`.
- API HTTP transport + JSON parse + text extraction shared between `claude-reviewer.js` and `dual-ai-intervention.js`.
- Provider commit: `60d0e37f833b02e51ceee6c2a6c467ca3f76d9f8`.
- Dual AI migration: `22a872e0ed9a945f68f97a505182a28b930a0738`.
- Reviewer/final source migration: `fed3556b5a01504107f84da3fd43fad5f52db0e9`.
- Deterministic validation evidence: `88e2fc617f3ae1103296267e3b3ade89ca2c987f` in `docs/ai-coengineer/V78-013_VALIDATION.txt`.
- DECISION-004 separation preserved: reviewer dynamic max_tokens + budget/cooldown + rich parser remain independent from dual-ai fixed 950 tokens + lease arbiter + separate parser/prompt.

Next:
- V78-014 DecisionEvidence shadow-populate — NOT STARTED. Claude must fresh-read post-V78-013 HEAD, verify V78-013, then provide an implementation-ready shadow/observability-first patch.
- User requested visible practical progress (especially Hub) in addition to architecture cleanup. After V78-014 scope is safe, prioritize a separately-scoped low-risk Hub-visible progress issue rather than hiding all V78 progress in internal refactors.

Execution authority / safety:
- Signal remains advisory and cannot place real-capital orders.
- Hyro remains current safety-gated real-capital execution authority.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- Never reset `TRADING_STATE` or delete `v775:books`.
- Never restore legacy Futures Signal or Hyro TK2.
- Never weaken hard risk, freshness, structural-SL or hard-news safeguards.
- Never fabricate market/provider/test evidence or expose secrets.
