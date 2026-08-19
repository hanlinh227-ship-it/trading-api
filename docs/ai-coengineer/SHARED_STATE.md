# AI SHARED STATE

Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`

Permanent coordination:
- ChatGPT is the physical GitHub writer / primary implementer.
- Claude is optimizer / co-architect / patch designer / independent verifier when available.
- Claude API usage is currently PAUSED by explicit user instruction; do not make Anthropic network calls until the user explicitly re-enables them.
- One writer at a time via `/docs/ai-coengineer/WRITE_LOCK.md`.

Current production component versions retained:
- `cloudflare-worker/index.js`: V77.18.43
- `cloudflare-worker/hub-v77171.js`: V77.18.42 + V78 additive Hub Evidence view
- `cloudflare-worker/engine-v77168.js`: V77.16.20 + V78 shared ATR + DecisionEvidence shadow
- `cloudflare-worker/hyro-execution.js`: V77.18.46 telemetry-degradation repair retained.

V78 completed foundation:
- V78-001 KV/state registry — RESOLVED.
- V78-002 DecisionEvidence schema — RESOLVED.
- V78-003 Hyro news-gate status — RESOLVED; funding is not hard-news clearance.
- V78-004 Binance20 DECISION-005 quarantine — RESOLVED.
- V78-005 execution authority map — RESOLVED.
- V78-006 baseline validation matrix — RESOLVED.
- V78-007 provider capability inventory — RESOLVED.

Wave 1 source progress:

V78-010 — RESOLVED / CLAUDE PASS
- Shared Bybit HMAC primitive: `providers/bybit-signed-client.js:hmacHex`.
- V78-010b remains DEFERRED / NOT STARTED.

V78-011 — RESOLVED / CLAUDE PASS
- Shared Telegram transport across proven-equivalent consumers.
- `engine-v77168.js` timeout Telegram path remains deferred V78-054.
- `verifyTelegram` remains deferred V78-081.

V78-012 — RESOLVED / CLAUDE PASS
- Shared ATR only via `providers/indicators.js:atrFromHLC`.
- EMA/RSI remain local because semantics differ.

V78-013 — RESOLVED / IMPLEMENTED / VALIDATED
- Shared Anthropic transport via `providers/anthropic-client.js`.
- DECISION-004 boundaries preserved.
- Final source migration: `fed3556b5a01504107f84da3fd43fad5f52db0e9`.
- Validation: `docs/ai-coengineer/V78-013_VALIDATION.txt`.

Claude API pause — ACTIVE
- Commit: `c61987415a3e53832a444466406df9ffe25951f9`.
- `anthropicMessagesRequest()` now fail-closes before network fetch unless `CLAUDE_API_ENABLED=true`.
- Default is disabled; no Claude API/token usage should occur while paused.

V78-014 — RESOLVED / IMPLEMENTED / VALIDATED
- Final migration: `0c3dc007433c3e9afae1990d07d23c149742500a`.
- New `providers/decision-evidence.js`.
- Signal `runGroup()` and Hyro `done()` populate isolated V78-002 shadow evidence only after existing authoritative persistence.
- Additive `/evidence/signal` read-only endpoint.
- Validation: `docs/ai-coengineer/V78-014_VALIDATION.txt`.

V78-015 — IMPLEMENTED / VALIDATED
- Source commit: `db2b48f5b96d36e411fbd2f93c0cc73e354fe213`.
- Telegram Hub `••• Thêm` now exposes `📋 Evidence V78`.
- Read-only Evidence screen shows Signal evidence count + LIVE/STALE/UNKNOWN distribution, recent gate blocks, latest Signal/Hyro evidence outcome, Hub/evidence revision, and current Claude API PAUSED/ENABLED state.
- No trading decision/KV write/threshold/execution change from the screen.
- `verifyTelegram` remains untouched.
- Validation: `docs/ai-coengineer/V78-015_VALIDATION.txt`.

Claude resume handoff:
- `docs/ai-coengineer/CLAUDE_RESUME_HANDOFF_2026-08-19.md`.
- When Claude is available again, fresh-read GitHub and optimize the next ENTRY INTELLIGENCE FOUNDATION batch rather than returning to generic transport cleanup.

Next engineering priority:
- market-specific entry intelligence shadow layer for Forex / Crypto / Metals / Index Cash;
- preserve existing outputs first, compare shadow reasoning before authority changes;
- expose compact WHY NOW / BLOCK REASON / FRESHNESS / RR in Hub after validation;
- high-risk Hyro execution hardening remains separately scoped.

Execution authority / safety:
- Signal remains advisory and cannot place real-capital orders.
- Hyro remains current safety-gated real-capital execution authority.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- Never reset `TRADING_STATE` or delete `v775:books`.
- Never restore legacy Futures Signal or Hyro TK2.
- Never weaken hard risk, freshness, structural-SL or hard-news safeguards.
- Never fabricate market/provider/test evidence or expose secrets.
