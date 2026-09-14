# Curious Beyond Render Gateway V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-device, multi-worker, multi-engine render gateway where ChatGPT can accept prompts/references from any device, persist assets in Google Drive, route jobs through GitHub, render at the strongest authorized quality tier, run truthful QA, and return image/video artifacts back through ChatGPT/Drive.

**Architecture:** Google Drive is the binary asset/artifact plane; GitHub is the signed control plane. A provider-agnostic render orchestrator selects between local workers and authorized cloud/interactive providers under a fail-closed `FLOW_GRADE` policy. The current SD1.5 + global IPAdapter path is retained only as `DRAFT_LOCAL`, while new master-lock, scene-contract, QA, repair, and artifact-return layers enforce identity/composition/continuity.

**Tech Stack:** Python 3.11, GitHub control files + existing HMAC worker bridge, Google Drive API/connector, ComfyUI local adapter, FFmpeg, Pillow, pytest, optional Google auth libraries on render workers, provider adapters behind typed interfaces.

**Spec:** `docs/superpowers/specs/2026-09-14-curious-beyond-render-gateway-v2-design.md`

## Global Constraints

- `QUALITY_DEFAULT = FLOW_GRADE`
- `LOCAL_DRAFT_ALLOWED = TRUE`
- `AUTO_PURCHASE = FALSE`
- `PAID_RENDER_REQUIRES_APPROVAL = TRUE`
- `USE_EXISTING_ENTITLEMENTS = TRUE`
- `SILENT_QUALITY_DOWNGRADE = FALSE`
- GitHub stores compact text metadata only; large image/video/ZIP binaries stay out of GitHub.
- Google Drive is the primary asset/artifact bus.
- No arbitrary shell execution; all worker jobs remain allowlisted and typed.
- `FLOW_GRADE` must fail closed with `QUALITY_TARGET_UNAVAILABLE` if no qualifying provider is authorized/available.
- A file existing on disk is not sufficient for `VERIFIED`; QA status must reflect actual evidence.
- Local GTX 1650 output must never be described as inherently equivalent to Nano Banana Pro/Veo.
- All jobs are idempotent by `job_id + attempt_id`.
- Provider credentials/tokens never appear in GitHub job JSON or ChatGPT-visible diagnostics.

---

## File Structure

Create a focused package rather than expanding `worker/runtime.py` further:

```text
money_ecosystem/render_gateway/
  __init__.py
  contract.py             # provider-agnostic job + scene + asset contracts
  state.py                # job state machine and failure states
  asset_store.py          # AssetStore protocol + hashing helpers
  drive_store.py          # Google Drive worker-side asset client
  control_plane.py        # GitHub-manifest paths and immutable attempt model
  worker_registry.py      # heartbeat/capabilities/leases
  router.py               # quality/cost/provider selection
  master_lock.py          # persistent entity identity records
  scene_contract.py       # scene validation and exact entity constraints
  qa.py                   # deterministic/structural/identity/semantic/finish gates
  repair.py               # retry/repair/reroute decision policy
  artifacts.py            # output manifest + Drive return metadata
  orchestrator.py         # top-level state-machine coordinator
  providers/
    __init__.py
    base.py                # provider protocol
    local_comfyui.py       # wraps existing local image runtime as DRAFT_LOCAL
    local_ffmpeg.py        # local draft/final assembly adapter
    google_flow_image.py   # INTERACTIVE/API capability-gated image adapter
    google_flow_video.py   # INTERACTIVE/API capability-gated video adapter
    runway.py              # optional adapter, disabled unless authorized
```

Tests mirror the package under `tests/money_ecosystem/render_gateway/`.

---

### Task 1: Provider-Agnostic Contract + State Machine

**Files:**
- Create: `money_ecosystem/render_gateway/__init__.py`
- Create: `money_ecosystem/render_gateway/contract.py`
- Create: `money_ecosystem/render_gateway/state.py`
- Test: `tests/money_ecosystem/render_gateway/test_contract.py`
- Test: `tests/money_ecosystem/render_gateway/test_state.py`

