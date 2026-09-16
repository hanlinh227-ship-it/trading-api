# Live Multi-Market Data Fabric V3 — C2 Hybrid Design

Date: 2026-09-16
Status: approved in chat as C2; written-spec review pending
Parent capability: Autonomous Market Research V2
Canonical authority: GITHUB_BRAIN_V4

## Goal

Make a short user request such as `tìm lệnh`, `quét market`, `tìm setup tốt nhất`, or `quét đa thị trường` produce an end-to-end live research scan across approved domains without requiring the user to manually choose providers, symbols, timeframes, or charts.

Approved research domains:

- crypto;
- forex;
- futures;
- indices;
- metals;
- commodities.

The system must automatically resolve a bounded symbol universe, acquire live or explicitly delayed market evidence through approved source planes, normalize all observations into one typed contract, enforce freshness/session/semantic checks, build domain-aware candidates, challenge conflicts, rank candidates across markets, and return `TOP_SETUP` or `NO_TRADE` with explicit Entry/Stop/Target research levels and provenance.

The user experience target is one user command with multiple internal tool/provider calls. It is not a requirement that Railway itself own every external provider credential.

## Non-negotiable authority boundaries

- `AI_SKILL_LIBRARY/v4/stable/router.yaml` remains the sole global routing authority.
- `task_router` remains mandatory infrastructure and `multi_market_analysis` remains the primary trading-research skill for broad market scans.
- No second global router, trading router, or provider-driven reasoning authority is introduced.
- External providers/connectors/plugins are market-evidence sources only. They never become reasoning authority or production execution authority.
- Production order execution remains BTCUSDT Linear Perpetual on Bybit only under `BYBIT-BTC-STATEFLOW-2.1`.
- Forex, futures, indices, metals, commodities, and non-authorized crypto symbols remain research-only even when a ranked setup contains Entry/Stop/Target.
- The signed V5 BTC-only execution barrier must remain unchanged and all existing Bybit authority regression tests must remain green.
- Connector credentials are never copied, exported, logged, persisted, or assumed to exist in Railway/Cloudflare.
- Unknown, stale, delayed-without-label, semantically conflicting, or entitlement-uncertain data fails closed for live ranking.
- TradingView is presentation/navigation context only and is never a market-data authority.
- Zero-local remains mandatory for normal user operation.
- No paid fallback may be enabled implicitly. Source use must respect current entitlement and `FREE_ONLY`/provider policy where applicable.

## Architectural decision: C2 Hybrid

C2 intentionally separates data acquisition into two planes that share one observation contract.

### Plane A — Railway gateway-native market data

The existing `crypto-research-gateway` continues to obtain crypto evidence directly from its native public providers:

- Bybit;
- Binance;
- OKX;
- Gate;
- KuCoin.

This plane is authoritative only for the evidence it actually returns. It does not gain authority over Forex/Futures/Indices/Metals/Commodities by configuration alone.

### Plane B — connector/tool market data

When ChatGPT has an approved market-data connector such as Massive, the orchestration layer may request:

- Forex current snapshot/last quote and OHLC bars;
- Futures real-time snapshot/trades and OHLC bars;
- Indices current snapshot and OHLC bars;
- Metals through verified futures products/contracts;
- Commodities through verified futures products/contracts.

The connector result is normalized into the same `NormalizedMarketObservation` contract and submitted as research evidence to the gateway.

Connector authentication remains entirely outside Railway. The implementation must not attempt to extract, copy, serialize, infer, or reuse connector credentials.

### Optional future native non-crypto adapters

The source-fabric interface must allow future Railway-native Forex/Futures/Indices adapters if separately configured with valid credentials/entitlements, but V3 must not claim those adapters are live unless runtime evidence proves they are configured and healthy.

This extension point must not be used to fabricate provider coverage during V3 delivery.

## End-to-end request flow

