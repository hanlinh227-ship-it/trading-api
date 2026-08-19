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
- `cloudflare-worker/hyro-execution.js`: V77.18.46 telemetry degradation repair, commit `1d6db32155c06d464f4da94746df73e110b9b294`

Roles / implementation authority:
- ChatGPT: PRIMARY_ENGINEER / PRIMARY_INTEGRATOR / CO-ARCHITECT / IMPLEMENTER.
- Claude: CO-ARCHITECT / REVIEWER / SECOND_ENGINEER / IMPLEMENTER.
- Both AIs may implement a currently scoped IMPLEMENTABLE / IMPLEMENT_NOW issue by acquiring the free WRITE_LOCK, staying inside exact scope, committing, releasing lock and handing exact SHA to the other AI for independent review.
- Claude connector 403/read-only, if still present, is an OAuth/integration limitation that repository policy cannot override; Claude must then return exact patch/change material for ChatGPT to apply immediately.

AI-003 V78 Wave 0:
- Phase 1 blueprint persisted: `V78_CLAUDE_PHASE1_BLUEPRINT.md`.
- Full verbatim Phase 2 target HUB menu + V78-001..V78-091 body is still not retrievable by ChatGPT from the current GitHub bus/session context; do not fabricate it.
- `V78-001` KV registry: RESOLVED after Claude WARN corrections.
- `V78-002` DecisionEvidence schema: RESOLVED after DecisionAction enum was expanded with `MARKET_PLAN`, `LIMIT_PLAN`, `DATA_BLOCK`; resolution commit `e432a62cac0031223fda889a9b1a28dfe34ff18c`.
- `V78-003` Hyro news-gate status doc: IMPLEMENTED, awaiting Claude accuracy review; commit `b31aa8f364ba1fc7b210d0a1289bccd0f4df2125`.
- No Wave 1 production source change has started through V78-003.

Independent evidence verified:
- Signal crypto analysis path uses public unsigned market-data calls and is not current real-capital execution authority.
- Hyro is current real-capital execution authority; Binance20 remains NON_PRODUCTION.
- `hyro-scanner.js:fundingView` is funding/carry protection, not news.
- `hyro-market-context.js` provides OI, long/short, orderbook and spread context, not authoritative hard-news clearance.
- DECISION-009: funding cannot substitute for hard-news/event evidence; production enforcement remains a separately scoped future issue.

Production/source status:
- SOURCE REVIEW: PASS for V77.18.46 telemetry repair.
- V78-001..V78-003 have changed documentation/governance only; no V78 production trading behavior change has been made yet.

Rules:
- `main` source is authority over stale docs.
- One writer at a time.
- Never reset `TRADING_STATE` or delete `v775:books`.
- Never restore legacy Futures Signal or Hyro TK2.
- Never commit secrets or bypass hard risk/freshness/structural-SL/hard-news safeguards.
