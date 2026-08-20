# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: AI-INFRA-006 DeepSeek structured-edit transport only; scripts/ai/deepseek_implementer.py and docs/ai-coengineer/**. No Trading Signal/runtime logic.
ACQUIRED: 2026-08-20
BASE_SHA: 513697218346edc55d722f397774331089932bef

Protocol:
- ENTRY-001-R2 failed before any source branch/PR was created because DeepSeek-generated unified patch remained corrupt after bounded regeneration.
- One writer at a time.
- Do not modify cloudflare-worker/** or Trading decision logic in this hotfix.
- Preserve TRADING_STATE and v775:books.
- Preserve SIGNAL-ONLY architecture.
- Do not weaken quote freshness, structural SL, RR, hard-news, execution-authority, or market identity protections.
- Production Claude/Anthropic API remains paused.
- DeepSeek API usage remains bounded by task max_rounds/output-token guards.
- Structured edits must obey allowed_paths/forbidden_paths, exact-match guards, secret guards, stale SHA, and deterministic validation.
- No secret may be committed or printed.
