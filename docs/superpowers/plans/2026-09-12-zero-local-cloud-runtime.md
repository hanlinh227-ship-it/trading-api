# Zero-Local Cloud Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a GitHub-controlled, Railway-hosted read-only crypto research gateway so normal crypto skill execution requires no installation on the user's computer.

**Architecture:** GitHub Brain remains the canonical control plane. `task_router` selects canonical reasoning skills, then the checkpoint-resolved provider registry selects at most three RESEARCH_SAFE evidence providers. A Node.js 22 TypeScript service on Railway calls public first-party HTTPS endpoints, normalizes evidence, exposes read-only HTTP + Streamable HTTP MCP surfaces, and rejects HIGH_RISK capabilities before provider dispatch.

**Tech Stack:** Node.js 22, TypeScript, Fastify, Zod, Vitest, `@modelcontextprotocol/sdk`, native `fetch`, GitHub Actions, Railway.

**Spec:** `docs/superpowers/specs/2026-09-12-zero-local-cloud-runtime-design.md`

## Global Constraints

- Node.js runtime is 22.x.
- No normal research workflow may require local Node/npm/Python/MCP/CLI installation.
- GitHub is the routing/configuration source of truth; Railway is execution only.
- Provider adapters execute only `RESEARCH_SAFE` capabilities in this project.
- `AUTH_READ_ONLY` stays registered but disabled until separate explicit authorization.
- `HIGH_RISK` never has an executable adapter or MCP tool.
- No API keys, secrets, wallet credentials, OAuth tokens, private keys, or seed phrases enter GitHub.
- Provider output is evidence, never independent reasoning authority.
- Existing `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml` remains the conflict authority.
- Existing immutable hash-pinned V4 Stable release files are not edited directly.
- Unknown or semantically incompatible data fails closed; no silent averaging and no fabricated freshness.

---

### Task 1: Cloud-runtime Brain policy contract