**Interfaces:**
- Produces: `RenderJob.from_dict(payload) -> RenderJob`
- Produces: `SceneContract`, `AssetRef`, `QualityTier`, `CostPolicy`, `ReturnMode`
- Produces: `transition(current: JobState, target: JobState) -> JobState`

- [ ] **Step 1: Write failing contract tests**

```python
from money_ecosystem.render_gateway.contract import RenderJob, QualityTier


def test_flow_grade_is_explicit_and_assets_are_hashed():
    job = RenderJob.from_dict({
        "job_id": "job-1",
        "attempt_id": "a1",
        "project_id": "max-bus",
        "job_type": "IMAGE_RENDER",
        "quality_tier": "FLOW_GRADE",
        "cost_policy": "USE_EXISTING_ENTITLEMENTS",
        "aspect_ratio": "16:9",
        "output_resolution": "1920x1080",
        "prompt": "Max waves beside the bus",
        "negative_constraints": ["no extra characters"],
        "assets": [{
            "asset_id": "character.max",
            "drive_file_id": "drive-1",
            "logical_role": "character_reference",
            "mime_type": "image/png",
            "byte_size": 100,
            "sha256": "a" * 64,
            "source": "user_upload",
            "rights_note": "user supplied",
        }],
        "scene_contract": {"required_entities": ["character.max"]},
        "max_attempts": 3,
        "return_mode": "CHAT_ATTACHMENT_PREFERRED",
    })
    assert job.quality_tier is QualityTier.FLOW_GRADE
    assert job.assets[0].sha256 == "a" * 64
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest -q tests/money_ecosystem/render_gateway/test_contract.py`
Expected: import/module failure.

- [ ] **Step 3: Implement frozen dataclasses/enums and validation**

```python
class QualityTier(str, Enum):
    FLOW_GRADE = "FLOW_GRADE"
    HIGH = "HIGH"
    DRAFT_LOCAL = "DRAFT_LOCAL"

class CostPolicy(str, Enum):
    USE_EXISTING_ENTITLEMENTS = "USE_EXISTING_ENTITLEMENTS"
    ASK_BEFORE_PAID = "ASK_BEFORE_PAID"
    LOCAL_ONLY = "LOCAL_ONLY"
```

Validation must reject missing `attempt_id`, malformed SHA256, unknown quality/cost values, empty prompt, missing scene contract, and `max_attempts` outside `1..5`.

- [ ] **Step 4: Add state-machine tests**

```python
from money_ecosystem.render_gateway.state import JobState, transition, InvalidTransition


def test_complete_requires_returning_path():
    with pytest.raises(InvalidTransition):
        transition(JobState.QA, JobState.COMPLETE)
```

Allowed happy path:
`RECEIVED -> ASSETS_STAGED -> VALIDATED -> ROUTED -> QUEUED -> RENDERING -> QA -> PACKAGING -> RETURNING -> COMPLETE`.

- [ ] **Step 5: Run Task 1 tests and commit**

Run: `python -m pytest -q tests/money_ecosystem/render_gateway/test_contract.py tests/money_ecosystem/render_gateway/test_state.py`
Expected: PASS.

Commit: `feat(render-gateway): add portable contract and state machine`

---

### Task 2: Asset Store Protocol + Google Drive Worker Client

**Files:**
- Create: `money_ecosystem/render_gateway/asset_store.py`
- Create: `money_ecosystem/render_gateway/drive_store.py`
- Create: `money_ecosystem/render_gateway/requirements-drive.txt`
- Test: `tests/money_ecosystem/render_gateway/test_asset_store.py`
- Test: `tests/money_ecosystem/render_gateway/test_drive_store.py`

