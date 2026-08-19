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

Current reviewed component state:
- `cloudflare-worker/index.js`: V77.18.43
- `cloudflare-worker/hub-v77171.js`: V77.18.42
- `cloudflare-worker/engine-v77168.js`: V77.16.20
- Health fixes present through V77.18.45
- `cloudflare-worker/hyro-execution.js`: V77.18.46 telemetry degradation repair, commit `1d6db32155c06d464f4da94746df73e110b9b294`

Roles:
- ChatGPT: PRIMARY_ENGINEER / PRIMARY_INTEGRATOR / CO-ARCHITECT
- Claude: CO-ARCHITECT / REVIEWER / SECOND_ENGINEER

AI-003 V78 status:
- Phase 1 blueprint persisted: `V78_CLAUDE_PHASE1_BLUEPRINT.md`.
- Phase 2 reported by user to contain target HUB menu, DecisionEvidence schema, and V78-001..V78-091 backlog.
- Exact Phase 2 body is not yet available in GitHub/current attachment; placeholder created at `V78_CLAUDE_PHASE2_BACKLOG.md` and must not be treated as the exact Claude backlog until Claude resends it.
- Wave 0/Wave 1 provisional scoped planning is in `V78_IMPLEMENTATION_WAVE0_WAVE1.md`.

Independent evidence verified:
- `engine-v77168.js` Signal crypto path uses unsigned public GET market-data helpers; no `/v5/order/create` in that file.
- Hyro is current real-capital execution authority; Binance20 remains NON_PRODUCTION.
- V78-041 / DECISION-009: funding is not a substitute for news. Hyro executable new orders require a distinct hard-news/context gate under the active mandate; funding remains a separate carry/microstructure gate.

Production/source status:
- SOURCE REVIEW: PASS for V77.18.46 telemetry repair.
- No V78 production behavior change has been authorized by current Wave 0/Wave 1 planning commits.

Rules:
- `main` source is authority over stale docs.
- One writer at a time.
- Never reset `TRADING_STATE` or delete `v775:books`.
- Never restore legacy Futures Signal or Hyro TK2.
- Never commit secrets or bypass hard risk/freshness/structural-SL gates.