**Files:**
- Create: `AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml`
- Create: `AI_SKILL_LIBRARY/skills/registry/runtime_policy.yaml`
- Create: `tests/test_cloud_runtime_policy.py`
- Modify: `AI_SKILL_LIBRARY/checkpoint.json`
- Modify: `AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: existing checkpoint pointers and crypto provider modes.
- Produces: `cloud_runtime_policy_path`, `cloud_runtime_manifest_path`, and per-capability `cloud_execution`/`runtime_target` metadata.

- [ ] **Step 1: Write failing policy regression tests**

Create tests asserting:
```python
assert runtime_policy["local_install_required"] is False
assert runtime_policy["local_cli_execution"] is False
assert runtime_policy["local_mcp_server_required"] is False
assert runtime_policy["cloud_runtime_required_for_provider_execution"] is True
assert all(not cap.get("cloud_execution", False) for cap in high_risk_caps)
assert all(cap.get("runtime_target") in {"cloud_gateway", "none"} for cap in capabilities)
```
Also assert checkpoint paths exist and AGENTS bootstrap resolves them instead of asking for local installation.

- [ ] **Step 2: Run test and confirm RED**

Run:
```bash
python -m unittest discover -s tests -p 'test_cloud_runtime_policy.py' -v
```
Expected: FAIL because cloud runtime policy/pointers do not yet exist.

- [ ] **Step 3: Add cloud policy files and registry metadata**

`AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml` must declare:
```yaml
version: 1
runtime: railway
node_major: 22
local_install_required: false
local_cli_execution: false
local_mcp_server_required: false
cloud_runtime_required_for_provider_execution: true
default_execution_mode: research_safe_only
high_risk_cloud_execution: false
auth_read_only_default_enabled: false
health_path: /health
capabilities_path: /capabilities
mcp_path: /mcp
```

`AI_SKILL_LIBRARY/skills/registry/runtime_policy.yaml` must declare precedence:
`connected_cloud_tool -> public_first_party_https -> approved_remote_read_only_mcp -> degraded_failure` and explicitly forbid a local-install fallback.

Add to checkpoint:
```json
"cloud_runtime_policy_path": "AI_SKILL_LIBRARY/skills/registry/runtime_policy.yaml",
"cloud_runtime_manifest_path": "AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml"
```

For each capability in `crypto_agents.yaml`:
- `RESEARCH_SAFE`: `runtime_target: cloud_gateway`, `cloud_execution: true` only when implemented by the gateway.
- `AUTH_READ_ONLY`: `runtime_target: cloud_gateway`, `cloud_execution: false`.
- `HIGH_RISK`: `runtime_target: none`, `cloud_execution: false`.

- [ ] **Step 4: Run policy test and existing Brain validators**

Run:
```bash
python -m unittest discover -s tests -p 'test_cloud_runtime_policy.py' -v
python AI_SKILL_LIBRARY/validate_skill_registry.py
python AI_SKILL_LIBRARY/validate_brain.py
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_v4.py
python AI_SKILL_LIBRARY/validate_authority.py
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AI_SKILL_LIBRARY AGENTS.md tests/test_cloud_runtime_policy.py
git commit -m "feat: define zero-local cloud runtime policy"
```

---

### Task 2: Gateway policy core and build scaffold

**Files:**
- Create: `crypto-research-gateway/package.json`
- Create: `crypto-research-gateway/package-lock.json`
- Create: `crypto-research-gateway/tsconfig.json`
- Create: `crypto-research-gateway/src/types.ts`
- Create: `crypto-research-gateway/src/policy/capability-policy.ts`
- Create: `crypto-research-gateway/test/policy.test.ts`

**Interfaces:**
- Produces:
```ts
export type CapabilityMode = 'RESEARCH_SAFE' | 'AUTH_READ_ONLY' | 'HIGH_RISK';
export type CapabilityDecision = { allowed: boolean; reason: string };
export function authorizeCapability(id: string, mode: CapabilityMode): CapabilityDecision;
```

- [ ] **Step 1: Write failing Vitest policy tests**

Tests must assert RESEARCH_SAFE is allowed, AUTH_READ_ONLY is denied by default, HIGH_RISK is denied, and unknown modes fail closed.

- [ ] **Step 2: Run and confirm RED**

Run:
```bash
cd crypto-research-gateway
npm ci
npm test -- --run test/policy.test.ts
```
Expected: FAIL because implementation is absent.

- [ ] **Step 3: Implement minimal policy core**

`authorizeCapability()` returns allowed only for `RESEARCH_SAFE`; all other states return explicit denial reasons. No environment variable may override HIGH_RISK.

`package.json` scripts:
```json
{
  "build": "tsc -p tsconfig.json",
  "typecheck": "tsc -p tsconfig.json --noEmit",
  "test": "vitest",
  "start": "node dist/server.js"
}
```
Dependencies: Fastify, Zod, `@modelcontextprotocol/sdk`; dev dependencies: TypeScript, Vitest, `@types/node`.

- [ ] **Step 4: Run tests/typecheck**

```bash
npm test -- --run test/policy.test.ts
npm run typecheck
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway
git commit -m "feat: scaffold read-only crypto research gateway"
```

---

### Task 3: Provider-neutral market model and normalization

**Files:**
- Create: `crypto-research-gateway/src/normalization/market-normalizer.ts`
- Create: `crypto-research-gateway/src/normalization/conflict-resolver.ts`
- Create: `crypto-research-gateway/test/normalization.test.ts`

**Interfaces:**
```ts
export type InstrumentType = 'spot' | 'perpetual' | 'delivery_futures' | 'index';
export type PriceSemantic = 'last' | 'mark' | 'index' | 'bid' | 'ask' | 'mid';
export type MarketObservation = {
  provider: string;
  venue: string;
  symbol: string;
  instrumentType: InstrumentType;
  quoteCurrency: string;
  priceSemantic: PriceSemantic;
  price: number;
  sourceTimestampMs: number;
  receivedTimestampMs: number;
};
export function normalizeObservation(input: unknown): MarketObservation;
export function resolveObservations(items: MarketObservation[]): { status: 'ok' | 'conflict'; observations: MarketObservation[]; reason?: string };
```

- [ ] **Step 1: Write failing normalization tests**

Assert spot/perpetual cannot collapse into one price; last/mark cannot silently merge; equal-semantics observations retain provider identity; materially divergent equivalent observations return `conflict`.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/normalization.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Implement normalization/conflict rules**

Use strict Zod schemas. Preserve raw provider timestamps. Do not calculate an average price. Define material divergence as configurable basis-points threshold used only for equivalent semantics; default `PRICE_DIVERGENCE_BPS=30`.

- [ ] **Step 4: Run GREEN**

```bash
npm test -- --run test/normalization.test.ts
npm run typecheck
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/normalization crypto-research-gateway/test/normalization.test.ts
git commit -m "feat: normalize and reconcile provider market evidence"
```

---

### Task 4: Public first-party provider adapters

**Files:**
- Create: `crypto-research-gateway/src/providers/types.ts`
- Create: `crypto-research-gateway/src/providers/http.ts`
- Create: `crypto-research-gateway/src/providers/binance.ts`
- Create: `crypto-research-gateway/src/providers/okx.ts`
- Create: `crypto-research-gateway/src/providers/bybit.ts`
- Create: `crypto-research-gateway/src/providers/gate.ts`
- Create: `crypto-research-gateway/src/providers/kucoin.ts`
- Create: `crypto-research-gateway/src/providers/index.ts`
- Create: `crypto-research-gateway/test/providers.test.ts`

**Interfaces:**
```ts
export interface PublicMarketProvider {
  id: 'binance' | 'okx' | 'bybit' | 'gate' | 'kucoin';
  snapshot(symbol: string, instrument: 'spot' | 'perpetual'): Promise<MarketObservation[]>;
  candles(symbol: string, instrument: 'spot' | 'perpetual', interval: string, limit: number): Promise<unknown[]>;
  orderbook(symbol: string, instrument: 'spot' | 'perpetual', limit: number): Promise<unknown>;
  derivatives?(symbol: string): Promise<unknown>;
  healthProbe(): Promise<{ ok: boolean; latencyMs: number; error?: string }>;
}
```

- [ ] **Step 1: Write adapter tests with mocked fetch**

Tests must verify URL construction, symbol transforms, timestamps, price semantics, timeout handling, and that adapters use only GET public endpoints.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/providers.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Implement provider adapters against current official public APIs**

Use these first-party bases verified during planning:
- Binance spot market-data-only base: `https://data-api.binance.vision` with `/api/v3/ticker/24hr`, `/api/v3/klines`, `/api/v3/depth`; derivatives use public Binance futures market endpoints only.
- OKX: `https://www.okx.com/api/v5/market/*` and read-only `api/v5/public/*` funding/open-interest endpoints.
- Bybit: `https://api.bybit.com/v5/market/tickers`, `/v5/market/kline`, `/v5/market/orderbook`, `/v5/market/open-interest`; ticker supplies mark/index/funding fields for derivatives.
- Gate: `https://api.gateio.ws/api/v4/spot/tickers`, `/spot/candlesticks`, `/spot/order_book`, and public `/futures/usdt/*` reads for perpetuals.
- KuCoin: current public market endpoints under `https://api.kucoin.com` and `https://api-futures.kucoin.com`; use the current UTA K-line endpoint where required by current docs.

