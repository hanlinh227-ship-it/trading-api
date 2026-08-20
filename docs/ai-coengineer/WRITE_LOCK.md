# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V78-032 Forex + Metal regime admission repair; cloudflare-worker/engine-v77168.js and scripts/ai/forex-metal-index-validation.js only.
ACQUIRED: 2026-08-20
BASE_SHA: c5b2cea9849ba5e5420d86967a2d994edc0ac340

Protocol:
- ENTRY-001-R4 was verified stale before takeover: Issue #57 had no comments, no matching implementation branch, and no matching PR.
- One writer at a time.
- Preserve TRADING_STATE and v775:books.
- Preserve SIGNAL-ONLY architecture and executionAuthority=SIGNAL_ONLY/NONE for non-crypto advisory signals.
- Do not weaken quote freshness, structural SL, RR, hard-news, anti-chase, or market identity protections.
- Yahoo/Twelve Data visibility-only Cash Index fallbacks remain fresh=false and may never create MARKET/MARKET_SIGNAL.
- Do not restore Hyro auto-trade, Futures Signal, TK2, Binance20 production execution, or any real-capital execution path.
- V73 historical data and symbol_knowledge_registry.json remain read-only in this batch.
- Production Claude/Anthropic API remains paused.
- No secret may be committed or printed.
