# Cloudflare-First Zero-Cost Runtime Design

## Status
Approved for implementation by the user on 2026-09-12.

## Goal
Move the public read-only crypto research/execution-price runtime from Railway-first to Cloudflare-first without changing trading authority, private Bybit safety controls, execution-price semantics, or the zero-local requirement. The migration must preserve a verified rollback path until Cloudflare has passed production smoke tests, then retire Railway as a required production dependency.

## Non-goals
- Do not enable order placement, cancellation, leverage changes, wallet actions, transfers, withdrawals, swaps, bridges, or any HIGH_RISK capability.
- Do not change the BTCUSDT Bybit production strategy authority.
- Do not change `BYBIT_AUTO_LIVE`, `BYBIT_BTC_LIVE_ACK`, account credentials, or BTC state KV keys.
- Do not introduce D1, Durable Objects, paid queues, or other billable Cloudflare resources for this migration.
- Do not create a second Cloudflare application that requires new manual deployment configuration when the existing `trading-v77-scanner` Worker can host the read-only gateway surface safely.

## Current State
- GitHub `main` is the canonical source of truth.
- `cloudflare-worker/` is already the production Cloudflare Worker and is deployed by Cloudflare Builds. GitHub Actions validates it but is not deployment authority.
- `crypto-research-gateway/` contains the validated read-only provider, routing, normalization, and venue-bound execution-quote logic currently served by Railway.
- `AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml` and `AI_GLOBAL_CHECKPOINT.md` currently declare Railway production authority.
- The existing Cloudflare Worker preserves private Bybit/VPS bindings and runtime switches through generated Wrangler configuration.

## Architecture

### 1. One Cloudflare Worker, modular routes
The existing `cloudflare-worker/index.js` remains the Cloudflare entry point and trading front door. A new focused module `cloudflare-worker/research-gateway.js` owns only the read-only research HTTP surface. `index.js` delegates `/health`, `/capabilities`, and `/research/market` to that module before falling through to existing trading routes.

The research module imports the platform-neutral `ResearchRuntime` from `crypto-research-gateway/src/research.ts`. This avoids duplicating provider, normalization, execution-price, freshness, divergence, and venue-selection semantics.

### 2. Web-runtime compatibility
Shared provider HTTP utilities must run in both Node 22 and Cloudflare Workers. Node-only byte counting (`Buffer.byteLength`) is replaced with standards-based `TextEncoder` sizing. No Node process, filesystem, child process, socket server, or local CLI is used by request handling.

### 3. Warm health state without stale execution prices
A module-scoped `ResearchRuntime` is reused within a Cloudflare isolate. Provider health probes are cached for a short TTL and deduplicated with a single in-flight probe promise. A request ensures health is initialized before provider routing.

Health caching never caches executable bid/ask. Every `execution_quote` request still performs a fresh provider snapshot and applies the existing freshness, spread, semantic, instrument, and cross-venue divergence rules.

### 4. HTTP surface
Cloudflare exposes only the read-only surfaces needed by the current runtime:
- `GET /health`
- `GET /capabilities`
- `POST /research/market`

The Cloudflare `/health` response includes:
- `ok`
- `service = crypto-research-gateway`
- `runtimeMode = zero-local-research-safe`
- `runtimeProvider = cloudflare-workers`
- `deploymentRelease = live-price-execution-v1`
- `deploymentSourceSha` from `RUNTIME_REVISION`
- `localInstallRequired = false`
- provider health and last probe metadata

`/capabilities` remains read-only and includes the same market capabilities as the Railway gateway. Unsupported token/news/risk routes are not advertised as executable capabilities.

`POST /research/market` validates the same semantic constraints as the Node server: supported action/instrument, side required for `execution_quote`, bounded limit, normalized symbol, and explicit execution venue when supplied. Validation failure is 400; provider/runtime degradation remains fail-closed.

### 5. Trading isolation
Existing trading/private routes continue to execute through their current modules and bindings. Research routes do not receive or use private Bybit credentials, trading state KV, or VPC private signing authority. No migration code mutates trading state.