**Interfaces:**
- Produces: `sha256_file(path: Path) -> str`
- Produces: `AssetStore.fetch(asset: AssetRef, dest: Path) -> Path`
- Produces: `AssetStore.put(path: Path, logical_role: str, parent_id: str) -> StoredArtifact`

- [ ] **Step 1: Write SHA and boundary tests**

```python
def test_fetch_rejects_checksum_mismatch(tmp_path, fake_drive):
    asset = asset_ref(sha256="0" * 64)
    with pytest.raises(AssetIntegrityError, match="SHA256"):
        fake_drive.fetch(asset, tmp_path / "ref.png")
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/money_ecosystem/render_gateway/test_asset_store.py tests/money_ecosystem/render_gateway/test_drive_store.py`

- [ ] **Step 3: Implement protocol and Drive client**

`drive_store.py` must accept an injected credential/token provider; it must not read secrets from job JSON. Use Google Drive `files.get?alt=media` for downloads and resumable/simple upload for outputs. Hash after every download and before/after every upload boundary.

`requirements-drive.txt`:

```text
google-auth>=2.35,<3
google-auth-oauthlib>=1.2,<2
google-api-python-client>=2.140,<3
```

- [ ] **Step 4: Add path/layout helper tests**

Canonical logical paths must map to:
`CuriousBeyond_RenderGateway/projects/<project_id>/jobs/<job_id>/<role>/`.

- [ ] **Step 5: Run tests and commit**

Commit: `feat(render-gateway): add Drive asset bus with integrity checks`

---

### Task 3: Immutable GitHub Control Manifest + Signed Attempt Model

**Files:**
- Create: `money_ecosystem/render_gateway/control_plane.py`
- Modify: `money_ecosystem/worker/protocol.py`
- Modify: `money_ecosystem/worker/allowlist.py`
- Test: `tests/money_ecosystem/render_gateway/test_control_plane.py`
- Test: `tests/money_ecosystem/test_worker_protocol.py`

**Interfaces:**
- Produces: `attempt_path(project_id, job_id, attempt_id) -> str`
- Produces: `result_path(project_id, job_id, attempt_id) -> str`
- Existing worker signature verification remains HMAC-SHA256.

- [ ] **Step 1: Write tests proving signed payload immutability**

```python
def test_revision_requires_new_attempt_id():
    original = make_job(attempt_id="a1")
    revised = dict(original, prompt="changed")
    with pytest.raises(ControlPlaneError, match="immutable"):
        assert_same_attempt(original, revised)
```

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Implement compact control paths**

Use text-only JSON under:

```text
render_gateway/jobs/<project>/<job>/<attempt>/request.json
render_gateway/jobs/<project>/<job>/<attempt>/signed.json
render_gateway/jobs/<project>/<job>/<attempt>/result.json
```

No binary payload field is permitted.

- [ ] **Step 4: Extend worker allowlist to accept typed gateway jobs only**

Reject `command`, `cmd`, `shell`, `powershell`, `script`, `argv`, `executable` recursively exactly as current security policy does.

- [ ] **Step 5: Run regression tests and commit**

Commit: `feat(render-gateway): add immutable signed control manifests`

---

### Task 4: Worker Registry, Heartbeats, and Leases

**Files:**
- Create: `money_ecosystem/render_gateway/worker_registry.py`
- Modify: `money_ecosystem/worker/runner.py`
- Test: `tests/money_ecosystem/render_gateway/test_worker_registry.py`
- Test: `tests/money_ecosystem/test_worker_runner_reliability.py`

**Interfaces:**
- Produces: `WorkerCapabilities`
- Produces: `acquire_lease(job_id, attempt_id, worker_id, now) -> Lease`
- Produces: `lease_valid(lease, now) -> bool`

- [ ] **Step 1: Write lease race test**

Two workers must not acquire the same active lease.

- [ ] **Step 2: Write stale-worker test**

