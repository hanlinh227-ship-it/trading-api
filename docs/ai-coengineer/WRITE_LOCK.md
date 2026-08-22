# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: NONE
RELEASED: 2026-08-22
RELEASED_BY: CHATGPT

## Current baseline

Signal V11 is the sole public signal authority on GitHub `main` and remains SIGNAL_ONLY.

Completed automation scope:
- automatic Telegram alert for newly stored V11 MARKET-ready approved signals;
- automatic Telegram TP / SL / EXPIRED lifecycle alerts;
- Telegram dashboard LIVE / WATCH / scans / history / stats / manual three-AI hunter;
- automatic duplicate OPEN suppression;
- legacy non-market approvals invalidated without resetting TRADING_STATE;
- CI validation on `main` for V11 automation invariants;
- canonical Cloudflare auto-deploy workflow remains the normal deployment path.

## Current protocol

- No writer currently owns the repository write lock.
- Future source changes must fresh-read GitHub `main` before writing.
- One writer at a time.
- Preserve TRADING_STATE, V11 native scheduler, deterministic market gates and VPC bridge bindings.
- Never fabricate market/financial data or deployment evidence.
- Never promote LIMIT/WATCH into MARKET.
- Never restore legacy Futures Signal or Hyro/TK2 execution into Signal V11.
- Never merge Binance Auto execution authority into Signal V11.
- Never commit secrets, tokens or private keys.
