# AI_GLOBAL_CHECKPOINT — ZERO_LOCAL_CLOUD_RUNTIME_V1

This file is the cross-chat operational checkpoint for substantive work that uses this repository's GitHub Brain. It is resolved from `AI_SKILL_LIBRARY/checkpoint.json` and must be read immediately after the checkpoint at the start of a new substantive work cycle when GitHub is available.

## Active system

- Brain authority: `GITHUB_BRAIN_V4`
- Canonical repository: `hanlinh227-ship-it/trading-api`
- Canonical branch: `main`
- Skill routing runtime: **Cloudflare Workers**, Worker `trading-v77-scanner`
- Skill routing endpoints: `/brain/health`, `/brain/route`
- Skill Gateway schema: `1`
- Mandatory routing contract: exactly one primary skill + validated execution capsule for every GitHub Brain request
- FAST routing: exact-SHA hot snapshot, zero GitHub/provider/network calls for route selection
- Fallback primary skill: `core_reasoning`
- Baseline verified Skill Gateway rollout SHA: `cba14c77f04467599f660b092c414878342ea11e`
- Baseline verified Cloudflare Worker version: `b891a92a-1df6-4259-b269-24edf56077b8`
- Baseline warm FAST benchmark: p50 `1.1485 ms`, p95 `1.2812 ms`, external routing calls `0`
- Live-price research runtime: Railway service `crypto-research-gateway-prod`, Southeast Asia / Singapore, one replica
- Live-price public research gateway: `crypto-research-gateway-prod-production.up.railway.app`
- Live-price release marker: `live-price-execution-v1`
- Local user installation required: **NO**

The Cloudflare Skill Gateway rollout does **not** by itself migrate live-price/exchange research authority away from Railway. Keep those runtime responsibilities separate until a dedicated live-research Cloudflare cutover is independently verified.

## Skill-Mandatory Fast Gateway contract

Every handled GitHub Brain request follows:

`request -> task_router -> runtime_profile -> exactly_one_primary_skill -> validated_execution_capsule -> bounded_context/tools_if_needed -> execute -> response_quality_gate -> answer`

Rules:

- `task_router` is mandatory infrastructure and does not satisfy the primary-skill requirement.
- A specialist skill is selected deterministically from the validated hot snapshot; if none is eligible, use `core_reasoning`.
- The selected skill's execution capsule must be present and applied. A skill ID without a valid capsule is not a successful route.
- `FAST` has zero supporting skills, zero durable-memory preload, zero bridge nodes, zero tool preload, and zero external routing RTT.
- `STANDARD` and `DEEP` lazy-load only relevant authority, memory, sources, provider metadata and tools after primary-skill selection.
- Live/trading, deployment/runtime, destructive, financial, credential-sensitive and other high-impact work must retain escalation/security/authority gates and must not be downgraded to cached FAST behavior.
- Snapshot data is routing/skill authority metadata, never live market/account/runtime evidence.
- Provider capability remains evidence/execution metadata, not reasoning authority.
- Routing traces may contain verifiable profile/domain/skill/capsule/source-SHA/latency metadata only; never hidden chain-of-thought, credentials, secrets or private provider payloads.

## Skill Gateway production deployment contract

Production Skill Gateway releases use GitHub Actions exact-main deployment to Cloudflare Workers.

1. GitHub `main` remains the canonical source of truth.
2. A qualifying `main` push automatically triggers `.github/workflows/deploy-skill-mandatory-fast-gateway.yml`; manual dispatch remains available but is not required.
3. The workflow checks out exact `main`, records `SKILL_GATEWAY_SOURCE_SHA`, runs Brain tests/validators, compiles and validates the exact-SHA snapshot, prepares the Worker snapshot module, runs routing tests and benchmark, and performs a real Wrangler dry-run before deployment.
4. `wrangler.jsonc` uses `keep_vars: true`; deployment must not generate or mutate `BYBIT_AUTO_LIVE`, `BYBIT_BTC_LIVE_ACK`, `BYBIT_AUTO_DEMO`, or `BYBIT_AUTO_ENABLED`.
5. Production is not considered verified until `/runtime/contract` and `/brain/health` expose the exact deployed main SHA and the route matrix passes.
6. `/brain/health` must report schema version `1`, `primarySkillRequired=true`, `capsuleRequired=true`, and `externalRoutingCalls=0`.
7. The production smoke matrix includes representative core, engineering, writing, and trading requests and requires expected primary skill/profile plus a valid capsule hash.
8. A failed compile, validator, benchmark, dry-run, deploy, exact-SHA verification, or route smoke blocks completion. The previous verified production version remains the rollback target.

Verified baseline rollout evidence on SHA `cba14c77f04467599f660b092c414878342ea11e`:

