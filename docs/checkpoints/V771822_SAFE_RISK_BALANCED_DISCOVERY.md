# V77.18.22 — SAFE DAILY RISK + BALANCED DISCOVERY

## PURPOSE
Protect the Hyro daily loss budget after the next official UTC reset without tightening structural stops, while keeping entry discovery practical and preserving hard safety gates.

## EFFECTIVE TIME
New PROP risk and TP-management policy activates at `2026-08-19T00:00:00Z` (07:00 Vietnam). Before that instant the legacy risk policy remains active so the current Hyro trading day is not changed mid-cycle.

## PROP RISK AFTER RESET
- A-tier base risk: 0.45% of current equity before dynamic defense scaling.
- Max single worst-loss budget: 0.55% equity.
- Max combined open risk: 0.90% equity.
- Internal daily hard stop: 1.60% equity.
- Internal daily profit lock: approximately 1.20% of day-start equity.
- New-entry risk scale: 75% after ~0.4% DD, 50% after ~0.8% DD, 30% after ~1.2% DD; after +0.8% daily profit new-entry scale is capped around 55%.
- Structural SL remains authoritative. Lower USD risk is achieved by smaller position sizing rather than mechanically shortening the stop.

## TP / POSITION MANAGEMENT AFTER RESET
- TP1 capped around 0.85R, approximately 45% reduction.
- TP2 capped around 1.60R, approximately 35% reduction.
- Runner remains approximately 20%, TP3 capped around 2.45R.
- Existing BE after TP1, trailing after TP2, native stop/TP and HOLD/TIGHTEN/CUT logic remain.

## CLAUDE REVIEW AUTOMATION
Claude remains REVIEW-ONLY. It cannot trade, close, deploy or modify secrets. Until the same 07:00 reset boundary, Worker internal cadence allows one `OVERNIGHT_30M_SYSTEM_REVIEW` approximately every 30 minutes, subject to a bounded temporary daily budget. Normal release/incident/daily review continues after the temporary window.

The reviewer reads truncated public code for Signal engine, HUB, Health, PROP scanner/execution/microstructure/portfolio/position management and a sanitized runtime snapshot. It reviews code/config conflicts, HUB UX, market-specific entry quality/frequency and PROP risk/management.

## HUB
Main HUB hierarchy is simplified to Signal / PROP, Personal / Symbol, Orders / System, then AI Review. Existing callbacks remain, so this is a presentation cleanup rather than a state migration.

## SIGNAL
At this checkpoint the existing Signal core remains V77.16.9 until its large engine file receives a separately validated soft-gate patch. Do not falsely label the Signal core V77.16.10 before that patch lands. The intended tuning is limited to soft discovery gates; hard news, freshness, structural, execution-authority and futures-risk gates must remain.

## STATE SAFETY
Never reset `TRADING_STATE` or `v775:books`. Existing PROP position/runtime/idempotency/management/review state remains continuous. Version deployment must not close positions solely because code changed.

## BUILD/DEPLOY
Canonical validator is updated for V77.18.22 risk/TP/Claude/HUB locks. Production is not considered active until Cloudflare deploys the new Worker successfully. A one-shot V77.18.22 verification workflow is provided to record syntax/npm/Wrangler results when GitHub Actions executes it.
