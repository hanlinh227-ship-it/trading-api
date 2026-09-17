# Image Runtime Activation Evidence — 2026-09-17

## Scope

Evidence for the final Image Agent V3/V4 runtime-activation gates. This document does not promote a model by itself. Runtime health and benchmark evidence remain empirical production gates.

## Production runtime evidence

Image Render production smoke on exact main `431b1dac6f34cfd565014e5b554594bbd937dec6` completed successfully in GitHub Actions run `35166593290`.

Observed runtime facts from that run:

- AI Horde model discovery: 8/8 listed models had live workers.
- Cloudflare Workers AI binding: discovered and baseline text-to-image request responded using `@cf/black-forest-labs/flux-1-schnell`.
- FREE_ONLY contract: `paidFallback=false`, `autoPurchase=false`.
- Exact deployed Worker SHA matched the expected main SHA.

The same run also exposed an evidence gap: provider-level Workers AI health was being reused for reference generation, inpainting and the visual critic even though those paths were not independently exercised. PR #409 replaces that with task-specific probes.

## Cloudflare Workers AI cost evidence

Official source:
https://developers.cloudflare.com/workers-ai/platform/pricing/

Workers Free includes 10,000 Neurons/day at no charge. Exceeding the Free allocation fails rather than automatically billing; usage beyond the allocation requires the Workers Paid plan. The image subsystem therefore treats allocation exhaustion as `WAITING_FOR_FREE_COMPUTE` and keeps paid fallback disabled.

## Cloudflare Workers AI data/privacy evidence

Official source:
https://developers.cloudflare.com/workers-ai/platform/data-usage/

Cloudflare documents Workers AI inputs and outputs as Customer Content, states that Customer Content is not made available to other Cloudflare customers, and states that Customer Content is not used to train Workers AI models or improve Cloudflare/third-party services without explicit consent. Storage occurs only when a storage product is explicitly used with Workers AI.

This is the evidence source used for the `cloudflare_workers_ai` privacy gate. It does not make AI Horde reference-safe; AI Horde remains PUBLIC-only.

## Model/runtime sources

### FLUX.1 Schnell

Cloudflare model page:
https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/

Provider model id:
`@cf/black-forest-labs/flux-1-schnell`

Role:
TEXT_TO_IMAGE / MULTI_SCENE_BATCH.

### Stable Diffusion 1.5 img2img

Cloudflare model page:
https://developers.cloudflare.com/workers-ai/models/stable-diffusion-v1-5-img2img/

Provider model id:
`@cf/runwayml/stable-diffusion-v1-5-img2img`

Role:
REFERENCE_GENERATION / IMAGE_EDIT_GLOBAL / STYLE_TRANSFER.

### Stable Diffusion 1.5 inpainting

Cloudflare model page:
https://developers.cloudflare.com/workers-ai/models/stable-diffusion-v1-5-inpainting/

Provider model id:
`@cf/runwayml/stable-diffusion-v1-5-inpainting`

Role:
INPAINT / IMAGE_EDIT_LOCAL / BACKGROUND_REPLACE / OBJECT_REPLACE / TARGETED_REPAIR.

### Llama 3.2 11B Vision Instruct

Cloudflare model page:
https://developers.cloudflare.com/workers-ai/models/llama-3.2-11b-vision-instruct/

Provider model id:
`@cf/meta/llama-3.2-11b-vision-instruct`

Role:
visual critic.

Important: Cloudflare documents an explicit Meta License / Acceptable Use Policy agreement requirement for this model. A successful visual-critic task probe is therefore required before the system may report the critic runtime as AVAILABLE. Merely having the Workers AI binding is not enough.

## Activation invariant

A model/task may only reach ACTIVE after:

`CANDIDATE -> RUNTIME_DISCOVERED -> HEALTH_VERIFIED -> LICENSE_VERIFIED -> PRIVACY_VERIFIED -> BENCHMARKED -> ACTIVE`

The benchmark gate uses the canonical default threshold:

- minimum samples: 10
- minimum average score: 85
- minimum verified rate: 0.80

An `ok:true` benchmark object without these thresholds is not promotion evidence.

## Remaining empirical work

After PR #409 deploys, production must run the task-specific probe and report separate evidence for:

- `TEXT_TO_IMAGE`
- `REFERENCE_GENERATION`
- `INPAINT`
- `VISUAL_CRITIC`

Only capabilities whose own task probe passes may read `AVAILABLE`.

After that, benchmark samples must be collected. No benchmark scores are fabricated or inferred from provider documentation.
