# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: AI-INFRA-005 DeepSeek corrupt-patch regeneration resilience only; scripts/ai/deepseek_implementer.py and docs/ai-coengineer/**. No Trading Signal/runtime logic.
ACQUIRED: 2026-08-20
BASE_SHA: 9aeab7387c1d0ecdd16c23987dc47a62df53af9f

Protocol:
- ENTRY-001-R1 failed before any source diff/branch/PR was created because git apply --check rejected a corrupt generated patch.
- One writer at a time.
- Do not modify cloudflare-worker/** or Trading decision logic in this hotfix.
- Preserve TRADING_STATE and v775:books.
- Preserve SIGNAL-ONLY architecture.
- Do not weaken quote freshness, structural SL, RR, hard-news, execution-authority, or market identity protections.
- Production Claude/Anthropic API remains paused.
- DeepSeek API usage must remain bounded by task max_rounds/output-token guards plus a small explicit patch-format retry cap.
- No secret may be committed or printed.
