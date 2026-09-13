# AI Money Ecosystem Autopilot V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable, policy-gated content production and YouTube automation subsystem under GitHub Brain 4.6 without widening trading, payment, credential, or unrestricted publishing authority.

**Architecture:** Add a dedicated money-ecosystem project authority and orchestrator that uses the existing Brain routing/skill model, then attach provider-neutral research, content, media, publishing, analytics, and revenue adapters. V1 defaults to private upload with human approval and keeps local GPU rendering optional rather than mandatory for Brain operation.

**Tech Stack:** Python, YAML/JSON project state, GitHub Actions, existing Cloudflare/Railway Brain infrastructure where applicable, official YouTube Data/Analytics APIs, FFmpeg-compatible renderer, provider adapters, optional Windows media worker.

**Spec:** `docs/superpowers/specs/2026-09-14-ai-money-ecosystem-autopilot-v1-design.md`

## Global Constraints

- Preserve GitHub Brain V4 / release 4.6 authority chain.
- Exactly one primary reasoning skill per request; up to two supporting skills only when materially useful.
- Do not create a parallel reasoning authority.
- Do not widen trading, payment, wallet, credential, destructive, or unrestricted publishing permissions.
- Default publishing mode is not public auto-publish.
- Use official owned-channel OAuth/API paths for YouTube writes.
- No secrets committed to GitHub.
- No fabricated analytics, revenue, live state, or provider availability.
- Provider/cloud/local media execution must remain replaceable through adapters.
- Local media worker is optional and must not become a normal Brain routing dependency.
- New behavior follows RED -> minimum GREEN -> regression -> validators -> CI -> review.

---

### Task 1: Add Project Authority and State Contracts

**Files:**
- Create: `AI_SKILL_LIBRARY/projects/ai_money_ecosystem.yaml`
- Create: `money_ecosystem/contracts.py`
- Create: `money_ecosystem/__init__.py`
- Test: `tests/money_ecosystem/test_contracts.py`

**Interfaces:**
- Produces dataclass/schema contracts for `ChannelProfile`, `TopicCandidate`, `ResearchPacket`, `ScriptPackage`, `ScenePlan`, `AssetManifest`, `RenderManifest`, `PublishPackage`, `ContentOutcome`, `RevenueRecord`.
- Project authority exposes publishing modes `DISABLED`, `PRIVATE_UPLOAD_ONLY`, `SCHEDULE_WITH_HUMAN_APPROVAL`, `AUTO_SCHEDULE`.

- [ ] Write failing contract tests validating required IDs, timestamps, provenance fields, actual-vs-estimated revenue separation, and publishing-state enum.
- [ ] Run targeted tests and verify RED.
- [ ] Implement minimal contracts and project authority.
- [ ] Run targeted tests and verify GREEN.
- [ ] Run Brain authority validators to confirm no permission widening.
- [ ] Commit `feat(money): add ecosystem authority and state contracts`.

### Task 2: Build Resumable Money Orchestrator

**Files:**
- Create: `money_ecosystem/orchestrator.py`
- Create: `money_ecosystem/state_store.py`
- Test: `tests/money_ecosystem/test_orchestrator.py`

**Interfaces:**
- Consumes project authority and typed state contracts.
- Produces `create_job`, `resume_job`, `advance_job`, `pause_job`, `fail_job`.
- Job stages: `DISCOVER`, `RESEARCH`, `SCRIPT`, `SCENES`, `ASSETS`, `VOICE`, `EDIT`, `QA`, `PACKAGE`, `UPLOAD`, `ANALYTICS`.

- [ ] Write failing idempotency/resume tests.
- [ ] Verify RED.
- [ ] Implement append-safe state transitions and stage guards.
- [ ] Verify GREEN.
- [ ] Add regression test ensuring repeated command does not duplicate already-complete stages.
- [ ] Commit `feat(money): add resumable orchestration state machine`.

### Task 3: Opportunity Engine