`user command -> task_router -> multi_market_analysis -> live source planner -> verified symbol universe -> provider/connector acquisition -> unified normalization -> freshness/session/entitlement gate -> timeframe bundle -> domain profile -> candidate builder -> conflict challenger -> cross-market ranking -> research levels -> TradingView navigation context -> answer`

The user issues one command. Internal orchestration may perform many bounded tool/provider calls.

## Source planner

Add a deterministic source planner that returns a `DataAcquisitionPlan` before candidate construction.

Required fields:

- `requestedDomains`;
- `resolvedDomains`;
- `symbolsByDomain`;
- `sourcesByDomain`;
- `timeframesByDomain`;
- `requiredEvidenceByDomain`;
- `entitlementStateBySource`;
- `fallbackPolicy`;
- `researchOnly: true` for every non-BTC execution domain;
- `productionExecutionAuthority: false` for the research scan itself.

Source priority rules:

1. Use gateway-native crypto sources for crypto evidence when healthy.
2. Use an approved connector source for non-crypto evidence when available and permitted.
3. Use a verified native non-crypto adapter only if runtime configuration and entitlement are explicitly healthy.
4. Never silently substitute an unrelated asset as a proxy.
5. If a requested domain has no usable source, mark coverage `GAP` and continue other domains.
6. Missing source coverage cannot improve another candidate's score.

## Verified symbol universe

Add a versioned `market-universe` contract instead of hard-coding ad hoc symbols inside route handlers.

### Crypto

Use the existing research universe/provider symbol normalization. The default V3 broad-scan universe should be bounded and configurable; it must not imply execution authority for non-BTC symbols.

### Forex

Initial verified research universe should cover highly liquid pairs such as:

- EURUSD;
- GBPUSD;
- USDJPY;
- USDCHF;
- USDCAD;
- AUDUSD;
- NZDUSD;
- EURJPY;
- GBPJPY.

Connector/provider-specific symbols must be generated through a symbol mapping layer, never by string concatenation in business logic.

### Futures

Use product-level intents such as `ES`, `NQ`, `YM`, and `RTY`, then resolve to an actual currently tradable contract using the provider's contract/reference/snapshot capability.

Never hard-code a dated contract as permanently current. An unresolved or expired contract produces a coverage gap.

### Indices

Initial verified intents may include `SPX`, `NDX`, and `VIX` when the active source confirms the corresponding provider symbol. Unknown mappings remain unverified and are excluded from live ranking.

### Metals

Initial product intents may include gold, silver, and copper through verified futures products such as `GC`, `SI`, and `HG` when a currently tradable contract is resolved.

### Commodities

Initial product intents may include crude oil and natural gas through verified products such as `CL` and `NG`, with the same current-contract resolution requirement.

## Normalized observation V3

Extend the existing normalized observation contract while remaining backward compatible with V2 inputs.

Required core fields remain:

- `id`;
- `domain`;
- `symbol`;
- `source`;
- `sourceType`;
- `eventTime`;
- `ingestTime`;
- `freshness`;
- `timeframe`;
- `open`;
- `high`;
- `low`;
- `close`.

Optional market fields:

- `bid`;
- `ask`;
- `volume`;
- `session`;
- `metadata`;
- verified chart context.

V3 adds explicit source semantics:

- `latencyMs` when derivable;
- `delayClass: REALTIME|DELAYED|UNKNOWN`;
- `entitlement: VERIFIED_REALTIME|VERIFIED_DELAYED|UNVERIFIED`;
- `instrumentType`;
- `providerSymbol`;
- `canonicalSymbol`;
- `contractExpiry` for futures when applicable;
- `evidenceKind: quote|snapshot|bar|trade|session|context`.

A source marked `DELAYED` or `UNVERIFIED` must never be relabeled `FRESH_REALTIME` merely because its HTTP response arrived recently.

## Freshness and entitlement gate

Freshness is a combination of event-time age and source entitlement semantics.

The gate must distinguish:

- fresh real-time evidence;
- fresh-but-delayed evidence;
- stale evidence;
- unknown timing/entitlement.

Rules:

