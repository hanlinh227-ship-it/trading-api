# AI Money Ecosystem Autopilot V1 — Design Spec

## Goal
Build a user-controlled, automation-first digital asset and YouTube revenue ecosystem that reuses the existing GitHub Brain 4.6 authority model without widening permissions, spending money automatically, or publishing unsafe/low-quality content.

## User outcome
The user should be able to operate the ecosystem primarily through ChatGPT with commands such as:

- `Chạy hệ sinh thái hôm nay`
- `Tạo 3 video tuần này`
- `Tìm niche tiềm năng nhất`
- `Scale chủ đề đang thắng`

The system handles planning, research, production orchestration, QA, packaging, upload preparation, analytics, and learning loops. High-impact actions remain gated.

## Non-goals
- No job/freelance marketplace workflow.
- No purchase of views, subscribers, ads, credits, or paid promotion.
- No hidden auto-spend.
- No crypto/trading execution linkage.
- No mass-produced AI spam.
- No copyright evasion or reuse of third-party content without rights.
- No automatic publication until the dedicated publishing authority is explicitly enabled and production-tested.

## Authority model
This subsystem must remain subordinate to GitHub Brain V4 Stable authority.

Request path:

`request -> task_router -> runtime_profile -> exactly_one_primary_skill -> validated_execution_capsule -> project authority -> money orchestrator -> bounded execution -> QA -> human/policy gate -> output`

Constraints:
- Brain 4.6 remains the reasoning authority.
- The ecosystem does not create a parallel reasoning system.
- Provider apps are execution/evidence capabilities only.
- STANDARD/DEEP may use at most two supporting skills when materially useful.
- No provider or upstream source grants financial, destructive, credential, or publishing authority.
- External model/tool availability must never be treated as guaranteed.

## System architecture

```text
ChatGPT
  -> GitHub Brain 4.6
  -> Money Orchestrator
      -> Opportunity Engine
      -> Research Engine
      -> Script Engine
      -> Scene Planner
      -> Asset Factory
      -> Voice Engine
      -> Video Editor Engine
      -> Thumbnail Engine
      -> Metadata/SEO Engine
      -> Publishing Engine
      -> Analytics Engine
      -> Revenue Engine
      -> Policy/QA Engine
  -> Shared Project State
  -> Decision Loop
```

## Phase-1 revenue focus
V1 focuses on one production pipeline and one distribution surface:

1. YouTube long-form.
2. YouTube Shorts derived from approved long-form research.
3. Asset reuse ledger prepared for later stock/digital-product expansion.

Stock marketplaces, KDP, affiliate links, and digital products are V2+ outputs, not blocking dependencies for V1.

## Opportunity Engine
Purpose: discover what is worth producing.

Inputs:
- vidIQ channel/trend/outlier/keyword data when authorized and within free quota.
- YouTube public search/trending data.
- Current owned-channel analytics when authorized.
- Web research.
- Existing content library and performance history.

Output: ranked `TopicCandidate` records.

Scoring dimensions:
- demand
- breakout/trend strength
- competition gap
- evergreen value
- monetization potential
- production feasibility
- originality opportunity
- copyright/policy risk
- saturation penalty

No score may be presented as a guarantee of views or revenue.

## Research Engine
Purpose: build a factual evidence packet before script writing.

Rules:
- Material factual claims should be supported by multiple credible sources when feasible.
- Fresh/current claims require live web verification.
- Conflicting evidence is surfaced, not majority-voted.
- Source provenance is stored with each research packet.
- Unsupported claims fail closed or are rewritten as uncertainty.

Output: `ResearchPacket`.

## Script Engine
Purpose: create original scripts optimized for viewer comprehension and retention, not article-like exposition.

A script package contains:
- hook
- promise
- narrative structure
- sections
- narration
- evidence references
- scene cues
- pattern interrupts
- CTA policy
- estimated runtime

The engine must reject copy/paraphrase workflows that are too close to a single source.

## Scene Planner
Converts an approved script into structured `ScenePlan` items.

Per scene:
- duration target
- narration span
- visual intent
- asset type
- camera/motion direction
- text overlay policy
- source/copyright status
- fallback asset type

