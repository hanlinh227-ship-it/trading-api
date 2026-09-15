# Adaptive Free Model Mesh — Design

Date: 2026-09-15
Status: Approved design, implementation not started
Repository: `hanlinh227-ship-it/trading-api`
Canonical branch: `main`
Checkpoint-resolved baseline at approval: Brain V4, release `4.8.1`

## 1. Purpose

Add a cloud-first, quota-aware, multi-provider model execution mesh that can discover and use as many legitimately free or free-tier models as practical, while preserving the existing GitHub Brain authority chain.

The mesh exists to increase throughput, resilience, and cost efficiency. It must not create a second reasoning authority, bypass `task_router`, widen permissions, or make the Stable Runtime Plane depend on any single external provider.

The core rule is:

`large available model pool != all models run on every request`

The system should maintain a broad pool, but activate only the smallest useful set of workers for each routed task.

## 2. Existing authority and invariants

This design inherits all checkpoint-resolved Brain contracts. In particular:

- `task_router` remains mandatory and singular.
- Exactly one primary reasoning skill remains required for each routed request.
- Provider/model outputs are execution/evidence inputs, never reasoning authority.
- Project authority, Stable security, risk policy, freshness, and verification outrank provider output.
- No majority vote for truth.
- No hidden chain-of-thought persistence.
- Normal operation remains zero-local and cloud-first.
- FAST must preserve zero external routing calls and zero extra revision loops.
- STANDARD/DEEP may use bounded external workers after canonical routing.
- Trading, credential, destructive, financial, deployment, and other high-impact tasks retain existing hard gates.
- Secrets, API keys, private keys, credentials, and raw sensitive personal data must never be sent to a provider that is not explicitly approved for that data class.

The mesh therefore attaches after canonical routing, not before it.

## 3. Goals

1. Discover the current set of free/free-tier models dynamically rather than hard-code a permanent list.
2. Use provider health, quota, latency, reliability, capability fit, privacy policy, and cost status to choose workers.
3. Split only independent subproblems and execute them in parallel within Brain budgets.
4. Recombine outputs deterministically through schema normalization, conflict detection, and verification.
5. Put exhausted or unhealthy providers into cooldown and automatically return them to service after a verified reset/health recovery.
6. Deduplicate the same model family across providers so provider redundancy is not mistaken for reasoning diversity.
7. Prefer recurring free allocations; use limited trials and time-limited free endpoints only as opportunistic capacity.
8. Never circumvent quota, rate limits, geography, account restrictions, or provider abuse controls.
9. Preserve Stable availability when the mesh, discovery plane, or any provider fails.
10. Provide evidence-based telemetry so concurrency can be increased only when benchmarks show a real throughput gain without protected-regression loss.

## 4. Non-goals

- No IP rotation, account cycling, key farming, proxy hopping, or other quota circumvention.
- No attempt to make temporary free offers permanent.
- No unbounded fan-out to every available model.
- No provider majority vote as a truth mechanism.
- No autonomous widening of tool, repository-write, trading, wallet, credential, or production permissions.
- No requirement for a user-local OpenCode CLI, local MCP server, or local model runtime.
- No automatic Stable promotion of Class C/D changes.

## 5. Architecture

```text
user request
    |
    v
canonical task_router
    |
runtime profile + project authority
    |
exactly one primary skill + capsule
    |
    v
mesh eligibility gate
    |
    +-- ineligible/FAST/high-risk restricted --> normal Brain execution
    |
    v
bounded task graph
    |
independent subtask partitioner
    |
    +-------------------+-------------------+
    |                   |                   |
    v                   v                   v
worker selector A   worker selector B   worker selector C
    |                   |                   |
provider/model      provider/model      provider/model
    |                   |                   |
    +-------------------+-------------------+
                        |
                        v
                normalized result bus
                        |
                conflict detector
                  /           \
              clear         material conflict
                |                 |
                v                 v
              merge          verifier/checker
                  \           /
                    final synthesis
                        |
                Brain verification
                        |
                      answer
```

The mesh has two planes:

### 5.1 Stable execution plane

Used only after a request is routed. It consumes a last-known-good provider/model snapshot and never waits for provider discovery.

### 5.2 Evergreen discovery plane

Refreshes provider/model metadata outside the request path, quarantines candidates, checks policy/security/privacy/capability, benchmarks candidates, and promotes only validated provider adapters/model entries into the last-known-good snapshot.

Discovery failure must not break Stable execution.

## 6. Provider classes

Providers are grouped by economic and lifecycle semantics, not by marketing name.

### Class F1 — recurring free allocation

