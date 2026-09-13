# G9 Continuous Trading Intelligence — Design

Date: 2026-09-13
Status: APPROVED BY USER INTENT; IMPLEMENTATION FOLLOWS WITHOUT PER-STEP APPROVAL
Base: G8 Continuous BrainLoop + GITHUB_BRAIN_V4

## Objective

Create a cloud-first trading intelligence system that improves continuously without weakening execution authority. The system must update live market understanding every minute, continuously research better features/setups/models, harmonize validated improvements into the GitHub Brain, and ensure every future trading-analysis request uses the best validated knowledge available at that moment.

The system must optimize decision quality, not merely maximize in-sample win rate. It must fail closed when evidence is stale, conflicting, under-sampled, or statistically weak.

## Non-negotiable authority boundary

Production execution authority remains `BYBIT-BTC-STATEFLOW-2.1` and BTCUSDT Linear Perpetual on Bybit only. G9 may improve research evidence, market-reading skill, entry-analysis skill, feature libraries, candidate profiles and routing metadata, but may not silently expand live execution permissions, symbols, venues, leverage or account mutation.

Cloudflare Skill Gateway remains reasoning/routing authority. Railway remains live-price research authority until a separately verified migration. G9 adds minute-level learning services without collapsing these responsibilities into one plane.

## Architecture

Three planes operate at different speeds:

1. **Minute Intelligence Plane — Railway**
   - Runs every minute.
   - Collects/normalizes read-only market state.
   - Builds per-coin `MarketStateSnapshot` and `EntryContextSnapshot`.
   - Computes freshness, regime, structure, derivatives context, cross-asset context, flow quality and uncertainty.
   - Writes only research-safe state/evidence.
   - Never promotes strategy authority directly.

2. **Continuous Research Plane — G8/G9 BrainLoop**
   - Runs bounded research generations continuously/hourly.
   - Generates challengers across feature subsets, setup definitions, regime routing, calibration, model choices and risk geometry.
   - Uses purged walk-forward/CPCV, cost stress, falsification/null tests, evidence epochs and trial budgets.
   - Produces `RESEARCH_CHAMPION` and, only after fresh independent evidence, `CERTIFIED_RESEARCH` profiles.

3. **Stable Brain Plane — Cloudflare + GitHub Brain V4**
   - Serves current validated trading reasoning.
   - Consumes immutable promoted research manifests/snapshots.
   - Resolves exactly one primary trading skill/capsule for trading requests.
   - Uses the newest valid research evidence without mutating in-flight requests.
   - Supports instant rollback to the previous verified snapshot.

## Approaches considered

### A. Single self-modifying live model every minute
Rejected. Fastest adaptation but unacceptable overfit, unstable behavior and authority contamination.

### B. Hourly batch-only research
Safe but too slow for market-state adaptation and fails the user's requirement for minute-level intelligence.

### C. Dual-speed continuous intelligence (selected)
Minute-level state learning + slower statistically gated strategy promotion. This preserves responsiveness while preventing raw minute noise from rewriting the strategy authority.

## Minute Intelligence Plane

### Universe

Research universe remains the locked 10-core-coin set unless a future authority migration changes it:
`BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT, SOLUSDT, TRXUSDT, DOGEUSDT, LINKUSDT, ADAUSDT, XLMUSDT`.

### Snapshot contract

Each minute produces a deterministic JSON record containing at minimum:

- symbol
- venue/instrument semantics
- event_time / ingest_time / quote_age_ms
- price / best bid / best ask / spread
- OHLCV-derived causal state
- realized volatility / directional efficiency
- regime + regime confidence + transition probability
- market structure state
- liquidity/sweep/reclaim/break/retest descriptors
- taker-flow / trade-imbalance descriptors where available
- open-interest delta where available
- funding / mark-index premium / basis where available
- BTC/ETH cross-asset context
- relative strength / breadth context
- data-quality flags
- uncertainty
- provenance / source timestamps

A single indicator or single provider output may never authorize a trading conclusion.

