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
- Current capability release: **resolve from `AI_SKILL_LIBRARY/v4/releases/current.json`** (never trust a version number written in prose; verify `known_good` in `history.yaml` and `promotion.validated` in the pointed manifest). Latest closure record: `CHECKPOINTS/OPEN_MODEL_CAPABILITY_LEDGER_4_17_0_CLOSURE_2026-09-17.md` (its Status line says whether the release it describes is production-verified; the preceding 4.15.0 record is `CHECKPOINTS/BRAIN_EXPANSION_BROWSER_RUNTIME_4_15_0_CLOSURE_2026-09-17.md`, the 4.14.0 record is `CHECKPOINTS/BRAIN_EXPANSION_4_14_0_CLOSURE_2026-09-17.md`, the 4.13.0 record is `CHECKPOINTS/FREE_IMAGE_RENDER_AGENT_V2_4_13_0_CANDIDATE_2026-09-16.md` and the 4.11.0 record is `CHECKPOINTS/UNIVERSAL_BRAIN_FABRIC_4_11_0_CLOSURE_2026-09-16.md`). Historical figure at time of writing of this paragraph: `4.9.1` at `99359b1720a28614749d53615fe2b740044de40e` (deploy run 34987419682).
- Master cross-session handoff: `CHECKPOINTS/GITHUB_BRAIN_MASTER_HANDOFF_2026-09-15.md` — read this after the checkpoint for current production truth, Model Mesh architecture, unresolved items and the next-phase boundary
- Model Mesh production state: FREE_ONLY; provider health is runtime evidence — read it from `/brain/mesh/health` (or the latest gated deploy run log), never from this document. Provider counts written here go stale within one deploy.
- Continuous Intelligence rule: the Evergreen Update Plane may autonomously refresh sources, detect evidence-backed gaps, generate/test candidates, and prepare bounded improvements; Stable remains immutable during request execution and changes only through validated release promotion.
- Autonomous promotion boundary: Class A/B may promote only after all required gates (and sandbox for B); Class C/D require explicit human authorization and cannot unattended-promote.
- Open-source fusion rule: upstream repositories are reference/evidence only; strengthen existing canonical skills first; no parallel reasoning authority; no permission widening; no mandatory local runtime
- Plain-language presentation: enabled; user-facing default locale `vi`, simple language; exact technical tokens remain available when needed
- Live-price research runtime: Railway service `crypto-research-gateway-prod`, Southeast Asia / Singapore, one replica
- Live-price public research gateway: `crypto-research-gateway-prod-production.up.railway.app`
- Live-price release marker: `live-price-execution-v1`
- Local user installation required: **NO**

## Peer Tri-Layer AI Legion candidate checkpoint — 2026-09-15

This implementation exists on isolated branch `github-brain-v4-afmm-implementation2`. It is a **candidate**, not the active Stable release and not a production-deployment claim.

- Sole commander/routing authority remains `GITHUB_BRAIN_V4`.
- AI Legion is a bounded specialist execution layer; `routing_authority=false`, `reasoning_authority=false`.
- Learning Layer A=`experience`, B=`curated`, C=`exploration`; all three are epistemic peers with no fixed layer weight or priority.
- Learning Layers A/B/C are distinct from existing Risk Class A/B/C/D. Source layer never lowers or raises risk by itself.
- Truth is never selected by majority vote. Claims are resolved by provenance, freshness, claim-specific authority, reproducibility, measured evidence and verification.
- Legion worker concurrency remains FAST=0, STANDARD<=2, DEEP<=4.
- Adaptive Free Model Mesh (AFMM) remains the only provider/model execution layer; Legion does not create a second provider registry.
- OpenCode is optional bounded execution only; Awesome LLM Apps and AutoSkill/SkillEvo contribute patterns/capabilities only.
- Skill Factory/SkillEvo may mine, create, merge, mutate, replay and benchmark candidates, but may not write Stable directly or widen permissions.
- Idle learning may generate only budgeted low-risk background objectives and yields immediately to active user work.
- Existing cloud handler now has candidate contracts for `/brain/legion/health`, `/brain/legion/capabilities`, and `/brain/learning/status`; `/brain/route` remains provider-free with `externalRoutingCalls=0`.
- `validate_legion.py` enforces single authority, peer-layer invariants, prompt-injection boundaries, credential redaction, permission ceilings and research-only financial defaults.
- Checkpoint paths for Legion/learning policies are registered in `AI_SKILL_LIBRARY/checkpoint.json`.
- Candidate release packaging is non-promoting. `release.py build_candidate_manifest()` hashes Stable + Legion contracts without mutating `current.json`.
- Stable promotion is intentionally blocked until AFMM release/snapshot/runtime dependency verification is complete and all canonical release hashes are reconciled.
- The Legion candidate never moved the active stable release pointer; the active release is whatever `AI_SKILL_LIBRARY/v4/releases/current.json` says. Do not represent the Legion candidate as active production.
- Implementation audit: `AI_SKILL_LIBRARY/v4/audit/PEER_TRI_LAYER_AI_LEGION_IMPLEMENTATION_REPORT.md`.
- Approved spec: `docs/superpowers/specs/2026-09-15-peer-tri-layer-ai-legion-design.md`.
- Implementation plan: `docs/superpowers/plans/2026-09-15-peer-tri-layer-ai-legion.md`.

