# Live-Price Execution Layer Design

Date: 2026-09-12
Status: Approved in chat, written-spec review pending
Repository: `hanlinh227-ship-it/trading-api`
Branch: `live-price-execution-layer-20260912`

## Goal

Make future crypto market scans use the freshest venue-correct execution quote possible, with Bybit and Binance handled as first-class live sources and with fail-closed freshness/semantic/divergence gates. The design must prevent confusing Spot with Perpetual, Last with Bid/Ask, or Mark/Index with executable market-entry prices.

## Existing authority that must not change

- `docs/checkpoints/CURRENT_HANDOFF.md` remains the single production trading authority.
- Current production strategy authority remains BTCUSDT Bybit Linear Perpetual.
- Bybit WebSocket microstructure collector remains preferred where available; REST remains fail-safe/fallback.
- No live-order permission is added by this change.
- Provider output remains evidence only and never becomes reasoning authority.
- Zero-local execution remains mandatory for normal research.

## Chosen approach

Use a venue-bound execution-quote layer rather than a single global provider order.

1. Resolve canonical symbol and instrument first.
2. Resolve execution venue.
3. Fetch venue-native executable quote semantics.
4. Normalize bid, ask, last, mark, index and timestamps.
5. Compute freshness and spread.
6. Apply freshness and semantic gates.
7. Cross-check against one or more secondary venues using only equivalent semantics.
8. Produce one explicit `executionQuote` object, or fail closed.

When the request is for the current production trading route and no venue is explicitly supplied, Bybit Linear is the default execution venue. If a request explicitly targets Binance, Binance USD-M becomes the execution venue. Secondary venues may confirm or warn, but must never silently replace the requested venue's execution price.

## Execution quote contract

The runtime must expose a normalized execution quote with these fields:

```ts
type ExecutionQuote = {
  venue: 'bybit' | 'binance' | string;
  symbol: string;
  instrumentType: 'perpetual' | 'spot';
  side: 'LONG' | 'SHORT';
  executableSemantic: 'ask' | 'bid';
  executablePrice: number;
  bid: number;
  ask: number;
  mid: number;
  last?: number;
  mark?: number;
  index?: number;
  sourceTimestampMs: number;
  receivedTimestampMs: number;
  quoteAgeMs: number;
  spreadBps: number;
  fresh: boolean;
  executionVerified: boolean;
  status: 'OK' | 'STALE_PRICE' | 'PRICE_DIVERGENCE' | 'SEMANTIC_MISMATCH' | 'VENUE_UNAVAILABLE';
  crossVenue?: Array<{
    venue: string;
    semantic: 'bid' | 'ask' | 'last' | 'mark' | 'index' | 'mid';
    price: number;
    sourceTimestampMs: number;
    quoteAgeMs: number;
    deviationBps: number;
  }>;
};
```

## Execution semantics

- MARKET LONG must use the execution venue's current **ask** as the fill estimate.
- MARKET SHORT must use the execution venue's current **bid** as the fill estimate.
- `last` is informational and must never be substituted for bid/ask execution semantics.
- `mark` is for derivatives risk/liquidation/funding context only.
- `index` is for reference/divergence context only.
- `mid` may be used for spread/context, never as the claimed market-entry fill.

## Venue-specific data acquisition

### Bybit Linear

For perpetual execution quotes, use Bybit V5 `category=linear` ticker semantics and orderbook as required.

Required ticker fields when available:
- `bid1Price`
- `ask1Price`
- `lastPrice`
- `markPrice`
- `indexPrice`
- source `time`

If the Bybit ticker response lacks executable bid/ask or those values are non-positive, the quote is not execution-verified. The runtime may consult orderbook top-of-book as a same-venue fallback, but must not substitute Binance execution prices for a Bybit trade.

### Binance USD-M

For perpetual execution quotes:
- use USD-M `bookTicker` for bid/ask and its own event/source time;
- use ticker price only for `last`;
- use premium index only for `mark` and `index`.

Do not reuse premium-index timestamp for the Binance execution bid/ask or last observation. Each observation must carry the timestamp of the endpoint that produced that semantic.

## Freshness policy

Freshness is computed as:

```text
quoteAgeMs = max(0, receivedTimestampMs - sourceTimestampMs)
```

The implementation must support explicit thresholds in runtime policy rather than burying them in provider code. Initial defaults:

- executable bid/ask freshness target: <= 2,000 ms
- hard stale threshold for execution bid/ask: > 5,000 ms
- contextual mark/index tolerance: <= 10,000 ms
- if provider source time is unavailable or clearly invalid, execution must fail closed rather than pretending data is live

The policy may distinguish WebSocket and REST later, but this change must work correctly with current REST gateway paths.

## Spread policy

Compute:

```text
mid = (bid + ask) / 2
spreadBps = ((ask - bid) / mid) * 10_000
```

Reject invalid books where:
- `bid <= 0`
- `ask <= 0`
- `ask < bid`
- spread is non-finite

Spread alone does not authorize a trade. It is execution-quality evidence.

## Cross-venue divergence policy

Cross-venue comparison is allowed only when all of the following match:
- canonical symbol
- instrument type
- quote currency
- price semantic
- materially comparable timestamp window

For a LONG execution quote, compare execution venue `ask` primarily against secondary venue `ask`. For SHORT, compare `bid` against `bid`. Do not compare Bybit bid against Binance mark, or Perpetual against Spot.

Initial material divergence threshold: 30 bps unless the existing conflict policy or project authority defines a stricter threshold for a specific route.

If material divergence remains unresolved:
- return `PRICE_DIVERGENCE`;
- set `executionVerified=false`;
- do not issue a MARKET entry recommendation that depends on the disputed price.

