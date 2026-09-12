# GitHub Brain Capability Fusion Design

## Goal
Upgrade GITHUB_BRAIN_V4 with faster retrieval/response paths and deeper bounded analysis by absorbing proven open-source patterns without introducing a second router, second authority chain, or mandatory local/runtime dependency.

## Authority model
The authority chain remains unchanged:

`request -> task_router -> runtime profile -> project authority -> primary skill -> capability plane -> sources/tools -> verification -> answer`

Upstream projects are evidence and design references only. They never become routing, project, security, trading, or truth authority.

## Capability fusion
The Stable plane gains a canonical `capability_fusion.yaml` contract with six capability families:

1. **Bounded execution graph** — state/checkpoint/resume and explicit graph transitions inspired by LangGraph, constrained by existing V4 replan/parallel budgets.
2. **Typed capability contracts** — schema-first input/output/tool contracts inspired by Pydantic AI; malformed or permission-expanding capability outputs fail closed.
3. **Context-engineered retrieval** — explicit normalize/filter/retrieve/rerank/dedupe/pack pipeline inspired by Haystack.
4. **Fast knowledge plane** — hybrid semantic/lexical index concepts inspired by Qdrant plus exact/semantic-cache concepts inspired by GPTCache. Cache can accelerate only safe non-fresh requests and never outranks authority or freshness.
5. **Selective memory** — retrieve-before-write, consolidation, supersession and scoped memory concepts inspired by Mem0 while retaining V4 privacy and authority rules.
6. **Eval and serving patterns** — regression/red-team/provider-matrix ideas inspired by Promptfoo; provider cooldown/fallback patterns inspired by LiteLLM; prefix/batching serving ideas inspired by SGLang only when self-hosting is explicitly enabled.

## Fast path
FAST must remain zero-external-routing-call and may not gain durable memory or project-state preload. Its allowed optimization path is:

`normalize -> exact safe cache -> semantic safe cache -> primary skill capsule -> answer`

Semantic cache reuse requires a high similarity threshold and a compatibility fingerprint covering primary skill, domain, authority revision and output contract. It is forbidden for live/current data, trading entry/execution, credentials, destructive actions, private connected-source content, deployment/runtime claims, or after authority/checkpoint/release changes.

## Standard/Deep retrieval
STANDARD and DEEP may use a pluggable knowledge index. Retrieval order is:

`normalize -> authority filter -> freshness filter -> lexical/semantic candidate retrieval -> metadata filtering -> rerank -> dedupe -> context pack`

An unavailable semantic index degrades to canonical lexical/source retrieval; it must never block Stable or fabricate knowledge.

## Execution graph
STANDARD permits one bounded checker revision when material. DEEP permits a bounded task graph with Maker/Checker and independent grader for high-impact/complex tasks. Durable graph checkpointing is scoped to resumable work artifacts only; hidden chain-of-thought is never persisted.

## Typed contracts
Every promoted skill/capability keeps explicit fields for domain, permissions, tools, sources, risk ceiling, input/output contract and capsule hash. Provider outputs must be normalized into this contract before execution. Schema failure or permission expansion fails closed.

## Memory
Memory remains subordinate to project authority and fresh verified state. Semantic retrieval can improve ranking, but durable writes still require reusable + verified + scoped + non-sensitive content. Contradictions create reverification/supersession, not majority voting.

## Evals
Promotion adds benchmark classes for routing, retrieval relevance, cache safety, authority preservation, adversarial prompt resistance, provider fallback, latency and answer quality. Protected dimensions remain zero-regression: correctness, verification, safety and authority.

## Upstream provenance
Approved reference sources with clear licenses are added to the source registry. No upstream repository is vendored and no code is copied into runtime as part of this upgrade. LiteLLM remains design-reference-only until its repository licensing is separately resolved because GitHub currently reports `NOASSERTION`.

## Runtime/dependency policy
No new package is required by production Worker for this release. Vector database, semantic cache backend and self-hosted serving are pluggable future adapters, default OFF. Zero-local cloud runtime is preserved.

## Trading boundary
Multi-market research can use the capability plane, but current Trading project authority and execution scope remain unchanged. Cache/memory never supplies live entry prices or execution decisions without fresh authoritative market data.

## Success criteria
- V4 has one canonical capability-fusion contract discoverable from checkpoint.
- FAST retains zero external routing calls and existing hard limits.
- Cache safety forbids freshness/high-impact classes.
- Semantic index is optional/fail-open-to-safe-retrieval, never authority.
- Memory remains scoped/private/authority-subordinate.
- Eval policy covers cache/retrieval/adversarial/latency regressions.
- Clear-license upstream sources are registered with training disabled.
- All V4/router/authority/Skill Gateway/source tests and CI remain green.
