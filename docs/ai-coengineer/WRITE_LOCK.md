# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V78-016 Entry Intelligence Foundation — shadow-only provider + Signal runGroup instrumentation + read-only Hub evidence summary
ACQUIRED: 2026-08-19
PURPOSE: Add market-specific, read-only entry reasoning derived only from already-finalized Signal decision objects. No new thresholds, ranking authority, execution authority, gate changes, risk changes, or existing output-shape changes.

Protocol:
- Guard engine-v77168.js pre-patch blob SHA = 8cf6f9cb2036149bd3fa16b417f601ce43a62769.
- Guard hub-v77171.js pre-patch blob SHA = 97116e56c466505cd22b287ac193b16db55a675b.
- New shadow key only: v78016:entry_intelligence:signal.
- Do not reset TRADING_STATE/v775:books.
- Do not weaken risk/freshness/structural-SL/news safeguards.
- Do not restore Futures/TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- Claude production API remains paused unless CLAUDE_API_ENABLED=true.