Implement `fetchJson()` with AbortSignal timeout (default 5s), GET-only method enforcement, bounded response-size handling, and no authorization headers.

- [ ] **Step 4: Run mocked tests/typecheck**

```bash
npm test -- --run test/providers.test.ts
npm run typecheck
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/providers crypto-research-gateway/test/providers.test.ts
git commit -m "feat: add public first-party crypto provider adapters"
```

---

### Task 5: Capability router and degraded-state behavior

**Files:**
- Create: `crypto-research-gateway/src/routing/capability-router.ts`
- Create: `crypto-research-gateway/test/routing.test.ts`

**Interfaces:**
```ts
export type ProviderHealth = Record<string, { ok: boolean; checkedAt: number }>;
export function selectProviders(input: {
  capability: string;
  preferredVenue?: string;
  maxCandidates?: number;
  health: ProviderHealth;
}): string[];
```

- [ ] **Step 1: Write failing routing tests**

Assert max three providers, exact venue wins when healthy, unhealthy providers are skipped, no eligible provider returns `[]`, and no HIGH_RISK id is ever routed.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/routing.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Implement deterministic routing**

Default provider order for equivalent public market reads: Binance -> OKX -> Bybit -> Gate -> KuCoin, unless exact requested venue is healthy. The order is fallback ordering, not truth authority.

