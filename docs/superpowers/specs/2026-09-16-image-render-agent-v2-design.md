# Image Render Agent V2 — Adaptive Batch + Quality Loop + Consistency Engine

Date: 2026-09-16
Status: Approved design, implementation not started
Authority: GITHUB_BRAIN_V4
Canonical repository: hanlinh227-ship-it/trading-api

## 1. Goal

Upgrade the existing FREE_ONLY image render agent so a user can issue a natural-language render command such as:

> Render scene 1–30 from these prompts, one 16:9 image per scene, keep Max consistent, vary camera angles, automatically retry failed images, then package the final results.

The system must translate that command into a render manifest, execute multiple image jobs safely and efficiently, verify output quality, retry failures within bounded limits, and return organized results without requiring the user to manually call APIs or split jobs.

This upgrade is a system capability change only. The upgrade process itself must not render images unless explicit test fixtures or smoke tests are needed later in the implementation phase.

## 2. Non-negotiable invariants

1. FREE_ONLY remains mandatory.
2. paid_fallback remains false.
3. auto_purchase remains false.
4. trial or promo credit must never be treated as an acceptable paid fallback path.
5. GITHUB_BRAIN_V4 remains the routing and reasoning authority.
6. image_render_agent remains a specialist executor, not a routing authority.
7. Existing single-image endpoints remain backward compatible.
8. User constraints and project authority override inferred render preferences.
9. No silent addition/removal of subjects.
10. No unbounded retry loops.
11. No hidden permission expansion.
12. No external image-generation framework becomes system authority.
13. Reference-image support, if added later, must be explicit and policy-gated; prompt-driven batch rendering is the core V2 requirement.

## 3. Current limitations

The current image agent has the following constraints:

- One provider path: AI Horde.
- Prompt-only orchestration.
- At most 4 images per provider request.
- No first-class batch object spanning many scenes.
- No dynamic model ranking using live worker/model availability.
- No per-scene quality score or automated retry policy.
- No persistent render manifest containing scene-level state.
- No dedicated natural-language render-command parser.
- No job-level concurrency manager.
- No structured packaging/report output.
- Existing creative continuity and render-quality logic exists in Brain policy, but it is not yet wired into the image execution loop.

## 4. Target architecture

User chat command
→ task_router
→ image command parser
→ render manifest compiler
→ prompt compiler
→ adaptive model router
→ batch scheduler
→ provider adapter(s)
→ render result collector
→ quality critic
→ retry/repair loop
→ result packager
→ final batch result

The design uses one authority chain. The new modules are implementation components under image_render_agent and do not create a parallel router.

## 5. Components

### 5.1 Image Command Parser

Purpose: convert a natural-language render instruction into a typed request.

Inputs may include:

- scene range: 1–10, 11–20, 1–30
- one prompt per scene
- aspect ratio or dimensions
- number of images per scene
- style constraints
- character consistency constraints
- background constraints
- camera diversity constraints
- negative constraints
- output naming rules
- retry tolerance
- packaging preference

Output: `image_render_batch_request_v2`.

The parser must not invent missing creative requirements that materially alter the task. Safe defaults may be used only for execution mechanics, such as concurrency limits or retry ceilings.

### 5.2 Render Manifest Compiler

Purpose: normalize a batch request into one manifest with independent scene tasks.

Each manifest contains:

- batch_id
- created_at
- data_class
- user_instruction
- output_format
- global_constraints
- shared_character_state
- shared_style_state
- scenes[]
- scheduler_config
- retry_policy
- QA_policy

Each scene task contains:

- scene_id
- original_prompt
- compiled_prompt
- negative_prompt
- dimensions
- aspect_ratio
- seed_strategy
- model_candidates
- expected_subject_count
- locked_identity_facts
- locked_wardrobe_facts
- locked_environment_facts
- camera_constraints
- continuity_inputs
- status
- attempts[]

### 5.3 Prompt Compiler

Purpose: turn user prompts into render-ready prompts without changing the user's intent.

Compilation layers:

1. explicit subject facts
2. explicit action
3. environment
4. composition
5. camera
6. lighting
7. visual style/materials
8. continuity locks
9. anatomy and deformation guards
10. negative constraints
11. output constraints

