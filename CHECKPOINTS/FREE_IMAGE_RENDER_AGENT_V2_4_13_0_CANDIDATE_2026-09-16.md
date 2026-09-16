# Free Image Render Agent V2 4.13.0 — Candidate Closure Checkpoint

Date: 2026-09-16
Architecture: GITHUB_BRAIN_V4
Status: CANDIDATE / VALIDATION PENDING / NOT PRODUCTION KNOWN-GOOD
Target release: `4.13.0`
Previous known-good release: `4.12.0`
Pull request: `#396`

## Scope

Integrate Image Render Agent V2 into the existing Brain authority chain without creating a second router, a second reasoning authority, a paid route, or any new financial/trading execution authority.

- Preserve the V1 image routes for backward compatibility.
- Add bounded V2 batch orchestration for up to 100 scenes.
- Use concurrency 4 by default, bounded to 1–8, with at most 3 attempts per scene.
- Isolate failed scenes so one render failure cannot corrupt or fail unrelated completed scenes.
- Persist batch state in the dedicated `IMAGE_RENDER_BATCH` Durable Object binding using `ImageRenderBatchState`.
- Forbid the image batch runtime from using `TRADING_STATE`.
- Add V2 batch, status, cancel, retry and model-discovery HTTP surfaces under `/brain/image/*`.
- Add export/report metadata handoff without storing generated binary assets in Worker state.
- Keep the provider contract FREE_ONLY, with `paid_fallback=false`, `auto_purchase=false`, and unknown-cost routes rejected.
- Keep volunteer-provider execution restricted to explicitly `PUBLIC` data.
- Keep reference-image upload to the volunteer provider disabled.
- Preserve the existing task router, project authority order, Multi-Market research boundary, Bybit BTCUSDT production execution authority and financial runtime switches.

## Quality semantics

Image Render V2 exposes `STRUCTURAL` and `STRICT` quality profiles. A STRICT render without a real visual critic must finish as `complete_unverified`; the runtime must never claim visual verification that did not occur.

Creative reasoning may treat user/project reference assets as source-of-truth constraints, but the current FREE_ONLY volunteer provider is not permitted to receive those reference assets.

## Release integration

Brain release `4.13.0` pins the canonical Image Render V2 policy in the immutable release manifest. The retrieval index is rebuilt from the canonical builder and points HOT release metadata at 4.13.0 while retaining 4.12.0 as historical rollback evidence.

The candidate release remains `validated: false` and `known_good: false` until the exact PR head passes all required validation gates. `4.12.0` remains the previous known-good rollback target during candidate validation.

## Verification gates

Candidate promotion requires all of the following on the exact PR head:

1. `AI_SKILL_LIBRARY/v4/tools/ci_validate.py` passes, including all repository tests, release verification, retrieval-index freshness, Legion validation, Model Mesh validation and consolidation.
2. Cloudflare Worker checks pass, including all V1 and Image Render V2 suites.
3. Real Wrangler bundle dry-run passes with `IMAGE_RENDER_BATCH -> ImageRenderBatchState` and migration `image-render-batch-v1`.
4. Zero-Local, Skill-Mandatory Fast Gateway, Crypto Skill Registry and Cloudflare Research Runtime gates pass.
5. Any one-shot maintenance workflow used to regenerate deterministic metadata is removed before promotion.

Production known-good status is not asserted by this candidate checkpoint. After candidate promotion and merge, exact-main deployment and production smoke/canary evidence must still pass before production completion is claimed.

## Amendment: Image Agent V3/V4 multi-model mesh (same 4.13.0 candidate)

`4.13.0` was never promoted to production known-good (`known_good: false`; the
exact-main deploy gate has not passed), so the Image Agent V3 control plane and V4
quality plane extend this same open candidate rather than opening `4.14.0`. The
release history invariant requires the preceding release to be known-good before a
new version is cut.

Added under this candidate:

- **V3 control plane** — `ImageIntent` contract, provider mesh with hard eligibility
  gates applied before scoring (task capability, privacy class, reference safety,
  resolution, health, FREE_ONLY, known-zero cost, autoPurchase false), task-specific
  model ranking, model vault with license gates, and logical jobs whose user-facing
  scene count is bounded only by an operational safeguard while physical chunks stay
  at 100 scenes. Logical job state lives in its own `IMAGE_LOGICAL_JOB` Durable Object
  (`image-logical-job-state-v3`); the V2 physical batch keeps `IMAGE_RENDER_BATCH`.
- **V4 quality plane** — normalized visual critic decisions, candidate tournament,
  targeted repair planner, and a benchmark/evolution registry.
- **V1/V2 compatibility** — the V2 policy, agent runtime and creative-fusion runtime
  keys are preserved verbatim; V3/V4 fields are additive. The V1/V2 `/brain/image/*`
  routes are unchanged.

Boundaries unchanged by this amendment: FREE_ONLY with `paid_fallback=false` and
`auto_purchase=false`; AI Horde remains PUBLIC-only with reference uploads disabled;
reference work with no reference-safe free runtime fails closed to
`WAITING_FOR_SAFE_FREE_RUNTIME` rather than silently dropping the reference; STRICT
quality without a real critic still completes `complete_unverified`; the image
subsystem must not use `TRADING_STATE`; Bybit BTCUSDT production execution authority
is untouched.

Not asserted by this checkpoint: any production runtime availability for the V3/V4
planes, any reference-capable free GPU runtime, and any visual-critic runtime. The
model vault entries remain `CANDIDATE` with `runtimeConfigured: false`.

Previous closure record: `CHECKPOINTS/FREE_IMAGE_RENDER_AGENT_4_12_0_CANDIDATE_2026-09-16.md`.
