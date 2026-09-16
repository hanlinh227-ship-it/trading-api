# Image Render Agent V2 — Adaptive Batch + Quality Loop + Consistency Engine

Date: 2026-09-16
Status: Approved design, implementation not started
Authority: GITHUB_BRAIN_V4
Canonical repository: hanlinh227-ship-it/trading-api

## 1. Goal

Upgrade the existing FREE_ONLY image render agent so the user can issue one natural-language render command such as:

> Render scene 1–30 from these prompts, one 16:9 image per scene, keep Max consistent, vary camera angles, automatically retry failed images, then package the final results.

The system must translate that command into a render manifest, execute many image jobs safely and concurrently, verify output quality, retry failures within bounded limits, and return organized results without requiring the user to manually call APIs, choose models, manage queues, or split jobs.

This upgrade is a system capability change only. The upgrade process itself must not render images except later implementation smoke tests using explicit PUBLIC test prompts.

## 2. Non-negotiable invariants

1. FREE_ONLY remains mandatory.
2. `paid_fallback` remains false.
3. `auto_purchase` remains false.
4. Trial or promo credit must never be treated as a paid fallback path.
5. GITHUB_BRAIN_V4 remains the routing and reasoning authority.
6. `image_render_agent` remains a specialist executor, not a routing authority.
7. Existing single-image endpoints remain backward compatible.
8. User constraints and project authority override inferred render preferences.
9. No silent addition or removal of subjects.
10. No unbounded retry loops.
11. No hidden permission expansion.
12. No external image-generation framework becomes system authority.
13. Prompt-driven batch rendering is the V2 core requirement.
14. Reference-image support, if added later, must be explicit and policy-gated.
15. Image batch state must not be stored in trading-specific state.

## 3. Current limitations

The current agent has:

- one provider path: AI Horde;
- prompt-only execution;
- at most 4 images per provider request;
- no first-class multi-scene batch object;
- no dynamic model ranking using live model/worker status;
- no durable scene-level batch state;
- no concurrency manager;
- no visual QA loop wired into execution;
- no automatic retry strategy based on failure category;
- no structured manifest/report/export flow.

Creative continuity and render-quality concepts already exist in Brain policy, but they are not yet connected to image execution.

## 4. Target architecture

User chat command
→ task_router
→ image command interpretation
→ typed batch request
→ render manifest compiler
→ prompt compiler
→ consistency engine
→ adaptive model router
→ durable batch coordinator
→ provider adapter(s)
→ render result collector
→ quality critic
→ bounded retry/repair loop
→ result packager/export adapter
→ final batch result

The design keeps one authority chain. New modules live under `image_render_agent` and do not create a parallel router or creative brain.

## 5. Command interpretation

Natural-language interpretation remains a Brain responsibility. The user can write instructions such as:

- "render 20 ảnh theo prompt này"
- "scene 1 đến 30, mỗi scene một ảnh"
- "giữ Max giống nhau ở tất cả scene"
- "ảnh ngang 16:9"
- "camera các scene liền nhau không trùng"
- "render lại scene 7"
- "ảnh lỗi thì tự render lại"
- "xong nén zip"

Brain converts the instruction into `image_render_batch_request_v2`; the Worker runtime validates and executes the typed request. The Worker must not implement a second free-form LLM router.

## 6. Render manifest

Each logical batch contains:

- `batch_id`
- `created_at`
- `data_class`
- `user_instruction`
- `quality_mode`
- `consistency_mode`
- `output_format`
- `global_constraints`
- `shared_character_state`
- `shared_style_state`
- `scenes[]`
- `scheduler_config`
- `retry_policy`
- `qa_policy`

Each scene contains:

- `scene_id`
- `original_prompt`
- `compiled_prompt`
- `negative_prompt`
- `dimensions`
- `aspect_ratio`
- `seed_strategy`
- `model_candidates`
- `expected_subject_count`
- `locked_identity_facts`
- `locked_wardrobe_facts`
- `locked_environment_facts`
- `camera_constraints`
- `continuity_inputs`
- `status`
- `attempts[]`

Each attempt records:

- attempt number
- provider
- model
- seed
- prompt hash
- dimensions
- submit/complete timestamps
- provider job ID
- queue/wait time
- generation state
- QA level
- QA result
- QA reasons

## 7. Prompt Compiler

The compiler transforms the user prompt into render-ready form while preserving intent.

Compilation layers:

