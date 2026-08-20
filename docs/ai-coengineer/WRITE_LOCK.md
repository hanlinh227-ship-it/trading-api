# AI WRITE LOCK

LOCKED: true
OWNER: CLAUDE_LOCAL
SCOPE: V78-032 PR #60 follow-up only: fix review blockers, re-sync canonical validate lock manifest if required, wire forex-metal-index validation into signal-integrity CI, and update PR #60 branch. Cloudflare provider-side build connection issue must remain separate and must not be chased by changing worker source.
ACQUIRED: 2026-08-20
BASE_SHA: f55df72e11bcaa529ef8b44b4f32a892618606e9

Protocol:
- ChatGPT review/implementation lock for V78-032 is released and transferred to Claude Code local for one bounded follow-up batch.
- Refresh origin/main and PR #60 HEAD immediately before any write.
- One writer at a time.
- Preserve TRADING_STATE and v775:books.
- Preserve SIGNAL-ONLY architecture and executionAuthority=SIGNAL_ONLY/NONE for non-crypto advisory signals.
- Do not weaken quote freshness, structural SL, RR, hard-news, anti-chase, or market identity protections.
- Yahoo/Twelve Data visibility-only Cash Index fallbacks remain fresh=false and may never create MARKET/MARKET_SIGNAL.
- Do not restore Hyro auto-trade, Futures Signal, TK2, Binance20 production execution, or any real-capital execution path.
- V73 historical data and symbol_knowledge_registry.json remain read-only in this batch.
- PR #60 source changes must remain bounded; separate unrelated CI/provider issues into separate commits/issues as appropriate.
- Cloudflare Workers Build connection failure is treated as provider/integration-side unless independently proven source-caused; do not modify worker business logic to chase it.
- Production Claude/Anthropic API remains paused.
- No secret may be committed or printed.
