# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: AI-INFRA-001 DeepSeek cloud implementer staging only; docs/ai-coengineer, scripts/ai, .github/workflows/ai-task.yml. No Trading Signal/runtime logic.
ACQUIRED: 2026-08-20
BASE_SHA: ce3581d531e28f8ea85d9e17037db9891b0d89e6

Protocol:
- One writer at a time.
- This scope is infrastructure-only.
- Do not modify cloudflare-worker/** or Trading decision logic.
- Do not reset TRADING_STATE or v775:books.
- Do not weaken freshness, structural SL, RR, news, execution-authority, or secret protections.
- Production Claude/Anthropic API remains paused.
- DEEPSEEK_API_KEY must remain a GitHub Secret and must never be committed.