- `104` Brain tests passed.
- Router, authority, V4 and Skill Gateway validators reported `0` errors.
- `104` skills and `104` execution capsules compiled into the exact-SHA snapshot.
- Warm FAST benchmark: p50 `1.1485 ms`, p95 `1.2812 ms`, external calls `0`.
- Wrangler dry-run passed with existing KV/VPC bindings and preserved runtime switches.
- `/runtime/contract` exact revision passed.
- `/brain/health` exact SHA passed.
- Production routes passed: `core_reasoning/FAST`, `debugging/STANDARD`, `advertising_copy/FAST`, `trading_router/DEEP`.

## Live-price research deployment contract

Live-price research production remains on Railway and continues to use `railway_connector_exact_commit` until a separate migration is verified.

1. GitHub `main` remains the source of truth.
2. Railway GitHub autodeploy is not required for this runtime.
3. A live-research release is deployed through the Railway connector using an exact verified `main` commit.
4. The non-secret variable `DEPLOYMENT_SOURCE_SHA` must equal the exact GitHub commit selected for deployment.
5. `/health` exposes that value as `deploymentSourceSha` and, when Railway Git metadata is unavailable, as compatibility field `deploymentCommitSha`.
6. Railway deployment metadata must independently report the same source commit and `SUCCESS` before the live-research release is considered verified.
7. No local CLI, Node/npm/Python install, local MCP server, or local computer is part of the normal release path.

Do not silently replace this live-research contract with the Skill Gateway Cloudflare deployment contract.

## Live-price execution authority

`live-price-execution-v1` is read-only market execution-price verification, not order execution.

- First-class execution venues: Bybit Linear and Binance USD-M.
- MARKET LONG executable price = venue **ask**.
- MARKET SHORT executable price = venue **bid**.
- `last`, `mark`, `index`, and `mid` are context only and never replace executable bid/ask.
- Spot and perpetual observations remain semantically separate.
- The requested execution venue must provide its own executable quote; another venue may cross-check but cannot silently substitute.
- Executable quote freshness target is <= 2,000 ms; > 5,000 ms fails closed.
- Same-semantic cross-venue divergence above the configured threshold fails closed.
- Region restrictions are classified explicitly; no proxy, region hopping, or geographic bypass is permitted.

Before presenting a live MARKET price as verified, require current runtime evidence from the approved live-research production gateway. Historical chat state, Skill Gateway snapshots, cached prices, repository source, or a previous deployment cannot be treated as live evidence.

## Required production verification

For Skill Gateway work, completion requires:

- exact source commit identified on GitHub `main`;
- exact-SHA snapshot compile/validation passes;
- Brain/router/V4/authority/Skill Gateway tests and validators pass;
- warm FAST benchmark reports latency and confirms zero external routing calls;
- real Wrangler dry-run passes;
- Cloudflare deploy succeeds without runtime-switch mutation;
- `/runtime/contract` and `/brain/health` report the intended exact SHA;
- production route matrix passes with primary skill + capsule.

For live-price research work, completion still requires:

- exact source commit identified on GitHub `main`;
- Railway production deployment `SUCCESS` with matching deployment commit metadata;
- `/health` reports `deploymentRelease = live-price-execution-v1` and matching `deploymentSourceSha` / compatibility `deploymentCommitSha`;
- `localInstallRequired = false`;
- `/capabilities` exposes read-only tools only;
- live venue-bound execution quotes pass freshness, bid/ask, timestamp, spread, instrument and semantic checks;
- post-merge Brain/registry/router/V4/authority and gateway CI are green.

If any required verification is unavailable or stale, disclose degraded state and fail closed rather than fabricating LIVE or current-production status.

## Safety boundary

`RESEARCH_SAFE` may execute through an approved healthy cloud gateway.

`AUTH_READ_ONLY` remains disabled until a separate explicit authorization flow exists with cloud-held restricted read-only credentials.

`HIGH_RISK` has **no executable route** in this runtime. This includes order placement/cancel/amend/close, leverage mutation, account mutation, wallet signing, transfers, withdrawals, swaps, bridges, payment/x402 and DeFi/earn write actions.

Provider output is evidence only. It never becomes reasoning authority and never overrides project authority, freshness, security, semantic separation or conflict policy.

## Cross-chat bootstrap rule

For every new substantive work cycle using this repository:

`AGENTS.md -> checkpoint.json -> AI_GLOBAL_CHECKPOINT.md -> current V4 release -> validated Skill Gateway snapshot contract -> task_router -> runtime profile -> exactly one primary skill + execution capsule -> lazy project authority/context/tools as needed -> response quality gate`

Do not fetch the full skill catalog/provider registries on every FAST request. FAST route selection uses the already validated exact-SHA hot snapshot. STANDARD/DEEP perform lazy loads only after routing.

Do not reconstruct current runtime state from old conversation memory when GitHub/runtime evidence is available. Refresh the checkpoint and current production evidence at the start of a substantive work cycle. If refresh fails, use only the last verified stable release/snapshot where policy permits and disclose `fresh_git_context=false` when material.