Preferred for routine free execution when policy and data class allow it.

Examples to verify continuously:

- Groq Free tier — published recurring rate limits and rate-limit/reset headers.
- Google Gemini Developer API Free tier — model-dependent free quota; daily request quota resets at midnight Pacific; free-tier data-use policy requires a conservative privacy classification.
- Cloudflare Workers AI Free allocation — published daily free allocation with daily reset.
- OpenRouter Free models/router — free-model pool with account-level daily request limits.
- Mistral Free mode — included monthly usage within account-specific limits.
- Cohere trial/evaluation keys — free limited usage with a recurring monthly API-call ceiling; evaluation semantics make this lower priority than production-capable recurring free providers.
- Hugging Face Inference Providers free monthly credits — very small recurring allowance, therefore emergency/niche tier only.
- NVIDIA Developer Program hosted NIM endpoints — free access for prototyping/development, rate limited and subject to trial/developer terms; not a production guarantee.

### Class F2 — provider-specific or time-limited free models

Useful opportunistically, but never relied on for continuity.

- OpenCode Zen free models discovered from `https://opencode.ai/zen/v1/models` and current pricing metadata.
- The current OpenCode Zen free set is explicitly time-limited and may change without notice.
- Privacy constraints differ by free model; several free endpoints may use collected data for model/product improvement and therefore must be restricted to non-sensitive workloads.

### Class F3 — trial/free-credit capacity

Useful for evaluation or burst fallback but not counted as recurring free capacity.

- Cerebras current public pricing describes a free trial/free credits while separate rate-limit documentation exposes a Free tier. The registry must treat Cerebras as `trial_or_policy_uncertain` until account/runtime verification resolves the current entitlement.
- Alibaba Cloud Model Studio gives time-bounded model-specific free quotas in eligible regions; these are not renewable permanent capacity and may be region-specific.

### Class Q — quarantine/uncertain

Any provider with contradictory pricing/limit documentation, unclear data policy, unresolved license/terms, or unverifiable account entitlement starts here.

SambaNova currently has official documentation that describes a no-payment-method Free Tier and published free rate-limit tables, while its current plan page language may imply purchased credits are required to run requests. It therefore starts in `Q` until runtime entitlement is verified on the actual account.

## 7. Initial provider evidence sources

The implementation must store evidence metadata, not just provider names. Bootstrap discovery should use first-party sources where possible.

- Groq rate limits: `https://console.groq.com/docs/rate-limits`
- Groq data policy: `https://console.groq.com/docs/your-data`
- Gemini rate limits: `https://ai.google.dev/gemini-api/docs/rate-limits`
- Gemini pricing/data-use notes: `https://ai.google.dev/gemini-api/docs/pricing`
- Cloudflare Workers AI pricing: `https://developers.cloudflare.com/workers-ai/platform/pricing/`
- OpenRouter free models: `https://openrouter.ai/collections/free-models`
- OpenRouter pricing/limits: `https://openrouter.ai/pricing`
- OpenCode Zen models/pricing/privacy: `https://opencode.ai/docs/zen`
- OpenCode providers: `https://opencode.ai/docs/providers`
- Mistral limits/free mode: `https://docs.mistral.ai/admin/billing-usage/usage-limits`
- Cohere trial rate limits: `https://docs.cohere.com/v1/docs/rate-limits`
- NVIDIA NIM developer access: `https://docs.api.nvidia.com/nim/docs/product`
- Hugging Face Inference Providers pricing: `https://huggingface.co/docs/inference-providers/pricing`
- SambaNova rate limits: `https://docs.sambanova.ai/docs/en/models/rate-limits`
- Cerebras rate limits: `https://inference-docs.cerebras.ai/support/rate-limits`
- Cerebras pricing: `https://www.cerebras.ai/pricing`
- Alibaba Model Studio free quota: `https://help.aliyun.com/en/model-studio/new-free-quota`

Provider documentation is evidence only. Runtime account entitlement and current API responses outrank stale docs when available.

## 8. Dynamic model registry

No request path may depend on a permanently hard-coded free model list.

Each model entry should normalize to a contract similar to:

