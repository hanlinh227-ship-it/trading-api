# Image Agent V3/V4 Multi-Model Image Intelligence Mesh

Date: 2026-09-17
Status: Design candidate for approval
Authority: GITHUB_BRAIN_V4
Scope: image generation/editing subsystem only

## 1. Goal

Upgrade the existing Image Render Agent V2 into a cloud-only, FREE_ONLY, multi-model image intelligence mesh controlled from ChatGPT through GITHUB_BRAIN_V4. The system must support arbitrary text-to-image, reference-guided generation, image editing, inpainting, background replacement, style transfer, multi-image composition, and very large logical batch jobs without requiring any model/runtime installation on the user's computer.

The target is not to make an unverifiable blanket claim that the system is always equal to ChatGPT Images or Gemini/Flow. The target is to build an architecture capable of approaching current frontier quality on prompt adherence, reference fidelity, edit preservation, character consistency, text rendering, anatomy, composition, and multi-scene continuity, with measurable internal benchmarks and automatic model promotion when better free/open models become available.

## 2. Hard Constraints

The following constraints are non-negotiable:

1. Cloud-only / zero-local runtime for normal operation.
2. User controls the system by messaging ChatGPT; no local UI, ComfyUI, or manual desktop workflow is required.
3. FREE_ONLY: no paid fallback, no auto-purchase, no hidden credits, no silent trial-credit routing.
4. If no safe free runtime is available, jobs wait or fail with an explicit reason; they never silently route paid.
5. Existing GITHUB_BRAIN_V4 remains the single authority for routing/orchestration policy.
6. Image execution agents have no trading authority and must not modify trading state or trading execution policies.
7. V1/V2 image API compatibility is preserved unless explicitly versioned.
8. AI Horde remains PUBLIC-only; reference/private assets are never sent to volunteer infrastructure.
9. Reference/edit assets may only be routed to providers explicitly classified reference_safe=true and approved for the relevant data class.
10. No model is treated as permanent simply because a public endpoint exists. Long-term resilience requires versioned model metadata, license snapshots, weight identifiers, compatibility tests, and mirror strategy where legally permitted.
11. No infinite retries. Every scene/job has bounded attempts per model and bounded model-switch attempts.
12. Quality verification must be evidence-based. If the critic is unavailable, the system must report unverified completion rather than fake PASS.

## 3. Existing V2 Assets to Preserve

V2 already provides useful control-plane components that remain authoritative unless superseded by a versioned interface:

- Durable Object batch state.
- Batch lifecycle: create/status/cancel/selective retry/resume.
- FREE_ONLY policy and paid-route prohibition.
- Provider registry pattern.
- Model routing and health concepts.
- Prompt compiler.
- Quality policy with PASS_UNVERIFIED behavior.
- Export/report metadata.
- Exact-SHA deploy and production smoke architecture.
- Cloudflare orchestration.

V3/V4 extends these components; it does not create an independent parallel brain.

## 4. Target Architecture

```text
ChatGPT
  -> GITHUB_BRAIN_V4
    -> Image Task Classifier
      -> Image Intent Compiler
        -> Privacy / License / Cost Gate
          -> Image Model Mesh Router
            -> Candidate Generation / Edit
              -> Vision Critic
                -> Identity / Prompt / Anatomy / Layout Scoring
                  -> Targeted Repair Planner
                    -> Grounding / Segmentation
                      -> Local Edit / Inpaint
                        -> Final QA
                          -> Durable Job State
                            -> Export / Result
```

The architecture separates control plane from inference plane.

Control plane:
- Cloudflare Worker + Durable Object.
- Brain policy, task classification, provider/model selection, retries, manifests, state, QA decisions.

Inference plane:
- Free/open cloud runtimes exposing compatible model adapters.
- Provider-specific workers/services are replaceable and have no global authority.

## 5. Image Task Taxonomy

The task classifier must map requests into one or more normalized capabilities:

- TEXT_TO_IMAGE
- REFERENCE_GENERATION
- IMAGE_EDIT_GLOBAL
- IMAGE_EDIT_LOCAL
- INPAINT
- OUTPAINT
- BACKGROUND_REPLACE
- STYLE_TRANSFER
- OBJECT_REPLACE
- TEXT_RENDER_EDIT
- MULTI_IMAGE_COMPOSE
- CHARACTER_CONSISTENCY
- PRODUCT_CONSISTENCY
- MULTI_SCENE_BATCH
- TARGETED_REPAIR

Classifier output must include required capabilities, privacy class, reference requirements, target resolution, latency preference, quality profile, and whether destructive redraw is allowed.

## 6. Image Intent Compiler

Replace text-only prompt expansion with a structured ImageIntent manifest. It must preserve the user's explicit facts and never silently add/remove subjects.

