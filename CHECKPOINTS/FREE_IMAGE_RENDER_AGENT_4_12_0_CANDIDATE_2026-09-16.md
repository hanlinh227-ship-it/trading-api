# Free Image Render Agent 4.12.0 — Candidate Closure Checkpoint

Date: 2026-09-16
Architecture: GITHUB_BRAIN_V4
Status: CANDIDATE / NOT PRODUCTION KNOWN-GOOD
Target release: `4.12.0`
Previous known-good release: `4.11.1`
Pull request: `#385`

## Scope

Add one bounded image-generation execution capability to the existing Brain without creating a second router, second reasoning authority, or paid execution path.

- Register `image_render_agent` in the Legion as a non-authoritative creative executor.
- Add AI Horde as the first FREE_ONLY image provider using its documented anonymous access when no provider API key is configured.
- Add asynchronous submit/check/status/cancel endpoints under `/brain/image/*`.
- Reuse the existing authenticated Model Mesh execution token when a dedicated image-render token is not configured.
- Keep `paid_fallback=false`, `auto_purchase=false`, and reject unknown-cost paths.
- Require explicit `PUBLIC` classification before sending prompts to volunteer compute.
- Reject INTERNAL, CONFIDENTIAL and SECRET prompts and reject reference-image upload to the volunteer provider.
- Preserve the existing task router, project authority order, Trading authority and financial execution switches.

## Provider evidence and limitation

AI Horde publicly states that its service is free, community-powered, available anonymously, and that it will not introduce a paid tier or premium queue. This repository therefore treats AI Horde as a zero-monetary-cost provider while still failing closed if the provider becomes unavailable or its terms/cost model change.

No external provider can be technically guaranteed to exist forever. The enforceable repository invariant is stronger and precise: the image renderer must never silently switch to a paid route.

Anonymous AI Horde requests may be shared by the provider even when a client requests `shared=false`; therefore anonymous rendering is restricted to explicitly PUBLIC prompts and project reference assets are not sent.

## Verification gates

Candidate promotion requires all of the following on the exact PR head:

1. `AI_SKILL_LIBRARY/v4/tools/ci_validate.py` passes, including router, authority, runtime, release, retrieval-index, Legion, Model Mesh and repository tests.
2. `cloudflare-worker/npm run check` passes, including `test-image-render-agent.mjs`.
3. The release manifest is reproducible and the retrieval index is fresh.
4. The one-shot release bootstrap workflow is removed before the candidate commit is recorded.

Production known-good status is not asserted by this candidate checkpoint. It requires merge to `main`, exact-main deployment, production canaries and `FINAL_EXACT_SHA_GATE=PASS` before any later known-good promotion.

Previous closure record: `CHECKPOINTS/FINAL_HARDENING_4_11_1_2026-09-16.md`.
