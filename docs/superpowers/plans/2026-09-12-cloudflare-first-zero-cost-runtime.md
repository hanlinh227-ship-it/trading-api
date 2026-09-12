# Cloudflare-First Zero-Cost Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the validated read-only crypto research/execution-price runtime into the existing Cloudflare Worker, verify it live, transfer production authority from Railway to Cloudflare, then retire Railway.

**Architecture:** Keep `cloudflare-worker/index.js` as the existing production entry point and add a separate research route module that reuses `crypto-research-gateway/src/research.ts`. Make shared provider HTTP code Web-runtime compatible, reuse a warm `ResearchRuntime` with bounded health-probe TTL, never cache executable bid/ask, and preserve all existing trading/private routes. Deploy through the existing Cloudflare Builds authority and transfer checkpoint authority only after exact-revision production smoke succeeds.

**Tech Stack:** Cloudflare Workers/Wrangler 4, TypeScript/ES modules, Vitest, Node 22 for CI validation, GitHub Actions, GitHub Brain V4.

**Spec:** `docs/superpowers/specs/2026-09-12-cloudflare-first-zero-cost-runtime-design.md`

## Global Constraints
- Zero local runtime: no user Node/npm/Python/CLI/MCP requirement.
- Existing BTCUSDT Bybit strategy/private transport/state authority must remain unchanged.
- `HIGH_RISK` remains blocked and `AUTH_READ_ONLY` remains disabled.
- LONG=ask, SHORT=bid; no last/mark/index substitution; >5s stale fails closed; no cross-venue substitution.
- Cloudflare Builds remains deployment authority; GitHub Actions validates only.
- Do not retire Railway until exact-revision Cloudflare production smoke passes.

---

### Task 1: Make shared provider HTTP Web-runtime compatible

**Files:**
- Modify: `crypto-research-gateway/src/providers/http.ts`
- Modify: `crypto-research-gateway/test/http.test.ts`

**Interfaces:**
- Consumes: `fetchJson(url: string, timeoutMs?: number)`.
- Produces: the same interface without a Node `Buffer` runtime dependency.

- [ ] **Step 1: Add a failing regression test**

Add a test that temporarily sets `globalThis.Buffer` unavailable where possible and verifies a small JSON response is parsed while oversized UTF-8 text still throws `provider_response_too_large`.

- [ ] **Step 2: Run the focused test**

Run: `cd crypto-research-gateway && npm test -- --run test/http.test.ts`
Expected before implementation: failure caused by `Buffer.byteLength` dependency or the new compatibility assertion.

- [ ] **Step 3: Implement standards-based byte sizing**

Use:
```ts
const RESPONSE_ENCODER = new TextEncoder();
...
if (RESPONSE_ENCODER.encode(text).byteLength > MAX_RESPONSE_BYTES) {
  throw new Error('provider_response_too_large');
}
```
Keep timeout, redirects, JSON parsing, and HTTP status behavior unchanged.

- [ ] **Step 4: Re-run focused tests**

Run: `cd crypto-research-gateway && npm test -- --run test/http.test.ts`
Expected: PASS.

### Task 2: Add Cloudflare research HTTP adapter with warm health probing

**Files:**
- Create: `cloudflare-worker/research-gateway.js`
- Create: `cloudflare-worker/research-gateway.test.ts`
- Modify: `cloudflare-worker/package.json`

**Interfaces:**
- Produces: `handleResearchGateway(request, env): Promise<Response | null>`.
- Routes: `GET /health`, `GET /capabilities`, `POST /research/market`; returns `null` for unrelated paths.
- Imports: `ResearchRuntime` from `../crypto-research-gateway/src/research.ts`.

- [ ] **Step 1: Write route/validation tests**

Cover: unrelated route returns `null`; health identifies `cloudflare-workers`; capabilities are read-only; malformed JSON -> 400; unsupported action/instrument -> 400; `execution_quote` without side -> 400; a valid request reaches an injected/fake runtime path.

