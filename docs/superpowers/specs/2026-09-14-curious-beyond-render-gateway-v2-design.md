# Curious Beyond Render Gateway V2 — Multi-Device, Multi-Engine, Flow-Grade Quality

Date: 2026-09-14
Status: SPEC READY FOR USER REVIEW
Repository: `hanlinh227-ship-it/trading-api`
Target branch: `ai-money-ecosystem-autopilot-v1`

## 1. Goal

Build a render gateway that lets the user open this ChatGPT from any computer or phone, upload prompt/reference/background/audio/project files, and have ChatGPT route the job to a remote render worker, then return the produced image/video/ZIP back through ChatGPT without requiring the user to sit at the render PC.

The system must combine local rendering, Google Flow/Gemini/Veo-class cloud rendering, and other approved engines behind one orchestration layer. It must optimize for the highest visual quality available, not merely for the cheapest or fastest path.

## 2. Non-negotiable requirements

1. **Flow-grade quality target is the default final-output policy.**
   - Final images must target the quality/control level associated with Google Flow image workflows: high prompt adherence, professional-grade detail, strong multi-reference control, clean composition, stable characters, and production-ready finish.
   - Final video must target Flow/Veo-class continuity, prompt adherence, camera coherence, and audiovisual polish when such an engine is connected and authorized.
   - The system must never silently downgrade a `FLOW_GRADE` job to a weak local SD1.5 result.

2. **Any-device ChatGPT ingress.**
   - A user can start or resume a render job from ChatGPT on another device.
   - Job state cannot depend on the local browser session or the machine from which the user uploaded files.

3. **Binary assets do not live in GitHub.**
   - Google Drive is the primary asset/artifact bus for reference images, backgrounds, audio, videos, ZIPs, and final outputs.
   - GitHub is the control plane for manifests, signed jobs, worker state, routing decisions, audit metadata, and compact validation results.

4. **Multi-worker and multi-engine.**
   - Local Windows worker remains supported.
   - Additional render PCs can be paired later.
   - Cloud engines such as Google Flow/Gemini/Veo and Runway can be added through adapters without changing the job contract.

5. **No arbitrary remote shell.**
   - All local execution remains allowlisted and typed.
   - Render workers never become remote-desktop or arbitrary command agents.

6. **No unapproved spending.**
   - Existing subscriptions/entitlements may be used when explicitly enabled in policy.
   - Auto-purchase, buying credits, or changing plans is forbidden.
   - If the required Flow-grade engine is unavailable because of quota/plan/region, the job must stop with `QUALITY_TARGET_UNAVAILABLE` unless the user explicitly allows a lower tier.

7. **Truthful QA.**
   - Do not label a scene `VERIFIED` unless an actual deterministic, identity, structural, or semantic check supports the claim.
   - A successful file write is not equivalent to a successful scene.

## 3. Quality baseline and provider reality

As of 2026-09-14, Google Flow officially supports a high-end image/video stack including:
- Nano Banana Pro for advanced image generation/editing with professional-grade control.
- Nano Banana 2 / 2 Lite for faster image generation/editing.
- Veo 3.1 variants for text-to-video and frames-to-video; some variants support ingredients/references and first/last frames.
- Flow/Gemini Omni features that support iterative editing, start/end frame control, and high-resolution export/upscaling depending on model and entitlement.

Official references used for this baseline:
- https://support.google.com/flow/answer/16352836
- https://support.google.com/flow/answer/16353334
- https://blog.google/innovation-and-ai/products/veo-updates-flow/
- https://blog.google/innovation-and-ai/models-and-research/google-labs/new-creative-controls-google-flow/

**Important:** An open-source/local model on GTX 1650 4 GB cannot be guaranteed to match proprietary Flow/Nano Banana Pro/Veo quality. Therefore `FLOW_GRADE` is a routing policy, not a claim that every local engine is equivalent. When a Flow-grade provider is unavailable, the system must fail closed or ask for downgrade approval.

## 4. High-level architecture

```text
Any user device
(phone / laptop / desktop)
        |
        v
ChatGPT Render Gateway
        |
        +--------------------+
        |                    |
        v                    v
Google Drive Asset Bus    GitHub Control Plane
(ref/bg/audio/video/ZIP)  (jobs/manifests/signatures/state)
        |                    |
        +----------+---------+
                   |
                   v
            Render Orchestrator
                   |
        +----------+----------+----------------+
        |                     |                |
        v                     v                v
 Local Worker Pool      Google/Flow Adapter   Other Adapters
 ComfyUI/FFmpeg         Image + Video         Runway/etc.
        |                     |                |
        +----------+----------+----------------+
                   |
                   v
              Quality Gate
                   |
        retry / inpaint / reroute
                   |
                   v
          Drive Output / Artifact Bus
                   |
                   v
          ChatGPT Artifact Return
```