A heartbeat older than configured TTL must be considered offline and route to `WORKER_OFFLINE` when no alternative exists.

- [ ] **Step 3: Implement worker capability record**

Required fields:
`worker_id`, `online`, `gpu`, `engines`, `capabilities`, `current_job`, `heartbeat_at`, `runner_build`, `runtime_build`.

- [ ] **Step 4: Integrate heartbeat publication without shell widening**

Existing runner remains outbound-only and bounded.

- [ ] **Step 5: Run tests and commit**

Commit: `feat(render-gateway): add worker registry and job leases`

---

### Task 5: Provider Adapter Interface + Local Adapter Migration

**Files:**
- Create: `money_ecosystem/render_gateway/providers/__init__.py`
- Create: `money_ecosystem/render_gateway/providers/base.py`
- Create: `money_ecosystem/render_gateway/providers/local_comfyui.py`
- Create: `money_ecosystem/render_gateway/providers/local_ffmpeg.py`
- Modify: `money_ecosystem/worker/runtime.py`
- Test: `tests/money_ecosystem/render_gateway/test_provider_base.py`
- Test: `tests/money_ecosystem/render_gateway/test_local_comfyui_provider.py`

**Interfaces:**

```python
class RenderProvider(Protocol):
    def preflight(self) -> ProviderStatus: ...
    def capabilities(self) -> ProviderCapabilities: ...
    def estimate(self, job: RenderJob) -> Estimate: ...
    def stage_assets(self, job: RenderJob) -> StagedJob: ...
    def submit(self, job: StagedJob) -> ProviderJob: ...
    def poll(self, provider_job_id: str) -> ProviderPoll: ...
    def collect(self, provider_job_id: str) -> list[Path]: ...
    def cancel(self, provider_job_id: str) -> None: ...
```

- [ ] **Step 1: Write capability tests**

Current SD1.5 path must advertise `max_quality_tier=DRAFT_LOCAL`, never `FLOW_GRADE`.

- [ ] **Step 2: Run RED**

- [ ] **Step 3: Wrap current `IMAGE_RENDER v1` as local provider**

Reuse `ComfyUIAdapter`, `SerialImageExecutor`, and `build_sd15_reference_workflow`; do not duplicate existing working code.

- [ ] **Step 4: Add FFmpeg provider capability record**

It may advertise assembly/motion capabilities but not Flow-grade generative video.

- [ ] **Step 5: Run tests and commit**

Commit: `refactor(render-gateway): wrap local engines behind provider adapters`

---

### Task 6: Master Lock Registry + Exact Scene Contract

**Files:**
- Create: `money_ecosystem/render_gateway/master_lock.py`
- Create: `money_ecosystem/render_gateway/scene_contract.py`
- Test: `tests/money_ecosystem/render_gateway/test_master_lock.py`
- Test: `tests/money_ecosystem/render_gateway/test_scene_contract.py`

**Interfaces:**
- Produces: `MasterEntity`
- Produces: `validate_scene_against_masters(scene, registry) -> None`

- [ ] **Step 1: Encode Max/Dad Max/bus/BG1 fixture records**

Tests must include distinct forbidden mutations, wardrobe, palette, and role constraints.

- [ ] **Step 2: Reject blended/ambiguous scene bindings**

A scene with two characters must bind each visible entity to its own stable entity ID and reference set.

- [ ] **Step 3: Require exact composition fields**

For nontrivial multi-entity scenes require: exact visible count, required/forbidden entities, background ID, camera/framing, action map, spatial placement, wardrobe state, object state, style/lighting lock, no-text/logo/watermark rule.

- [ ] **Step 4: Run tests and commit**

Commit: `feat(render-gateway): add master identity locks and scene contracts`

---

### Task 7: Flow-Like Composition Blueprint + Local Regional Conditioning Contract

