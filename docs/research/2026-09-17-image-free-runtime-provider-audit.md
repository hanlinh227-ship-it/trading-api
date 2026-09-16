# Image Agent V3/V4 — FREE Runtime Provider Audit

Date: 2026-09-17
Scope: cloud-only image inference for `GITHUB_BRAIN_V4` / Image Agent V3/V4.

## Admission rule

A provider/model runtime may become ACTIVE only when all of the following are evidenced:

- `monetaryCost = zero`
- `paidFallback = false`
- `autoPurchase = false`
- runtime health can be checked
- queue/rate-limit behavior is known
- privacy/data-class behavior is known
- reference assets are accepted only when the runtime is explicitly `referenceSafe=true`
- model/code/weights licensing is known and permitted by the Model Vault
- task capability is verified by benchmark, not inferred from a marketing model name

Unknown fields fail closed.

## Current decisions

### AI Horde

Decision: **ACTIVE for PUBLIC prompt-only generation only**.

Evidence already exists in the repository adapter:

- base API: `https://aihorde.net/api/v2`
- health: `/status/heartbeat`
- public volunteer queue
- anonymous operation supported by the current adapter
- no paid fallback in Image Agent policy

Restrictions:

- `supportedDataClasses = [PUBLIC]`
- `referenceSafe = false`
- user/private/reference assets MUST NOT be uploaded
- model availability remains dynamic

### Cloudflare Workers AI

Decision: **REJECT as FREE_ONLY frontier image runtime**.

Official pricing currently provides a daily free allocation, but usage beyond the free allocation requires Workers Paid. This conflicts with the requirement that the image subsystem never upgrades to or relies on a paid fallback.

Evidence:
- https://developers.cloudflare.com/workers-ai/platform/pricing/

May be reconsidered only if used behind a strict zero-cost quota gate that can provably fail closed before any paid usage. It must still satisfy model-quality and task-capability requirements.

### Hugging Face Inference Providers

Decision: **REJECT as FREE_ONLY production runtime**.

Free accounts receive small monthly credits and the service is otherwise pay-as-you-go. Free credits are not treated as a permanent zero-cost runtime.

Evidence:
- https://huggingface.co/docs/inference-providers/en/pricing

### Hugging Face ZeroGPU

Decision: **BLOCKED / candidate infrastructure, not ACTIVE**.

ZeroGPU is genuinely available free under account-dependent daily quotas and can host up to two ZeroGPU Spaces for qualifying free personal accounts. It is promising for private/self-controlled model hosting, but it is quota-limited and requires an actual account/Space deployment before runtime health, privacy, task support, and endpoint stability can be verified.

Evidence:
- https://huggingface.co/docs/hub/spaces-zerogpu

Requirements before activation:

1. Dedicated Space under a controlled account.
2. Exact model/revision from Model Vault.
3. Stable API contract tested from the Cloudflare control plane.
4. No automatic credit extension or paid hardware upgrade.
5. Explicit reference/private asset policy.
6. Health, queue and quota telemetry.
7. Benchmark PASS for the claimed task.

Until then: `WAITING_FOR_FREE_COMPUTE` / `WAITING_FOR_SAFE_FREE_RUNTIME`.

### Pollinations

Decision: **REJECT for direct ACTIVE registration; community zero-price models may be re-audited individually**.

The current unified API uses API keys and Pollen pricing for model usage. The model catalog also exposes community models whose owners can set a blank/zero price, but zero price must be verified per concrete runtime and privacy behavior is not automatically reference-safe.

Current docs also describe image edits and media storage; uploaded/generated media can have a lifecycle on `media.pollinations.ai`, so arbitrary user reference assets must not be treated as private by default.

Evidence:
- https://github.com/pollinations/pollinations
- https://github.com/pollinations/pollinations/blob/main/gen.pollinations.ai/src/docs/models.md
- https://github.com/pollinations/pollinations/blob/main/gen.pollinations.ai/src/docs/apidocs-recipes.md

Any future Pollinations community runtime must be registered as a distinct provider/model record with:

- exact zero-price evidence
- no paid fallback
- explicit data-class policy
- `referenceSafe=false` unless privacy/retention is independently verified
- live health and benchmark evidence

## Current production conclusion

At this checkpoint, **AI Horde remains the only runtime that can be kept ACTIVE without weakening FREE_ONLY requirements**, and only for PUBLIC prompt-only generation.

The higher-quality candidates in Model Vault (FLUX.2 Klein 4B, Qwen Image Edit, HiDream E1.1, Step1X Edit) MUST remain `CANDIDATE` until a real zero-cost cloud runtime is configured and benchmarked.

Do not claim ChatGPT/Flow parity from control-plane completion alone.