## 5. Control plane vs asset plane

### 5.1 GitHub control plane

GitHub stores only compact text metadata:
- job request
- job state
- signed payload
- engine routing decision
- worker lease/heartbeat
- expected asset hashes
- Drive file IDs, MIME types, logical roles
- QA summary
- final artifact IDs and checksums
- compact error diagnostics

GitHub must not store large generated images/videos or secret provider tokens.

### 5.2 Google Drive asset bus

Canonical layout:

```text
CuriousBeyond_RenderGateway/
  projects/<project_id>/
    masters/
      characters/
      objects/
      vehicles/
      backgrounds/
      style/
    jobs/<job_id>/
      input/
      staged/
      output/
      qa/
      package/
```

Each binary asset is represented in the control manifest by:
- `drive_file_id`
- `logical_role`
- `mime_type`
- `byte_size`
- `sha256`
- `source`
- `license/rights note` when relevant

## 6. Core job contract

Every render request becomes a provider-agnostic manifest:

```json
{
  "job_id": "...",
  "project_id": "...",
  "job_type": "IMAGE_RENDER | VIDEO_RENDER | FINAL_RENDER",
  "quality_tier": "FLOW_GRADE | HIGH | DRAFT_LOCAL",
  "cost_policy": "USE_EXISTING_ENTITLEMENTS | ASK_BEFORE_PAID | LOCAL_ONLY",
  "aspect_ratio": "16:9",
  "output_resolution": "...",
  "prompt": "...",
  "negative_constraints": [],
  "assets": [],
  "scene_contract": {},
  "max_attempts": 3,
  "return_mode": "CHAT_ATTACHMENT_PREFERRED"
}
```

The manifest is immutable after signing. Revisions create a new attempt or child job.

## 7. Render Router

The router selects the best engine based on quality, reference complexity, video needs, hardware, quota, and policy.

### 7.1 Default routing hierarchy for images

For `FLOW_GRADE`:
1. Google Flow/Nano Banana Pro-class engine when connected and entitled.
2. Another approved premium image engine that meets the same scene contract.
3. Local advanced pipeline only if its measured quality profile meets the job threshold.
4. Otherwise `QUALITY_TARGET_UNAVAILABLE` — no silent downgrade.

For `HIGH`:
1. Best connected cloud engine within user-approved budget/entitlement.
2. Local advanced pipeline.

For `DRAFT_LOCAL`:
1. Local pipeline only.

### 7.2 Default routing hierarchy for video

For scenes requiring strong identity continuity:
- Prefer first/last-frame video generation after approved keyframes exist.
- Use ingredients/reference-capable video mode when it improves identity/object fidelity.
- Select Veo model variant according to supported feature matrix, not merely model name.
- Use local FFmpeg motion/parallax only for drafts or when explicitly requested.

## 8. Flow-like image pipeline

The existing `prompt + global IPAdapter chain` is retired as the final-quality architecture.

New pipeline:

```text
Asset Normalization
  -> Master Lock Registry
  -> Scene Decomposition
  -> Composition Blueprint
  -> Per-entity Regions / Masks
  -> Engine-specific Conditioning
  -> Draft Candidates
  -> Structural QA
  -> Identity QA
  -> Semantic QA
  -> Targeted Repair / Inpaint
  -> Detail Pass
  -> Upscale / Finish
  -> Final QA
```

### 8.1 Master Lock Registry

Each persistent entity has a master record:
- stable entity ID
- canonical reference set
- silhouette traits
- face/head traits
- palette
- clothing/accessories
- forbidden mutations
- allowed pose variation
- role-specific constraints

Examples:
- `character.max`
- `character.dad_max`
- `vehicle.yellow_bus`
- `background.bg01_bus_stop`

### 8.2 Scene Contract

Each scene must explicitly declare:
- exact visible entity count
- required entities
- forbidden entities
- camera position/lens/framing
- background ID
- action per entity
- relative spatial placement
- wardrobe state
- object state
- lighting/style lock
- text/logo/watermark prohibition

The generator is not allowed to infer character substitutions from lyrics.

### 8.3 Entity isolation

For multi-character scenes:
- Never rely solely on multiple global unmasked IPAdapter embeddings.
- Use engine-native ingredients/references where available.
- For local workflows, use regional/masked conditioning, ControlNet/layout constraints, or equivalent entity-isolated conditioning.
- Each character/object must retain its own reference binding and QA identity score.

### 8.4 Composition control

For complex scenes, require at least one of:
- composition sketch/layout map
- depth/pose/control image
- background master
- engine-native reference composition

A text prompt alone is insufficient for scenes whose acceptance depends on exact positioning.

## 9. Image QA hierarchy

