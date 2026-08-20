# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: AI-INFRA-002 Closed-loop orchestration only; docs/ai-coengineer/**, scripts/ai/**, .github/workflows/ai-loop.yml, .github/workflows/ai-task.yml. No Trading Signal/runtime logic.
ACQUIRED: 2026-08-20
BASE_SHA: 66c9122e9c0705119b9ff4d5574593fd255f9194

Protocol:
- One writer at a time.
- Infrastructure-only scope; do not modify cloudflare-worker/** or Trading decision logic.
- Preserve TRADING_STATE and v775:books.
- Do not weaken freshness, structural SL, RR, hard-news, execution-authority, or secret protections.
- Production Claude/Anthropic API remains paused.
- DeepSeek API usage must be bounded by task max_rounds/token budget.
- Claude Max/Claude Code Web remains subscription-based and must not be represented as a headless API worker.
- Secrets must never be committed or printed.