```yaml
provider_id: string
provider_class: F1 | F2 | F3 | Q
model_id: string
model_family: string
endpoint_family: openai_compatible | anthropic_compatible | native | other
free_status: recurring | limited_time | trial_credit | account_specific | unknown
free_verified_at: timestamp
quota_scope: provider | account | project | model
quota_dimensions: [rpm, rpd, tpm, tpd, monthly_tokens, credits, neurons]
reset_semantics: rolling | minute | hour | daily | monthly | none | unknown
capabilities: [text, code, reasoning, vision, tool_calling, structured_output, long_context]
context_window: integer | unknown
privacy_class: public_safe | restricted | confidential_safe | unknown
data_training_allowed_by_provider: true | false | unknown
retention_policy: normalized string
usage_terms: prototyping | evaluation | production_allowed | unknown
health: healthy | degraded | cooldown | unavailable
latency_ema_ms: number
success_rate_ema: number
quality_scores: map
last_benchmark_at: timestamp
source_evidence: list
```

Unknown privacy, usage terms, or free status must fail closed for automatic promotion.

## 9. Model-family deduplication

The same underlying model can appear through multiple providers. The mesh must distinguish:

- `model_family`: reasoning diversity identity.
- `provider_id`: hosting/availability identity.

Example:

```text
gpt-oss-120b @ Groq
 gpt-oss-120b @ Cerebras
 gpt-oss-120b @ SambaNova
```

These are one model family with three possible serving paths, not three independent votes.

Provider redundancy may improve uptime and latency. It must not inflate confidence or count as independent epistemic evidence.

## 10. Eligibility and task decomposition

### 10.1 Mesh eligibility

The mesh is disabled for:

- FAST requests.
- requests whose primary skill does not benefit from parallel decomposition.
- tasks where provider privacy policy does not match data classification.
- credential/secret/private-key material.
- high-risk financial execution or wallet actions.
- any task for which external-provider execution is forbidden by existing authority.

### 10.2 Parallel decomposition

Split only when subproblems are independent or have explicit dependency edges.

Allowed example:

```text
repository bugfix
  -> reproduce/test research
  -> inspect relevant module A
  -> inspect relevant module B
  -> dependency/security check
```

Not allowed:

```text
worker A edits same file while worker B independently edits same lines
```

Repository mutations remain serialized through one implementation authority unless explicit isolated branches/worktrees and deterministic merge ownership are designed for that task.

## 11. Worker selection

Selection is score-based but policy-constrained.

Candidate filtering occurs before scoring:

1. capability compatibility
2. permission ceiling
3. data/privacy class
4. current health
5. current free entitlement
6. quota availability
7. context-window fit
8. task/provider usage terms

Then rank remaining candidates using a bounded score such as:

```text
score =
  capability_fit * Wc
+ measured_quality * Wq
+ reliability * Wr
+ quota_headroom * Wh
+ latency_score * Wl
+ diversity_bonus * Wd
- cooldown_penalty
- uncertainty_penalty
```

Cost is effectively zero only when the current entitlement is verified free. Unknown or paid state receives an infinite-cost exclusion when running in `FREE_ONLY` mode.

The weights are configuration, not reasoning authority, and must be benchmarked rather than guessed into Stable.

## 12. Quota-aware scheduler

The scheduler tracks provider/model quota state from:

- response headers when available,
- provider quota APIs when available,
- account limits metadata,
- known reset schedules,
- observed 429/403/quota responses.

State machine:

```text
AVAILABLE
  -> LOW_HEADROOM
  -> COOLDOWN_QUOTA
  -> PROBE_READY
  -> AVAILABLE

AVAILABLE
  -> DEGRADED
  -> CIRCUIT_OPEN
  -> HALF_OPEN
  -> AVAILABLE
```

A quota exhaustion event must never trigger IP rotation, project/account cycling, or other evasion. The provider enters cooldown until its legitimate reset/recovery condition.

Reset semantics should prefer provider-supplied headers over static schedules.

## 13. Concurrency policy

The existing DEEP hard limit is four parallel tasks. Initial rollout preserves that limit.

The mesh may have dozens of available models but at most the current Brain budget may be active concurrently.

Initial policy:

- FAST: 0 mesh workers.
- STANDARD: normally 1 worker; at most 2 independent workers when the existing profile budget permits.
- DEEP: 1–4 independent workers within the existing hard limit.
- verifier/checker consumes budget and must not create an unbounded extra fan-out.

Increasing the hard concurrency limit requires a separate benchmark-backed change showing:

- lower wall-clock latency or higher throughput,
- no protected-regression loss in correctness/security/authority/project isolation,
- acceptable provider throttling,
- no quota-collapse behavior,
- no material increase in conflict/merge failures.

## 14. Result contract and conflict prevention

Every worker result is normalized before synthesis.

Required metadata:

```text
task_id
subtask_id
input_hash
authority_revision
primary_skill_id
capsule_hash
provider_id
model_id
model_family
started_at
completed_at
latency_ms
quota_state_at_start
quota_state_at_end
source_refs
confidence_metadata
verification_status
```

