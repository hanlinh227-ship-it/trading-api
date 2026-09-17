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

## Amendment: execution continuity and the reference-safe render path (2026-09-17)

The V3 control plane selected a provider correctly and the selection was then
discarded. The logical job compiled a physical manifest carrying only a prompt,
a negative prompt and a target size; the task type, privacy class, reference
assets, source image, mask and the selected provider were all dropped, and the
manifest's data class was hardcoded `PUBLIC`. The physical batch, given nothing
to honour, selected a provider of its own and preferred AI Horde. Cloudflare
Workers AI had no executable adapter at all, so the reference-safe route had no
execution path in either direction. Reference, edit and inpaint work therefore
could not run, and what did run was routed to a volunteer provider that must
never receive a reference image.

Changed under this candidate:

- **Routing continuity.** The physical manifest carries the compiled intent, the
  task type, the privacy class, the reference assets, the source image, the
  mask, the background constraints, the preserve/editable regions and the
  selected provider and model. Its data class is the strictest class among the
  scenes it carries, never a fixed value.
- **Route honouring.** The physical batch executes the route it was given. A
  manifest with no recorded route may fall back to the registry default only
  when it is prompt-only and `PUBLIC`; anything image-bound or above `PUBLIC`
  fails closed with `reference_route_lost`. `AI_HORDE` is never reachable for
  reference, edit or inpaint work.
- **Executable reference-safe runtime.** Cloudflare Workers AI is now an
  executable provider. It is synchronous -- the Worker's own AI binding returns
  the image on the same call -- so submissions settle in place rather than
  waiting for a provider-side job that does not exist. It is handed out only
  when the `AI` binding is actually present.
- **Model chains.** Each task walks an ordered list of image-capable Workers AI
  models rather than depending on one. Only models whose licence is audited in
  the model vault may run; SDXL 1.0 base (CreativeML Open RAIL++-M) is added as
  the audited fallback for the img2img and inpainting routes. Every rejected
  candidate is retained as diagnostic evidence.
- **Visual critic.** The critic runs on the produced bytes when its runtime is
  present, and the image is passed in the form Workers AI vision models accept.
  Without a critic the quality layer still reports `PASS_UNVERIFIED`.
- **Targeted repair.** A critic verdict naming a fixable fault produces a repair
  attempt that edits the image the previous attempt produced, subject to the
  caller's `destructiveRedrawAllowed`. Local masked repair is not claimed: there
  is no segmentation runtime here, so the planner falls back instead.
- **Wait states.** An exhausted free allocation surfaces as
  `WAITING_FOR_FREE_COMPUTE`. A reference-safe runtime that rejects every model
  it has surfaces as `WAITING_FOR_SAFE_FREE_RUNTIME` rather than as a failed
  scene, so the reference is kept and the work waits.

### Amended boundary: rendered binary assets

The original V2 boundary -- export/report metadata only, no generated binary in
Worker state -- was written when the only provider was AI Horde, which returns a
hosted URL. A synchronous first-party runtime returns bytes and no URL, so that
boundary made a real render unrepresentable.

Rendered bytes are now held in the render batch's own Durable Object storage,
keyed to the attempt that produced them, and served from it through
`/brain/image/v3/assets`. They live and die with the batch, are never written to
`TRADING_STATE`, and no new storage product, vendor or paid dependency is
introduced. This is the amendment that lets a caller receive the image rather
than only a status.

### Unchanged boundaries

FREE_ONLY with `paid_fallback=false` and `auto_purchase=false`; no new paid
service and no auto-purchase; AI Horde stays `PUBLIC`-only with reference
uploads disabled; STRICT quality without a real critic still completes
`complete_unverified`; the image subsystem still does not use `TRADING_STATE`;
Bybit BTCUSDT production execution authority and the trading project authority
are untouched.

### Verification

Production runtime availability for the reference-safe render path is **not**
asserted by this amendment. Production smoke now submits Scene 1 -- two locked
character references plus a locked background, `CONFIDENTIAL`, through the
canonical V3 job path -- fails outright if the volunteer provider is reached,
and reports either a real rendered asset or an explicit wait state. Each task
probe now prints its sanitized diagnostic and every model it rejected. Model
vault entries remain `CANDIDATE`; no benchmark evidence is fabricated.
