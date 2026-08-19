# AI ENGINEERING DECISIONS

## DECISION-001 — GitHub communication bus
Decision:
ChatGPT and Claude coordinate through `docs/ai-coengineer/` on GitHub.

Rules:
- One writer at a time.
- Source `main` outranks stale checkpoint text.
- Review messages do not authorize production writes by themselves.
- Claude may BLOCK a change; ChatGPT must verify the finding before acting.
- After every substantive work cycle, the acting AI must leave exactly one ready-to-send handoff prompt for the other AI.

## DECISION-002 — Signal market architecture
Decision:
Legacy Futures Signal remains removed. Canonical Signal markets are Forex, Crypto, Metal and Index Cash.

Do not restore:
- Futures Signal proxy logic.
- Global legacy scan/live callbacks.

## DECISION-003 — State safety
Decision:
Releases must preserve `TRADING_STATE` and `v775:books`; no release-driven forced position closure.

## DECISION-004 — V78 AI runtime separation
Decision:
Do **not** blindly merge `claude-reviewer.js` and `dual-ai-intervention.js` into one behavior. They currently serve meaningfully different roles: code/release review versus runtime/tuning intervention. V78 should instead share common Anthropic client/evidence-snapshot/budget primitives while keeping two explicit bounded workflows unless further source evidence proves one redundant.

## DECISION-005 — Binance20 quarantine, not restoration
Decision:
`binance-futures20-*` / `binance-usdm-client.js` are not part of current production authority. Do not delete them yet and do not activate them. Quarantine/document them as NON_PRODUCTION and reuse only if they become an explicit future `ExecutionVenue` / `AccountAdapter` pilot after review. This is not permission to restore old TK2/multi-account architecture.

## DECISION-006 — Hyro pre-submit telemetry policy
Decision:
Do not simply delete the second telemetry read in `executeHyroPlan` without replacement. V78 should pass caller telemetry into execution with freshness metadata, then perform a narrow pre-submit revalidation only for execution-critical state when age/conditions require it. Goal: preserve defense-in-depth while avoiding full duplicate 4-endpoint telemetry round trips and inconsistent snapshots.

## DECISION-007 — One canonical Hyro risk/profile view
Decision:
HUB must not maintain an independent hardcoded Hyro risk shell. After source verification, UI profile/risk rendering should consume the same canonical dynamic risk/profile computation used by execution so display cannot contradict gates.

## DECISION-008 — News gate semantics
Decision:
For advisory discovery/WATCH, missing external news service may be represented explicitly as `NEWS_UNVERIFIED`/degraded rather than fabricated clearance. For **new executable orders**, absence/failure of the required hard-news source must not be silently described as a hard-news pass. V78 design must make the policy explicit and fail closed wherever the active trading mandate requires hard-news clearance. Do not change production behavior until the scoped implementation/review phase.