**Files:**
- Create: `money_ecosystem/opportunity.py`
- Create: `money_ecosystem/providers/opportunity/base.py`
- Create: `money_ecosystem/providers/opportunity/vidiq.py`
- Create: `money_ecosystem/providers/opportunity/youtube_public.py`
- Test: `tests/money_ecosystem/test_opportunity.py`

**Interfaces:**
- `OpportunityProvider.collect(query_context) -> list[OpportunitySignal]`
- `rank_topics(signals) -> list[TopicCandidate]`

- [ ] Write failing tests for provider failure tolerance, score transparency, and no revenue/view guarantee language.
- [ ] Verify RED.
- [ ] Implement bounded scoring for demand, trend, gap, evergreen, feasibility, originality, risk, saturation.
- [ ] Verify GREEN.
- [ ] Add degraded-mode test when vidIQ quota/auth is unavailable.
- [ ] Commit `feat(money): add opportunity ranking engine`.

### Task 4: Evidence-First Research Engine

**Files:**
- Create: `money_ecosystem/research.py`
- Create: `money_ecosystem/evidence.py`
- Test: `tests/money_ecosystem/test_research.py`

**Interfaces:**
- `build_research_packet(topic, evidence_items) -> ResearchPacket`
- `validate_claims(packet) -> ResearchValidation`

- [ ] Write failing tests for unsupported material claims, conflicting sources, stale current claims, and provenance retention.
- [ ] Verify RED.
- [ ] Implement claim/evidence mapping and fail-closed validation.
- [ ] Verify GREEN.
- [ ] Commit `feat(money): add evidence-first research packets`.

### Task 5: Original Script Engine

**Files:**
- Create: `money_ecosystem/script_engine.py`
- Create: `money_ecosystem/originality.py`
- Test: `tests/money_ecosystem/test_script_engine.py`

**Interfaces:**
- `generate_script(packet, channel_profile) -> ScriptPackage`
- `check_originality(script, evidence) -> OriginalityResult`

- [ ] Write failing tests for required structure, evidence traceability, unsupported-claim rejection, and single-source over-paraphrase rejection.
- [ ] Verify RED.
- [ ] Implement script package generation hooks and originality gate.
- [ ] Verify GREEN.
- [ ] Commit `feat(money): add original evidence-linked script engine`.

### Task 6: Scene Planner and Asset Manifest

**Files:**
- Create: `money_ecosystem/scene_planner.py`
- Create: `money_ecosystem/assets.py`
- Test: `tests/money_ecosystem/test_scene_planner.py`

**Interfaces:**
- `plan_scenes(script) -> list[ScenePlan]`
- `build_asset_manifest(scenes) -> AssetManifest`

- [ ] Write failing tests for duration coverage, narration coverage, asset provenance requirement, fallback asset type, and no duplicate scene IDs.
- [ ] Verify RED.
- [ ] Implement deterministic scene planning contracts.
- [ ] Verify GREEN.
- [ ] Commit `feat(money): add scene and asset planning`.

### Task 7: Provider-Neutral Media Adapters

**Files:**
- Create: `money_ecosystem/providers/media/base.py`
- Create: `money_ecosystem/providers/media/local_worker.py`
- Create: `money_ecosystem/providers/media/runway.py`
- Create: `money_ecosystem/providers/media/descript.py`
- Test: `tests/money_ecosystem/test_media_providers.py`

**Interfaces:**
- `ImageProvider.generate(scene) -> AssetResult`
- `VideoProvider.generate(scene) -> AssetResult`
- `VoiceProvider.synthesize(script_span) -> AssetResult`
- `EditorProvider.render(render_spec) -> RenderResult`

- [ ] Write failing tests proving provider outages do not mutate Brain authority or corrupt job state.
- [ ] Verify RED.
- [ ] Implement adapter interfaces and capability detection.
- [ ] Verify GREEN.
- [ ] Add quota-exhaustion fallback tests.
- [ ] Commit `feat(money): add replaceable media provider adapters`.

### Task 8: Optional Windows Media Worker

