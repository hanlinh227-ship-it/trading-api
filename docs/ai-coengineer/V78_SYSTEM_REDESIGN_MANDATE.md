# V78 SYSTEM REDESIGN MANDATE

Status: DESIGN ACTIVE
Owners: CHATGPT + CLAUDE
Primary integrator: CHATGPT
Co-architect: CLAUDE
Production write rule: one writer at a time via WRITE_LOCK

## Goal
Redesign the Trading system as a cleaner, more reliable, easier-to-understand platform while preserving capital safety, state continuity and current proven invariants.

This is NOT permission to delete working production paths blindly. First map current source, identify conflicts/duplication, design target architecture, then migrate incrementally with rollback-safe checkpoints.

## Workstream A — HUB / Telegram UX redesign
Design a compact HUB that is easy to understand, low-noise and resistant to callback/state bugs.

Required outcomes:
- fewer top-level buttons and clearer market/account separation;
- one consistent navigation grammar;
- live state shown once, not duplicated across screens;
- clear distinction between SIGNAL, WATCH, LIVE ORDER, POSITION, SYSTEM HEALTH and SETTINGS;
- no confusing legacy labels;
- deterministic callback routing;
- stale messages/buttons handled safely;
- notification dedupe/cooldown by semantic event, not just text;
- system-health alerts aggregated instead of spammed;
- diagnostics separated from normal user-facing UX.

## Workstream B — Trading intelligence redesign
Redesign how the system discovers opportunities, evaluates entries and gathers information.

Required architecture questions:
- separate broad discovery from deep confirmation;
- provider-neutral market-data layer;
- exact symbol/venue identity and freshness contract;
- current-news/context acquisition layer;
- HTF structure/liquidity/regime layer;
- entry-location/trigger layer;
- risk/room/execution-suitability layer;
- score must explain WHY, not hide hard gates;
- MARKET/LIMIT/WATCH/NO_TRADE lifecycle must be explicit;
- avoid stale legacy scoring paths and duplicated decision logic;
- add evidence object so every decision can be traced back to source/timestamp/provider;
- distinguish research priors from live execution authority.

Design a canonical decision pipeline such as:
DISCOVERY -> DATA INTEGRITY -> CONTEXT -> STRUCTURE -> LOCATION -> TRIGGER -> RISK -> EXECUTION QUOTE -> DECISION -> LIFECYCLE.

## Workstream C — Hyro auto-trade redesign
Goal: make Hyro execution robust enough for unattended operation without weakening hard risk.

Required outcomes:
- explicit account connection state vs degraded optional telemetry;
- account snapshot abstraction;
- order intent lifecycle and idempotency;
- retry-safe execution when API response is ambiguous;
- exchange reconciliation as authority for positions/orders;
- native SL/TP verification;
- partial fill/partial close handling;
- restart recovery;
- position manager independent from new-entry scanner;
- emergency stop / manual pause / hard daily loss preserved;
- order and position state transitions explicit and auditable;
- no order duplication after timeout/retry;
- telemetry failures classified CRITICAL vs OPTIONAL;
- safe management of existing positions even when optional endpoints fail.

## Workstream D — API foundation + future multi-account architecture
Inventory every API/provider already present in the repository and design an adapter/capability architecture that can scale to multiple accounts later without restoring legacy TK2 code.

Target abstractions should consider:
- MarketDataProvider
- NewsContextProvider
- ExecutionVenue
- AccountAdapter
- AccountRegistry
- PositionRepository
- OrderRepository
- RiskPolicy
- ExecutionPolicy
- ReconciliationService
- NotificationBus
- HealthProvider

Each account/venue adapter must declare capabilities rather than assuming all venues behave identically, for example:
- spot vs derivatives;
- native SL/TP support;
- position modes;
- order types;
- leverage;
- closed-PnL endpoint availability;
- quote freshness semantics;
- rate limits;
- authentication variables.

Future multi-account design must isolate state by account ID and venue, preserve idempotency per account and prevent one account failure from poisoning others.

## Cross-cutting architecture requirements
- current `main` source is the factual starting point;
- preserve `TRADING_STATE` and `v775:books` until an explicit migration exists;
- no secret values in source/docs;
- state keys need versioning/migration plans;
- deterministic validation before merge;
- observable health with component severity;
- clear ownership of each decision and state transition;
- remove duplicated/legacy code only after callers are mapped;
- every migration step must have rollback notes;
- avoid giant god-files where feasible;
- external APIs are adapters, not business logic owners;
- runtime code must tolerate partial provider failure;
- design for Cloudflare Worker stateless/concurrent execution.

## Required Claude deliverable — Phase 1
Claude must audit current `main` and return a source-backed architecture blueprint, not code changes yet.

Deliverable sections:
1. CURRENT SYSTEM MAP
2. HUB PROBLEMS + TARGET HUB
3. CURRENT SIGNAL/ENTRY PIPELINE + TARGET PIPELINE
4. INFORMATION/API INVENTORY
5. HYRO FAILURE MODES + TARGET EXECUTION STATE MACHINE
6. MULTI-ACCOUNT FOUNDATION
7. MODULES TO KEEP
8. MODULES TO REFACTOR
9. MODULES TO DEPRECATE
10. STATE/KV MIGRATION PLAN
11. TARGET FILE/FOLDER STRUCTURE
12. PHASED IMPLEMENTATION PLAN
13. HIGH-RISK MIGRATIONS
14. QUICK WINS
15. QUESTIONS/DISAGREEMENTS FOR CHATGPT

For every major claim, cite exact files/functions from current `main`.

Do not modify production source during Phase 1.

## Review model
Claude proposes architecture independently. ChatGPT independently validates it against current source. Disagreements are written to the GitHub bus. Only agreed design slices become implementation issues with explicit owner and WRITE_LOCK scope.
