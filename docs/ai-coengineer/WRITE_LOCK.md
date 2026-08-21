# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: NONE
RELEASED: 2026-08-21
RELEASED_BY: CHATGPT

## Completed scope

V10-CRYPTO-SCALP-THROUGHPUT-R2 completed on GitHub `main`.

Changes:
- Increased three-AI worker batch capacity from max/default 3 candidates to max/default 6 candidates per provider cycle. This addresses review backlog risk created by 1-minute Crypto scanning without reducing the requirement that Claude, DeepSeek and Codex all return successfully.
- Made the shared council prompt explicitly Crypto-scalp aware: evaluate short-horizon scalp evidence instead of demanding swing-trade confirmation.
- Missing optional Crypto derivatives telemetry (funding, OI, long/short, orderbook) or named session context alone is no longer instructed as a reason to reject an otherwise coherent scalp.
- Reviewers are explicitly told not to require every indicator/timeframe to agree.
- Unsupported reversal is discouraged: uncertainty/incomplete optional context must be WAIT; opposite LONG/SHORT requires positive supplied evidence for the opposite direction.
- Claude role now treats 24/7 Crypto session ambiguity appropriately; DeepSeek distinguishes hard risk from missing optional telemetry; Codex validates the supplied short-horizon plan without adding unsupplied swing criteria.
- DeepSeek response budget increased from 900 to 1400 tokens so a six-candidate batch can return every candidate exactly once without avoidable truncation.
- Verified-fresh quote, Entry/SL/TP geometry, Crypto Quality 64, RR 1.10, AI confidence 60, all-three-provider health, 2-of-3 same direction and no-opposition council rule remain unchanged.
- Signal V10 remains separate from Binance Auto execution authority.

Validation evidence note:
- GitHub accepted the source update at commit 2149796defb5d0a64555fa79e2d8b872180d0d72.
- Commit status endpoint currently exposes no CI statuses for that commit; production VPS/runtime deployment is therefore not claimed from source state alone.

## Current protocol

- No writer currently owns the repository write lock.
- Future changes must fresh-read `main` before writing and preserve canonical V10 scheduler/council authority and verified-fresh pricing.