High-risk gates remain unchanged: no autonomous live financial execution, fund transfer, credential/secret mutation, destructive production operation, production permission widening, security-control disabling, authority-hierarchy self-modification, high-risk self-promotion, or quota/access-control circumvention.

The Cloudflare Skill Gateway rollout does **not** by itself migrate live-price/exchange research authority away from Railway. Keep those runtime responsibilities separate until a dedicated live-research Cloudflare cutover is independently verified.

## Skill-Mandatory Fast Gateway contract

Every handled GitHub Brain request follows:

`request -> task_router -> runtime_profile -> exactly_one_primary_skill -> validated_execution_capsule -> bounded_context/tools_if_needed -> execute -> response_quality_gate -> plain_language_presentation -> answer`

Rules:

- `task_router` is mandatory infrastructure and does not satisfy the primary-skill requirement.
- A specialist skill is selected deterministically from the validated hot snapshot; if none is eligible, use `core_reasoning`.
- The selected skill's execution capsule must be present and applied. A skill ID without a valid capsule is not a successful route.
- `FAST` has zero supporting skills, zero durable-memory preload, zero bridge nodes, zero tool preload, and zero external routing RTT.
- `STANDARD` and `DEEP` lazy-load only relevant authority, memory, sources, provider metadata and tools after primary-skill selection.
- Live/trading, deployment/runtime, destructive, financial, credential-sensitive and other high-impact work must retain escalation/security/authority gates and must not be downgraded to cached FAST behavior.
- Snapshot data is routing/skill authority metadata, never live market/account/runtime evidence.
- Provider and upstream capability remains evidence/execution metadata, not reasoning authority.
- Routing traces may contain verifiable profile/domain/skill/capsule/source-SHA/latency metadata only; never hidden chain-of-thought, credentials, secrets or private provider payloads.

## Brain 4.8 Continuous Intelligence contract

Brain 4.8 extends the existing dual-plane Evergreen architecture so intelligence maintenance can continue without waiting for a user command.

- Stable Runtime Plane and Evergreen Update Plane remain isolated. Evergreen failure must not take down Stable.
- Stable request handling never waits for source discovery, gap research, candidate generation, or learning cycles.
- The canonical Continuous Intelligence contract is checkpoint-resolved at `AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml` and is part of the immutable capability release.
- Source/discovery refresh runs every hour; candidate analysis and bounded upgrade preparation also run every hour; a deep read-only intelligence audit runs weekly; verified failure intake is event-driven when sanitized evidence is available.
- Source lifecycle states are `active`, `stale`, `reverify`, `deprecated`, and `archived`.
- Fast-changing official docs, approved GitHub maintenance metadata and plugin metadata default to 48-hour revalidation windows; scientific-discovery metadata defaults to 14 days.
- Stale historical evidence may remain available for history/audit but cannot masquerade as current API/runtime truth.
- Gap detection is evidence-led. A capability gap requires a domain, signal type, severity, evidence reference, recommended capability and timestamp. Unsupported inferred gaps do not become durable facts.
- Verified failures may become candidate regression evidence only from sanitized observable fields. Hidden reasoning, secrets, credentials, raw private prompts and private tool payloads are forbidden from durable failure state.
- Candidate comparisons require baseline evidence and candidate evidence. Protected dimensions (`correctness`, `authority`, `security`, `verification`, `project_isolation`) have zero regression tolerance.
- Default candidate quality threshold is at least `0.01` primary-quality gain, with no more than `0.10` relative latency regression and `0.05` relative execution-cost regression unless a separately approved policy explicitly changes the release contract.
- Class A declarative low-risk and Class B sandboxed non-privileged helpers may unattended-promote only after all required gates; Class B additionally requires sandbox evidence.
- Class C kernel/router/security/authority changes may be autonomously researched, prepared, tested and proposed, but require explicit human authorization before Stable promotion.
- Class D financial/credential/destructive/permission-expansion changes never auto-promote and require explicit authorization.
- Continuous learning cannot relabel a high-risk capability into a lower class to bypass authority.
- External code remains untrusted by default; discovery never grants execution permission.
- Automatic Evergreen capability releases increment patch only within the active Brain V4 minor line, e.g. `4.8.0 -> 4.8.1`. Automatic minor-version bumps are forbidden.
- Continuous Intelligence never grants trading execution, wallet, credential, destructive, production-write, secret-access or security-bypass authority.
- The default canonical routed skill/capsule count remains `109/109`; a new primary skill remains exceptional and requires a distinct contract, trigger ownership, measurable eval gain and full admission gates.

