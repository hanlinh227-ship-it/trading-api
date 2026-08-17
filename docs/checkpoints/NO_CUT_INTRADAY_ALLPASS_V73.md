# NO-CUT INTRADAY ALL-PASS V73

Updated: 2026-08-17 UTC+7
Status: FROZEN statistical/development prior

## Locked target represented by the frozen artifact
- CUT is forbidden.
- Discretionary whole-day NO TRADE is forbidden.
- Each Forex pair / Crypto symbol targets 1–3 trades per eligible day; current frozen passing maps use exactly 1 trade/day.
- RR may only be 1:1 or 1:2; current frozen passing maps use RR1:1.
- Per-symbol development WR gate was >=80%.
- TIMEOUT is a non-win.
- Same-bar TP+SL is scored as SL conservatively.
- Each symbol owns its own frozen method and historical context metadata.

## Frozen development gate
- Forex: **28/28 PASS**; minimum individual development WR **80.00%**.
- Crypto: **61/61 PASS**; minimum individual development WR **80.22%**.
- Forex uses H1.
- 59 Crypto symbols use H1.
- TON/IP use dedicated 4H methods.

Recorded difficult-symbol development results:
- HBAR 95.60%.
- TAO 96.70%.
- TON 91.21%.
- IP 86.81%.

## Frozen lineage
The frozen artifact was assembled from the completed development lineage:
- Forex V64 base + V66 targeted refinement;
- Crypto V69 static passes + V70 observable routers + V71 HBAR/TAO + V72 TON/IP.

Those optimizer/rebuild generations are historical provenance, **not active runtime code**. They have been removed from the active `main` tree during repository cleanup so live operation cannot accidentally rerun or retune V73. Git history remains the archive if the historical development lineage ever needs inspection.

## Canonical runtime sources
Frozen source of truth:
- `data/nocut_intraday_allpass_v73.json`

Operational reader:
- `scripts/nocut_intraday_method_v73.py`

Hard-gate validator:
- `scripts/validate_nocut_v73.py`
- `.github/workflows/validate-nocut-v73.yml`

Historical build run `32032071403` remains provenance only; there is intentionally no active V73 rebuild workflow after cleanup.

Operational validation evidence retained in project history:
- validation run `32033371607`, job `95398145183` — PASS;
- 28 Forex + 61 Crypto;
- minimum development WR 80.00% / 80.22%;
- frozen maps exactly 1 trade/day;
- 89/89 instruments contain context metadata;
- router/action references validated.

## Live-use rule
**Never execute V73 raw.** V73 is only the frozen statistical/setup prior consumed by V74.

For current live context, symbol identity, news, price freshness, M15/M5 confirmation, execution quality and structural risk, always use `LIVE_SYMBOL_ANALYSIS_V74.md` and the current data policy.

The old V73 live-news metadata is retained inside the frozen JSON for provenance but is deprecated for current crypto context because V74 corrected identity/profile mappings.

## Integrity classification
**EXPOSED DEVELOPMENT ALL-PASS — NOT UNTOUCHED OOS.**

May–Jul 2026 was used to search/refine these maps. The requested development gate was met, but the development WR must not be described as a future/live guarantee.

V73 must remain unchanged while V73+V74 forward/OOS evidence is collected. A future method change must create a new version rather than silently rewriting V73.