Required fields:

- task_type
- prompt_original
- prompt_compiled
- negative_constraints
- subject_count
- subject_identity_constraints
- reference_assets
- preserve_regions
- editable_regions
- wardrobe_constraints
- prop_constraints
- background_constraints
- style_constraints
- camera_constraints
- composition_constraints
- text_render_constraints
- continuity_constraints
- target_width / target_height / aspect_ratio
- privacy_class
- quality_profile
- destructive_redraw_allowed

Explicit user constraints always override inferred defaults.

## 7. Multi-Model Mesh

### 7.1 Initial candidate model families

The mesh is designed to support multiple open model families without hard-coding the architecture to one vendor. Initial integration targets:

Generation / reference-aware generation:
- FLUX.2 [klein] 4B where compatible free runtimes exist.
- Qwen-Image.
- OmniGen2.
- BAGEL as a heavier multimodal fallback where free compute is available.

Editing / targeted repair:
- Qwen-Image-Edit-2509.
- HiDream-E1.1.
- Step1X-Edit.

Vision critic / multimodal evaluation:
- Qwen3-VL family or another approved open VLM meeting benchmark thresholds.

Grounding / segmentation:
- GroundingDINO.
- SAM2.

Reference conditioning adapters where model/runtime compatibility permits:
- IP-Adapter-style conditioning.

### 7.2 License policy

The initial preference order is Apache-2.0 and MIT licensed code/models. Any component with non-commercial, research-only, ambiguous weight licensing, or dependency licensing incompatible with the project must be excluded from the default production mesh.

Every model/provider registration must record:

- repo/source
- model identifier
- exact revision/hash when available
- code license
- weights license
- dependency license notes
- commercial-use eligibility
- redistribution/mirroring eligibility
- last verified date
- runtime compatibility

License verification is a deployment gate, not documentation-only metadata.

## 8. Provider Mesh Contract

Provider registry V2 evolves into a provider/model mesh. Each provider adapter must expose normalized metadata and functions.

Required metadata:

- provider_id
- provider_class
- monetary_cost
- paid_fallback=false
- auto_purchase=false
- supported_data_classes
- reference_safe
- supported_tasks
- supported_models
- max_resolution
- max_reference_images
- queue_estimate
- health
- privacy notes
- retention notes

Required functions:

- health()
- listModels()
- capabilities()
- submit()
- check()
- status()
- cancel()

Optional functions:

- edit()
- inpaint()
- uploadReference()
- deleteReference()
- critic()
- segment()

No provider may become routing or reasoning authority.

## 9. Privacy Routing

Privacy routing is mandatory before model routing.

PUBLIC prompts with no private references may use community/volunteer providers if allowed by policy.

Reference/private image requests require a runtime classified reference_safe=true for that data class. If none is available:

- scene/job state becomes WAITING_FOR_SAFE_FREE_RUNTIME or fails explicitly by configured timeout policy;
- do not downgrade the privacy class;
- do not strip the reference and pretend to satisfy the request;
- do not send to AI Horde.

Reference uploads should use ephemeral provider storage where possible, with explicit deletion and retention reporting.

## 10. Reference Fidelity Engine

For reference-guided tasks, create a ReferenceProfile describing stable traits. The profile is metadata, not a claim of biometric identity.

For stylized/fictional characters such as Max, traits may include:

- species / character class
- head shape
- body proportions
- fur/skin palette
- eye style
- clothing
- accessories
- recurring props
- silhouette
- forbidden deviations
- scene-invariant features

The critic evaluates generated candidates against these constraints. Where model/runtime allows direct multi-reference conditioning, references are provided directly to the approved runtime. Where it does not, the router must lower expected fidelity and prefer another model rather than falsely claiming exact reference reproduction.

## 11. Candidate Tournament

High-quality profiles should generate multiple candidates when free compute is available.

Example:

- candidate_count default: 2
- candidate_count high-quality: 4
- candidate_count low-capacity: 1

The critic scores each candidate on normalized dimensions:

- prompt_adherence
- reference_fidelity
- subject_count_accuracy
- anatomy
- composition
- background_accuracy
- wardrobe_accuracy
- prop_accuracy
- text_accuracy
- style_accuracy
- continuity
- artifact/watermark detection

The router selects the highest passing candidate. If all candidates fail, it applies a bounded repair or model-switch policy.

## 12. Vision Critic

V4 introduces a real visual critic abstraction. Metadata-only QA from V2 remains available as STRUCTURAL mode, but STRICT_VISUAL requires actual image inspection.

Critic output:

- overall_score
- per-dimension scores
- detected problems
- affected regions/objects when available
- recommended action
- confidence

Allowed decisions:

- PASS
- PASS_UNVERIFIED
- REPAIR_LOCAL
- REPAIR_GLOBAL
- RETRY_SEED
- RETRY_MODEL
- RETRY_PROMPT
- FAIL_TERMINAL

The system must never label a result visually verified without a successful critic pass.

## 13. Targeted Repair Loop

When a candidate is mostly correct, do not redraw the full image by default.

Repair flow:

1. Critic identifies the failing attribute/object.
2. GroundingDINO (or approved equivalent) localizes the target.
3. SAM2 (or approved equivalent) creates/refines a mask.
4. Repair planner creates a minimal edit instruction.
5. Qwen-Image-Edit, HiDream-E1.1, Step1X-Edit, or another approved editor performs a local edit/inpaint.
6. Critic re-evaluates the repaired image.
7. Preserve successful regions unless the user explicitly allows global redraw.

Bound the loop by repair_attempt_limit and total_scene_attempt_limit.

## 14. Model Router V3

Routing score should combine:

- task capability match
- reference support
- privacy eligibility
- license eligibility
- FREE_ONLY eligibility
- live health
- queue estimate
- historical task-specific quality
- critic pass rate
- latency
- retry history
- max resolution
- text-render performance where relevant

The router maintains task-specific historical quality instead of one global model score.

Example: a model can rank first for TEXT_RENDER_EDIT but third for CHARACTER_CONSISTENCY.

## 15. Self-Evolving Benchmark Layer

The system must benchmark new models before promotion.

Benchmark suites should include:

- prompt following
- exact subject count
- reference consistency
- targeted edit preservation
- background replacement
- text rendering
- hands/anatomy
- object replacement
- style transfer
- multi-scene continuity

Promotion rules:

- new model starts CANDIDATE;
- benchmark must pass minimum quality and policy gates;
- model may become ACTIVE for specific task classes only;
- regression automatically demotes it;
- no model becomes universal default solely from marketing claims or upstream benchmark claims.

## 16. Unlimited Logical Jobs

Remove the concept that one logical user job is limited to 100 scenes. Preserve the existing 100-scene physical batch size as an implementation unit if useful.

LogicalJob:

- logical_job_id
- scene_count: unbounded by product policy, bounded only by operational safeguards
- chunk_size: <=100
- checkpointed progress
- resumable
- cancelable
- partial export
- per-scene retry state

Example: 5,000 scenes become 50 physical chunks of 100. The user sees one logical job.

Operational safeguards may enforce quotas against runaway or abusive jobs, but the API should not have an arbitrary small total-scene ceiling when capacity is available.

## 17. Free Compute Exhaustion

No free capacity is not an error that permits paid fallback.

Allowed states:

- WAITING_FOR_FREE_COMPUTE
- WAITING_FOR_SAFE_FREE_RUNTIME
- PROVIDER_DEGRADED

Scheduler behavior:

- periodically re-check eligible providers;
- preserve durable state;
- optionally downgrade candidate_count/quality profile only if user policy permits;
- never downgrade privacy requirements;
- never purchase compute.

## 18. Model Vault

Create a Model Vault metadata layer to reduce dependency on disappearing upstream endpoints.

For each approved model:

- canonical repo
- model source
- exact revision
- checksum/hash if available
- license snapshot metadata
- redistribution eligibility
- approved mirror locations
- runtime adapter version
- smoke test
- benchmark snapshot

This does not mean storing multi-GB weights in Git. It means the Brain knows exactly what artifact is approved and how to reproduce the runtime. Actual mirrors may use approved external object/model storage only where licensing permits.

## 19. API Evolution

Preserve existing V1/V2 routes.

Add versioned V3 logical-job APIs rather than breaking V2:

- POST /brain/image/v3/jobs
- GET /brain/image/v3/jobs/status?id=
- DELETE /brain/image/v3/jobs?id=
- POST /brain/image/v3/jobs/retry
- POST /brain/image/v3/edit
- GET /brain/image/v3/models
- GET /brain/image/v3/capabilities

Reference upload may use a separate versioned endpoint only after a secure storage/runtime contract is defined.

## 20. Durable State

Image V3/V4 state remains separate from TRADING_STATE.

Recommended Durable Object classes:

- ImageRenderBatchState (existing physical batch)
- ImageLogicalJobState (new logical multi-batch coordinator)

No image state may use trading bindings as fallback.

## 21. Failure Isolation

One failed scene must not fail the entire logical job unless the user requested all-or-nothing semantics.

Provider outage, critic outage, editor outage, reference-runtime outage, or segmentation failure must be isolated and represented in scene state.

Quality degradation must be explicit.

## 22. Security