- [ ] **Step 2: Run focused test and confirm RED**

Run: `cd cloudflare-worker && npm test -- --run research-gateway.test.ts`
Expected: FAIL because module/test script does not exist yet.

- [ ] **Step 3: Implement adapter**

Create a module-scoped runtime and probe state:
```js
const runtime = new ResearchRuntime();
let probePromise = null;
let healthValidUntil = 0;
const HEALTH_TTL_MS = 30_000;

async function ensureHealth() {
  if (Date.now() < healthValidUntil && runtime.getLastProbeAt()) return;
  if (!probePromise) {
    probePromise = runtime.probeAll().finally(() => { probePromise = null; });
  }
  await probePromise;
  healthValidUntil = Date.now() + HEALTH_TTL_MS;
}
```
Validation must normalize symbols to uppercase, constrain `limit` to 1..500, allow instruments `spot|perpetual`, actions `snapshot|candles|orderbook|funding_oi|execution_quote`, sides `LONG|SHORT`, and execution venues `bybit|binance`.

Health response must include `deploymentSourceSha: String(env.RUNTIME_REVISION || '')`, `runtimeProvider: 'cloudflare-workers'`, and `localInstallRequired: false`.

- [ ] **Step 4: Add Vitest to Cloudflare validation package and run tests**

Add scripts:
```json
"test": "vitest run"
```
and dev dependency `vitest` compatible with the repository Node floor.
Run: `cd cloudflare-worker && npm test`.
Expected: PASS.

### Task 3: Wire Cloudflare entry point without disturbing trading routes

**Files:**
- Modify: `cloudflare-worker/index.js`
- Modify: `cloudflare-worker/research-gateway.test.ts`

**Interfaces:**
- `index.js` imports `handleResearchGateway` and calls it before existing monitor/health/control/auto-hub fallthrough.

- [ ] **Step 1: Add an integration assertion**

Test that `/research/market` is claimed by the research adapter while a representative existing trading route remains unclaimed by the adapter and therefore available to existing handlers.

- [ ] **Step 2: Confirm RED**

Run: `cd cloudflare-worker && npm test`.
Expected: new entry integration assertion fails before wiring.

- [ ] **Step 3: Add minimal entry delegation**

At the start of `fetch` after URL construction or before existing module handlers:
```js
const research = await handleResearchGateway(req, env);
if (research) return research;
```
Do not reorder or change existing trading handler internals beyond this bounded delegation.

- [ ] **Step 4: Run Cloudflare tests and Wrangler dry-run**

Run:
```bash
cd cloudflare-worker
npm test
npm run check
```
Expected: PASS and Wrangler successfully bundles sibling TypeScript research modules.

### Task 4: Strengthen CI for pull requests and shared runtime regression

**Files:**
- Modify: `.github/workflows/deploy-cloudflare-worker.yml`
- Modify if needed: `.github/workflows/zero-local-cloud-runtime.yml`

**Interfaces:**
- Cloudflare workflow remains validate-only, never deploys or changes runtime variables.

- [ ] **Step 1: Add PR trigger and research-runtime validation commands**

Trigger on `pull_request` for `cloudflare-worker/**`, `crypto-research-gateway/**`, relevant runtime policy files, and this workflow. Validation runs `npm ci`/tests/build for `crypto-research-gateway`, then `npm ci`/test/check for `cloudflare-worker`.

- [ ] **Step 2: Preserve deployment authority message**

CI output must still state Cloudflare Builds is sole Worker deployment authority and `BYBIT_BTC_LIVE_ACK` is never forced.

- [ ] **Step 3: Validate workflow syntax and repository validators**

Run the repository's existing Brain/registry/router/V4/authority/zero-local validation suite through CI.

### Task 5: Gate A PR, merge, and live Cloudflare verification

**Files:** all Gate A code/test/workflow/spec/plan changes.