- `VERIFIED_REALTIME + age within domain/timeframe tolerance` may authorize a live candidate.
- `VERIFIED_DELAYED` may be used for context/research but cannot authorize a setup labeled live/current.
- `UNVERIFIED` entitlement cannot authorize a live/current candidate.
- Event times in the future beyond clock-skew tolerance are invalid.
- `ingestTime < eventTime` beyond clock-skew tolerance is invalid.
- Bid/ask data must preserve executable-side semantics when present.
- A market-closed session is not equivalent to stale data; session metadata must be considered before classifying a legitimate last close.

V3 tests must use deterministic clocks and avoid assumptions that every market trades 24/7.

## Timeframe bundle

Retain the autonomous planner concept but require a multi-timeframe evidence bundle where the source supports it:

- context: `1h`;
- entry: `15m`;
- fast/refinement: `5m` where available and meaningful.

A candidate may not treat three bars from one timeframe as equivalent to confirmed multi-timeframe context when the domain profile requires context confirmation.

When a provider cannot supply a requested timeframe, the source planner records a capability gap instead of fabricating aggregation quality.

## Domain evidence profiles

V3 must enforce, not merely document, minimum evidence requirements.

### Crypto

Required:

- structure;
- price/liquidity quality;
- freshness;
- conflict check.

### Forex

Required:

- structure;
- session/context;
- quote quality when available;
- freshness.

### Futures

Required:

- resolved current contract;
- structure;
- active session/context;
- liquidity/price quality;
- freshness.

### Indices

Required:

- structure;
- session state;
- context evidence;
- freshness.

Cross-market context such as NQ/ES relationships may strengthen a candidate only when both underlying observations are independently valid and current.

### Metals

Required:

- resolved instrument/contract;
- structure;
- liquidity/price quality;
- context evidence;
- freshness.

### Commodities

Required:

- resolved instrument/contract;
- structure;
- liquidity/price quality;
- context evidence;
- freshness.

Macro/news context may enrich research when available, but V3 must not invent macro confirmation. Absence of optional macro context must be represented honestly.

## Candidate builder V3

Candidate construction remains deterministic and explainable.

It must output:

- direction;
- structure evidence;
- supporting/opposing evidence;
- confidence;
- bounded normalized score;
- invalidation;
- provenance;
- source quality;
- coverage state;
- explicit research levels when mathematically valid.

The candidate builder must not use RSI/MACD/EMA or any single indicator as sole authority.

## Research Entry / Stop / Target levels

V3 adds numeric levels to ranked candidates.

For a valid LONG research candidate:

- `entryReference` uses current ask when a verified real-time executable quote is available; otherwise uses an explicitly labeled reference close and cannot be called executable;
- `stop` derives from validated structural invalidation below entry;
- `risk = entryReference - stop` must be positive;
- `target = entryReference + risk * selectedRR`.

For a valid SHORT research candidate:

- `entryReference` uses current bid when a verified real-time executable quote is available; otherwise uses an explicitly labeled reference close;
- `stop` derives from validated structural invalidation above entry;
- `risk = stop - entryReference` must be positive;
- `target = entryReference - risk * selectedRR`.

Default research RR is 2.0 unless an existing domain profile explicitly provides another bounded value.

Every level object must include:

- `entry`;
- `entrySemantic: EXECUTABLE_ASK|EXECUTABLE_BID|REFERENCE_CLOSE`;
- `stop`;
- `target`;
- `riskReward`;
- `invalidationBasis`;
- `researchOnly: true` for all outputs from multi-market autoscan.

No research level grants order-placement permission.

## Autoscan V3 API behavior

Keep `POST /research/autoscan` as the canonical gateway endpoint and evolve its capability contract rather than creating a competing endpoint.

V3 request remains compatible with V2:

- `intent`;
- optional `requestedDomains`;
- optional bounded `symbols`;
- optional `externalObservations`;
- optional `maxResults`.

V3 may additionally accept a validated `acquisitionContext` generated by the trusted orchestration layer. It must not accept raw credentials, API keys, order quantity, leverage, or execution directives.