- [ ] **Step 4: Run GREEN**

```bash
npm test -- --run test/routing.test.ts
npm run typecheck
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/routing crypto-research-gateway/test/routing.test.ts
git commit -m "feat: add bounded cloud provider routing"
```

---

### Task 6: HTTP research API and health surface

**Files:**
- Create: `crypto-research-gateway/src/config.ts`
- Create: `crypto-research-gateway/src/routes/health.ts`
- Create: `crypto-research-gateway/src/routes/capabilities.ts`
- Create: `crypto-research-gateway/src/routes/research.ts`
- Create: `crypto-research-gateway/src/server.ts`
- Create: `crypto-research-gateway/test/http.test.ts`

**Interfaces:**
- `GET /health`
- `GET /capabilities`
- `POST /research/market`
- `POST /research/token`
- `POST /research/news`
- `POST /research/risk`

- [ ] **Step 1: Write failing HTTP injection tests**

Use Fastify inject. Assert health contains no env values/secrets, capabilities lists read-only tools only, invalid capability returns 400/403, and provider exhaustion returns structured `degraded: true` rather than fake data.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/http.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Implement minimal HTTP surface**

`/research/market` supports `snapshot`, `candles`, `orderbook`, `funding_oi`. Token/news/risk endpoints expose only capabilities actually backed by safe public adapters; if unavailable, return `501 capability_not_available` rather than simulating results.

Health returns version, runtime mode, provider status, last public probe timestamp, degraded provider ids. Never include process environment content.

- [ ] **Step 4: Run GREEN**

```bash
npm test -- --run test/http.test.ts
npm run typecheck
npm run build
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src crypto-research-gateway/test/http.test.ts
git commit -m "feat: expose zero-local read-only research API"
```

---

### Task 7: Remote Streamable HTTP MCP surface

**Files:**
- Create: `crypto-research-gateway/src/mcp/server.ts`
- Create: `crypto-research-gateway/test/mcp.test.ts`
- Modify: `crypto-research-gateway/src/server.ts`

**Interfaces:**
Read-only MCP tools:
- `market_snapshot`
- `market_candles`
- `market_orderbook`
- `derivatives_funding_oi`
- `token_research`
- `token_risk_check`
- `crypto_news_research`

- [ ] **Step 1: Write failing MCP tests**

Assert tool listing contains no order/wallet/transfer/swap/withdraw/pay verbs and that market tool requests execute the same policy/routing path as HTTP.

- [ ] **Step 2: Run RED**