A scene is accepted only after all mandatory gates pass.

### Gate A — deterministic file QA
- decodes
- expected format
- expected dimensions/aspect ratio
- nonempty
- not duplicate hash

### Gate B — structural QA
- expected visible character/object count
- no extra major subjects
- no missing required major subjects
- anatomy sanity where detectable
- no visible text/logo/watermark unless requested

### Gate C — identity QA
- compare each entity crop/region against canonical references
- embedding-based identity/style similarity where applicable
- clothing/palette consistency
- character-specific forbidden traits

### Gate D — semantic scene QA
- background matches requested scene
- camera/framing broadly matches contract
- required action is visible
- role/location constraints are respected

### Gate E — finish QA
- sharpness/detail threshold
- no obvious generation artifacts
- production-resolution output

Possible statuses:
- `VERIFIED`
- `HEURISTIC_PASS`
- `HUMAN_REVIEW`
- `RETRY`
- `REJECTED`

`FLOW_GRADE` final outputs cannot end in `HEURISTIC_PASS` if a mandatory semantic condition remains unverified; they must be reviewed or rerouted.

## 10. Repair strategy

Do not regenerate an entire scene for every defect.

Use targeted repair order:
1. local inpaint/edit for isolated defect
2. engine-native edit using original references
3. rerender only failed entity/region
4. rerender whole scene with revised composition blueprint
5. reroute to a stronger engine

Every retry records the reason and changed parameters.

## 11. Video pipeline

A video scene is built from approved still-state anchors, not directly from an unchecked text prompt.

```text
Approved Scene Keyframe
  -> Start Frame State
  -> Motion Contract
  -> Optional End Frame State
  -> Video Engine
  -> Frame Sampling
  -> Identity/Continuity QA
  -> Artifact QA
  -> Audio QA
  -> Approved Clip
```

### 11.1 Continuity state

For every shot, preserve:
- character identity
- wardrobe
- object count
- object geometry
- environment/background
- camera direction
- lighting direction
- start/end position
- previous-shot continuity anchors

### 11.2 Video QA

Sample frames at deterministic intervals and check:
- identity drift
- new/missing limbs
- object morphing
- extra duplicated characters
- vehicle geometry drift
- background replacement
- impossible motion
- start/end mismatch
- severe flicker/jumps

If a video fails, rerender or shorten the motion contract before accepting it.

## 12. Multi-device ChatGPT ingress

The user's device is only an interface. Job continuity lives in GitHub/Drive.

User experience target:
1. Open ChatGPT from any device.
2. Upload references/prompts/source files.
3. Say `render project X / scene Y`.
4. ChatGPT stages assets to Drive, writes manifest to GitHub, and submits the signed job.
5. A paired worker or cloud adapter performs the job.
6. Result manifest is committed.
7. ChatGPT retrieves the result from Drive.
8. ChatGPT returns a downloadable artifact in chat when the attachment bridge is available; otherwise it returns the Drive artifact link/card as fallback.

The implementation acceptance test must prove this flow from a second device/session, not only from the render PC.

## 13. Multi-worker model

Workers register a compact capability record:

```json
{
  "worker_id": "win1650-01",
  "online": true,
  "gpu": "GTX 1650 4GB",
  "engines": ["comfyui", "ffmpeg"],
  "capabilities": ["image_local_draft", "video_ffmpeg"],
  "current_job": null,
  "heartbeat_at": "..."
}
```

Future workers can advertise stronger GPUs or different engines.

The scheduler uses leases so only one worker executes a given local job.

## 14. Provider adapters

All provider-specific logic sits behind adapters.

Required adapter interface:
- `preflight()`
- `capabilities()`
- `estimate(job)`
- `stage_assets(job)`
- `submit(job)`
- `poll(job_id)`
- `collect(job_id)`
- `cancel(job_id)` when provider supports it

Initial adapters:
- `local_comfyui`
- `local_ffmpeg`
- `google_flow_image`
- `google_flow_video`
- optional `runway`

If browser/UI automation is required for a provider rather than a supported API/connector, that adapter must be explicitly marked `INTERACTIVE` and may require a human confirmation step. It must not masquerade as a fully autonomous API path.

## 15. Artifact return through ChatGPT

Preferred order:
1. Direct ChatGPT downloadable attachment/card sourced from Drive file bytes when the runtime supports it.
2. Connected Google Drive file card/link.
3. Local path only as a diagnostic fallback — never as the primary remote-device experience.

For images and ZIPs, the gateway should also generate a compact preview/manifest so ChatGPT can inspect QA before surfacing the final artifact.

## 16. Security