**Files:**
- Create: `money_ecosystem/render_gateway/composition.py`
- Create: `money_ecosystem/worker/image_workflow_v2.py`
- Test: `tests/money_ecosystem/render_gateway/test_composition.py`
- Test: `tests/money_ecosystem/test_image_workflow_v2.py`

**Interfaces:**
- Produces: `CompositionBlueprint`
- Produces: `build_local_regional_workflow(scene, masters, blueprint, ...) -> dict`

- [ ] **Step 1: Write test that two characters receive isolated conditioning regions**

The workflow graph must not use a single unmasked global IPAdapter chain as the only identity mechanism.

- [ ] **Step 2: Require at least one composition anchor**

Accepted anchors: layout sketch, depth/pose/control image, background master, provider-native composition reference.

- [ ] **Step 3: Implement low-VRAM local draft workflow**

Use regional/masked conditioning where supported; if required nodes are absent, fail with `LOCAL_COMPOSITION_CAPABILITY_MISSING` rather than silently falling back to v1.

- [ ] **Step 4: Run tests and commit**

Commit: `feat(render-gateway): add entity-isolated composition pipeline`

---

### Task 8: Quality Gates + Semantic Truthfulness

**Files:**
- Create: `money_ecosystem/render_gateway/qa.py`
- Modify: `money_ecosystem/worker/image_qa.py`
- Test: `tests/money_ecosystem/render_gateway/test_qa.py`

**Interfaces:**
- Produces: `QAReport`
- Produces: `evaluate_scene(scene, artifact, evidence) -> QAReport`

- [ ] **Step 1: Implement Gate A deterministic QA**

Reuse decode/dimension/hash checks.

- [ ] **Step 2: Implement evidence-bearing gates B-E**

Each assertion stores `status`, `score`, `evidence_source`, `reason`.

- [ ] **Step 3: Add deliberate bad-composition fixture**

A two-character white-background image missing the bus/BG1 must not pass a Scene-1 `FLOW_GRADE` contract even if dimensions are correct.

- [ ] **Step 4: Enforce truthful terminal statuses**

`FLOW_GRADE` with any mandatory semantic requirement unverified => `HUMAN_REVIEW` or `RETRY`, never `VERIFIED`.

- [ ] **Step 5: Run tests and commit**

Commit: `feat(render-gateway): add structural identity semantic and finish QA`

---

### Task 9: Repair Planner + Render Router + Cost Policy

**Files:**
- Create: `money_ecosystem/render_gateway/repair.py`
- Create: `money_ecosystem/render_gateway/router.py`
- Test: `tests/money_ecosystem/render_gateway/test_repair.py`
- Test: `tests/money_ecosystem/render_gateway/test_router.py`

**Interfaces:**
- Produces: `route(job, providers, workers) -> RouteDecision`
- Produces: `next_repair(report, attempt_history) -> RepairDecision`

- [ ] **Step 1: Write no-silent-downgrade test**

```python
def test_flow_grade_never_routes_to_draft_local_only():
    with pytest.raises(QualityTargetUnavailable):
        route(flow_job(), providers=[draft_local_provider()], workers=[])
```

- [ ] **Step 2: Write spending-policy test**

A provider that requires new paid credits must not be selected under `USE_EXISTING_ENTITLEMENTS` unless current entitlement explicitly covers the job.

- [ ] **Step 3: Implement deterministic route scoring**

Score quality qualification first, then capability fit, authorization/entitlement, availability, estimated latency, and cost. Record rejected alternatives and reasons.

- [ ] **Step 4: Implement repair order from spec**

`local inpaint/edit -> provider edit -> failed region rerender -> whole scene rerender -> stronger provider`.

- [ ] **Step 5: Run tests and commit**

Commit: `feat(render-gateway): add quality-first router and repair policy`

---

### Task 10: Cloud/Interactive Quality Adapters with Fail-Closed Capability Gates

