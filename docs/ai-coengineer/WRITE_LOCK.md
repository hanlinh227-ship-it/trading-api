# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V78-012 shared ATR indicator extraction — providers/indicators.js + engine-v77168.js + hyro-scanner.js only
ACQUIRED: 2026-08-19
PURPOSE: Extract byte-equivalent ATR math only. EMA and RSI remain separate because Claude's executed equivalence test found semantic divergence. No trading behavior, risk, state, execution authority, freshness, SL or news policy change intended.

Protocol:
- Verify engine-v77168.js blob SHA = 26fba0ee017fc7d821a8685af88fc0a56a3327d5 before write.
- Verify hyro-scanner.js blob SHA = c8f96fd9130d249f9a155559813b20c0e8711f5a before write.
- Do not reset TRADING_STATE/v775:books.
- Do not weaken risk/freshness/structural-SL/news safeguards.
- Do not restore Futures/TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