If sanitized production failure telemetry is unavailable, Brain may maintain the ingestion/eval machinery but must not claim that it learned from nonexistent production failures.

## Brain 4.7 selective open-source fusion contract

Brain 4.7 capability-fusion guarantees remain inherited by Brain 4.8.

- Default canonical routed skills: `109`.
- Default execution capsules: `109`.
- New upstream candidates start quarantined with zero routing/reasoning authority.
- Active-source registration requires verified provenance, allowed license/usage status, maintenance status, overlap/conflict scan, risk/permission ceiling, performance impact, authority impact and eval impact.
- If a candidate overlaps an existing skill, strengthen the existing skill first or use a reference/adapter; do not create a competing primary skill.
- A new primary skill requires a distinct task intent, unique input/output contract, no trigger ownership conflict, measurable eval gain, valid capsule, and security/authority approval.
- External code is untrusted by default. Reference patterns do not imply code reuse.
- License-unresolved or non-allowlisted sources remain design/reference-only and cannot auto-promote into active registry/RAG.
- Upgrade bottleneck checks cover context growth, FAST latency, external routing calls, duplicate capabilities, trigger ownership, authority overlap, permission ceilings, license status, source maintenance and source security posture.
- MCP interoperability uses typed capability contracts, explicit protocol compatibility, discovery/invocation separation and fail-closed permission ceilings; no local MCP server is mandatory.
- Document intelligence prefers structured/native extraction before OCR and preserves hierarchy, page/section provenance and table structure when material.
- Graph retrieval is optional, bounded to STANDARD/DEEP, source-traceable and subordinate to authority/freshness filters; no graph database is mandatory.
- Eval engineering explicitly separates task, case set, solver/agent, scorer, baseline/candidate and protected-regression evidence.
- Open-source intake may use security-health, vulnerability, secret, SBOM and provenance signals as advisory evidence; a high score never grants authority or auto-promotion.
- AI observability follows sanitized OpenTelemetry-aligned semantics while forbidding raw prompts, private tool payloads, secrets and hidden reasoning.
- Browser-facing verification prefers runnable end-to-end evidence when an executable environment exists.
- No unresolved bottleneck may be promoted to Stable.
- No open-source reference may grant trading execution, wallet, credential, destructive or production-write authority.

Quality upgrades retained from 4.6 include stronger repository workflow verification, adversarial/eval coverage, quantitative realism, 3D asset validation, design-system validation, prompt regression discipline, game runtime validation, source/license provenance checks and duplicate-capability detection. Brain 4.7 added MCP contract integrity, document fidelity, graph-retrieval safety, OSS intake security, observability sanitization and browser-runtime verification; Brain 4.8 adds continuous source aging, evidence-backed gap detection, sanitized failure-to-regression conversion, baseline/candidate comparison and stricter autonomous-promotion boundaries.

## Consolidation contract (release 4.3.0+)

- One router: `AI_SKILL_LIBRARY/v4/stable/router.yaml`; legacy `AI_SKILL_LIBRARY/router.yaml` is a compatibility adapter with `routing_authority: false`.
- One budget file: `AI_SKILL_LIBRARY/v4/stable/budgets.yaml` (FAST: 1 skill load, 0 supporting, 0 sources, ≤3 index hits, 1 retrieval stage, 0 tool calls, HOT tier only).
- One retrieval contract: `AI_SKILL_LIBRARY/v4/stable/retrieval.yaml` + committed index `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml` (HOT/WARM/COLD; exact lookup before semantic; stale index fails CI).
- One validation entrypoint: `python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha <sha>`.
- Release manifests/hashes/history are generated: `python AI_SKILL_LIBRARY/v4/tools/release.py build --version X.Y.Z ...`.
- Alias skill rows (`alias_of`) never route; the compiled snapshot exposes `skill_aliases`.
- Production deploy workflows queue (`cancel-in-progress: false`) so a Worker deploy is never cancelled mid-flight by a sibling workflow.

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

Provider/upstream output is evidence only. It never becomes reasoning authority and never overrides project authority, freshness, security, semantic separation or conflict policy.

## Cross-chat bootstrap rule

For every new substantive work cycle using this repository:

`AGENTS.md -> checkpoint.json -> AI_GLOBAL_CHECKPOINT.md -> current V4 release -> validated Skill Gateway snapshot contract -> task_router -> runtime profile -> exactly one primary skill + execution capsule -> lazy project authority/context/tools as needed -> response quality gate -> plain_language_presentation -> answer`

For Brain maintenance, resolve `stable_continuous_intelligence_path` before changing Evergreen discovery/promotion behavior. For AI Legion work, also resolve `legion_policy_path`, `learning_policy_path`, `learning_sources_path`, `skill_factory_policy_path`, `skill_evo_policy_path`, and `idle_learning_policy_path` from the checkpoint before changing autonomous-learning behavior.

Do not fetch the full skill catalog/provider registries on every FAST request. FAST route selection uses the already validated exact-SHA hot snapshot. STANDARD/DEEP perform lazy loads only after routing.

Do not reconstruct current runtime state from old conversation memory when GitHub/runtime evidence is available. Refresh the checkpoint and current production evidence at the start of a substantive work cycle. If refresh fails, use only the last verified stable release/snapshot where policy permits and disclose `fresh_git_context=false` when material.


## Brain 4.9 Adaptive Free Model Mesh + Peer Tri-Layer AI Legion contract

- `task_router` and project authority remain the sole routing/reasoning authority; model providers, OpenCode workers, specialist agents, RAG/MCP patterns and learning engines are subordinate execution/evidence resources.
- FAST remains provider-free with `externalRoutingCalls=0`; STANDARD and DEEP may use bounded independent workers only, capped at 2 and 4 respectively.
- Model Mesh mode is `FREE_ONLY`; catalog presence is not free-entitlement proof, and paid/unknown/quarantined models are not execution eligible.
- Provider execution is disabled by default and requires runtime configuration, current free entitlement, privacy compatibility and health evidence. Integrated providers without those gates are `INTEGRATED_NOT_ACTIVE`, never reported LIVE.
- Learning planes Experience, Curated and Exploration are peers for hypothesis/challenge/candidate creation. No plane has a fixed truth weight and majority vote is forbidden.
- AutoSkill/SkillEvo patterns are absorbed as Brain-native skill mining/evolution with replay, protected regression checks, sandbox/canary and promotion gates; they cannot self-elevate permissions or authority.
- Idle learning may create bounded low-risk background jobs but yields immediately to active user work and cannot execute live financial actions, access secrets outside scope, or widen permissions.
- Trading specialists remain research/backtest/evidence workers only; real order execution is outside this release authority.
- Brain 4.9 is not known-good until canonical CI, Worker checks, Wrangler dry-run, exact-SHA deployment, `/brain/health`, `/brain/mesh/health`, route/planner smoke and post-deploy verification all pass.

## Wave 3 operational closure + Free Worker Mesh (2026-09-17)

- `WAVE3_OPERATIONAL_CLOSED = true` and `WAVE3_ALL_EXACT_MODELS_AVAILABLE = false` are **separate facts recorded separately**. Wave 3 closed on terminal states with exact, evidenced blockers; it did not close by making every candidate available. Three candidates end with no executable exact path. Do not read either flag as the other.
- Terminal states: Qwen3-8B `AVAILABLE_LOCAL`; gpt-oss-20b `AVAILABLE_SERVERLESS` (exact model, real inference proven on Cloudflare Workers AI free tier); Qwen3-Coder-30B-A3B `REMOTE_WORKER_REQUIRED`; Phi-4-mini and DeepSeek-R1-Distill-Qwen-7B `QUARANTINED_PROVENANCE`; gemma-3-4b-it `DEFERRED_TO_WAVE4` behind its human licence gate.
- **Free Worker Mesh** (`AI_SKILL_LIBRARY/v4/local_runtime/free_worker_mesh.py`, spec `FREE_WORKER_MESH.md`) is execution capacity only and holds none of the six authorities. Worker, provider and mesh authority flags are class attributes fixed at False; passing one is a `TypeError`.
- Three rules that must not be relaxed by a later wave: a capability qualifies a worker only when **measured**, never when merely declared; a provider serving a **different** model covers a capability under its own name and is never the requested model's availability; a provider is `VERIFIED_AVAILABLE` only after a real completion on a zero-cost tier, because documentation is not execution proof.
- Third-party GGUF conversions must name base model, **base revision** and converter tool. Provenance is read from the artifact's own GGUF metadata first, the model card second, README prose last, and the source of each field is recorded.
- Resource measurements are scoped to the machine they were taken on. This container's RAM is not operator hardware, not a GitHub limit and not a property of any model.
- Wave 4 is **prepared, not started**: `wave4_capability_requirements.yaml` declares capability tags only — zero models named, discovered, staged or admitted — and adds no orchestration authority.
