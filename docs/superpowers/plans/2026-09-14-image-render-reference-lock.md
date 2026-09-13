# IMAGE_RENDER Reference-Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a secure local `IMAGE_RENDER` batch executor that drives ComfyUI with declared character references, performs truthful QA/retries, and packages accepted scenes plus provenance.

**Architecture:** Extend the existing signed Windows Worker job dispatcher with an `IMAGE_RENDER` executor. Keep ComfyUI-specific workflow bindings in a profile, render serially for 4 GB VRAM, write binary assets locally, and return compact result metadata through the existing Git queue.

**Tech Stack:** Python 3.11, stdlib HTTP/JSON/zip/hash/pathlib, Pillow for image validation when available, ComfyUI HTTP API, pytest.

**Spec:** `docs/superpowers/specs/2026-09-14-image-render-reference-lock-design.md`

## Global Constraints
- No arbitrary shell execution.
- Paid API, cloud GPU, auto-purchase, credit spend and paid fallback are OFF.
- GTX 1650 4 GB: serial rendering only.
- No claim of pixel-identical reference reproduction.
- Identity QA must be labeled `VERIFIED`, `HEURISTIC`, or `UNVERIFIED` truthfully.
- Git stores metadata only; generated image/ZIP binaries stay out of Git.

---

### Task 1: IMAGE_RENDER contract and security validation

**Files:**
- Create: `money_ecosystem/worker/image_render_contract.py`
- Modify: `money_ecosystem/worker/worker.py`
- Test: `tests/money_ecosystem/test_image_render_contract.py`

**Interfaces:**
- Consumes: signed Worker job dictionary.
- Produces: `ImageRenderJob.from_payload(payload, workspace_root)` and validated scene/reference records.

- [ ] Write failing tests for allowlisting, required fields, duplicate reference IDs, undeclared scene references, traversal such as `../secret`, invalid dimensions, and max-attempt bounds.
- [ ] Run `pytest tests/money_ecosystem/test_image_render_contract.py -v` and confirm RED.
- [ ] Implement immutable validated records and sandbox path resolution; add `IMAGE_RENDER` to the existing explicit allowlist without adding shell execution.
- [ ] Run the contract tests and existing Worker tests; confirm GREEN.
- [ ] Commit `feat(worker): validate IMAGE_RENDER jobs`.

### Task 2: ComfyUI workflow profile and API adapter

**Files:**
- Create: `money_ecosystem/worker/comfyui_adapter.py`
- Create: `money_ecosystem/worker/workflows/sd15_reference_lowvram.json`
- Test: `tests/money_ecosystem/test_comfyui_adapter.py`

**Interfaces:**
- Consumes: validated scene, references, workflow profile.
- Produces: `RenderSubmission`, `RenderArtifact` metadata; never executes a shell command.

- [ ] Write failing mocked-HTTP tests for `/system_stats`, workflow validation, prompt/reference injection, `/prompt` submission, bounded `/history/<id>` polling, timeout and ComfyUI error propagation.
- [ ] Run adapter tests and confirm RED.
- [ ] Implement stdlib HTTP client with explicit `http://127.0.0.1:8188` allowlist and bounded timeout/poll count.
- [ ] Add a versioned workflow profile with named binding metadata for prompt, dimensions, seed, checkpoint and reference-conditioning nodes; missing required nodes/models must raise actionable `DependencyMissing` rather than falling back to text-only/cloud generation.
- [ ] Run adapter tests and confirm GREEN.
- [ ] Commit `feat(worker): add bounded ComfyUI adapter`.

### Task 3: Serial scene renderer and retry state machine

**Files:**
- Create: `money_ecosystem/worker/image_render_executor.py`
- Test: `tests/money_ecosystem/test_image_render_executor.py`

**Interfaces:**
- Consumes: `ImageRenderJob`, `ComfyUIAdapter`.
- Produces: per-scene `ACCEPTED`/`FAILED` records and local artifact paths.

- [ ] Write failing tests proving scenes render strictly one-at-a-time, retry seeds change deterministically, attempts never exceed the job limit, OOM/error is recorded, and exhausted scenes are not silently omitted.
- [ ] Run executor tests and confirm RED.
- [ ] Implement the minimal serial state machine with job-specific output directories and deterministic `scene_XX.png` names.
- [ ] Run executor and Worker regression tests; confirm GREEN.
- [ ] Commit `feat(worker): execute serial image scene batches`.

### Task 4: Deterministic asset QA and truthful identity status

