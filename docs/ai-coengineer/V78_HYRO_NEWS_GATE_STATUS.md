# V78-003 — Hyro News-Gate Status

Status: RESOLVED — DOCUMENTATION ONLY / ZERO_BEHAVIOR
Owner: CHATGPT
Reviewer: CLAUDE
Review result: PASS reported by user handoff on 2026-08-19

## Purpose
Document the current source-backed state of hard-news/event-risk handling in the Hyro auto-trading path before any production enforcement issue is opened.

V78-003 changes no runtime behavior. It does not add a provider, call an API, block or permit an order, change risk, alter KV state, or modify any production JavaScript.

---

## Current source-backed status

### 1. Hyro scanner has a funding/carry gate
Current source: `cloudflare-worker/hyro-scanner.js`.

`fundingView(ticker, side)` evaluates:
- funding rate;
- next funding timestamp;
- minutes to settlement;
- whether the selected side pays funding;
- adverse funding magnitude;
- a near-settlement funding block;
- an RR penalty.

Current `basePlan()` can return WATCH with reason `ADVERSE_FUNDING_NEAR_SETTLEMENT` when that funding condition blocks a plan.

This is a microstructure/carry control. It is **not** a news, macro-event, token-event, exchange-event or economic-calendar feed.

### 2. Hyro market context has microstructure only
Current source: `cloudflare-worker/hyro-market-context.js`.

`getHyroMarketContext(plan)` currently pulls Bybit public data for:
- open interest;
- account long/short ratio;
- orderbook;
- spread derived from top bid/ask.

The context score uses OI, book imbalance, crowding and spread weights. There is no authoritative news/calendar/event provider in this module.

### 3. Current Hyro runtime does not expose a hard-news clearance gate before execution
Current source chain:

```text
hyro-runtime.js
→ hyroDynamicScan()
→ enrichHyroPlans()
→ evaluateHyroPortfolio()
→ executeHyroPlan()
```

The currently documented/observed scanner and market-context stages provide technical/microstructure evidence but no distinct authoritative hard-news status such as `NEWS_CLEAR`, `NEWS_BLOCK`, `NEWS_UNVERIFIED`, event severity, event timestamp or source freshness.

Therefore current source evidence does **not** support claiming that a Hyro executable order has passed an authoritative hard-news gate.

---

## Canonical V78 interpretation

Per DECISION-009 / V78-041:

- funding-rate protection remains a separate microstructure/carry gate;
- funding must never be documented as equivalent to hard-news clearance;
- advisory/watch analysis may explicitly carry `NEWS_UNVERIFIED` when authoritative news evidence is unavailable;
- new executable Hyro orders must eventually have an explicit authoritative news/context policy before the system may claim `NEWS PASS` where the active mandate requires hard-news clearance;
- absence/failure of the required hard-news source must not be silently converted into PASS.

This document records the gap only. It does **not** change current production behavior.

---

## DecisionEvidence mapping

Future Hyro evidence should represent news independently from funding:

```text
MICROSTRUCTURE
  funding: PASS | BLOCK | DEGRADED | UNKNOWN
  openInterest: ...
  longShort: ...
  orderbook: ...
  spread: ...

NEWS
  state: PASS | BLOCK | DEGRADED | UNKNOWN
  provider: <authoritative source>
  eventId: <if available>
  eventTime: <if available>
  severity: <policy-defined>
  checkedAt: <timestamp>
  freshness: LIVE | DELAYED | STALE | DEGRADED | MISSING | UNKNOWN
```

Funding state must not populate the NEWS gate.

---

## Current status classification

| Concern | Current status | Evidence |
|---|---|---|
| Funding/carry protection | PRESENT | `hyro-scanner.js:fundingView` |
| Open-interest context | PRESENT | `hyro-market-context.js:getHyroMarketContext` |
| Long/short crowding context | PRESENT | `hyro-market-context.js:getHyroMarketContext` |
| Orderbook/spread context | PRESENT | `hyro-market-context.js:getHyroMarketContext` |
| Authoritative hard-news provider | NOT PRESENT IN CURRENT HYRO MODULES REVIEWED | No news provider call in scanner/market-context path |
| Explicit `NEWS_UNVERIFIED` state | NOT PRESENT IN CURRENT HYRO EXECUTION PIPELINE REVIEWED | Requires later implementation |
| Executable hard-news fail-closed gate | NOT YET IMPLEMENTED / NOT PROVEN | Requires separate source issue |
| Funding used as news substitute | MUST NOT | DECISION-009 |

---

## Required future implementation issue — NOT AUTHORIZED BY V78-003

A later separately scoped issue should define and implement:

1. authoritative news/context provider abstraction;
2. provider timestamp/freshness semantics;
3. event severity and symbol/market applicability;
4. `PASS | BLOCK | DEGRADED | UNKNOWN` news state;
5. explicit `NEWS_UNVERIFIED` for advisory/watch paths;
6. fail-closed policy for executable new orders where hard-news clearance is mandatory;
7. DecisionEvidence population;
8. timeout/failure behavior;
9. caching/rate-limit policy without fabricating clearance;
10. deterministic fixtures for no-event, blocking-event, provider-down, stale-event and unrelated-event cases.

That implementation must be a separate WRITE_LOCK scope and should receive `trading-data-integrity-auditor`, `hyro-execution-auditor`, `trading-risk-guardian` and regression review before production cutover.

---

## Hard invariants

V78-003 does not authorize:
- weakening/removing `fundingView`;
- assuming no news because a provider is unavailable;
- using funding as a proxy for news;
- changing Hyro order eligibility;
- changing hard risk;
- changing structural SL;
- adding/removing credentials;
- resetting `TRADING_STATE`;
- deleting/resetting `v775:books`;
- restoring TK2 or legacy Futures Signal.

---

## Acceptance criteria

- [x] Current funding logic is documented as funding/carry, not news.
- [x] Current Hyro microstructure context is documented separately from news.
- [x] Current source does not get falsely labeled as having authoritative hard-news clearance.
- [x] Future executable hard-news requirement is explicit and separated from V78-003.
- [x] `NEWS_UNVERIFIED` semantics are documented for later advisory evidence work.
- [x] No production JS, API call, order behavior, risk, provider or KV state changed.
- [x] Claude review outcome reported PASS; V78-003 is resolved.

## Resolution note
V78-003 is documentation-only and is now closed. Any production hard-news enforcement remains a separate future issue with its own exact WRITE_LOCK, tests and independent review.
