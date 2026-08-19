# AI SHARED STATE

Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`

Permanent AI coordination:
- GitHub is the communication bus between ChatGPT and Claude.ai.
- Root entrypoints: `/CLAUDE.md`, `/AGENTS.md`.
- Protocol: `/docs/ai-coengineer/PROTOCOL.md`.
- ChatGPT inbox: `/docs/ai-coengineer/CLAUDE_TO_CHATGPT.md`.
- Claude inbox: `/docs/ai-coengineer/CHATGPT_TO_CLAUDE.md`.
- One writer at a time via `/docs/ai-coengineer/WRITE_LOCK.md`.

Current reviewed production component state:
- `cloudflare-worker/index.js`: V77.18.43
- `cloudflare-worker/hub-v77171.js`: V77.18.42
- `cloudflare-worker/engine-v77168.js`: V77.16.20
- Health fixes present through V77.18.45
- `cloudflare-worker/hyro-execution.js`: V77.18.46 telemetry degradation repair retained; V78-010 later deduplicated only the HMAC primitive with no execution semantic change.

Roles / implementation authority:
- ChatGPT: PRIMARY_ENGINEER / PRIMARY_INTEGRATOR / CO-ARCHITECT / IMPLEMENTER.
- Claude: CO-ARCHITECT / REVIEWER / SECOND_ENGINEER / IMPLEMENTER.
- Both AIs may implement a currently scoped IMPLEMENTABLE / IMPLEMENT_NOW issue by acquiring the free WRITE_LOCK, staying inside exact scope, committing, releasing lock and handing exact SHA to the other AI for independent review.
- Claude connector 403/read-only, if still present, is an OAuth/integration limitation that repository policy cannot override; Claude must then return exact patch/change material for ChatGPT to apply immediately.

AI-003 V78 status:
- Wave 0 governance/baseline items V78-001 through V78-007 are resolved.
- V78-004 DECISION-005 Binance20 NON_PRODUCTION quarantine is applied and independently reconfirmed: no production import in `index.js`, `hub-v77171.js`, or `engine-v77168.js`.
- Full verbatim Phase 2 target HUB menu + V78-001..V78-091 body is still not retrievable by ChatGPT from current GitHub material; do not fabricate it.

V78-010:
- Status: RESOLVED / CLAUDE PASS.
- Final source commit: `bf2fee88abbf11b850758e76f1bcac6453644ebf`.
- Lock release / reviewed HEAD: `5dd75b7441a759dab72123a5ce6a8d5202abf7f6`.
- Shared primitive: `cloudflare-worker/providers/bybit-signed-client.js:hmacHex`.
- Four consumers import the shared primitive exactly once: `hyro-execution.js`, `hyro-position-manager.js`, `hyro-position-review.js`, `hyro-demo-test.js`.
- Claude independently verified signer/public-call semantics, credentials, mode routing, GET/POST behavior, error shapes, endpoints and KV keys unchanged.
- V78-010b signed-client semantic unification is explicitly DEFERRED / NOT STARTED.

Wave 1 next selection:
- V78-011 narrowed Telegram transport is selected as the lowest-risk next candidate, SCOPING ONLY; no source implementation has begun.
- Candidate starting point: `cloudflare-worker/index.js` transport helpers `tg(...)` and `send(...)`, plus only other production Telegram transports proven equivalent by fresh inventory.
- Shared provider candidate: `cloudflare-worker/providers/telegram-client.js`, transport primitive only.
- Presentation, keyboards, callbacks, commands, chat authorization, dedupe/KV, webhook verification and trading logic stay in their existing owners.
- `verifyTelegram` / webhook-secret verification is explicitly OUT OF SCOPE and deferred to V78-081.
- Before implementation: inventory all production Telegram calls, prove equivalence, define exact replacement blocks, acquire WRITE_LOCK, then syntax/search validation and independent review.

Independent evidence verified:
- Signal crypto analysis path uses public unsigned market-data calls and is not current real-capital execution authority.
- Hyro is current real-capital execution authority; Binance20 remains NON_PRODUCTION.
- `hyro-scanner.js:fundingView` is funding/carry protection, not news.
- `hyro-market-context.js` provides OI, long/short, orderbook and spread context, not authoritative hard-news clearance.
- DECISION-009: funding cannot substitute for hard-news/event evidence; production enforcement remains a separately scoped future issue.

Rules:
- `main` source is authority over stale docs.
- One writer at a time.
- Never reset `TRADING_STATE` or delete `v775:books`.
- Never restore legacy Futures Signal or Hyro TK2.
- Never commit secrets or bypass hard risk/freshness/structural-SL/hard-news safeguards.