- Existing internal auth remains required.
- Reference asset access must use short-lived scoped tokens/URLs.
- Provider credentials remain server-side.
- Logs must not contain raw private reference URLs or secrets.
- No public export of private assets by default.
- No provider is allowed to retain private references unless policy explicitly permits it and retention is disclosed.

## 23. Testing Strategy

Implementation follows RED -> GREEN.

Required test layers:

1. ImageIntent compiler contracts.
2. Provider/model registry contracts.
3. FREE_ONLY and privacy routing.
4. Reference-safe provider selection.
5. Task-specific model routing.
6. Critic decision policy.
7. Candidate tournament.
8. Targeted repair planner.
9. Logical job chunking/resume/cancel.
10. Failure isolation.
11. Model Vault/license gates.
12. API V3 compatibility.
13. Wrangler/deployment binding safety.
14. Production smoke without private references.
15. Optional reference smoke only against an explicitly safe test runtime and synthetic/public fixture.

V1 and V2 regression suites remain mandatory.

## 24. Production Smoke

Production smoke must not consume a real user's private reference image.

Core smoke:

- exact deployed SHA
- health/capabilities
- FREE_ONLY policy
- model mesh metadata
- one synthetic/public text-to-image logical job create/cancel/status
- critic health if available
- no paid fallback
- no TRADING_STATE dependency

Provider degradation should be classified where external outages are non-core, while control-plane failures remain hard failures.

## 25. Claude Code Integration Boundary

Claude Code will act as a code contributor, not a second authority.

Claude Code instructions must require it to:

- load current main and GITHUB_BRAIN_V4 before changes;
- work only on the image subsystem unless a shared file is strictly necessary;
- preserve trading authority and never modify trading execution semantics;
- preserve FREE_ONLY and privacy gates;
- not create duplicate routers/registries/brains;
- follow existing Image Agent versioned contracts;
- use RED -> GREEN tests;
- verify licenses for any new model/runtime adapter;
- preserve V1/V2 compatibility;
- run Brain validators and Worker tests;
- create a PR and report exact head SHA;
- never claim frontier parity without benchmark evidence.

A dedicated Claude Code handoff prompt will be produced after implementation-plan approval so it references exact files/tasks rather than a vague architecture request.

## 26. Phased Delivery

### Phase 1 — V3 Control Plane

- ImageIntent compiler.
- Provider/model mesh registry.
- Task-specific router.
- Logical job coordinator.
- Model Vault metadata.
- V3 APIs.
- Preserve AI Horde as PUBLIC-only fallback.

### Phase 2 — Reference & Edit Plane

- Reference-safe runtime adapter contract.
- Qwen-Image/Edit and FLUX.2-compatible adapters where free cloud runtime is available.
- ReferenceProfile.
- Edit task routing.

### Phase 3 — V4 Quality Plane

- Qwen3-VL-compatible critic adapter.
- Candidate tournament.
- Critic-driven retry/repair decisions.
- GroundingDINO/SAM2 repair path.
- Editor selection for local repair.

### Phase 4 — Continuous Model Evolution

- Benchmark harness.
- Task-specific promotion/demotion.
- New-model candidate ingestion.
- Model Vault health/license refresh.

## 27. Success Criteria

V3/V4 is considered production-ready only when:

1. V1/V2 remain backward compatible.
2. FREE_ONLY is proven by tests and production policy.
3. No image component can route to paid compute.
4. No private/reference asset can route to AI Horde.
5. V3 logical jobs can exceed 100 scenes via chunking.
6. Jobs survive Worker restarts and provider outages.
7. At least two distinct generation/edit capabilities are represented in the mesh when free runtimes are actually available.
8. Reference-guided generation/edit uses only approved reference-safe runtime paths.
9. STRICT_VISUAL verification uses a real critic.
10. Candidate tournament and targeted repair are benchmarked against single-pass V2 and demonstrate measurable quality improvement on internal fixtures.
11. Exact-main deployment and production smoke pass.
12. Claude Code handoff prompt is generated from the final implementation plan and explicitly prevents architecture duplication and trading conflicts.

## 28. Non-Goals

- Claiming guaranteed parity with proprietary frontier models on every prompt.
- Guaranteeing unlimited instantaneous GPU capacity from third-party free providers.
- Running required inference on the user's computer.
- Using paid API credits as hidden fallback.
- Training a foundation model from scratch.
- Altering trading authority or execution policies.

## 29. Design Decision

Chosen approach: Multi-Model Image Intelligence Mesh (Option C).

Reason: no single open model is strongest at generation, reference fidelity, editing, text rendering, visual reasoning, and targeted repair simultaneously. A task-specialized mesh controlled by GITHUB_BRAIN_V4 can combine open/free models, preserve V2 infrastructure, benchmark new models over time, and fail safely when free compute is unavailable.
