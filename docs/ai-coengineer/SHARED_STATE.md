# AI SHARED STATE

Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`

Permanent coordination:
- ChatGPT is the physical GitHub writer / primary implementer.
- Claude.ai WEB remains a full co-engineer with full project authority to read, optimize, architect, audit, design exact patches, and modify source whenever its GitHub connection permits. It is NOT demoted to reviewer-only.
- The production Anthropic/Claude API integration is PAUSED by explicit user instruction; do not make runtime Anthropic network calls until the user explicitly re-enables them.
- This API pause applies ONLY to automated/runtime API usage. It does NOT restrict the user from using Claude.ai Web manually as a co-engineer.
- If Claude.ai Web GitHub write access is still blocked by its integration-level 403, Claude should produce complete transfer-safe patches and ChatGPT will physically commit them. If that permission is later fixed, Claude.ai Web may write under the same WRITE_LOCK protocol.
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

Production Claude API pause — ACTIVE
- Commit: `c61987415a3e53832a444466406df9ffe25951f9`.
- `anthropicMessagesRequest()` fail-closes before network fetch unless `CLAUDE_API_ENABLED=true`.
- Default is disabled; no automated/runtime Claude API/token usage should occur while paused.
- Claude.ai Web remains fully authorized by the user to continue co-engineering manually.

V78-014 — RESOLVED / IMPLEMENTED / VALIDATED
- Final migration: `0c3dc007433c3e9afae1990d07d23c149742500a`.
- New `providers/decision-evidence.js`.
- Signal `runGroup()` and Hyro `done()` populate isolated V78-002 shadow evidence only after existing authoritative persistence.
- Additive `/evidence/signal` read-only endpoint.
- Validation: `docs/ai-coengineer/V78-014_VALIDATION.txt`.

V78-015 — IMPLEMENTED / VALIDATED
- Source commit: `db2b48f5b96d36e411fbd2f93c0cc73e354fe213`.
- Telegram Hub `••• Thêm` exposes `📋 Evidence V78`.
- Read-only Evidence screen shows Signal evidence count + LIVE/STALE/UNKNOWN distribution, recent gate blocks, latest Signal/Hyro evidence outcome, Hub/evidence revision, and current production Claude API PAUSED/ENABLED state.
- No trading decision/KV write/threshold/execution change from the screen.
- `verifyTelegram` remains untouched.
- Validation: `docs/ai-coengineer/V78-015_VALIDATION.txt`.

Claude resume handoff:
- `docs/ai-coengineer/CLAUDE_RESUME_HANDOFF_2026-08-19.md`.
- Claude.ai Web should fresh-read GitHub and continue optimizing the next ENTRY INTELLIGENCE FOUNDATION batch; production Claude API stays paused.

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

V78-016 — IMPLEMENTED / VALIDATED
- New `providers/entry-intelligence.js` shadow-only evaluator.
- Signal finalized decisions now append market-specific reasoning to isolated `v78016:entry_intelligence:signal` after existing authoritative persistence.
- Read-only `/evidence/entry-intelligence` endpoint.
- Telegram Hub adds `🧭 Entry Intel` showing WHY NOW / PRICE / SL / TP-RR / INVALIDATION / freshness / completeness / existing block reason.
- No authority change: current status/ranking/gates/orders remain authoritative; V78-016 is comparison/observability only.
- Claude production API remains paused; Claude.ai Web retains full co-engineer authority when available.

V78-017 — IMPLEMENTED / VALIDATED
- Manual `/analyze` and Telegram single-symbol analysis now populate both V78-002 DecisionEvidence and V78-016 Entry Intelligence shadow records.
- Shadow writes are isolated in try/catch after `runSymbol()` returns and do not mutate the returned decision object.
- Hub visible UI revision is now `HUB-R11-ENTRY-INTEL-SHADOW` so deployment progress is visible.
- Claude production API remains paused; Claude.ai Web remains a full co-engineer.

V78-020 — CLAUDE OVER-BLOCK FIX + SAFE PROMOTION IMPLEMENTED
- Corrected rescue-plan false hard-block: M15_LOCATION_REQUIRED, M5_MSS_DISPLACEMENT_RETEST_REQUIRED and RR_QUALITY_REQUIRED now block only when top-level status is not actionable.
- Entry Intelligence now contributes a bounded secondary term to actionableRank.
- Entry Intelligence promotion gate is applied only to non-crypto MARKET_SIGNAL admission. Crypto MARKET/LIMIT admission remains unchanged.
- Primary single-symbol output now shows Entry Intelligence quality/admission evidence.
- No Hyro execution/risk/freshness/SL/news/account behavior changed.

V78-020 — PRODUCTION-VERIFIED
- Current production deployment contains commit 47800df837101611db8b61e0a25b8fcbd8888f55 or a descendant.
- One real /run-now request was executed for each forex/crypto/metal/index without retry-hiding BUSY/RATE_BUDGET_WAIT.
- Immediately-prior /latest-scan snapshots were compared to the new results; candidate rotation is recorded but is not treated as promotion suppression because promotion occurs after analyses are produced.
- Rescue MARKET_PLAN/LIMIT_PLAN evidence checks use /evidence/entry-intelligence and require promotion.allowed=true when quote/entry/SL/target evidence is valid.
- Exact live statuses, symbols, scanIds and timestamps are appended to V78-020_VALIDATION.txt.


V78-021 — RESOLVED / DEPLOYED
- Source commit: 111d0618a505a9d65652e52283fb7f22e6bd7c0a.
- Group-scan candidate rendering now adds Entry Intelligence quality grade/score, blocked-promotion reasons, and quote freshness through buildEntryIntelligenceShadow().
- REQUIRED/QUALITY/OPTIONAL classification remains unchanged; visibility only.
- Exact validation: docs/ai-coengineer/V78-021_VALIDATION.txt.
- hubSummary() separate inline top-7 builder remains deferred as a separate follow-up.


V78-022 — RESOLVED / DEPLOYED
- Source commit: c41706b99b6357cc829b1a6ded0b7240bc428a27.
- Cloudflare Version ID: c60f16a4-6a93-4ba3-aab3-a450b0188de0.
- Hub cross-market top-setups rendering now shows Entry Intelligence Quality grade/score, blocked-promotion reasons, and Freshness.
- hubRank/runHub top selection unchanged; rendering-only.
- Validation: docs/ai-coengineer/V78-022_VALIDATION.txt.