**Files:**
- Create: `money_ecosystem/render_gateway/providers/google_flow_image.py`
- Create: `money_ecosystem/render_gateway/providers/google_flow_video.py`
- Create: `money_ecosystem/render_gateway/providers/runway.py`
- Test: `tests/money_ecosystem/render_gateway/test_google_flow_provider.py`
- Test: `tests/money_ecosystem/render_gateway/test_runway_provider.py`

**Interfaces:**
- Providers expose `mode = API | CONNECTOR | INTERACTIVE | DISABLED`.

- [ ] **Step 1: Write fail-closed tests for unsupported automation**

If no supported authenticated API/connector exists, `preflight()` must return `INTERACTIVE` or `BLOCKED_AUTH`; it must not pretend to be autonomous.

- [ ] **Step 2: Write entitlement/quota capability test**

Unknown quota/plan must be reported as unknown and must not be fabricated.

- [ ] **Step 3: Implement provider shells with explicit feature matrices**

Image matrix includes multi-reference/ingredients/edit/upscale capabilities; video matrix includes text-to-video, first/last-frame, reference/ingredients, audio, resolution.

- [ ] **Step 4: Keep provider execution disabled until a real supported auth path is connected**

This preserves truthful status while allowing the router/orchestrator to be complete.

- [ ] **Step 5: Run tests and commit**

Commit: `feat(render-gateway): add capability-gated cloud quality adapters`

---

### Task 11: Artifact Packaging + Drive Return Metadata

**Files:**
- Create: `money_ecosystem/render_gateway/artifacts.py`
- Modify: `money_ecosystem/worker/image_package.py`
- Test: `tests/money_ecosystem/render_gateway/test_artifacts.py`

**Interfaces:**
- Produces: `ReturnArtifact`
- Produces: `package_and_upload(job, files, qa_report, asset_store) -> ReturnManifest`

- [ ] **Step 1: Write output hash tests**

Every returned artifact requires `drive_file_id`, MIME type, byte size, SHA256, QA summary, logical role.

- [ ] **Step 2: Write return fallback test**

Preferred order: `CHAT_ATTACHMENT_PREFERRED -> DRIVE_CARD -> LOCAL_PATH_DIAGNOSTIC`.

- [ ] **Step 3: Implement package upload**

Upload final image/video/ZIP and compact manifest to Drive; store only metadata in GitHub.

- [ ] **Step 4: Run tests and commit**

Commit: `feat(render-gateway): add Drive-backed artifact return manifests`

---

### Task 12: Top-Level Orchestrator

**Files:**
- Create: `money_ecosystem/render_gateway/orchestrator.py`
- Modify: `money_ecosystem/worker/runtime.py`
- Test: `tests/money_ecosystem/render_gateway/test_orchestrator.py`

**Interfaces:**
- Produces: `RenderOrchestrator.run(job: RenderJob) -> RenderResult`

- [ ] **Step 1: Write state progression test**

Assert real progression through asset staging, validation, routing, rendering, QA, repair if needed, packaging, returning.

- [ ] **Step 2: Write failure-state tests**

Cover: `BLOCKED_ASSET`, `BLOCKED_AUTH`, `QUALITY_TARGET_UNAVAILABLE`, `PROVIDER_QUOTA`, `WORKER_OFFLINE`, `RENDER_FAILED`, `QA_REJECTED`, `RETURN_FAILED`.

- [ ] **Step 3: Implement orchestrator as dependency-injected coordinator**

No provider-specific code in orchestrator.

- [ ] **Step 4: Wire current worker gateway job type to orchestrator**

Keep old direct `IMAGE_RENDER v1` callable for explicit `DRAFT_LOCAL` compatibility only.

- [ ] **Step 5: Run tests and commit**

Commit: `feat(render-gateway): orchestrate signed multi-engine render jobs`

---

### Task 13: Flow-Like Video Contract + Continuity QA