- HMAC-sign worker jobs.
- Secrets stay outside GitHub.
- Drive OAuth/provider tokens stay in the worker credential store or connector auth, never in job JSON.
- Verify SHA256 after every download/upload boundary.
- Paths remain sandboxed to known workspace roots.
- No arbitrary shell fields.
- No provider credential echoing to ChatGPT.
- Jobs are idempotent by `job_id + attempt_id`.

## 17. Cost and quota policy

Default:

```text
QUALITY_DEFAULT = FLOW_GRADE
LOCAL_DRAFT_ALLOWED = TRUE
AUTO_PURCHASE = FALSE
PAID_RENDER_REQUIRES_APPROVAL = TRUE
USE_EXISTING_ENTITLEMENTS = TRUE
SILENT_QUALITY_DOWNGRADE = FALSE
```

If the user later authorizes a monthly/job budget, the router may consume paid credits within that explicit limit. Without such authorization, it may use only already-entitled/no-additional-purchase capacity.

## 18. State machine

```text
RECEIVED
 -> ASSETS_STAGED
 -> VALIDATED
 -> ROUTED
 -> QUEUED
 -> RENDERING
 -> QA
 -> REPAIRING (optional loop)
 -> PACKAGING
 -> RETURNING
 -> COMPLETE
```

Failure states:
- `BLOCKED_ASSET`
- `BLOCKED_AUTH`
- `QUALITY_TARGET_UNAVAILABLE`
- `PROVIDER_QUOTA`
- `WORKER_OFFLINE`
- `RENDER_FAILED`
- `QA_REJECTED`
- `RETURN_FAILED`

A job never reports `COMPLETE` until the artifact exists, hashes match, required QA passed, and return metadata is available.

## 19. Observability

Every job records:
- selected engine and why
- rejected alternate engines and why
- render duration
- provider/local attempt count
- source asset hashes
- output hashes
- QA results by gate
- cost/credit estimate when available
- actual provider status when available
- artifact return state

No fabricated cost, quota, or provider status is allowed.

## 20. Migration from IMAGE_RENDER v1

Keep the current local Worker bridge and ComfyUI installation, but demote the present SD1.5 + global-IPAdapter path to `DRAFT_LOCAL`.

Do not delete it; it remains useful for:
- connectivity smoke tests
- quick layout drafts
- zero-cost fallback when the user explicitly permits lower quality

It must no longer satisfy `FLOW_GRADE` acceptance by itself.

## 21. Rollout phases

### Phase 1 — Asset Bus + portable job contract
- Drive project/job folders
- asset hashes and logical roles
- upload/download adapter
- result-return contract

### Phase 2 — Render Router + worker registry
- quality tiers
- engine capability registry
- worker heartbeat/lease
- no-silent-downgrade policy

### Phase 3 — Flow-like image pipeline
- master locks
- scene contracts
- multi-entity isolation
- composition controls
- upgraded QA

### Phase 4 — Cloud quality adapters
- Google/Flow image adapter where authorized
- provider entitlement/quota preflight
- best-quality routing

### Phase 5 — Artifact return through ChatGPT
- Drive result retrieval
- attachment/card return
- second-device E2E test

### Phase 6 — Flow-like video pipeline
- start/end frames
- ingredients/reference routing
- continuity state
- video QA
- final packaging

### Phase 7 — Additional workers/providers
- stronger render PC
- Runway or other approved adapters
- scheduler load balancing

## 22. Acceptance criteria

V2 is not considered complete until all of the following are demonstrated with real jobs:

1. From a device that is not the render PC, the user supplies prompt + references to ChatGPT.
2. Assets are staged to Drive and represented by immutable hashes in the job manifest.
3. GitHub signs and queues the job.
4. The router selects an engine according to `FLOW_GRADE` policy.
5. A render engine produces the output.
6. QA rejects a deliberately bad composition test.
7. QA accepts a deliberately good composition test.
8. Multi-character references do not collapse into a single blended identity in the reference test set.
9. The result is uploaded to Drive with verified checksum.
10. ChatGPT returns the artifact to the user via direct attachment/card when supported, or via connected Drive fallback.
11. The same project can be resumed from another ChatGPT session/device using persisted project/job state.
12. No paid purchase occurs without explicit user authorization.
13. `FLOW_GRADE` never silently falls back to the current SD1.5 smoke-test quality.

## 23. Explicit non-goals

- Claiming local GTX 1650 output is inherently equivalent to Nano Banana Pro/Veo.
- Remote desktop or unrestricted Windows control.
- Automatic purchasing of credits/subscriptions.
- Storing large binaries in GitHub.
- Claiming pixel-identical character reproduction when the provider/model cannot guarantee it.

## 24. Success definition

The system is successful when the user can treat ChatGPT as the single render desk from any device: send source assets and instructions once, receive a high-quality finished image/video back, and have the gateway automatically select the strongest authorized engine while preserving character identity, scene composition, continuity, auditability, and cost controls.