**Files:**
- Create: `money_ecosystem/worker/protocol.py`
- Create: `money_ecosystem/worker/allowlist.py`
- Create: `money_ecosystem/worker/client.py`
- Create: `money_ecosystem/worker/README_SETUP.md`
- Test: `tests/money_ecosystem/test_worker_protocol.py`

**Interfaces:**
- Signed job types limited to `IMAGE_RENDER`, `VIDEO_RENDER`, `VOICE_RENDER`, `FINAL_RENDER`, `MEDIA_PROBE`.
- Worker returns artifact manifest and status only.

- [ ] Write failing tests rejecting arbitrary shell commands, unknown job types, path traversal, and unsigned jobs.
- [ ] Verify RED.
- [ ] Implement allowlisted protocol and outbound-only client contract.
- [ ] Verify GREEN.
- [ ] Document one-time Windows setup without making it a Brain requirement.
- [ ] Commit `feat(money): add optional sandboxed media worker protocol`.

### Task 9: Quality-Control Pipeline

**Files:**
- Create: `money_ecosystem/qa.py`
- Create: `money_ecosystem/policy.py`
- Test: `tests/money_ecosystem/test_qa.py`

**Interfaces:**
- `run_pre_publish_qa(package) -> QAReport`
- Hard gates: originality, evidence, copyright/license, visual, audio, render, metadata truthfulness, synthetic-media disclosure, intended-channel identity.

- [ ] Write failing tests for each hard-block condition.
- [ ] Verify RED.
- [ ] Implement fail-closed gate aggregation.
- [ ] Verify GREEN.
- [ ] Commit `feat(money): add pre-publish policy and QA gates`.

### Task 10: YouTube OAuth and Owned-Channel Identity

**Files:**
- Create: `money_ecosystem/providers/youtube/auth.py`
- Create: `money_ecosystem/providers/youtube/channel.py`
- Test: `tests/money_ecosystem/test_youtube_auth.py`

**Interfaces:**
- `verify_owned_channel(auth_context, expected_channel_id) -> ChannelVerification`
- No secret/token persistence in repository.

- [ ] Write failing tests for wrong-account/wrong-channel rejection and expired authorization.
- [ ] Verify RED.
- [ ] Implement minimum-scope OAuth adapter contract.
- [ ] Verify GREEN with mocks/stubs only.
- [ ] Commit `feat(money): verify owned YouTube channel identity`.

### Task 11: Private Upload and Metadata Package

**Files:**
- Create: `money_ecosystem/providers/youtube/publish.py`
- Create: `money_ecosystem/metadata.py`
- Test: `tests/money_ecosystem/test_youtube_publish.py`

**Interfaces:**
- `build_publish_package(...) -> PublishPackage`
- `upload_private(package, verified_channel) -> UploadResult`
- `schedule_after_approval(upload, approval) -> PublishResult`

- [ ] Write failing tests enforcing `PRIVATE_UPLOAD_ONLY` default and blocking unresolved QA.
- [ ] Verify RED.
- [ ] Implement private-upload adapter against official YouTube API interface.
- [ ] Verify GREEN with API mocks.
- [ ] Add test that public auto-publish is impossible without explicit authority-state change.
- [ ] Commit `feat(money): add gated YouTube private publishing`.

### Task 12: Analytics Ingestion and Learning Loop

**Files:**
- Create: `money_ecosystem/analytics.py`
- Create: `money_ecosystem/learning.py`
- Test: `tests/money_ecosystem/test_analytics.py`

**Interfaces:**
- `ingest_metrics(...) -> ContentOutcome`
- `classify_outcome(history, outcome) -> OutcomeClass`
- `derive_patterns(outcomes) -> list[ReusablePattern]`

- [ ] Write failing tests separating fresh actual metrics from estimates and preventing one-video auto-scale.
- [ ] Verify RED.
- [ ] Implement channel-relative classification and bounded pattern extraction.
- [ ] Verify GREEN.
- [ ] Commit `feat(money): add analytics feedback loop`.

### Task 13: Revenue Ledger

**Files:**
- Create: `money_ecosystem/revenue.py`
- Test: `tests/money_ecosystem/test_revenue.py`

