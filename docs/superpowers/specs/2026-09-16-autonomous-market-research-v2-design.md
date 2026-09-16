# Autonomous Market Research V2 — Hybrid Autopilot Design

Date: 2026-09-16
Status: approved for implementation by user
Parent capability: Harmonized Multi-Market Intelligence (PR #383)

## Goal

Make the Trading Brain operate from a short natural-language request such as `tìm lệnh`, `quét thị trường`, or `tìm setup tốt nhất` without requiring the user to choose a market, provider, timeframe, strategy, or TradingView chart manually.

The system must automatically plan research scope, obtain or accept bounded market evidence, build candidates, challenge them, rank them across domains, and return `TOP_SETUP` or `NO_TRADE` with provenance and chart context.

## Non-negotiable authority boundaries

- `AI_SKILL_LIBRARY/v4/stable/router.yaml` remains the only global router authority.
- The canonical primary skill remains `multi_market_analysis`; no parallel global/trading reasoning router is introduced.
- External providers/plugins/connectors are evidence/capability sources only. They never become reasoning or execution authority.
- Production execution authority is unchanged: BTCUSDT Linear Perpetual on Bybit only under `BYBIT-BTC-STATEFLOW-2.1`.
- Forex, futures, indices, metals, commodities, and non-authorized crypto paths remain research-only until separately validated/promoted.
- No provider credential from a ChatGPT connector/plugin is assumed to exist inside Railway. Connector evidence and gateway provider evidence are separate source planes sharing one typed research contract.
- Unknown/stale/conflicting evidence fails closed. The system must never fabricate live state or a TradingView mapping.
- Zero-local remains mandatory for normal user operation.

## Architecture

`task_router -> multi_market_analysis -> autonomous research planner -> source capability planner -> market evidence -> timeframe/profile selection -> candidate builder -> freshness/conflict challenge -> cross-market ranking -> chart context -> concise answer`

The implementation extends the existing `crypto-research-gateway` research lane. It reuses provider routing, data contracts, freshness semantics, conflict detection, and `rankOpportunities()` from PR #383.

It adds orchestration contracts and deterministic candidate-building logic. It does not duplicate the existing crypto provider registry or create a second data router.

## Source planes

### 1. Gateway-native plane

The existing Railway gateway can directly obtain crypto market evidence through the current provider/runtime infrastructure. This is the first-class path for gateway-native scanning.

### 2. Connector/tool plane

When the caller has access to external market-data connectors such as Massive, it may supply normalized external observations for Forex/Futures/Indices/Metals/Commodities. Connector authentication remains outside Railway.

The gateway validates supplied observations with strict schemas, freshness timestamps, source IDs, and permission ceilings. External observations are always `research_evidence`, never production execution authority.

### 3. Missing-source behavior

If a requested domain has no usable evidence, the response records a coverage gap. Missing evidence does not silently become a neutral/positive signal. A domain with insufficient required evidence cannot produce a ranked candidate.

## Autonomous research request

Add `POST /research/autoscan`.

Request fields:

- `intent`: optional free-text research intent, max 240 chars.
- `requestedDomains`: optional subset of `crypto|forex|futures|indices|metals|commodities`; default all.
- `symbols`: optional bounded per-domain symbol list.
- `externalObservations`: optional normalized connector/tool observations.
- `maxResults`: optional, 1..10, default 3.

Forbidden fields include execution/order directives such as `placeOrder`, `quantity`, `leverage`, API credentials, or any production permission expansion.

Response fields:

- `ok`
- `researchOnly: true`
- `productionExecutionAuthority: false`
- `capability: autonomous_multi_market_research`
- `scope`
- `coverage`
- `timeframePlan`
- `candidatesBuilt`
- `decision: TOP_SETUP|NO_TRADE`
- `ranked`
- `blocked`
- `dataContract`

## Market observation contract

A normalized external observation contains:

- `id`
- `domain`
- `symbol`
- `source`
- `sourceType: connector|gateway`
- `eventTime`
- `ingestTime`
- `freshness: FRESH|DEGRADED|STALE|UNKNOWN`
- `timeframe`
- `open/high/low/close`
- optional `bid/ask/volume`
- optional `session`
- optional `metadata`

Validation rules:

- finite numeric prices only;
- `high >= max(open, close, low)` and `low <= min(open, close, high)`;
- `ask >= bid` when both exist;
- timestamps must parse;
- stale/unknown observations are preserved for provenance but are not allowed to authorize a candidate;
- no credential/secrets fields.

## Timeframe planner

The planner is deterministic and research-oriented:

- default broad context: `1h`;
- entry refinement: `15m`;
- fast crypto context may additionally use `5m` when gateway data is available;
- explicit caller timeframe is not accepted in V2 autoscan to keep orchestration autonomous and avoid user micromanagement.

The response exposes the chosen plan for auditability.

## Domain profiles and candidate builder

Reuse the profiles introduced in PR #383. Candidate construction uses domain evidence, not a single universal trading strategy.

Minimum research evidence by domain:

- crypto: structure + liquidity/price quality + freshness;
- forex: structure + session/context + freshness;
- futures: structure + session/liquidity + freshness;
- indices: structure + session + cross-market/context + freshness;
- metals: structure + liquidity/price quality + macro/context + freshness;
- commodities: structure + liquidity/price quality + macro/context + freshness.

V2 candidate scoring is intentionally simple and explainable. It derives direction from multi-bar structure and current-price location, creates explicit aligned/opposing evidence, computes a bounded raw score, confidence, risk-reward estimate, and an invalidation string. It must not use an indicator as sole entry authority.

A candidate is not built when:

- evidence is stale/unknown;
- fewer than the minimum bars/evidence required for structure exist;
- price semantics conflict materially;
- the direction is ambiguous;
- invalidation cannot be derived.

## TradingView/chart integration

TradingView remains a presentation/navigation layer, not the market-data authority.

- Reuse `VerifiedChartMapping` and `buildChartContext()`.
- Autoscan may accept an externally verified TradingView mapping attached to an observation/symbol.
- Unknown mappings remain `UNVERIFIED` with `symbol: null`.
- The system may return a non-authoritative TradingView search/navigation hint, but must never label it `VERIFIED` unless supplied/validated as such.
- No scraping of TradingView internal websocket/HTML/private endpoints.
- No paid TradingView account is required for the Brain research pipeline.

## Natural-language autonomy contract

The Brain skill layer should interpret common requests such as:

- `tìm lệnh`
- `tìm lệnh tốt nhất`
- `quét market`
- `quét toàn bộ thị trường`
- `có setup nào không`

as an autonomous multi-market research intent when current Trading project authority applies.

The expected behavior is research orchestration, not automatic permission to place an order.

## Failure behavior

- no sources -> `NO_TRADE` with `NO_USABLE_EVIDENCE` coverage reasons;
- stale sources -> `NO_TRADE` and stale provenance;
- conflicting prices -> affected candidates blocked;
- connector unavailable -> remaining domains continue; coverage gap disclosed;
- internal crypto provider outage -> gateway degrades/fails closed under current policy;
- unknown TradingView mapping -> analysis may continue, chart mapping remains `UNVERIFIED`;
- order/execution fields in autoscan request -> HTTP 400.

## Testing

TDD is mandatory.

Required RED/GREEN coverage:

1. autonomous scope defaults to all approved domains;
2. external observations validate and normalize;
3. malformed OHLC/bid-ask data is rejected;
4. stale/unknown evidence cannot produce a candidate;
5. deterministic timeframe plan is returned;
6. candidate builder creates directional candidates from valid bar sequences;
7. ambiguous structure returns no candidate;
8. ranking reuses `rankOpportunities()` and returns `TOP_SETUP`/`NO_TRADE`;
9. unknown chart mappings remain unverified;
10. `/research/autoscan` rejects execution/order fields;
11. endpoint remains research-only and exposes coverage gaps;
12. all existing gateway/Brain/Bybit safety tests remain green.

## Deployment

- Implement on isolated branch.
- PR/CI must show RED evidence before production implementation and GREEN evidence afterward.
- Do not deploy feature branch to Railway production.
- Merge only after exact-head CI/validators pass.
- Railway production deployment must use exact verified `main` commit and set `DEPLOYMENT_SOURCE_SHA` accordingly.
- `/health` and Railway deployment metadata must agree on exact source SHA before claiming the research capability LIVE.
- BTC execution runtime switches/authority must remain unchanged.
