# Adaptive Generalist Brain vNext — Design Draft

> **Status: DRAFT / NOT APPROVED / NOT IMPLEMENTED.**
> Recorded separately from the Model Mesh production stabilization work so the
> remediation change set stays reviewable on its own. Nothing here may be built
> until Model Mesh is production-verified `KNOWN_GOOD = YES` and this design has
> passed the checkpoint-resolved harmonization gates.

## 1. Goal

Any request -- research, coding, analysis, design, artifact generation,
automation, multi-domain reasoning -- routes itself to the capability that can
actually serve it, without the caller naming a model, a provider or a profile.

## 2. Invariants that do not move

These are inherited from the current Brain and are not open for renegotiation
by anything in this document.

| Invariant | Meaning for vNext |
|---|---|
| GitHub Brain is the single authority | Every capability added below is a worker or an evidence source. Routing and reasoning authority stay `false` on every external result, as `model-mesh-runtime.js` enforces today. |
| No majority vote | Disagreement escalates to a checker or surfaces as an unresolved conflict. Averaging or counting provider opinions stays forbidden. |
| Family dedupe | N agents from one model family are one reasoner, not N. Already enforced in `selector.js`; vNext must preserve it across a larger agent pool. |
| FAST stays fast | Zero external calls, zero KV reads, zero preload. Any vNext feature that cannot honour this is not available on FAST. |
| STANDARD is minimal | Use the fewest workers that answer the question, not the configured maximum. |
| DEEP scales out | Parallel fan-out bounded by the compiled policy. |
| Provider failure is not Brain failure | Verified by the graceful-zero contract; vNext must keep it under a larger capability surface. |
| Cloud-first / zero-local | No feature may require a local install. |
| FREE_ONLY core | No paid fallback, no auto-purchase. |
| TinyFish and every evidence provider is OPTIONAL | Cost-gated, never a hard dependency. |

## 3. Components (each needs its own spec before implementation)

### 3.1 Capability-based routing
Route on required *capability* (long-context synthesis, code generation,
structured extraction, vision, tool use), not on provider identity.
`domain_capabilities.yaml` becomes a real input to selection rather than
documentation. Builds directly on the `selectionRejection` filter chain now in
`contracts.js`, which already reports which filter rejected a model.

### 3.2 Domain Skill Registry
One canonical owner per capability, aliases fold in at compile time. Extends
the existing skill catalog rather than introducing a parallel registry --
adding a second authority is the specific failure mode the current
harmonization rules exist to prevent.

### 3.3 Dynamic free model discovery
Evergreen discovery proposes candidates; promotion to the active registry stays
gated by FREE_ONLY verification, `usage_terms`, privacy class, and a live probe.
Discovery may never widen eligibility on its own -- it proposes, the promotion
gate decides.

### 3.4 Adaptive parallel execution
- **Latency budgets** per profile; a worker that misses its budget is dropped
  from the round, not waited on.
- **Early exit** once the maker and checker agree and the confidence bar is met.
- **Speculative parallel execution** for DEEP only, bounded by the compiled
  `max_parallel`, with speculative results discarded rather than merged.
- **Pre-warming** limited to snapshot/contract warmup. It may not pre-spend
  provider quota, which would reintroduce the 429-on-every-probe failure this
  remediation just fixed.

### 3.5 GPT-OSS Agent Legion
Multiple agents over open-weight models, family-deduplicated before they count
as independent verification. Two agents on the same base model are one opinion.

### 3.6 Multi-family verification
Verification requires genuinely independent families. Where only one family is
live, the result is reported as single-family and unverified rather than
presented as cross-checked.

## 4. Open questions to resolve before any implementation

1. How is "capability" verified rather than declared? A registry claim is not
   evidence; the current mesh learned this the hard way with a model id that
   404s (`gemini_developer_api`).
2. What is the confidence bar for early exit, and how is it measured without
   becoming a disguised majority vote?
3. Does speculative execution respect free quota at DEEP fan-out, given that
   probe cadence alone already exhausted two providers' free tiers?
4. How does the health model scale from 6 models to a dynamic pool without the
   KV read amplification already noted on `/brain/mesh/health`?
5. Where does per-viewer or per-request state live, given Workers KV offers no
   compare-and-set (the concurrent-write limitation documented in
   `health-store.js`)?

## 5. Explicit non-goals

- No change to trading execution authority.
- No paid provider tier, under any latency or quality argument.
- No second reasoning authority, no matter how capable an external model is.