**Interfaces:**
- `record_actual_revenue(source, amount, period, evidence) -> RevenueRecord`
- `record_estimate(...)` stored separately and visibly marked estimate.

- [ ] Write failing tests preventing estimates from being counted as actual earnings.
- [ ] Verify RED.
- [ ] Implement revenue ledger.
- [ ] Verify GREEN.
- [ ] Commit `feat(money): add actual-vs-estimated revenue ledger`.

### Task 14: Dashboard/API Surface

**Files:**
- Create: `money_ecosystem/dashboard.py`
- Create: `money_ecosystem/api.py`
- Test: `tests/money_ecosystem/test_dashboard.py`

**Interfaces:**
- Read surfaces: overview, ideas, queue, assets, publishing, analytics, revenue, safety.
- Commands: create job, pause, resume, approve publish, global publishing kill switch.

- [ ] Write failing tests for Vietnamese plain-language state and hidden internal IDs by default.
- [ ] Verify RED.
- [ ] Implement compact dashboard/API models.
- [ ] Verify GREEN.
- [ ] Commit `feat(money): add ecosystem control surface`.

### Task 15: GitHub Brain Routing Integration

**Files:**
- Modify only the checkpoint-resolved project/skill routing files required by the current 4.6 harmonization contract.
- Test: new/extended Brain routing tests.

**Interfaces:**
- Money-ecosystem commands route through existing canonical skills; strengthen existing skills before adding any new skill.

- [ ] Write failing route tests for `Chạy hệ sinh thái`, `Tạo 3 video tuần này`, `Scale chủ đề đang thắng`.
- [ ] Run overlap/trigger-ownership analysis.
- [ ] Implement minimal routing/project-authority integration without increasing skill count unless the distinct-intent gate proves necessary.
- [ ] Run duplicate capability, authority, permission, and latency validators.
- [ ] Commit `feat(brain): integrate money ecosystem project routing`.

### Task 16: End-to-End Dry Run

**Files:**
- Create: `tests/money_ecosystem/test_end_to_end.py`
- Create: `docs/checkpoints/AI_MONEY_ECOSYSTEM_V1_HANDOFF.md`

**Interfaces:**
- End-to-end path stops before real public publishing.

- [ ] Build a synthetic topic fixture and mock provider suite.
- [ ] Run `discover -> research -> script -> scenes -> assets -> voice -> render -> QA -> publish package -> mocked private upload -> analytics`.
- [ ] Verify restart/resume from every persisted stage.
- [ ] Verify kill switch.
- [ ] Verify wrong-channel rejection.
- [ ] Verify zero modification to trading runtime switches/authority.
- [ ] Commit `test(money): verify end-to-end autopilot workflow`.

### Task 17: Full Validation and Review

**Files:**
- No new behavior unless verification finds defects.

- [ ] Run all money-ecosystem tests.
- [ ] Run `python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha <feature-head-sha>` in the approved CI environment.
- [ ] Run Brain/router/authority/skill-gateway validators.
- [ ] Confirm 109-skill count remains stable unless an approved distinct skill is intentionally introduced.
- [ ] Confirm no secrets and no trading/runtime switch mutation.
- [ ] Request code review.
- [ ] Resolve review findings with evidence.
- [ ] Prepare PR from `ai-money-ecosystem-autopilot-v1` to `main`.

### Task 18: Controlled Production Rollout

**Files:**
- Deployment/runtime config only after code review and approval conditions are satisfied.

- [ ] Deploy research/orchestration surfaces without public publishing.
- [ ] Verify exact production source SHA.
- [ ] Connect user-owned YouTube OAuth interactively.
- [ ] Verify exact intended channel ID.
- [ ] Enable `PRIVATE_UPLOAD_ONLY`.
- [ ] Produce first real private test video.
- [ ] User reviews first batch.
- [ ] Enable schedule-with-human-approval only after successful test batch.
- [ ] Keep `AUTO_SCHEDULE` disabled until a later explicit production decision.