No majority vote and no silent averaging are allowed.

## Venue selection policy

The current generic provider order must not be used to choose an execution price.

Rules:
- explicit `executionVenue=bybit` -> Bybit is source-of-truth for executable price;
- explicit `executionVenue=binance` -> Binance is source-of-truth;
- production trading route with no venue supplied -> Bybit Linear by current authority;
- other research-only requests may retain generic provider routing, but an execution quote must always be venue-bound.

If the execution venue is unavailable or region-restricted, return `VENUE_UNAVAILABLE`/degraded state. A secondary venue may be shown as reference data but must not be mislabeled as the requested execution price.

## Runtime/API changes

Extend the gateway request model with an execution-quote action or equivalent dedicated path that accepts:
- `symbol`
- `instrument`
- `side`
- optional `executionVenue`

The response must include the normalized `executionQuote` contract above.

Existing research actions (`snapshot`, `candles`, `orderbook`, `funding_oi`) remain backward-compatible.

## Normalization changes

`MarketObservation` already supports `bid`, `ask`, `mid`, `last`, `mark`, and `index`; provider adapters must begin emitting bid/ask where available.

Add helpers to:
- group only semantically equivalent observations;
- compute quote age;
- compute spread;
- choose executable semantic from side;
- validate required execution semantics;
- cross-check same-semantic secondary venue observations.

## Provider changes

### `crypto-research-gateway/src/providers/bybit.ts`
- emit `bid` and `ask` from `bid1Price`/`ask1Price` for ticker snapshots;
- preserve Bybit response time for all ticker-derived observations;
- retain last/mark/index as distinct semantics;
- retain region restriction behavior.

### `crypto-research-gateway/src/providers/binance.ts`
- fetch USD-M `bookTicker` for perpetual bid/ask;
- carry its own execution timestamp;
- retain ticker price as `last` with its own timestamp;
- retain premium index as mark/index with premium-index timestamp;
- never assign one shared premium timestamp to all perpetual semantics.

## Routing changes

Keep generic research provider routing for non-execution research.

Add a separate execution-venue resolver so the source-of-truth is selected by venue policy rather than generic provider ranking. Generic provider fallback must not override venue-bound execution semantics.

## Policy/config changes

Add explicit live-price policy to checkpoint-resolved runtime configuration, including:
- default production execution venue: Bybit
- instrument: Linear Perpetual for current trading authority
- executable freshness target/hard limit
- contextual freshness limit
- divergence tolerance bps
- fail-closed behavior
- no silent cross-venue substitution

The exact configuration file may be a focused new `live_price_policy.yaml` referenced by `checkpoint.json`, or an isolated section in the existing runtime policy if that keeps validation simpler. Prefer a dedicated file if it makes the contract easier to test and reason about.

## Test-first requirements

Implementation must follow RED -> minimum GREEN -> regression suite.

Required test coverage:

1. Bybit perpetual snapshot emits bid, ask, last, mark, index with correct semantics.
2. Binance perpetual snapshot emits bid/ask from bookTicker with their own timestamp, last with its own timestamp, mark/index with premium timestamp.
3. LONG execution chooses ask, never last/mid/mark.
4. SHORT execution chooses bid, never last/mid/mark.
5. Stale executable quote returns `STALE_PRICE` and cannot be execution-verified.
6. Missing or invalid source timestamp fails closed.
7. Spot/Perpetual mismatch returns semantic conflict.
8. Bid/ask compared across venues only against the same semantic.
9. Cross-venue divergence above tolerance returns `PRICE_DIVERGENCE`.
10. Requested Bybit execution cannot silently fall back to Binance executable price.
11. Bybit region restriction returns explicit degraded/venue-unavailable state.
12. Existing research endpoints remain backward-compatible.
13. Existing HIGH_RISK restrictions remain unchanged.

## Live smoke verification

Before merge, CI/runtime smoke should query public first-party endpoints for BTCUSDT/SOLUSDT and validate:
- source timestamps are parseable and fresh enough for the test environment;
- bid <= ask;
- bid/ask/last are positive;
- mark/index are positive for perpetuals;
- Bybit region restriction is classified explicitly if the CI region is blocked;
- Binance live public endpoints work;
- divergence comparison never mixes semantics.

A CI environment blocked by Bybit policy may pass only if it returns the explicit known `region_restricted_bybit_cloud_region` classification. No proxy or geo-bypass is permitted.

## CI and deployment acceptance

Before merge to `main`:
- gateway unit tests green;
- TypeScript typecheck green;
- build green;
- registry validator green;
- Brain/V4/router/authority validators green;
- live smoke green or explicit Bybit region-restricted classification;
- PR head SHA exact checks green.

After merge:
- Railway deploy from canonical `main` succeeds;
- `/health` passes;
- execution-quote path responds correctly;
- canonical post-merge GitHub workflows pass.

## Security and permissions

- No new API keys are required for public price acquisition.
- No credential or secret is committed to GitHub.
- `RESEARCH_SAFE` remains read-only.
- `AUTH_READ_ONLY` remains separately gated.
- `HIGH_RISK` remains non-executable in the zero-local gateway.
- No order placement, cancellation, transfer, withdrawal, wallet signing, swap, bridge, or payment capability is introduced.

## Success criteria

The feature is complete only when future market-entry analysis can obtain a venue-bound execution quote that explicitly states bid, ask, executable price, source/receive timestamps, quote age, spread, venue, instrument and verification status; and when stale, semantically mismatched, cross-venue-divergent or unavailable execution quotes fail closed instead of being presented as a live market entry.
