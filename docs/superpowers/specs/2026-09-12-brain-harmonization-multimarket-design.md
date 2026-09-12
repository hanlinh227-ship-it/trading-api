# Brain Harmonization + Deep Multi-Market Analysis Design

## Goal
Enhance the canonical GitHub Brain with a permanent harmonization layer for future skills/upgrades and a research-only deep multi-market analysis capability, without changing current production trading execution authority.

## Authority boundary
- `CURRENT_HANDOFF.md` remains the single Trading execution authority.
- Current production execution remains BTCUSDT Linear Perpetual on Bybit until a separate explicit migration is approved and verified.
- Multi-market capability introduced here is analysis/research only; it cannot authorize order placement, leverage/account mutation, or silently revive retired strategy authority.
- Provider and upstream repository output is evidence/capability metadata, never reasoning authority.

## Architecture
`request -> task_router -> runtime_profile -> project authority -> primary skill -> execution capsule -> harmonization gate -> bounded supporting skills/tools -> maker -> checker -> independent grader when DEEP/high-impact -> evidence reconciliation -> verification -> artifact shaping -> answer`

### Harmonization Layer
A canonical stable policy governs all future skill/provider/knowledge additions. Every candidate must be normalized, deduplicated, classified by authority/risk, checked for overlap/conflict, evaluated against existing capabilities, and promoted only through existing Evergreen/release gates. Canonical skills are strengthened in place where possible; aliases/adapters are preferred over duplicate reasoning authorities.

### Cognitive loop
- FAST: no extra loop; preserve latency contract.
- STANDARD: maker + lightweight checker when material.
- DEEP: bounded maker/checker loop plus independent grader for architecture, trading/live/high-impact, complex research, or production changes.
- No unbounded recursion; evidence conflicts are surfaced rather than averaged.

### Deep Multi-Market Analysis
A new `multi_market_analysis` trading skill provides cross-asset research across crypto, FX, futures, indices, commodities/metals and equities when tools/sources are available. It separates global regime, cross-asset relationships, instrument structure, microstructure, volatility/liquidity, catalyst risk, and execution semantics. Live claims require current approved runtime evidence and semantic normalization.

The skill may compare markets and rank research opportunities, but any execution recommendation must re-enter current project authority and risk/execution gates. It cannot infer that production supports an instrument merely because analysis supports it.

### Artifact Pyramid
DEEP results should default to layered output: executive conclusion -> market/regime synthesis -> instrument dossiers/evidence when useful. This reduces context bloat while preserving traceability.

## Conflict rules
1. Current runtime evidence wins for runtime facts.
2. Current project authority wins for project behavior.
3. Stable security/risk policy cannot be weakened by imported skills.
4. Normalize symbol/venue/instrument type/quote/price semantics/time/window/unit before comparison.
5. No majority vote and no silent averaging of contradictory evidence.
6. Unresolved material conflict blocks dependent high-consequence conclusions.
7. New skills/providers start quarantined and receive zero authority until promotion gates pass.

## Success criteria
- Permanent checkpoint-resolved harmonization policy exists.
- Router/catalog can discover `multi_market_analysis` without changing production execution authority.
- Trading router explicitly distinguishes multi-market analysis from production execution.
- Future skill upgrades have a documented merge/dedupe/conflict/promotion protocol.
- Existing validators/CI remain green before merge.
