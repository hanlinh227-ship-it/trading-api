# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: AI-INFRA-007 DeepSeek structured-edit exact-match recovery only; scripts/ai/deepseek_implementer.py and docs/ai-coengineer/**. No Trading Signal/runtime logic.
ACQUIRED: 2026-08-20
BASE_SHA: 4216b65cd2c89d871daa9e247d219416c28077b9

Protocol:
- ENTRY-001-R3 failed before any source branch/PR was created because structured edit old_text did not exactly match current source.
- One writer at a time.
- Do not modify cloudflare-worker/** or Trading decision logic in this hotfix.
- Preserve TRADING_STATE and v775:books.
- Preserve SIGNAL-ONLY architecture.
- Do not weaken quote freshness, structural SL, RR, hard-news, execution-authority, or market identity protections.
- Production Claude/Anthropic API remains paused.
- Recovery similarity may only select source context; it must never apply fuzzy edits.
- Final replacement still requires old_text to match exactly once.
- DeepSeek API usage remains bounded by task max_rounds/output-token guards.
- No secret may be committed or printed.