1. explicit subject facts
2. action
3. environment
4. composition
5. camera
6. lighting
7. visual style/materials
8. identity/wardrobe/environment locks
9. anatomy/deformation guards
10. negative constraints
11. output constraints

It must not silently substitute characters, wardrobe, props, environments, counts, actions, or requested camera behavior.

## 8. Consistency Engine

The engine preserves recurring state across scenes:

- character identity
- fur/hair/skin colors
- face shape
- body proportions
- wardrobe
- accessories
- recurring props
- environment family
- world style
- time of day
- light direction
- palette
- seed family

Modes:

- `STRICT`: stronger identity/wardrobe/environment locking.
- `FLEXIBLE`: keeps identity but allows more scene variation.

`STRICT` is selected when the user's instruction means "giữ nhân vật", "đúng ref", "không thay đổi nhân vật", or equivalent intent.

Prompt-only consistency improves repeatability but cannot guarantee reference-level identity. The system must not claim exact identity matching unless a policy-approved reference-conditioning path is actually used.

## 9. Adaptive Model Router

The router retrieves live AI Horde model status and ranks candidate models using:

`score = task_fit + live_availability + performance + batch_quality_history - queue_penalty - failure_penalty`

Inputs include:

- active worker count
- live ETA/queue
- performance
- model family/baseline when known
- style/task suitability
- success/failure statistics accumulated within the current batch

V2 core does not require a new global model-history database. Cross-batch quality history may be added later.

Rules:

- do not rely on provider default model selection for production multi-scene jobs;
- prefer task-appropriate models;
- prefer a comparable lower-queue free model when the best candidate is heavily delayed;
- record selected model and routing reason;
- all fallback routes remain FREE_ONLY.

## 10. Durable Batch Coordinator

A multi-scene batch can outlive a single Cloudflare Worker request. Therefore V2 uses a dedicated Durable Object binding:

- binding: `IMAGE_RENDER_BATCH`
- class: `ImageRenderBatchState`
- one Durable Object instance per `batch_id`
- SQLite-backed class migration, matching the repository's existing Durable Object deployment pattern

The Durable Object owns:

- manifest persistence
- scene state transitions
- active provider-job references
- concurrency counters
- retry queue
- cancellation state
- resumable progress

Image batch state must not use `TRADING_STATE` and must not modify financial/trading runtime state.

The batch coordinator may use Durable Object alarms for bounded continuation/polling. This is image-job lifecycle orchestration only; it does not create autonomous Brain or financial cron behavior.

## 11. Batch Scheduler

Initial operational defaults:

- maximum logical scenes per batch: 100
- default active provider jobs: 4
- adaptive concurrency ceiling: 8
- maximum total attempts per scene: 3
- provider request size: provider-specific; current AI Horde adapter remains max 4 images/request

Adaptive behavior:

- reduce concurrency on provider pressure/failures;
- refill worker slots as scenes complete;
- continue other scenes when one scene fails;
- support cancellation;
- preserve already completed scenes on resume.

Example:

30 scenes
→ 30 scene tasks
→ 4 active initially
→ increase up to 8 if provider health permits
→ completed slot starts next queued scene
→ QA failure enters bounded retry queue

## 12. Quality Critic

The critic checks:

- image decode/format validity
- censor state
- prompt fidelity
- expected subject count
- identity consistency
- wardrobe consistency
- scene continuity
- object count
- anatomy/deformation risk
- duplicated subjects/objects
- background correctness
- explicit camera constraints
- text/watermark presence when forbidden

It emits:

- `PASS`
- `RETRY_PROMPT`
- `RETRY_MODEL`
- `RETRY_SEED`
- `FAIL_TERMINAL`

plus structured reasons and `qa_confidence`.

### QA levels

`STRUCTURAL`
- metadata, provider state, prompt/manifest invariants, dimension/format checks.

`VISUAL`
- routes the generated image through an existing FREE_ONLY vision-capable model-mesh path or approved visual-review capability.
- must not create a new reasoning authority.

`STRICT` quality mode requires VISUAL QA before a scene may be reported as quality-verified. If no verified free vision critic is available, the scene must be marked `complete_unverified` or retried according to policy; it must not be falsely reported as fully verified.

This prevents metadata-only checks from declaring obviously malformed images "good".

## 13. Retry and Repair Loop

Default maximum: 3 total attempts per scene.

Attempt 1:
- highest-ranked free model + compiled prompt.

Attempt 2 after quality failure:
- targeted prompt repair preserving all locks;
- new seed;
- keep model unless failure indicates model mismatch.