For multi-scene work, the compiler must merge shared state with per-scene state.

The compiler must preserve explicit user facts and must not silently substitute characters, clothing, props, environments, counts, or actions.

### 5.4 Consistency Engine

Purpose: keep characters, wardrobe, props, backgrounds, style, and continuity stable across scene sequences.

Shared state examples:

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
- lighting direction
- palette
- seed family

The engine must support two modes:

- `STRICT`: stronger identity/wardrobe/environment locking for recurring characters.
- `FLEXIBLE`: preserves identity while allowing more scene variation.

For the user's recurring animation workflow, `STRICT` should be the default when the instruction includes phrases such as "giữ nhân vật", "đúng ref", "không thay đổi nhân vật", or equivalent intent.

### 5.5 Adaptive Model Router

Purpose: choose a suitable free model based on task fit and current provider availability.

The router must retrieve live AI Horde image model status and rank candidates using a weighted score:

`score = task_fit + quality_history + availability + performance - queue_penalty - failure_penalty`

Candidate attributes:

- model name
- model family/baseline when known
- active worker count
- performance
- queue ETA
- queued work
- recent internal success/failure statistics
- style/task suitability

Routing rules:

- Do not rely on provider default model selection for production-quality multi-scene jobs.
- Prefer models appropriate for the target style/task.
- Avoid models with excessive queue delay when an equivalent free model is available.
- Record selected model and reason in each attempt.
- Fallback remains FREE_ONLY.

### 5.6 Batch Scheduler

Purpose: execute many scene jobs concurrently while respecting provider/community capacity.

Default scheduler behavior:

- logical batch size: configurable, no hard user-facing 4-image ceiling
- provider request size: respect provider limits
- default active concurrency: 4
- adaptive concurrency ceiling: 8
- lower concurrency automatically on provider failures, rate pressure, or long queue conditions
- fair scene ordering
- support cancellation
- support partial completion

The scheduler manages many provider requests behind one batch ID.

Example:

30 scenes
→ 30 scene tasks
→ 4–8 active tasks
→ as one finishes, the next queued task starts
→ failed QA tasks re-enter retry queue according to policy

### 5.7 Quality Critic

Purpose: determine whether an output is acceptable before the scene is marked complete.

Required checks:

- prompt fidelity
- expected subject count
- identity consistency
- wardrobe consistency
- scene continuity
- object count
- anatomy risk
- deformation risk
- duplicate subjects/objects
- background correctness
- camera compliance when explicit
- text/watermark presence when forbidden
- image decode/format validity
- censor state

The critic emits:

- PASS
- RETRY_PROMPT
- RETRY_MODEL
- RETRY_SEED
- FAIL_TERMINAL

and a structured failure reason.

V2 implementation may initially use deterministic metadata/prompt checks plus optional visual-review hooks already represented in Brain architecture. Visual QA must be introduced without creating a new reasoning authority.

### 5.8 Retry and Repair Loop

Default maximum: 3 total attempts per scene.

Retry policy:

Attempt 1: selected model + compiled prompt

If quality failure:
- targeted prompt repair for the specific failure
- preserve all locked facts

Attempt 2:
- same model with repaired prompt and new seed, unless the failure indicates model mismatch

Attempt 3:
- alternate ranked free model with repaired prompt

After maximum attempts:
- scene status becomes `failed_quality` or `failed_provider`
- batch continues for other scenes
- final report clearly identifies failed scenes

No infinite retries.

### 5.9 Result Packager

Purpose: normalize final outputs for user delivery.

Output structure example:

```
render_batch_<batch_id>/
  Scene_01.webp
  Scene_02.webp
  ...
  Scene_30.webp
  render_report.json
  manifest.json
```

`render_report.json` includes:

- batch status
- total scenes
- passed scenes
- failed scenes
- total provider requests
- model usage
- seeds
- retries per scene
- QA outcomes
- failure reasons
- FREE_ONLY confirmation
- monetary cost: zero

ZIP packaging is supported as a delivery layer when requested or when the result contains multiple assets.

## 6. API surface

Existing endpoints remain:

- `GET /brain/image/health`
- `POST /brain/image/render`
- `GET /brain/image/check`
- `GET /brain/image/status`
- `DELETE /brain/image/status`

V2 adds:

### `POST /brain/image/batch`

Creates a batch from a typed render request or precompiled scene manifest.

Returns:

- batch_id
- scene_count
- accepted_count
- mode: FREE_ONLY
- status path

### `GET /brain/image/batch/status?id=<batch_id>`

Returns aggregate progress and scene-level states.

### `DELETE /brain/image/batch?id=<batch_id>`

Cancels queued work and requests cancellation for active provider jobs when supported.

### `GET /brain/image/models`

Returns normalized live free-model availability and ranking metadata.

### `POST /brain/image/retry`

Retries specific failed scenes under the same batch while preserving locked constraints.

## 7. Data model

### Batch states

- queued
- running
- partially_complete
- complete
- complete_with_failures
- cancelled
- failed

### Scene states

- queued
- submitting
- provider_wait
- provider_processing
- qa_pending
- retry_pending
- complete
- failed_quality
- failed_provider
- cancelled

### Attempt record

Each attempt records:

- attempt_number
- provider
- model
- seed
- prompt_hash
- width
- height
- submit_time
- complete_time
- provider_job_id
- provider_wait_time
- generation_state
- QA_result
- QA_reasons

## 8. Natural-language command behavior

The Brain should route render-related commands to the image domain when the user intent is clearly execution, for example:

- "render 20 ảnh theo prompt này"
- "tạo scene 1 đến 30"
- "mỗi scene một ảnh"
- "render lại scene 7"
- "giữ Max giống nhau ở tất cả scene"
- "ảnh ngang 16:9"
- "xong nén zip"

The user should not need to know provider names, model names, API routes, queue mechanics, or retry strategy.

The Brain remains responsible for interpreting the instruction and producing the structured request. The image_render_agent remains responsible for execution.

## 9. Provider strategy

### Phase 1 provider

AI Horde remains the first free execution provider because it is already integrated and verified in production.

### Multi-provider readiness

V2 interfaces must be provider-neutral so additional verified free providers can be added later without changing the batch contract.

Provider adapters expose the same minimal interface:

- health
- listModels
- submit
- check
- status
- cancel

No provider may be added unless its cost semantics are known and FREE_ONLY-safe.

## 10. Reference-image strategy

Reference-image support is not required to deliver the core prompt-and-command batch upgrade.

V2 should prepare an extension point for:

- img2img
- remix
- inpainting
- outpainting
- future identity conditioning adapters

However, AI Horde volunteer infrastructure may expose prompt/assets to community workers. Therefore reference images must remain disabled by default until a dedicated policy explicitly defines allowed data classes and opt-in behavior.

The core V2 batch system must work correctly with prompt-only input.

## 11. Security and privacy

- Explicit data class remains required.
- Current AI Horde execution remains PUBLIC-only unless policy is separately changed.
- INTERNAL, CONFIDENTIAL, and SECRET must fail closed for volunteer-provider execution.
- Execution tokens remain required.
- No model/provider response may widen permissions.
- Provider URLs returned to clients should be treated as untrusted external assets and validated before download/packaging.
- Batch identifiers must be generated server-side and validated.
- Prompt size and batch-size limits must be bounded to prevent abuse.

## 12. Operational limits

Recommended initial limits:

- maximum scenes per batch: 100
- default scenes per batch: user-defined
- maximum active provider jobs: 8
- default active provider jobs: 4
- maximum attempts per scene: 3
- maximum images per individual provider request: provider-specific, current AI Horde adapter max 4
- maximum total generated images per logical batch: 100 unless policy overrides

These are safety/operational limits, not paid quota limits.

## 13. Observability

Add structured batch metrics:

- batch_created
- scene_submitted
- scene_completed
- scene_retry
- scene_failed
- model_selected
- provider_error
- batch_completed
- batch_cancelled

Metrics should track:

- queue time
- provider processing time
- total scene time
- retries
- model success rate
- model failure rate
- QA failure categories

No hidden chain-of-thought is stored.

## 14. Failure handling

