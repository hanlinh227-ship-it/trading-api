# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: NONE
RELEASED: 2026-08-22
RELEASED_BY: CHATGPT

## Current baseline

Signal V11 is the sole public signal authority on GitHub `main`.

The V11 runtime/funnel/manual-hunter repair scope is complete and the lock is released.

Completed repair lineage includes:
- real M5/M15/H1/H4/D1 ATR14 + close evidence exposed to V11;
- native V11 candidate normalization aligned to real timeframe evidence;
- funnel `reason` / `gateReasons` / `planReason` semantics corrected;
- manual AI hunter prohibited from promoting LIMIT/WATCH/MARKET_PLAN into immediate MARKET;
- DeepSeek status preserved as OK/ERROR/UNAVAILABLE;
- VPC manual Claude/Codex bridge preserved as on-demand review only;
- V11 remains SIGNAL_ONLY and fail-closed.

Current canonical docs:
- `docs/checkpoints/MASTER_TRADING_STATE.md`;
- `docs/checkpoints/CURRENT_HANDOFF.md`;
- `docs/ai-coengineer/SHARED_STATE.md`.

## Current protocol

- No writer currently owns the repository write lock.
- Future source changes must fresh-read GitHub `main` before writing.
- One writer at a time.
- Current V11 source outranks historical V78/V10 wording when they conflict.
- Preserve `TRADING_STATE`, V11 native scheduler, deterministic market gates and VPC bridge bindings.
- Never fabricate market/financial data or deployment evidence.
- Never restore legacy Futures Signal or Hyro/TK2 execution into Signal V11.
- Never merge Binance Auto execution authority into Signal V11.
- Never commit secrets, tokens or private keys.