Attempt 3:
- next ranked free model + repaired prompt + new seed.

After the maximum:
- `failed_quality` or `failed_provider`;
- other scenes continue;
- final report identifies the failure.

No infinite retry loop is allowed.

## 14. Result Packager and ZIP export

The runtime always produces logical output metadata:

```text
render_batch_<batch_id>/
  Scene_01.webp
  Scene_02.webp
  ...
  render_report.json
  manifest.json
```

`render_report.json` includes:

- batch status
- total/passed/failed scenes
- provider requests
- model usage
- seeds
- retries
- QA levels/results
- failure reasons
- FREE_ONLY confirmation
- monetary image-provider cost: zero

V2 core must not add a paid object-storage dependency merely to create ZIP files.

Therefore ZIP delivery is implemented through a pluggable export adapter:

- runtime returns validated generation URLs plus manifest/report;
- an approved caller/export layer may fetch and stream/package them into a ZIP;
- no asset is silently copied into paid storage;
- if an optional persistent storage backend is added later, it requires a separate FREE_ONLY/cost-policy review.

The user experience can still be one command; packaging mechanics remain hidden from the user.

## 15. API surface

Existing endpoints remain compatible:

- `GET /brain/image/health`
- `POST /brain/image/render`
- `GET /brain/image/check`
- `GET /brain/image/status`
- `DELETE /brain/image/status`

V2 adds:

- `POST /brain/image/batch`
- `GET /brain/image/batch/status?id=<batch_id>`
- `DELETE /brain/image/batch?id=<batch_id>`
- `GET /brain/image/models`
- `POST /brain/image/retry`

`POST /brain/image/batch` returns `batch_id`, accepted scene count, mode `FREE_ONLY`, and status endpoint.

`GET /brain/image/batch/status` returns aggregate and scene-level states.

`DELETE /brain/image/batch` cancels queued work and requests active provider-job cancellation where supported.

`GET /brain/image/models` returns normalized live free-model data and routing metadata.

`POST /brain/image/retry` retries selected failed scenes under the same locks.

## 16. State model

Batch states:

- queued
- running
- partially_complete
- complete
- complete_with_failures
- cancelled
- failed

Scene states:

- queued
- submitting
- provider_wait
- provider_processing
- qa_pending
- retry_pending
- complete
- complete_unverified
- failed_quality
- failed_provider
- cancelled

State transitions must be idempotent enough that a resumed batch does not duplicate already-complete scene outputs.

## 17. Provider strategy

AI Horde remains the first execution provider because it is already integrated and verified.

V2 introduces a provider-neutral adapter interface:

- `health`
- `listModels`
- `submit`
- `check`
- `status`
- `cancel`

Additional providers can be added later only when cost semantics are verified and the route is FREE_ONLY-safe.

## 18. Reference-image extension point

Reference images are not required for the core V2 prompt-and-command batch upgrade.

The architecture reserves extension points for:

- img2img
- remix
- inpainting
- outpainting
- future identity conditioning

Because AI Horde volunteer infrastructure may expose submitted assets to community workers, reference images remain disabled by default until a separate policy explicitly defines allowed data classes and opt-in behavior.

## 19. Security and privacy

- Explicit data class remains required.
- AI Horde execution remains PUBLIC-only unless separately changed.
- INTERNAL, CONFIDENTIAL, and SECRET fail closed for volunteer execution.
- Execution tokens remain required.
- Provider responses cannot widen permissions.
- Generation URLs are treated as untrusted external assets and validated before fetch/export.
- Batch IDs are generated server-side and validated.
- Prompt size, batch size, and concurrency are bounded.
- No hidden chain-of-thought is persisted.

## 20. Observability

Structured events:

- batch_created
- scene_submitted
- scene_completed
- scene_retry
- scene_failed
- model_selected
- provider_error
- batch_completed
- batch_cancelled

Metrics:

- provider queue time
- provider processing time
- scene wall-clock time
- retry count
- per-batch model success/failure rate
- QA failure categories
- current concurrency

## 21. Failure handling

Provider unavailable:
- mark degraded;
- bounded backoff;
- lower concurrency;
- use another verified free provider only if one exists;
- never use a paid route.

Model unavailable:
- select next ranked free model.

One scene fails:
- continue the batch;
- report partial success.

Worker/process restart:
- resume from Durable Object state;
- do not resubmit completed scenes.

Malformed batch:
- reject before provider submission.

