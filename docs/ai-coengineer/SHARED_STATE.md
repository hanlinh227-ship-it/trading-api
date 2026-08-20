# AI SHARED STATE

Canonical repository: `hanlinh227-ship-it/trading-api`
Branch: `main`

## Current architecture — SIGNAL ONLY

User direction as of 2026-08-20:
- Hyro auto-trade is discontinued and must not return to the active architecture.
- The production worker must focus on Signal generation, market analysis, Entry Intelligence, Telegram Hub, market-data freshness and Signal lifecycle quality.
- No active real-capital execution authority exists in this repository runtime.
- `executionAuthority = SIGNAL_ONLY / NONE` for trading decisions.

## V78-027 — RESOLVED / SIGNAL-ONLY CUTOVER

Active source changes:
- `cloudflare-worker/index.js` no longer imports or schedules Hyro runtime, telemetry, position review, demo execution, order management or auto-cycle code.
- `cloudflare-worker/hub-v77171.js` is now `HUB-R14-SIGNAL-ONLY`; the Telegram main menu contains Signal / Forex / Crypto / Metal / Index / Entry Intel / Coverage only.
- Hyro setup/dashboard/positions/risk/connect/auto controls are removed from active Hub behavior.
- `/prop/*` and `/hyro/*` are no longer active execution surfaces.
- `providers/entry-intelligence.js` revision is V78-027 and remains advisory Signal-only with execution authority `NONE`.

Entry Intelligence improvements in V78-027:
- Forex OPTIONAL currency-strength evidence now consumes real `strengthDiff` aliases when already present.
- Crypto OPTIONAL funding evidence now consumes `fundingRate` aliases when already present.
- Crypto OPTIONAL open-interest and identity aliases were normalized without fabricating missing fields.
- WHY NOW / WHY PRICE / WHY SL / WHY TP text is clearer and remains derived only from existing evidence.
- REQUIRED / QUALITY / OPTIONAL contract is unchanged: REQUIRED may block; QUALITY may rank; OPTIONAL may not independently block.
- Coverage is sampled per market (max 15 per market from retained recent evidence) to reduce Forex/Crypto dominance.

Data cleanup evidence:
- `docs/ai-coengineer/V78-027_VALIDATION.txt`
- KV keys scanned: 168.
- Hyro-matching KV keys deleted: 76/76.
- Filter: case-insensitive `hyro` substring.
- `v775:books` preserved.
- TRADING_STATE was not reset.
- Signal evidence / Entry Intelligence data remains preserved.

V78-026 H1 and H2-H6 are CANCELLED by user direction and must not resume.
Completed H1 diagnostic workflows were removed from active `.github/workflows` after cancellation.

## Signal priorities from here

1. Improve market-specific evidence plumbing using only real provider fields.
2. Improve ranking discrimination between MARKET / LIMIT / WATCH without weakening hard gates.
3. Improve structural entry-location reasoning and trigger quality.
4. Improve multi-timeframe regime/session/context agreement.
5. Improve false-positive suppression using fresh-data evidence rather than arbitrary threshold inflation.
6. Improve Telegram output so the user can immediately see: best setup, mode, quality, freshness, why-now, entry, structural SL, TP/RR, invalidation and missing evidence.
7. Measure performance by market separately before approving market-specific quality weights.

## Permanent safety / integrity constraints

- Never reset `TRADING_STATE`.
- Never delete/reset `v775:books`.
- Never weaken quote freshness, structural-SL, RR-quality or required news/context protections.
- Never fabricate provider values, market evidence, tests or deployment results.
- Never restore legacy Futures Signal or TK2.
- Binance20 remains NON_PRODUCTION / QUARANTINED.
- Production Anthropic/Claude API remains PAUSED unless the user explicitly re-enables it.
- Claude.ai Web remains an equal co-engineer and may optimize Signal architecture under WRITE_LOCK.

Historical V78-001..V78-025 decisions and validation remain in Git history and `docs/ai-coengineer/`; this file describes the current canonical state.

V78-028 — RESOLVED / DEPLOYED
- Source SHA: 4e0a5732b59ec02077bd3e7198a9dae181c8f7ad
- Cloudflare Version ID: 1961e90e-900e-43d5-8e72-cc354dccbe4b
- Post-Yahoo-fix live acceptance passed for NAS100/US30/US500/DEX/JP225.
- Yahoo ^DJI is visibility-only for US30 when used: fresh=false, analysisOnly=true, executionVerified=false; MARKET/MARKET_SIGNAL admission blocked.

V78-030 — RESOLVED / DEPLOYED
- Source SHA: b98cdf3d2afa0d2e072b4ff262c56d30b0f5c03e
- Cloudflare Version ID: 3d78408f-d55e-4115-84e4-b1d967ab3b1b
- WHY NOW propagated only to watchLine() and hubSummary(); actionableRank/hubRank/fillBooks unchanged.
- Live group + Hub JSON passed and Hub top ordering remained unchanged.

V78-031 — true
- Dead setupCard entryIntelligence field present at fresh audit: true.
- Source SHA: 2716fc07d3305c1ddd880f4ff71a98244f15d41a
- Cloudflare Version ID: 691af45f-59d8-4993-9fc0-910b6ea90c30
- If applied, fix is rendering-only via buildEntryIntelligenceShadow(a).quality.
