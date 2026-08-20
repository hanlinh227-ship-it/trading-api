# AI WRITE LOCK

LOCKED: true
OWNER: DEEPSEEK
SCOPE: ENTRY-001-R2 Current-price entry intelligence integrity and anti-chase; cloudflare-worker/engine-v77168.js, cloudflare-worker/providers/entry-intelligence.js, cloudflare-worker/providers/decision-evidence.js, scripts/ai/entry-001-validation.js only.
ACQUIRED: 2026-08-20
BASE_SHA: 9f6de04488d87aab5112521e2d8c521ccf3bd34b

Protocol:
- One writer at a time.
- DeepSeek may modify only the explicit ENTRY-001-R2 allow-list.
- Codex and Claude may review but must not modify overlapping source while this lock is active.
- Preserve TRADING_STATE and v775:books.
- Preserve SIGNAL-ONLY architecture.
- Do not weaken quote freshness, structural SL, RR, hard-news, execution-authority, or market identity protections.
- Do not restore Hyro auto-trade, Futures Signal, TK2, Binance20 production execution, or any real-capital execution path.
- Production Claude/Anthropic API remains paused.
- DeepSeek semantic repair rounds remain bounded; patch-format regeneration is capped at one extra attempt per round.
- No secret may be committed or printed.