### Freshness gates

- executable-quote target <= 2,000 ms
- > 5,000 ms fails closed for live-price claims
- stale derivative or order-flow fields degrade to `UNKNOWN`; they are never silently forward-filled as current
- venue/instrument semantics remain explicit

## Live Experience Memory

G9 records decision-relevant observations rather than hidden chain-of-thought. Allowed persistent fields include:

- market snapshot ID
- candidate setup IDs
- selected/no-trade action
- calibrated confidence and uncertainty
- reason codes
- future path labels generated only after the outcome horizon closes
- MFE/MAE
- RR2 TP/SL/timeout outcome
- regime transition outcome
- cost assumptions
- data-quality state

The store is append-only by default and versioned by schema. No private reasoning traces are stored.

## Trading skill decomposition

Canonical trading authority remains one reasoning chain, but the primary trading skill can consume bounded specialist evidence modules:

- `market_state_reader`
- `structure_reader`
- `flow_reader`
- `derivatives_reader`
- `cross_asset_reader`
- `entry_quality_estimator`
- `risk_geometry_reader`
- `uncertainty_reader`

These are evidence/capability modules, not parallel authorities and not majority-vote agents. The final decision remains in the canonical trading skill/router.

## Per-coin specialist profiles

Research profiles are keyed by:

`symbol × regime × setup_family × side`

Each profile records:

- feature contract
- model/calibration contract
- entry threshold
- uncertainty threshold
- RR geometry
- sample size
- OOF/CPCV metrics
- worst-fold metrics
- Wilson lower bound
- expectancy
- drawdown
- cost-stress metrics
- evidence epoch
- profile hash
- promotion status

Profiles do not become live execution authority automatically.

## Self-Discovery Research Controller

G9 extends G8 from parameter mutation to bounded hypothesis discovery.

Allowed hypothesis dimensions:

- causal feature composition
- structural sequence predicates
- regime transitions
- cross-asset relationships
- derivative/flow interactions
- setup filters
- model/calibration choice
- abstention thresholds
- stop/holding geometry within approved risk bounds

Every generated hypothesis must include provenance, parent hypothesis, changed dimensions and a stable content hash.

The controller uses failure memory to avoid repeatedly testing equivalent rejected hypotheses.

## Learning Supervisor

The supervisor diagnoses bottlenecks before allocating research budget. Example bottleneck classes:

- poor regime separation
- weak structural event quality
- high expert disagreement
- low calibration quality
- high false-breakout rate
- edge destroyed by costs
- weak cross-asset conditioning
- insufficient sample size
- unstable folds

Research budget is routed toward the diagnosed bottleneck instead of uniform random mutation.

## Promotion hierarchy

Statuses:

- `EXPERIMENT`
- `RESEARCH_CHALLENGER`
- `RESEARCH_CHAMPION`
- `CERTIFIED_RESEARCH`
- `STABLE_BRAIN_EVIDENCE`

Promotion requires all applicable gates:

- causal/no-lookahead audit
- purged walk-forward/CPCV
- minimum completed trades
- positive post-cost expectancy
- stability/worst-fold gate
- Wilson lower bound gate
- cost stress
- falsification/null tests
- multiple-testing/evidence-budget accounting
- fresh independent evidence when required
- no authority/security regression

A higher raw win rate alone is insufficient.

## Evidence epochs and anti-overfit

Repeated search on the same OOF evidence consumes an adaptive trial budget. When exhausted, research may continue in quarantine but cannot promote until a new evidence epoch or independently reserved evidence is available.

Final certification windows are one-shot and retired after use. Historical certification outcomes may inform aggregate reliability but may not be repeatedly optimized against.

## Brain harmonization

Every promoted capability passes existing V4 harmonization:

- normalize
- deduplicate
- conflict scan
- security/risk scan
- provenance/license check
- eval impact
- authority check
- validator check

Semantically equivalent discoveries strengthen the existing canonical trading skill/capsule rather than creating duplicate primary skills.