Do not persist hidden reasoning.

Worker outputs should use typed task-specific result schemas whenever possible.

Conflict handling:

1. Syntactic/schema conflicts -> reject malformed output.
2. Permission conflicts -> fail closed.
3. Evidence conflicts -> prefer current authoritative evidence; otherwise escalate to verifier.
4. Code-change conflicts -> serialize ownership or isolate changes; never silently merge competing edits.
5. Unresolved material conflict -> disclose and block dependent high-consequence conclusions.

No silent averaging and no majority vote.

## 15. Privacy and data routing

Every request/subtask receives a data classification before provider selection:

- `PUBLIC`: public code/docs or non-sensitive prompts.
- `INTERNAL`: private but low-sensitivity project material.
- `CONFIDENTIAL`: credentials-adjacent, proprietary, personal, or sensitive material.
- `SECRET`: API keys, private keys, passwords, tokens, wallet seed material, or equivalent.

Rules:

- `SECRET` is never sent to free external model endpoints.
- `CONFIDENTIAL` is sent only to providers explicitly approved by policy for that class.
- `INTERNAL` may use providers with acceptable no-training/retention terms when verified.
- `PUBLIC` may use broader free pools, including endpoints that permit model-improvement use, subject to terms.

OpenCode Zen free models require per-model privacy handling. Current official Zen documentation states that several free models may use collected data for model/product improvement; such models are `PUBLIC` only unless future verified policy changes.

Gemini Free tier is also treated conservatively because current pricing/data-use documentation distinguishes free-tier product-improvement use from paid-tier privacy guarantees.

## 16. OpenCode integration role

OpenCode is an execution adapter and provider hub, not the Brain.

Permitted roles:

- discover OpenCode-supported providers/models,
- call OpenCode Zen free models when currently free and privacy-compatible,
- provide coding-agent execution where the routed primary skill authorizes it,
- expose provider/model metadata to the model registry.

Not permitted:

- replace `task_router`,
- become project authority,
- override Brain permissions,
- widen repository or runtime access,
- treat a Zen recommendation as truth authority.

Normal operation must not require the user to install OpenCode locally.

## 17. Health, telemetry, and reputation

Per provider/model track sanitized operational metrics:

- success/failure count,
- 429/403/5xx rate,
- latency p50/p95 EMA,
- timeout rate,
- schema-valid response rate,
- task-class benchmark score,
- verifier rejection rate,
- quota exhaustion frequency,
- cooldown duration,
- current free-status verification age.

Telemetry must not contain raw private prompts, secrets, credentials, private tool payloads, or hidden reasoning.

Reputation may rank equally authorized providers but can never override authority/security/privacy gates.

## 18. Discovery and promotion lifecycle

Candidate lifecycle:

```text
discovered
 -> quarantined
 -> normalized
 -> terms/privacy/provenance checked
 -> capability probed
 -> benchmarked
 -> canary eligible
 -> active free pool
 -> degraded/stale/reverify/deprecated
```

A model/provider can be removed automatically from the active free pool when:

- free pricing disappears,
- quota becomes zero/non-recurring,
- privacy/terms become incompatible,
- health is persistently bad,
- model is deprecated,
- provider returns payment-required state,
- benchmark quality falls below the task-class floor.

Promotion into active execution must follow existing harmonization and Evergreen gates.

## 19. Free-status freshness

Free status is time-sensitive state.

The registry should track `free_verified_at` and a provider-specific revalidation TTL. Stable execution uses the last validated snapshot but must avoid claiming a model is currently free when evidence is stale beyond policy.

Suggested initial TTLs for discovery metadata:

- OpenCode Zen / OpenRouter free catalogs: 6 hours.
- provider pricing/rate-limit docs: 24 hours.
- runtime account entitlement: 15–60 minutes where a cheap capability probe exists.

These values are starting points and must be benchmarked/adjusted through the implementation plan; they do not override existing Continuous Intelligence source-aging authority.

## 20. Failure handling

### Provider timeout

Retry only within bounded policy. Prefer another eligible provider/model rather than repeated retries.

### 429/quota

Read reset/retry metadata, enter quota cooldown, reschedule on another provider, and re-enable only after legitimate reset/probe.

### 401/403 entitlement

Disable the candidate for the current credential/account state. Do not attempt account/key rotation to bypass policy.

### Pricing changed

Immediately remove from `FREE_ONLY` routing until reverified.

### Discovery outage

Continue from the last known-good active model snapshot within freshness rules.

### All free capacity unavailable