Provider unavailable:
- mark provider health degraded
- pause new submissions briefly
- retry within bounded backoff
- use an alternate verified free provider only if one exists and is allowed
- never route to paid service

Model unavailable:
- select next ranked free model

One scene fails:
- continue other scenes
- report partial success

Batch process restart:
- manifest and scene states must allow safe resumption without duplicating already-completed scene results

Malformed user batch:
- reject before provider submission with a clear validation error

## 15. Backward compatibility

`POST /brain/image/render` continues to support existing single-image calls.

Internally, V2 may implement single-image rendering as a one-scene batch, but the external response contract must remain compatible unless a versioned response is explicitly requested.

Existing `FREE_ONLY`, privacy, auth, and provider behavior remains valid.

## 16. Testing strategy

### Unit tests

- natural-language command normalization helpers
- manifest validation
- prompt compilation
- consistency merge rules
- model scoring/ranking
- concurrency bounds
- retry transitions
- batch state transitions
- FREE_ONLY guard
- privacy/data-class guard
- provider adapter normalization

### Integration tests

Using mocked provider responses:

- 20-scene batch
- partial provider failure
- model unavailable fallback
- QA retry
- cancellation
- restart/resume
- backward-compatible single-image call

### Production smoke tests

Only after implementation tests pass:

- health
- live model list
- one small PUBLIC single-image render
- one small PUBLIC multi-scene batch

Smoke tests must not use user-private reference assets.

## 17. Files expected to change during implementation

Likely existing files:

- `cloudflare-worker/image-render-handler.js`
- `cloudflare-worker/image-render/ai-horde.js`
- `AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml`
- `AI_SKILL_LIBRARY/v4/legion/agents.yaml`
- `AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml`

Likely new focused modules:

- `cloudflare-worker/image-render/batch-manager.js`
- `cloudflare-worker/image-render/model-router.js`
- `cloudflare-worker/image-render/render-manifest.js`
- `cloudflare-worker/image-render/prompt-compiler.js`
- `cloudflare-worker/image-render/quality-policy.js`
- `cloudflare-worker/image-render/provider-registry.js`

Likely tests:

- unit tests for each focused module
- handler integration tests
- FREE_ONLY policy tests
- batch lifecycle tests

Final filenames may be adjusted to match existing repository conventions during implementation planning.

## 18. Acceptance criteria

The upgrade is accepted only when all of the following are true:

1. A natural-language render request can be converted into a structured batch request.
2. A single command can represent at least 20 independent scene renders.
3. The scheduler executes multiple scenes concurrently with a bounded maximum.
4. The system dynamically ranks active free image models.
5. Each scene records model, seed, provider job ID, attempt count, and QA result.
6. Failed scenes retry automatically up to the configured limit.
7. One scene failure does not terminate the full batch.
8. Character/wardrobe/environment locks are preserved in prompt compilation.
9. Batch status can be queried at aggregate and scene levels.
10. Batch cancellation works.
11. Results can be packaged with manifest and render report.
12. Existing single-image API remains compatible.
13. All production execution paths remain FREE_ONLY.
14. There is no paid fallback or automatic purchase path.
15. No private reference assets are sent to volunteer providers by default.
16. Tests cover the core scheduler, retry, routing, policy, and backward-compatibility paths.

## 19. Explicitly out of scope for this V2 core implementation

- Building or hosting our own GPU cluster.
- Paid image APIs.
- Unlimited unbounded concurrency.
- Training a custom Max model.
- Automatic publication of private reference assets.
- Video generation.
- Replacing GITHUB_BRAIN_V4 routing authority.
- Rewriting the entire creative skill system.

These can be addressed by later versions without changing the V2 batch contract.

## 20. Implementation principle

The implementation should prefer small, focused modules with typed/validated contracts. Existing creative logic remains canonical where it already exists; V2 wires that logic into execution rather than duplicating a second creative brain.

The system should optimize for this user experience:

> User gives one render instruction. Brain interprets it. Image Agent V2 plans the batch, selects free models, executes scenes in parallel, checks quality, retries failures, and returns organized results.

The user should not need to manually manage models, provider queues, API calls, retries, or scene-by-scene execution.