The endpoint itself must never claim it called connector tools that only the outer orchestration layer can invoke.

Response adds:

- `capabilityVersion: 3`;
- `dataAcquisitionPlan`;
- `sourceCoverage`;
- `entitlementSummary`;
- `levels` on valid ranked candidates;
- existing `coverage`, `ranked`, `blocked`, `decision`, and `dataContract` fields.

## One-command orchestration contract

The GitHub Brain and skill capsule must interpret the following as autonomous live multi-market research when the relevant tools are available:

- `tìm lệnh`;
- `tìm lệnh tốt nhất`;
- `quét market`;
- `quét đa thị trường`;
- `quét toàn bộ thị trường`;
- `có setup nào không`;
- `find best trade`;
- `scan markets`.

Expected orchestration:

1. route once through `task_router` to `multi_market_analysis`;
2. load trading project authority/checkpoint;
3. resolve the approved market universe;
4. acquire gateway-native crypto evidence;
5. acquire approved connector evidence for non-crypto domains when available;
6. normalize evidence locally in the orchestration layer or through a pure normalization contract;
7. call the research autoscan/ranking path;
8. return the best supported setup or `NO_TRADE`.

If the connector is unavailable, the system must not ask the user to manually gather market data unless no automated source remains. It should continue covered domains and disclose gaps.

## Connector/Railway trust boundary

This boundary is mandatory and testable.

- Massive connector calls happen only through the authorized connector/tool plane.
- Railway never receives Massive credentials.
- Railway receives only normalized market observations and non-secret source metadata.
- Source/provider payloads must be reduced to fields required for research; unnecessary account/plugin metadata is discarded.
- No connector secret or authentication object may appear in logs, `dataContract`, provenance, tests, or fixtures.
- A connector being installed in ChatGPT does not imply that Railway can call it independently.

## TradingView integration

TradingView remains non-authoritative chart context.

V3 returns:

- verified symbol navigation when a verified mapping exists;
- symbol-search navigation when mapping is unverified;
- timeframe hint matching the research plan;
- Entry/Stop/Target values suitable for chart overlay by a presentation layer.

Do not scrape TradingView HTML, internal websocket traffic, private endpoints, or require a paid TradingView account.

A future Lightweight Charts UI may render Brain-owned data directly, but it is not required to make V3 data acquisition correct.

## Failure and fallback behavior

### Missing connector

Continue gateway-native domains. Mark uncovered non-crypto domains `GAP: CONNECTOR_UNAVAILABLE`.

### Provider entitlement is delayed

Preserve evidence as delayed context, but block `LIVE` candidate labeling from that source.

### Rate limit / temporary provider failure

Use another explicitly compatible source only if its symbol/semantic mapping is verified. Otherwise mark a coverage gap.

### Unknown/expired futures contract

Block that product candidate with `CONTRACT_UNRESOLVED` or `CONTRACT_EXPIRED`.

### Market closed

Return session-aware state. Do not mislabel the last valid close as live executable pricing.

### Semantic conflict

Block affected candidate or reduce to context-only according to current conflict policy. Never average incompatible semantics.

### All domains unavailable

Return `NO_TRADE` with explicit source/coverage reasons.

### Connector data conflicts with gateway data

Use same-semantic comparison only. Different instrument types, contract months, or quote semantics are not directly comparable.

### Execution fields supplied to autoscan

Reject with HTTP 400.

## Observability

V3 adds sanitized research telemetry:

- domain coverage count;
- source coverage count;
- verified real-time vs delayed vs unknown evidence counts;
- unresolved symbol/contract count;
- blocked candidate reasons;
- acquisition latency by source class;
- final `TOP_SETUP|NO_TRADE` decision;
- exact source SHA.

Telemetry must exclude connector credentials, raw private tool payloads, hidden reasoning, account identifiers, and secrets.

## Testing strategy

TDD is mandatory: RED -> minimal GREEN -> regression -> validators -> exact-head CI.

Required tests include:

1. source planner defaults to all six approved domains for broad scans;
2. gateway-native crypto plan uses current provider registry and remains research-only at autoscan level;
3. connector plan covers Forex/Futures/Indices when connector capability is available;
4. Metals/Commodities resolve through verified futures products/contracts;
5. no connector credential can enter the normalized observation schema;
6. connector unavailable produces coverage gaps without crashing covered domains;
7. delayed entitlement cannot authorize a live candidate;
8. unknown entitlement cannot authorize a live candidate;
9. future timestamps and invalid ingest/event ordering fail validation;
10. closed-session evidence is classified session-aware rather than blindly stale;
11. current-contract resolver rejects expired or unresolved futures contracts;
12. provider symbol mapping never guesses an unverified symbol;
13. V3 enforces domain-specific evidence requirements;
14. multi-timeframe confirmation is distinguished from single-timeframe bar count;
15. valid LONG levels produce positive risk and mathematically correct target;
16. valid SHORT levels produce positive risk and mathematically correct target;
17. verified ask/bid use correct entry semantics;
18. reference close is labeled non-executable;
19. stale/conflicting evidence blocks candidates;
20. ranking returns `TOP_SETUP` or `NO_TRADE` using existing ranking authority;
21. TradingView mapping remains verified/search-only as appropriate;
22. `/research/autoscan` rejects order/leverage/credential fields;
23. all non-BTC outputs remain research-only;
24. signed Bybit writer still rejects non-BTC order symbols;
25. all existing Brain/Model Mesh/Image Render/Bybit safety/gateway tests remain green;
26. production smoke verifies representative evidence for every domain that runtime tooling can actually access, and reports unsupported domains honestly rather than fabricating PASS.

## Implementation boundaries

Expected implementation areas:

- `crypto-research-gateway/src/intelligence/` for source planning, market universe, entitlement/freshness semantics, contract resolution, levels;
- `crypto-research-gateway/src/server.ts` for V3 autoscan contract;
- gateway tests for source planning/normalization/ranking/levels;
- `AI_SKILL_LIBRARY` skill/capsule contracts only where needed for one-command orchestration;
- deployment/runtime docs and smoke contracts;
- no signed execution expansion;
- no credential migration from connector plane to Railway.

Do not refactor unrelated systems.

## Delivery sequence

1. Lock this design spec on an isolated branch.
2. Write an implementation plan after written-spec approval.
3. Add RED tests for source plan, entitlement/freshness, universe/contract resolution, levels, and authority barriers.
4. Implement pure source/universe/normalization modules.
5. Extend autoscan to V3 without breaking V2-compatible request shapes.
6. Update Brain orchestration/capsule contract for one-command acquisition.
7. Run gateway/Brain/Bybit/full regression CI.
8. Merge only exact-head GREEN PR.
9. Deploy Railway from exact verified `main` SHA.
10. Deploy Cloudflare Skill Gateway if Brain/capsule files changed.
11. Verify exact SHA on both runtimes.
12. Run live read-only smoke across every actually entitled domain.
13. Promote a new known-good capability release only after production evidence is complete.

## Completion criteria

V3 is complete only when all of the following are true:

- one user command routes to `multi_market_analysis`;
- crypto evidence is acquired automatically from gateway-native sources;
- Forex/Futures/Indices evidence is acquired automatically through the approved connector plane when available;
- Metals/Commodities use verified current futures contracts and never permanent hard-coded expiries;
- every source is labeled real-time/delayed/unknown from evidence, not assumption;
- all six domains either have usable evidence or an explicit coverage gap;
- domain evidence profiles are enforced;
- ranked candidates include valid Entry/Stop/Target research levels when derivable;
- `NO_TRADE` is returned when evidence is insufficient or conflicting;
- TradingView remains presentation-only;
- non-BTC execution is blocked at every existing execution barrier;
- exact-head CI is green;
- Railway/Cloudflare exact-main verification passes where applicable;
- production smoke does not fabricate provider coverage;
- the new release is promoted only after production verification.