### 6. Deployment and source verification
`cloudflare-worker/prepare-wrangler.mjs` continues to generate deployment config and preserve runtime switches. `RUNTIME_REVISION` remains the exact GitHub/Cloudflare source revision marker exposed by health.

Cloudflare Builds stays the sole Cloudflare deployment authority. GitHub Actions gains pull-request validation for the Cloudflare bundle and shared research tests, but it must not deploy or alter Worker runtime variables.

### 7. Migration gates
#### Gate A — capability deployment
1. Add the Cloudflare research surface and web-runtime compatibility.
2. Run unit/regression tests, TypeScript build, Wrangler dry-run, Brain validators, and zero-local policy checks.
3. Merge to `main` through PR.
4. Wait for the existing Cloudflare Builds deployment of the merged revision.
5. Verify the live Worker reports that exact `RUNTIME_REVISION`.
6. Verify `/health`, `/capabilities`, and live Bybit/Binance venue-bound execution quotes from Cloudflare.

Railway remains unchanged during Gate A.

#### Gate B — authority transfer
Only after Gate A passes:
1. Change `cloud_runtime.yaml` to `runtime: cloudflare_workers` and make Railway a retired/non-required rollback record rather than production authority.
2. Update `AI_GLOBAL_CHECKPOINT.md` and relevant zero-local CI/smoke contracts to Cloudflare production verification.
3. Merge the authority-transfer PR.
4. Verify GitHub main, Cloudflare runtime revision, read-only capabilities, and live quote smoke again.
5. Stop/remove the Railway production service only after Cloudflare authority is confirmed.

### 8. Failure and rollback
- If Cloudflare source validation fails, do not merge Gate A.
- If the merged Cloudflare deployment does not expose the expected revision or live execution smoke fails, do not change authority; Railway remains production.
- If Gate B has not completed, the existing Railway runtime remains canonical.
- After Gate B, a future rollback must be an explicit checkpoint/runtime-manifest change; no silent provider/runtime substitution is allowed.

## Execution-price invariants
The migration must preserve all current `live-price-execution-v1` invariants:
- default production execution venue: Bybit unless explicitly selected otherwise;
- LONG executable price = venue ask;
- SHORT executable price = venue bid;
- `last`, `mark`, `index`, and midpoint are context only;
- perpetual and spot observations never mix;
- source timestamps are mandatory;
- target executable quote freshness <= 2,000 ms;
- quote age > 5,000 ms fails closed;
- same-semantic cross-venue divergence above configured threshold fails closed;
- another venue may cross-check but may not silently substitute for the selected execution venue.

## Cost boundary
The target runtime uses the already-existing Cloudflare Worker and existing bindings. It adds no new mandatory paid infrastructure. Railway remains only during the bounded verification window and is retired after Gate B.

## Test strategy
- Unit test web-compatible response byte sizing and provider HTTP behavior.
- Unit test Cloudflare route validation and execution-quote side/venue semantics using injected/fake runtime behavior.
- Regression test existing `crypto-research-gateway` suite.
- Wrangler dry-run must bundle `cloudflare-worker/index.js` with the shared TypeScript research runtime.
- Existing Brain V4, authority, runtime, registry, zero-local, and live-price policy validators remain green.
- Production smoke must prove exact source revision plus live Bybit and Binance venue-bound perpetual quotes before runtime authority is transferred.

## Acceptance criteria
The migration is complete only when:
1. Cloudflare serves the read-only research gateway from the exact merged GitHub revision.
2. Cloudflare live `/health` and `/capabilities` pass.
3. Bybit and Binance perpetual LONG/SHORT execution quote smoke passes current freshness/semantic gates.
4. Existing trading/private Cloudflare routes remain healthy and their authority/state are unchanged.
5. GitHub CI and Cloudflare validation are green.
6. `cloud_runtime.yaml` and `AI_GLOBAL_CHECKPOINT.md` name Cloudflare Workers as production runtime.
7. Railway is no longer a required production dependency and has been stopped/retired after verification.
8. No local installation or user PC runtime is required.