- [ ] **Step 1: Open PR from `cloudflare-first-zero-cost-runtime` to `main`**

PR must state that Railway remains production authority until live Cloudflare verification completes.

- [ ] **Step 2: Require green CI and review diff**

Verify no trading state keys, live switches, private credentials, or HIGH_RISK routes changed.

- [ ] **Step 3: Merge Gate A**

Merge only after tests/checks pass.

- [ ] **Step 4: Verify Cloudflare Builds deployed exact merged revision**

Call the existing Worker `/health`; require `runtimeProvider=cloudflare-workers` and `deploymentSourceSha` equal the merged `main` SHA.

- [ ] **Step 5: Run live production smoke**

Require:
- `/health` 200 and zero-local/read-only markers.
- `/capabilities` exposes only approved read-only capabilities.
- Bybit BTCUSDT perpetual LONG returns ask semantic and fresh verified execution quote.
- Bybit SOLUSDT perpetual SHORT returns bid semantic and fresh verified execution quote.
- Binance BTCUSDT perpetual LONG returns ask semantic when Binance is reachable; region restriction must be explicit rather than substituted.
- existing `/runtime/contract` and `/bybit/health` remain healthy/unchanged.

If any item fails, stop before Task 6 and keep Railway canonical.

### Task 6: Transfer GitHub Brain runtime authority to Cloudflare

**Files:**
- Modify: `AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml`
- Modify: `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md`
- Modify: `AGENTS.md` only if deployment wording requires it.
- Modify: `.github/workflows/zero-local-cloud-runtime.yml`

**Interfaces:**
- `runtime: cloudflare_workers`
- production deployment source stays GitHub `main` through Cloudflare Builds.
- exact source field is Cloudflare `RUNTIME_REVISION`/health `deploymentSourceSha`.
- Railway becomes `retired_runtime`/rollback history, not a required health gate.

- [ ] **Step 1: Update runtime manifest and checkpoint**

Record Cloudflare as production; remove Railway-success requirement from current production verification; preserve live execution smoke and exact-SHA requirements.

- [ ] **Step 2: Update zero-local production smoke contract**

Point production health/capabilities/execution smoke at the verified Cloudflare endpoint and validate exact source SHA.

- [ ] **Step 3: Run all validators/tests on the authority-transfer branch**

Require Brain V4, registry, router, authority, live-price policy, Cloudflare bundle, gateway tests/typecheck/build all green.

- [ ] **Step 4: Open/merge the authority-transfer PR**

Merge only with live Cloudflare evidence from Task 5.

- [ ] **Step 5: Re-run post-merge Cloudflare exact-revision smoke**

The live Worker SHA and GitHub `main` must match the authority-transfer commit or the deployment revision Cloudflare reports for that exact code release.

### Task 7: Retire Railway and finalize handoff

**Files:**
- Modify if required: `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` / runtime history notes only if actual retirement metadata differs from Task 6.

- [ ] **Step 1: Stop/remove the Railway production service through the connected Railway control plane**

Do not remove it before Cloudflare authority and live smoke are verified. Prefer stopping/deactivating the service while preserving project history if the platform supports that without ongoing compute cost.

- [ ] **Step 2: Confirm no production contract still requires Railway**

Search canonical runtime/checkpoint/workflow files for production Railway dependencies. Historical docs may retain Railway history but must not be current authority.

- [ ] **Step 3: Final verification**

Collect fresh evidence for:
- GitHub `main` SHA;
- Cloudflare runtime revision/source SHA;
- `/health` and `/capabilities`;
- live venue-bound execution quote smoke;
- existing trading runtime contract/Bybit readonly health;
- all relevant CI conclusions;
- Railway stopped/retired state.

- [ ] **Step 4: Final handoff**

Report exactly what is production, what is retired, what remains blocked by design, and the zero-cost/zero-local operating model. Do not claim unlimited free usage; state that operation remains subject to Cloudflare free-tier limits and future provider policy changes.