**Files:**
- Create: `money_ecosystem/render_gateway/video.py`
- Create: `money_ecosystem/render_gateway/video_qa.py`
- Test: `tests/money_ecosystem/render_gateway/test_video.py`
- Test: `tests/money_ecosystem/render_gateway/test_video_qa.py`

**Interfaces:**
- Produces: `MotionContract`
- Produces: `ContinuityState`
- Produces: `sample_video_frames(path, interval_seconds) -> list[Path]`

- [ ] **Step 1: Require approved keyframe before Flow-grade video submit**

- [ ] **Step 2: Model start/end frame state and motion contract**

Persist identity, wardrobe, object count/geometry, environment, camera direction, lighting direction, start/end position, previous-shot anchors.

- [ ] **Step 3: Implement deterministic FFmpeg frame sampling**

- [ ] **Step 4: Evaluate continuity evidence without claiming unsupported certainty**

If no semantic verifier is connected, status is `HUMAN_REVIEW`, not `VERIFIED`.

- [ ] **Step 5: Run tests and commit**

Commit: `feat(render-gateway): add anchored video continuity pipeline`

---

### Task 14: Second-Device End-to-End Acceptance Harness

**Files:**
- Create: `tests/money_ecosystem/render_gateway/test_e2e_manifest_flow.py`
- Create: `docs/render_gateway/OPERATIONS.md`
- Create: `docs/render_gateway/ACCEPTANCE_CHECKLIST.md`
- Modify: `.github/workflows/curious-beyond-worker-ci.yml`

**Interfaces:**
- No new runtime interface; validates the full system contract.

- [ ] **Step 1: Add CI coverage for all pure-Python gateway tests**

- [ ] **Step 2: Add documented real-hardware acceptance procedure**

Procedure must require a ChatGPT session/device that is not the render PC, Drive asset staging, signed GitHub job, worker/cloud execution, QA, Drive upload, and artifact return.

- [ ] **Step 3: Add deliberate good/bad composition acceptance fixtures**

Bad fixture must be rejected; good fixture must pass applicable gates.

- [ ] **Step 4: Verify no paid purchase side effects**

Acceptance checklist explicitly records provider entitlement source and confirms `AUTO_PURCHASE = FALSE`.

- [ ] **Step 5: Run full tests**

Run:

```bash
python -m pytest -q tests/money_ecosystem/render_gateway tests/money_ecosystem/test_worker_protocol.py tests/money_ecosystem/test_worker_runner_reliability.py tests/money_ecosystem/test_image_workflow_v2.py
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

Commit: `test(render-gateway): add multi-device end-to-end acceptance harness`

---

## Execution Order and Checkpoints

1. Tasks 1-5: foundation usable independently — portable contracts, Drive bus, signed manifests, worker registry, provider interface.
2. Tasks 6-9: image quality core — master locks, scene contracts, composition, QA, repair, quality-first router.
3. Tasks 10-12: cloud capability gating, artifact return, orchestrator.
4. Task 13: anchored video pipeline.
5. Task 14: real second-device acceptance gate.

At each checkpoint, run the relevant test subset and inspect a real control-plane artifact before proceeding.

## Self-Review Against Spec

- Spec §§1-7: covered by Tasks 1-5 and 9-10.
- Spec §§8-10: covered by Tasks 6-9.
- Spec §11: covered by Task 13.
- Spec §§12-15: covered by Tasks 2-5, 11-12, 14.
- Spec §§16-19: covered by Tasks 1-5, 9, 11-12.
- Spec §20 migration: covered by Task 5 and Task 12; v1 is retained as `DRAFT_LOCAL` only.
- Spec §21 rollout phases: implementation order mirrors them.
- Spec §22 acceptance criteria: Task 14 maps each criterion into real-hardware/second-device checks.
- Spec §§23-24 non-goals/success definition: preserved in Global Constraints and acceptance procedure.

No implementation task is allowed to claim `FLOW_GRADE` solely because a render completed. Qualification comes from router capability + QA evidence + return integrity.
