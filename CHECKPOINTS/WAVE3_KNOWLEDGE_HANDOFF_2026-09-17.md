# Wave 3 Knowledge Handoff — Capability-Gap-Driven Local Model Expansion

Updated: 2026-09-17

## Scope

This is an additive knowledge handoff for the existing Personal AI / Open Model Universe pipeline.

It creates no Brain, router, runtime authority, admission authority, Model Mesh authority, activation, staging, or stable release mutation.

Canonical authority remains `GITHUB_BRAIN_V4`; `task_router` remains the sole routing authority; Model Mesh remains the sole model-selection layer; Claude local runtime remains runtime owner.

## Current prerequisite state

Before Wave 3 operational work begins, finish the current handoff actions:

1. re-run `PERSONAL_AI_BASELINE_001` against the strongest currently admitted measured model and freeze only on a genuine 12/12;
2. populate the capability index from verified digest-bound evidence only;
3. re-run `ai_core_release_gate.py`, `ci_validate`, and exact-head GitHub Actions;
4. do not start Trading.

Wave 3 knowledge may exist now, but operational staging/admission waits for those gates.

## Canonical Wave 3 knowledge manifest

`AI_SKILL_LIBRARY/v4/open_model_universe/wave3_knowledge_candidates.yaml`

The manifest is intentionally `KNOWLEDGE_ONLY_NOT_STAGED`.

## Candidate set

Wave 3 contains six discovery candidates chosen for complementary roles rather than model count:

| Candidate | Intended gap | Discovery state |
|---|---|---|
| `Qwen/Qwen3-8B-GGUF` | deeper reasoning, Vietnamese/multilingual, stronger generalist | discovery candidate; official GGUF and llama.cpp path exist |
| `Qwen/Qwen3-Coder-30B-A3B-Instruct` | coding/software-engineering specialist | resource-heavy; hardware and local artifact path must be proven |
| `openai/gpt-oss-20b` | reasoning/verifier/synthesis diversity | resource-heavy; backend and hardware must be proven |
| `microsoft/Phi-4-mini-instruct` | lightweight verifier, multilingual, fast-worker challenger | benchmark against existing Phi-3 before any active role |
| `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B` | reasoning/verifier lineage diversity | local artifact provenance and runtime compatibility required |
| `google/gemma-3-4b-it` | multilingual and future multimodal capability | HUMAN LICENSE GATE; never auto-acquire or auto-stage |

No public benchmark reputation is a capability score. These are discovery hypotheses only.

## Required operational sequence

When the prerequisite gates are green, Claude should continue on the existing branch and existing tools only:

`capability gap map -> candidate filtering -> immutable pin -> exact artifact identity -> license/provenance -> existing transport -> signature scan -> structural scan -> isolated real load -> real inference -> digest-bound benchmark -> admit/quarantine -> Model Mesh evidence eligibility -> residency recompute -> federation recheck -> observer rerun`

A candidate that cannot run on the existing supported backends is not force-admitted. Record it as `RESOLVED_INCOMPATIBLE` or `QUARANTINED_WITH_ACTIONABLE_GAP` with exact evidence.

## Selection rule

Do not blindly process all six candidates. First compare the measured current fleet against the target capabilities in the Wave 3 manifest. Only stage candidates that fill a measured gap or provide measurable redundancy/reliability value.

Prefer a small useful fleet over duplicate models.

## Human-only gates

Do not accept a model license or gated repository terms on behalf of the operator. In particular, Gemma remains knowledge-only until the operator explicitly accepts the required license terms.

## Exit condition

Wave 3 model/runtime work is complete when:

- every processed candidate has a truthful terminal state;
- every AVAILABLE model has digest-bound security, runtime, inference, capability, latency and resource evidence;
- Model Mesh eligibility is derived only from measured evidence;
- residency and federation are recomputed from measurements;
- observer actionable model/runtime gaps return to zero;
- exact-head validation remains green;
- no architecture authority or permission boundary was widened.

Wave 3 completion does not authorize Trading.