Possible asset types:
- AI image
- AI video
- public-domain/appropriately licensed stock
- infographic
- map/diagram
- typography/motion graphic

## Asset Factory
Provider-neutral execution layer.

Preferred local/open-source workers when the user chooses zero-per-use-cost operation:
- FLUX.1 Schnell-compatible image generation
- Wan-family or compatible open-source video generation
- local image motion/compositing

Cloud connectors such as Runway may be used opportunistically when already connected and free quota exists, but must not become mandatory dependencies.

Asset QA checks:
- deformation/artifacts
- duplication
- extra subjects
- inconsistent characters
- text/logo/watermark issues
- aspect ratio
- scene mismatch
- licensing/provenance status

Failed assets are rejected before editing.

## Voice Engine
Provider-neutral voice abstraction.

Preferred zero-per-use-cost local engines may include Kokoro/Piper-compatible TTS where model/voice licensing allows commercial use.

Rules:
- fixed channel voice identity
- normalized loudness
- pronunciation dictionary for recurring names/terms
- no unlicensed celebrity impersonation
- voice/model license must be recorded

## Video Editor Engine
Primary deterministic render path:
- FFmpeg-compatible renderer
- optional MoviePy/Descript adapters

Responsibilities:
- timeline composition
- pan/zoom
- transitions
- captions
- music/SFX layers
- voice sync
- loudness normalization
- intro/outro templates
- horizontal master
- vertical derivatives

Outputs:
- master video
- short-form derivatives
- subtitles
- thumbnail source frames
- render manifest

## Thumbnail Engine
Creates multiple candidate concepts and scores them using channel-relative heuristics.

Dimensions:
- mobile readability
- curiosity gap
- clutter
- focal hierarchy
- novelty against recent channel thumbnails
- policy compliance

CTR thresholds are learned from the user channel and are not hard-coded as universal truths.

## Metadata/SEO Engine
Generates:
- title candidates
- description
- chapters
- tags when useful
- playlist recommendation
- disclosure flags for synthetic media when required
- scheduling recommendation

vidIQ is an optional optimization input, not an authority or hard dependency.

## Publishing Engine
V1 default mode:

`render -> automated QA -> upload PRIVATE -> human approval -> schedule/public`

Publishing authority states:
- `DISABLED`
- `PRIVATE_UPLOAD_ONLY`
- `SCHEDULE_WITH_HUMAN_APPROVAL`
- `AUTO_SCHEDULE`

Default: `PRIVATE_UPLOAD_ONLY` only after OAuth/API upload integration is production-tested.

Kill switch:
- a single global flag disables all outbound publication actions.

No upload is allowed when:
- copyright status is unresolved
- research packet is invalid
- render QA fails
- metadata contains unsupported claims
- auth identity does not match the intended owned channel

## YouTube integration
Use official YouTube Data API/OAuth for owned-channel publishing and metadata workflows where possible.

vidIQ may provide analytics/research/metadata support but is not treated as the canonical uploader.

Secrets/tokens:
- never committed to GitHub
- stored in an approved secret manager/runtime environment
- minimum required scopes only
- refresh/revocation behavior documented

## Analytics Engine
Owned-channel analytics inputs:
- views
- impressions
- CTR
- average view duration
- average view percentage
- retention curve
- subscribers gained/lost
- traffic sources
- returning/new viewer signals when available
- revenue metrics when monetized and authorized

Analytics produce `ContentOutcome` records rather than hidden reasoning.

## Learning loop
The system may learn reusable metadata only:
- winning topic clusters
- hook structures
- thumbnail characteristics
- title patterns
- retention failure timestamps/categories
- production cost/time statistics

It must not persist hidden chain-of-thought.

Decision loop:

`publish -> measure -> classify -> extract reusable pattern -> generate next candidates -> research again`

No automatic scale-up occurs solely from one successful video.

## Revenue Engine
V1 records actual platform revenue only when available from authorized analytics.

Future revenue lanes:
- YouTube ads/Premium
- affiliate revenue
- stock image/video licensing
- digital products
- ebooks/KDP

Revenue estimates must be labeled estimates and separated from actual earnings.