```bash
npm test -- --run test/mcp.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Implement `/mcp` using the official MCP TypeScript SDK**

Use the stable SDK Streamable HTTP server surface. Register only read-only tools. Tool handlers call shared research functions; they do not invoke a shell or local process and do not register stdio transport.

- [ ] **Step 4: Run GREEN/build**

```bash
npm test -- --run test/mcp.test.ts
npm run typecheck
npm run build
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/src/mcp crypto-research-gateway/src/server.ts crypto-research-gateway/test/mcp.test.ts
git commit -m "feat: add read-only remote MCP transport"
```

---

### Task 8: Railway deployment configuration and cloud CI

**Files:**
- Create: `crypto-research-gateway/railway.toml`
- Create: `.github/workflows/zero-local-cloud-runtime.yml`
- Create: `tests/test_zero_local_manifest.py`

**Interfaces:**
`railway.toml` must configure root-service build/start expectations and `/health` healthcheck.

- [ ] **Step 1: Add failing manifest tests first**

Assert Railway config has health path `/health`, no cron, and gateway package engines requires Node >=22. Assert workflow runs tests/build and existing Brain validators.

- [ ] **Step 2: Run RED**

```bash
python -m unittest discover -s tests -p 'test_zero_local_manifest.py' -v
```
Expected: FAIL before config/workflow exist.

- [ ] **Step 3: Add Railway config + GitHub Actions workflow**

Workflow on the feature branch, PRs, and `main`:
```text
setup Node 22 -> npm ci -> typecheck -> vitest run -> build -> Python policy tests -> registry/Brain/router/V4/authority validators
```
No deploy secrets are required for test CI.

- [ ] **Step 4: Run/observe CI until all steps GREEN**

Expected: all gateway and Brain validation steps pass on the exact branch head.

- [ ] **Step 5: Commit**

```bash
git add crypto-research-gateway/railway.toml .github/workflows/zero-local-cloud-runtime.yml tests/test_zero_local_manifest.py
git commit -m "ci: validate zero-local cloud runtime"
```

---

### Task 9: Deploy branch to Railway and verify live public probes

**Files:**
- No source mutation required unless deployment exposes a defect.

**Interfaces:**
- Railway project: `github-brain-zero-local-runtime`
- Service: `crypto-research-gateway`
- Source repo: `hanlinh227-ship-it/trading-api`
- Branch: `zero-local-cloud-runtime-20260912`
- Root directory: `/crypto-research-gateway`
- Health path: `/health`

- [ ] **Step 1: Create Railway project**

Create private Railway project `github-brain-zero-local-runtime`.

- [ ] **Step 2: Create deployment from the confirmed GitHub repository/feature branch**

Use the Railway GitHub source, then set root directory `/crypto-research-gateway`, start command `npm start`, healthcheck `/health`, restart on failure, and continuous runtime.

- [ ] **Step 3: Verify deployment logs and health**

Require Railway deployment status `SUCCESS`. Inspect build/deploy logs for secret leakage, crashes, install failures, or Node-version mismatch.

- [ ] **Step 4: Verify live provider health**

`/health` must report successful public probes for Binance, OKX, Bybit, Gate, KuCoin or explicitly identify a provider-specific connectivity issue. Acceptance requires all five healthy before main merge.

- [ ] **Step 5: Verify `/capabilities`**

Confirm only read-only executable capabilities are exposed and no HIGH_RISK action exists.

---

### Task 10: Documentation, PR, merge, and canonical post-merge deploy

**Files:**
- Modify: `crypto-agent-skills/README_SETUP.md`
- Modify: `crypto-agent-skills/INSTALLED_SKILLS_REPORT.md`
- Create: `crypto-research-gateway/README.md`

**Interfaces:**
Documentation must state `local installation required: NO` for normal research and identify Railway/cloud as the runtime.

- [ ] **Step 1: Update docs**

Remove normal-workflow instructions to install provider skills locally. Keep local diagnostics only as optional developer troubleshooting, not a runtime requirement.

- [ ] **Step 2: Re-run full branch verification**

```bash
cd crypto-research-gateway && npm ci && npm run typecheck && npm test -- --run && npm run build
cd ..
python -m unittest discover -s tests -p 'test_cloud_runtime_policy.py' -v
python -m unittest discover -s tests -p 'test_zero_local_manifest.py' -v
python AI_SKILL_LIBRARY/validate_skill_registry.py
python AI_SKILL_LIBRARY/validate_brain.py
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_v4.py
python AI_SKILL_LIBRARY/validate_authority.py
```
Expected: PASS.

- [ ] **Step 3: Open PR to `main` and require PR CI GREEN**

PR description must explicitly document zero-local semantics, no live credentials, no HIGH_RISK execution, Railway live health status, and the verified provider list.

- [ ] **Step 4: Merge only after PR CI and Railway branch deployment are GREEN**

Use squash merge with expected head SHA.

- [ ] **Step 5: Deploy canonical `main` and verify again**

Update Railway source to canonical `main` if needed, deploy, require `SUCCESS`, verify `/health`, `/capabilities`, and post-merge GitHub CI.

- [ ] **Step 6: Final completion evidence**

Record merge commit, Railway project/service ids, deployment id/status, health result, provider probe summary, and CI run ids. Do not claim local installation because none is required or performed.
