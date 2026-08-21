# AI WRITE LOCK

LOCKED: false
OWNER: NONE
SCOPE: NONE
RELEASED: 2026-08-21
RELEASED_BY: CHATGPT

## Completed scope

V10-CONFLICT-AUDIT-R1 completed on GitHub `main`.

Conflict audit findings and fixes:
- Found a real previous-version scheduling conflict: `hub-v10-unified-v2.js` delegated `scheduled()` to `hub-v10.js`, while the canonical entry also runs `signal-v10-scheduled-v2.js`. The old core still carried obsolete Crypto 5-minute cadence and weaker lifecycle freshness semantics. Removed this delegation so scheduled authority is now exclusively `signal-v10-scheduled-v2.js`.
- Kept `hub-v10.js` only as compatibility fetch/core fallback; it no longer receives scheduled events through the canonical V10 path.
- Found a Telegram routing conflict: Unified V2 exposed `v10:stats` and `v10:council` buttons but did not claim those callbacks, causing fallback into the older V10 core. Unified V2 now owns and renders both callbacks directly.
- Unified V2 now handles `/signal-v10/*` API before compatibility fallback, keeping the three-AI bridge on the canonical V10 surface.
- Verified three-AI decision semantics: all Claude/DeepSeek/Codex reviews must be OK; at least two must align with candidate direction; any opposite-direction review blocks; WAIT is not treated as opposition; market-specific confidence floor remains enforced by the council.
- VPS provider order remains DeepSeek -> Claude -> Codex sequentially with successful-result cache; provider failure prevents submission instead of silently accepting partial council output.
- Added static regression guards preventing `v10Core.scheduled` from returning to Unified V2 and asserting the three-AI conflict policy/routing.
- Crypto final policy remains 1-minute target scan, Quality 64, advisory RR 1.10, aligned AI confidence 60, accepted TTL 2h, verified-fresh quote required.
- Signal V10 remains separate from Binance Auto execution authority.

Runtime evidence note:
- GitHub source conflict fixes and validation guards are complete.
- Successful Cloudflare/VPS production deployment is not claimed without workflow/runtime evidence.

## Current protocol

- No writer currently owns the repository write lock.
- Future changes must fresh-read `main` and preserve the single canonical V10 scheduler, three-AI conflict rules, verified-fresh pricing and Signal V10 / Binance Auto separation.