## Shared state
Recommended project-state entities:
- `ChannelProfile`
- `TopicCandidate`
- `ResearchPacket`
- `ScriptPackage`
- `ScenePlan`
- `AssetManifest`
- `RenderManifest`
- `PublishPackage`
- `ContentOutcome`
- `RevenueRecord`

State should be resumable and idempotent so interrupted jobs do not restart from zero.

## Scheduling model
The system supports:
- manual run
- scheduled research cycle
- scheduled production queue
- conditional analytics review

Recurring tasks should remain bounded. Production should stop when backlog, storage, QA failure rate, or channel policy risk exceeds thresholds.

## Cost model
The system distinguishes:
- zero paid API/credit use
- local compute/electricity/storage cost
- optional paid-provider use

It must never describe local GPU workloads as literally costless when electricity/hardware wear is material.

## User-local worker mode
If the user wants continuous generation without paid cloud GPU quotas, a Windows worker may be used.

Worker responsibilities:
- receive signed jobs
- download approved model/workflow manifests
- execute image/video/voice/render tasks
- upload artifacts/status back to the orchestration layer

Security:
- outbound-only connection preferred
- no arbitrary shell execution from chat
- allowlisted job types
- workspace sandbox
- secrets isolated from model files
- explicit resource limits

The user should not need to operate ComfyUI/FFmpeg manually after initial setup.

## Cloud-first compatibility
The Brain itself remains cloud-first and zero-local for normal research/routing. Local worker usage is optional and belongs only to media rendering when the user explicitly chooses that mode. The core Brain must continue to function if the worker is offline.

## Quality gates
Required gates before publish:
1. topic originality
2. source/evidence validity
3. script originality
4. copyright/license status
5. visual QA
6. audio QA
7. render integrity
8. metadata truthfulness
9. synthetic-media disclosure decision
10. intended-channel identity check

## Safety controls
Hard prohibitions:
- no buying/automating fake engagement
- no credential harvesting
- no bypass of Google/YouTube security
- no automatic billing/spend
- no posting to an unverified channel identity
- no silent license assumption
- no fabricated analytics/revenue

## Observability
Dashboard/status should expose:
- pipeline state
- current job
- queued jobs
- failed jobs
- QA failure reason
- asset/render locations
- intended channel
- publish state
- analytics freshness
- actual vs estimated revenue
- provider/free-quota usage

## Dashboard UX
Primary surfaces:
- Overview
- Ideas
- Production Queue
- Assets
- Publishing
- Analytics
- Revenue
- Settings/Safety

User-facing language defaults to Vietnamese and hides internal IDs unless needed for debugging.

## Rollout
### V1A — Foundation
- project authority and state schema
- money orchestrator
- opportunity/research/script interfaces
- no publishing writes

### V1B — Production
- scene planner
- asset abstraction
- voice abstraction
- renderer
- QA

### V1C — YouTube integration
- OAuth
- owned channel verification
- private upload
- metadata update
- scheduling gate

### V1D — Analytics loop
- analytics ingestion
- outcome classifier
- winner/loser pattern extraction
- topic-cluster recommendations

### V1E — Derivatives
- Shorts generation
- asset reuse ledger
- export package for future stock/digital-product lanes

## Success criteria
The V1 system is successful when:
- a user command can create a resumable production job
- the system can research and produce an original script with source provenance
- the system can generate or assemble required media through provider-neutral adapters
- a complete 1080p video can be rendered and QA-checked
- the correct authorized YouTube channel is verified before upload
- an approved video can be uploaded privately through official authorization
- analytics from published content can be ingested and converted into bounded recommendations
- no payment, trading, destructive, credential, or unrestricted auto-publish authority is introduced
- failure in any external provider does not corrupt Brain 4.6 authority or existing trading runtime

## User responsibilities
The user only needs to perform actions that cannot safely/legally be delegated:
- choose/confirm the owned YouTube channel
- complete Google OAuth/2FA prompts personally
- install the optional local media worker once if choosing zero-paid-GPU mode
- confirm commercial rights for any personal third-party assets supplied manually
- review the first production batch before enabling scheduling automation
- configure monetization/payment/tax details directly with the platform

Everything else should be automated where technically available and policy-compliant.