Vision critic unavailable in STRICT mode:
- do not claim full visual verification;
- mark `complete_unverified` or retry according to configured policy.

## 22. Backward compatibility

`POST /brain/image/render` continues to support the current single-image contract.

Internally, V2 may eventually treat one image as a one-scene batch, but external compatibility must be preserved unless a versioned response is explicitly requested.

Existing FREE_ONLY, auth, privacy, and provider rules remain valid.

## 23. Testing strategy

### Unit tests

- manifest validation
- prompt compilation
- consistency merge rules
- model ranking
- concurrency bounds
- retry transitions
- batch/scene state transitions
- Durable Object idempotency
- FREE_ONLY guard
- privacy/data-class guard
- provider adapter normalization
- structural QA rules
- STRICT visual-QA fallback behavior

### Integration tests with mocked providers

- 20-scene batch
- 100-scene manifest validation
- partial provider failure
- model unavailable fallback
- QA retry
- cancellation
- Durable Object resume
- duplicate-completion prevention
- backward-compatible single-image request
- ZIP/export manifest handoff

### Production smoke tests after implementation tests pass

- image health
- live model list
- one small PUBLIC single-image render
- one small PUBLIC multi-scene batch

Smoke tests must not use private user reference assets.

## 24. Expected implementation files

Likely existing files:

- `cloudflare-worker/image-render-handler.js`
- `cloudflare-worker/image-render/ai-horde.js`
- `cloudflare-worker/index.js`
- `cloudflare-worker/prepare-wrangler.mjs`
- `cloudflare-worker/wrangler.example.jsonc`
- `AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml`
- `AI_SKILL_LIBRARY/v4/legion/agents.yaml`
- `AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml`

Likely new focused modules:

- `cloudflare-worker/image-render/batch-state.js`
- `cloudflare-worker/image-render/batch-manager.js`
- `cloudflare-worker/image-render/model-router.js`
- `cloudflare-worker/image-render/render-manifest.js`
- `cloudflare-worker/image-render/prompt-compiler.js`
- `cloudflare-worker/image-render/quality-policy.js`
- `cloudflare-worker/image-render/provider-registry.js`
- `cloudflare-worker/image-render/export-contract.js`

Likely new Durable Object:

- `ImageRenderBatchState`
- binding `IMAGE_RENDER_BATCH`
- a new SQLite Durable Object migration tag

Final filenames may be adjusted to existing repository conventions during implementation planning.

## 25. Acceptance criteria

The upgrade is accepted only when:

1. One natural-language user instruction can become one typed batch request.
2. One command can represent at least 20 independent scene renders.
3. The logical API accepts up to 100 scenes under bounded policy.
4. Batch state survives beyond one Worker request using a dedicated Durable Object.
5. Scheduler runs multiple scenes concurrently with a bounded ceiling.
6. Live free models are ranked dynamically.
7. Every scene records provider, model, seed, job ID, attempt count, and QA result.
8. Failed scenes retry automatically up to the limit.
9. One scene failure does not terminate the rest of the batch.
10. Character/wardrobe/environment locks are preserved during prompt repair.
11. STRICT mode never reports metadata-only QA as full visual verification.
12. Batch status is queryable at aggregate and scene level.
13. Cancellation works.
14. Resume does not duplicate completed scene results.
15. Manifest/report are exportable and ZIP packaging can be performed without adding an unreviewed paid storage dependency.
16. Existing single-image API remains compatible.
17. All generation routes remain FREE_ONLY.
18. There is no paid fallback or auto-purchase path.
19. Private reference assets are not sent to volunteer providers by default.
20. Core scheduler, retry, routing, Durable Object, policy, QA, and compatibility paths are covered by tests.

## 26. Explicitly out of scope for V2 core

- building/hosting a custom GPU cluster;
- paid image APIs;
- unlimited concurrency;
- training a custom Max model;
- automatic publication of private reference assets;
- video generation;
- replacing GITHUB_BRAIN_V4 routing authority;
- rewriting the entire creative skill system;
- adding persistent paid asset storage.

## 27. Implementation principle

Prefer small focused modules with validated contracts. Reuse existing canonical creative logic rather than duplicating it.

Target user experience:

> User gives one render instruction. Brain interprets it. Image Render Agent V2 compiles the batch, chooses suitable free models, executes scenes concurrently, performs quality checks, retries failures, and returns organized results.

The user should not need to manually manage model names, provider queues, API calls, retries, or scene-by-scene execution.