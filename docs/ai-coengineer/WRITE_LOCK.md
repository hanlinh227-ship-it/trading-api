# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: AI-INFRA-004 DeepSeek diff-format resilience only; scripts/ai/deepseek_implementer.py and docs/ai-coengineer/**. No Trading Signal/runtime logic.
ACQUIRED: 2026-08-20
BASE_SHA: c110ea87096b1e79c166de1e34775533694184c3

Protocol:
- ENTRY-001 implementation attempt failed before any source diff/branch/PR was created.
- One writer at a time.
- Do not modify cloudflare-worker/** or Trading decision logic in this hotfix.
- Preserve TRADING_STATE and v775:books.
- Preserve SIGNAL-ONLY architecture.
- Do not weaken quote freshness, structural SL, RR, hard-news, execution-authority, or market identity protections.
- Production Claude/Anthropic API remains paused.
- DeepSeek API usage must remain bounded by task max_rounds/output-token guards.
- No secret may be committed or printed.