## Stable Brain Snapshot

Promotion emits an immutable manifest containing:

- source research commit
- research snapshot hash
- per-coin champion hashes
- schema version
- evidence epoch IDs
- metrics summary
- routing/capsule compatibility
- `research_only` flag where applicable
- `production_execution_authority: false` for G9 research evidence

Cloudflare consumes only validated immutable snapshots. Snapshot publication is atomic and rollback-safe.

## Railway minute service

A dedicated research worker/service runs an internal minute tick loop rather than relying on GitHub Actions for sub-hour scheduling.

Required behavior:

- single-leader lease/lock
- monotonic tick sequence
- skip overlapping ticks
- bounded per-tick runtime
- circuit breaker on upstream failure
- exponential backoff for provider errors
- per-source freshness logging
- no account/order write APIs
- health/readiness endpoints
- last successful tick metadata
- version/source SHA exposure

The minute loop may write snapshots and research observations only.

## Cloudflare responsibilities

Cloudflare continues to provide low-latency brain routing and may cache the latest validated research manifest/snapshot metadata. It must not become a raw self-modifying research engine. Stable route selection must remain exact-SHA/validated-snapshot based.

## User-query behavior

For requests such as `find the best entry now`, the trading flow becomes:

`request -> trading_router/DEEP -> current Stable trading capsule -> latest valid research evidence -> Railway live market snapshot/quote verification -> regime/structure/flow/cross-asset synthesis -> calibrated entry-quality/uncertainty -> risk geometry -> ranked candidate or NO_TRADE`.

The system must distinguish:

- model confidence
- historical OOS win rate
- live setup quality score

No score may be mislabeled as win probability without calibration/evidence.

## Observability

Expose at minimum:

- minute tick health
- last tick time
- market snapshot age
- source freshness by provider
- active research generation
- candidate counts
- champion changes
- rejected promotion reasons
- current evidence epoch
- trial budget remaining
- Stable Brain snapshot version/hash
- rollback target

## Failure behavior

- stale live data -> fail closed for live claim
- incomplete market snapshot -> degrade missing module to UNKNOWN
- conflicting high-consequence evidence -> block dependent conclusion
- failed promotion validator -> keep previous stable champion
- failed minute worker -> Stable Brain remains available from last verified evidence, with freshness clearly degraded
- Cloudflare routing failure -> last verified Stable release fallback where policy permits

## Security

G9 minute/research services are `RESEARCH_SAFE` only.
No order placement, cancel, amend, leverage changes, withdrawals, transfers, wallet signing or credential-sensitive write actions are added.

## Initial implementation scope

Phase 1 (this implementation cycle):

1. G9 schemas/state contracts.
2. Minute snapshot engine with deterministic causal feature/state computation from available public market inputs.
3. Live experience memory append-only storage interface.
4. Learning supervisor and bounded hypothesis factory.
5. Promotion manifest/harmonization adapter.
6. Railway minute-worker entrypoint + health endpoints.
7. Tests/validators/CI.
8. Wiring so trading analysis can resolve latest validated G9 evidence without granting execution authority.

Phase 2 (after real runtime verification): richer order-flow/derivatives/cross-asset feeds and stronger self-discovery search spaces.

## Acceptance criteria

- Minute worker can run repeatedly without overlapping ticks.
- Every snapshot has deterministic schema/provenance/freshness fields.
- Stale/partial data fails/degrades safely.
- Experience memory is append-only and outcome labels are not available before horizon closure.
- Learning supervisor deterministically classifies bottlenecks from metrics.
- Hypothesis factory avoids duplicate hashes and respects bounded mutation budgets.
- No candidate can bypass existing G8 validation/promotion gates.
- Published Brain evidence explicitly has no production execution authority.
- Existing G8 research tests/regression remain green.
- Existing V4 Brain/router/authority validators remain green.
- Railway runtime exposes source SHA and last-tick health.
- No production BTC StateFlow execution contract is weakened or silently replaced.