Return explicit degraded status or use a separately authorized non-free/self-hosted fallback. Never silently incur cost.

## 21. Operating modes

### `FREE_ONLY`

Only providers/models with verified zero-current-cost entitlement may execute. If none are available, degrade explicitly.

### `FREE_PREFERRED`

Use free pool first; a paid fallback may run only if separately configured and authorized.

Initial implementation target is `FREE_ONLY` for the new mesh so no accidental charges occur.

## 22. Testing and evaluation

Implementation must include at least:

1. Registry schema validation.
2. Duplicate model-family tests.
3. Provider-free-status classification tests.
4. Quota/reset state-machine tests.
5. 429 retry/cooldown tests.
6. Payment-required fail-closed tests.
7. Privacy-routing tests.
8. Secret-redaction/secret-block tests.
9. Parallel task graph tests.
10. Same-resource mutation conflict tests.
11. Provider outage/circuit-breaker tests.
12. Deterministic result-normalization tests.
13. Conflict-escalation tests.
14. No-majority-vote protected regression tests.
15. FAST-path no-external-call regression tests.
16. STANDARD/DEEP concurrency-budget tests.
17. Benchmark comparison against the current single-provider baseline.
18. Validators and CI through the checkpoint-resolved canonical validation entrypoint.

Protected dimensions with zero tolerated regression:

- correctness,
- authority integrity,
- security,
- verification,
- project isolation,
- no-secret leakage,
- FAST latency contract.

## 23. Rollout plan

### Phase A — registry and read-only discovery

- Add provider/model metadata schema.
- Add free-status and privacy classification.
- Add dynamic discovery adapters.
- No execution routing change yet.

### Phase B — shadow scoring

- Score candidates against real routed task metadata without sending task content.
- Compare predicted provider choice, availability, and quota behavior.

### Phase C — canary execution

- Enable `PUBLIC` low-risk engineering/research subtasks only.
- Preserve existing concurrency limits.
- Require result schema + verifier where material.

### Phase D — bounded expansion

- Expand to other low-risk domains where capability/privacy are verified.
- Keep high-risk/financial/credential-sensitive exclusions.

### Phase E — concurrency tuning

- Benchmark 1, 2, 3, and 4-worker execution.
- Increase beyond current Brain hard limits only through a separately approved architecture change.

## 24. Likely implementation surfaces

Exact paths must be confirmed during implementation planning and test-first exploration. The design expects changes around:

- provider/model registry under `AI_SKILL_LIBRARY/`,
- checkpoint-resolved capability fusion / harmonization integration,
- cloud runtime provider adapters,
- provider health/quota telemetry,
- task graph execution in STANDARD/DEEP,
- validation/eval tooling,
- generated release manifest/snapshot artifacts through existing release tools.

Generated manifests, hashes, retrieval indices, and release history must be produced by canonical tools rather than edited manually.

## 25. Acceptance criteria

The feature is complete only when all are true:

1. The Brain can hold multiple free/free-tier providers and dynamically discovered model entries without adding a second reasoning authority.
2. Provider/model discovery is outside the Stable request path.
3. At least three independently hosted recurring free-capacity providers are validated end-to-end in the test/canary environment, subject to actual account entitlement.
4. OpenCode Zen dynamic discovery works without hard-coding its current free model list.
5. Model-family deduplication prevents duplicate-hosted models from being counted as independent reasoning votes.
6. Quota exhaustion causes cooldown/fallback rather than failure or circumvention.
7. A provider automatically becomes eligible again only after legitimate reset/health recovery.
8. `FREE_ONLY` cannot incur paid usage.
9. Secret/confidential routing tests pass.
10. Parallel execution never exceeds the current Brain concurrency budget.
11. Material conflicts are verified/escalated; no silent averaging or majority vote occurs.
12. FAST preserves zero external routing calls.
13. Stable still answers when Evergreen discovery is unavailable.
14. Existing Brain validators and the new mesh tests pass.
15. Production/runtime completion is not claimed until exact-SHA deployment and post-deploy verification required by the current checkpoint contract pass.

## 26. Design decision summary

Chosen approach: **Adaptive Free Model Mesh**.

Rejected alternatives:

- **All-model fan-out** — wastes quota, increases latency, amplifies conflicts, and provides false confidence when the same model family is hosted by multiple providers.
- **Pure sequential fallback** — robust but fails to exploit independent task parallelism and leaves throughput gains unused.

The selected design combines a large dynamic availability pool with small bounded active sets, explicit task dependencies, quota-aware scheduling, provider/model-family deduplication, privacy-aware routing, and Brain-owned verification.
