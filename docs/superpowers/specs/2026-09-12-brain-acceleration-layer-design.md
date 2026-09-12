# Brain Acceleration Layer Design

## Purpose

Upgrade GITHUB_BRAIN_V4 with faster context selection, stronger typed skill contracts, bounded execution graphs, and regression-driven quality gates without introducing a second router, a second authority chain, or mandatory local infrastructure.

## Design principles

1. One Brain, one authority chain. External projects such as Qdrant, LangGraph, Pydantic AI, Haystack, Mem0, Promptfoo, LiteLLM, GPTCache and SGLang are pattern/evidence sources only.
2. Zero-local remains the default. No new database, model server, or daemon is required for the canonical runtime.
3. Fast-path work must stay deterministic and bounded. Cache/index results may select candidates but never outrank current project authority, security policy, fresh live data, or current runtime state.
4. High-impact conclusions remain fail-closed on unresolved material conflict.
5. Trading execution authority remains `docs/checkpoints/CURRENT_HANDOFF.md`; multi-market capability remains analysis/research only.

## Architecture

Canonical flow:

`request -> task_router -> acceleration_preflight -> runtime_profile -> project_authority_if_required -> primary_domain -> primary_skill -> typed_skill_capsule -> bounded_context_retrieval -> execution_graph_if_needed -> verifier/eval -> answer`

The acceleration preflight is advisory. It may return an exact-cache hit, semantic-index candidates, or provider/tool candidates. It cannot make factual claims, mutate project state, bypass authority, or execute financial/destructive actions.

## Acceleration policy

A new stable file `AI_SKILL_LIBRARY/v4/stable/acceleration.yaml` defines five capabilities.

### 1. Fast semantic retrieval

- exact normalized lookup first;
- semantic candidate retrieval second;
- lexical fallback when semantic infrastructure is unavailable;
- all retrieved items preserve provenance and revision metadata;
- fresh/live requests bypass answer caching;
- trading, credentials, destructive actions and deployment claims cannot reuse cached final answers.

The design is Qdrant-compatible but Qdrant is optional. The stable contract describes an adapter interface rather than making a vector database mandatory.

### 2. Typed skill contracts

Each skill capsule remains canonical. The acceleration layer requires explicit input/output contract identifiers, permission ceiling, freshness requirement, tool/source declarations and failure mode. This adopts typed-agent patterns without importing a competing agent runtime.

### 3. Bounded execution graphs

STANDARD may use one bounded maker/checker revision. DEEP may use a small dependency graph with maker, checker and independent grader when risk/complexity requires it. Graph execution must respect existing `max_parallel_tasks`, `max_replans`, authority and security ceilings.

### 4. Provider latency routing

Provider/tool routing may use latency, health, availability and capability fit as scheduling signals. Provider output remains evidence, never authority or a vote. Routing may not silently downgrade freshness, evidence quality, security or model/tool capability required by the task.

### 5. Eval and cache safety

Promptfoo/Pydantic-Evals/DeepEval-style ideas are absorbed into existing eval gates: deterministic regression cases, semantic quality checks, protected-task suites and promotion blocking on regression. Semantic caching is allowed only for low-risk reusable results and must invalidate on checkpoint, release, authority or source-revision changes.

## Profile behavior

FAST: no durable memory, no external semantic service requirement, deterministic exact/lexical index only, no execution graph, no answer cache for current/live requests.

STANDARD: bounded semantic retrieval if available, typed capsule enforcement, at most one maker/checker revision, optional work-cycle semantic cache.

DEEP: semantic retrieval plus bounded graph, checker, independent grader for high-impact/complex work, protected eval assertions and full evidence reconciliation.

## Harmonization contract

Future upstream upgrades must be normalized into one of these categories: retrieval/index, memory/context, orchestration/graph, provider routing, evaluation, inference serving, or cache. Equivalent capabilities strengthen the canonical acceleration policy instead of creating duplicate primary skills or parallel reasoning authorities.

## Failure handling

If semantic index/cache/provider router is unavailable, fall back to the existing stable deterministic path. If authority or freshness cannot be established, do not use cache as substitution. If an optimization changes a protected result, fail the candidate/promotion rather than weakening the protected contract.

## Validation

Regression tests must prove: acceleration policy exists; checkpoint resolves it; router places acceleration preflight before authority-dependent execution while authority still precedes memory; FAST remains tool-free and durable-memory-free; cache cannot store live/trading/credential/destructive final answers; provider routing cannot become authority; typed contracts and graph budgets remain bounded; current trading authority remains unchanged.

## Release

Because stable release files change, publish a new immutable V4 feature release manifest and update `v4/releases/current.json` only after validators and CI pass.