**Files:**
- Create: `money_ecosystem/worker/image_qa.py`
- Test: `tests/money_ecosystem/test_image_qa.py`

**Interfaces:**
- Consumes: produced image path, expected dimensions, declared references, optional identity checker result.
- Produces: `AssetQAResult` including `identity_status` in `{VERIFIED, HEURISTIC, UNVERIFIED}`.

- [ ] Write failing tests for missing/corrupt images, wrong aspect ratio, duplicate hashes, successful dimensions, and identity status truthfulness when no checker ran.
- [ ] Run QA tests and confirm RED.
- [ ] Implement image decode/dimension validation, SHA-256 and duplicate detection; never promote `UNVERIFIED` to `VERIFIED` without checker evidence.
- [ ] Run QA tests and confirm GREEN.
- [ ] Commit `feat(worker): add deterministic image QA`.

### Task 5: ZIP packaging and result manifest

**Files:**
- Create: `money_ecosystem/worker/image_package.py`
- Test: `tests/money_ecosystem/test_image_package.py`

**Interfaces:**
- Consumes: scene results and QA records.
- Produces: local ZIP, `manifest.json`, optional `failed_scenes.json`, compact Worker result JSON.

- [ ] Write failing tests for complete and partial batches, ZIP members, SHA-256 manifest fields, source prompt/reference provenance, zero-paid-service assertion and no binary Git paths.
- [ ] Run package tests and confirm RED.
- [ ] Implement deterministic ZIP packaging and compact result metadata with exact local artifact path.
- [ ] Run package tests and confirm GREEN.
- [ ] Commit `feat(worker): package image batches with provenance`.

### Task 6: Wire IMAGE_RENDER into signed Worker execution

**Files:**
- Modify: `money_ecosystem/worker/worker.py`
- Modify: `money_ecosystem/worker/runner.py`
- Test: `tests/money_ecosystem/test_worker.py`
- Test: `tests/money_ecosystem/test_image_render_integration.py`

**Interfaces:**
- Consumes: existing HMAC-verified signed job.
- Produces: existing Git result envelope containing IMAGE_RENDER status and local artifact metadata.

- [ ] Write failing integration test with a fake ComfyUI server and a two-scene signed job; assert no shell/cloud path is reachable.
- [ ] Run integration test and confirm RED.
- [ ] Dispatch validated `IMAGE_RENDER` jobs to the executor after signature verification; preserve dedupe/idempotency behavior.
- [ ] Run full Worker test suite and confirm GREEN.
- [ ] Commit `feat(worker): dispatch signed IMAGE_RENDER jobs`.

### Task 7: Windows dependency preflight and reference asset staging

**Files:**
- Modify: `money_ecosystem/worker/setup_windows.ps1`
- Create: `money_ecosystem/worker/image_preflight.py`
- Test: `tests/money_ecosystem/test_image_preflight.py`
- Test: `tests/money_ecosystem/test_worker_setup.py`

**Interfaces:**
- Consumes: local ComfyUI endpoint/workflow profile/reference paths.
- Produces: `READY` or actionable missing dependency list.

- [ ] Write failing tests for missing checkpoint, missing reference-conditioning node/model, inaccessible ComfyUI input directory, and successful low-VRAM preflight.
- [ ] Run preflight/setup tests and confirm RED.
- [ ] Implement read-only dependency discovery plus bounded reference staging; setup must not download paid/cloud dependencies or expose secrets.
- [ ] Run tests and confirm GREEN.
- [ ] Commit `feat(worker): preflight local reference rendering`.

### Task 8: Real Worker validation gate

**Files:**
- Create: `worker_jobs/requests/image-render-preflight.json` only when execution begins.
- Result expected: `worker_jobs/results/<job-id>.json`.

**Interfaces:**
- Consumes: connected Windows Worker.
- Produces: evidence that the actual machine either is `READY` or reports exact missing local dependency/model/node names.

- [ ] Run all repository tests relevant to Worker and IMAGE_RENDER and record pass/fail counts.
- [ ] Create a signed preflight job through the existing GitHub signing workflow without exposing `CURIOUS_WORKER_HMAC_KEY`.
- [ ] Wait for the Windows Worker result and inspect it.
- [ ] If dependencies are missing, stop before rendering and provide the exact zero-cost installation action; do not claim IMAGE_RENDER ready.
- [ ] If READY, submit one reference-conditioned scene as a hardware smoke test, verify dimensions/artifact manifest, then mark `IMAGE_RENDER_READY=true` in project state.
- [ ] Commit only compact validation metadata; never commit generated binaries.
