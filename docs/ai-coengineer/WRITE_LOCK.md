# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: AI-INFRA-003 Parallel Dual Review orchestration only; docs/ai-coengineer/** and .github/workflows/ai-loop.yml. No Trading Signal/runtime logic.
ACQUIRED: 2026-08-20
BASE_SHA: 29646435b32299d221794bf007a83ed1f7e117df

Protocol:
- One writer at a time.
- Infrastructure-only scope; do not modify cloudflare-worker/** or Trading decision logic.
- Preserve TRADING_STATE and v775:books.
- Do not weaken freshness, structural SL, RR, hard-news, execution-authority, or secret protections.
- Production Claude/Anthropic API remains paused.
- DeepSeek API usage must remain bounded by task max_rounds/token budget.
- Claude Scheduled Watcher is review/watchdog only and must not be represented as Anthropic API automation.
- Secrets must never be committed or printed.
