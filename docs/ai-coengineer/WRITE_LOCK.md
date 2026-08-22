# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V11 Telegram automation + observability finalization
ACQUIRED: 2026-08-22

## Current baseline

Signal V11 is the sole public signal authority on GitHub `main`.

Current automation scope:
- automatic Telegram notification for newly approved V11 MARKET signals;
- automatic Telegram lifecycle notification for TP / SL / EXPIRED;
- fail-closed runtime health summaries without lowering market gates;
- preserve native scheduler, TRADING_STATE, VPC bridge, SIGNAL_ONLY authority.

## Current protocol

- CHATGPT owns the repository write lock for this scope.
- One writer at a time.
- Current V11 source outranks historical V78/V10 wording when they conflict.
- Preserve `TRADING_STATE`, V11 native scheduler, deterministic market gates and VPC bridge bindings.
- Never fabricate market/financial data or deployment evidence.
- Never restore legacy Futures Signal or Hyro/TK2 execution into Signal V11.
- Never merge Binance Auto execution authority into Signal V11.
- Never commit secrets, tokens or private keys.
