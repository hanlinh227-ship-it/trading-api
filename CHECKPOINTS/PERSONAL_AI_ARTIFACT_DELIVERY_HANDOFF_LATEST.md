# Personal AI Artifact Delivery — B1 Control-Plane Handoff

**Project:** PERSONAL AI FEDERATION / OPEN MODEL UNIVERSE  
**Role owner:** Web Chat control-plane lane  
**Runtime owner:** Claude Code / `claude_local_runtime`  
**Repository:** `hanlinh227-ship-it/trading-api`  
**Base main SHA:** `94f302eaabfc7b365e2986c701d9549a2be5566e`  
**Branch:** `work/personal-ai-artifact-delivery-b1-active`  
**Implementation HEAD before this handoff-only commit:** `1b05d202d4ccbb3bcb892ecfc0df7b1c98cce915`  
**PR:** `#438`  
**behind_by at implementation HEAD:** `0`  
**mergeable at implementation HEAD:** `true`

## Scope

This lane implements only the control-plane bridge required to securely stage canonical model bytes for B1. It does not implement or duplicate runtime residency, model loading, inference, scheduler behavior, runtime failover, or runtime telemetry.

Canonical authority is preserved:

- `GITHUB_BRAIN_V4` remains Brain/project authority.
- `task_router` remains sole task-routing authority.
- Model Mesh remains model/provider selection authority only.
- Open Model Universe remains governance/admission authority only.
- Claude local runtime remains residency/execution owner.
- Artifact delivery success is not activation, `AVAILABLE`, Model Mesh admission, or runtime LIVE evidence.

## Files changed

- `AI_SKILL_LIBRARY/v4/control_plane/artifact_delivery.py`
- `AI_SKILL_LIBRARY/tests/test_personal_ai_artifact_delivery.py`
- `.github/workflows/personal-ai-artifact-delivery.yml`
- `CHECKPOINTS/PERSONAL_AI_ARTIFACT_DELIVERY_HANDOFF_LATEST.md`

No Claude-owned runtime implementation file is modified.

## Artifact delivery contract

The bridge dynamically reads:

- `AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml`
- `AI_SKILL_LIBRARY/v4/open_model_universe/admission_policy.yaml`

It does not hardcode Qwen/model identity in ingress or control-plane routing logic.

Required immutable identity fields are consumed from canonical `artifact_identity`:

- `model_id`
- `family`
- `variant`
- `immutable_revision`
- `sha256`
- `size_bytes`
- `format`
- `quantization`
- plus canonical `weights_source`

Fail-closed conditions include missing identity, floating/unpinned source URL, revision mismatch, non-positive size, SHA mismatch, byte-size mismatch, GGUF magic mismatch, unsafe pre-security evidence, failed malware evidence, blocked/unknown quarantine status, authority drift, router drift, Model Mesh ownership drift, and runtime residency ownership drift.

## Machine-readable manifest

After actual staged-byte verification the bridge emits `PERSONAL_AI_ARTIFACT_DELIVERY_V1` with bounded sections for:

- canonical model identity
- immutable revision
- artifact filename/format/size/SHA256/source
- retrieval method
- verification timestamp
- verifier version
- size/SHA/format verification
- malware scan status and engine
- preserved quarantine state
- runtime handoff permission
- runtime handoff purpose
- activation permission (always `false` in this bridge)
- Model Mesh candidate eligibility (preserved from canonical record; never promoted here)
- routing/runtime ownership markers

`runtime_handoff.permitted=true` means only: bytes passed delivery verification and may be handed to Claude for the canonical isolated first-load security probe. It does not mean the model is activated or generally routable.

## Repository-native delivery workflow

Workflow: `.github/workflows/personal-ai-artifact-delivery.yml`

Trigger: manual `workflow_dispatch` after the workflow is present on the default branch.

Path:

1. checkout exact ref
2. dynamically resolve canonical delivery candidate
3. download exact immutable `weights_source`
4. verify exact expected size
5. verify exact SHA256
6. verify GGUF magic where applicable
7. install/update ClamAV
8. scan exact artifact (scan failure or scan error fails the workflow)
9. emit bounded manifest with `malware_scan_status=pass` only after successful ClamAV execution
10. upload the model bytes + candidate JSON + manifest JSON as a one-day GitHub Actions artifact with compression disabled

The workflow never mutates `registry.yaml`, never clears quarantine, never sets `AVAILABLE`, and never activates Model Mesh candidates.

## TDD / tests

RED evidence was established before production implementation: importing `AI_SKILL_LIBRARY.v4.control_plane.artifact_delivery` failed with `ModuleNotFoundError` before the module existed.

Focused contract tests cover:

- nested canonical identity consumption
- dynamic canonical repository resolution
- immutable/pinned URL enforcement
- required size field
- blocked quarantine refusal
- staged size/digest mismatch refusal
- bounded manifest generation
- malware unknown => runtime handoff denied
- activation remains false

Canonical CI for implementation HEAD was running when this handoff document was written; do not treat this sentence as a PASS claim. Exact final-head CI must be checked on PR #438 after this handoff commit.

## Artifact delivery status

**Implementation:** READY  
**Actual canonical GGUF download:** NOT_RUN  
**Actual size/SHA verification against downloaded bytes:** NOT_RUN  
**Actual ClamAV scan:** NOT_RUN  
**Actual bounded workflow artifact:** NOT_PUBLISHED  
**Runtime LIVE:** false

No malware/security PASS is claimed until the manual artifact-delivery workflow succeeds on real bytes.

## Exact one external action required after merge

Run GitHub Actions workflow **Personal AI Artifact Delivery** from the default branch with `model_id` left blank unless canonical registry contains more than one deliverable candidate.

If that workflow fails, keep the model quarantined and do not hand anything to Claude.

## Exact next Claude action after successful workflow

Only after a successful `Personal AI Artifact Delivery` run publishes the bounded artifact:

1. download the single `personal-ai-*` workflow artifact;
2. read `candidate.json` and `manifest.json` from that artifact instead of copying identity values from chat;
3. require `manifest.runtime_handoff.permitted == true` and `manifest.activation.permitted == false`;
4. independently re-check staged GGUF size and SHA256 against the manifest/canonical identity;
5. stage the GGUF in Claude's runtime filesystem;
6. perform the existing isolated first-load path with egress denied as required by canonical admission policy;
7. set `LOCAL_RUNTIME_TEST_GGUF` to that exact staged file and run the existing real-generation test;
8. record actual load/inference/resource telemetry and return B1 evidence;
9. do not mutate canonical Open Model Universe state from the runtime lane.

## Remaining blocker

B1 cannot close until the repository-native delivery workflow successfully obtains and verifies the exact canonical GGUF and Claude completes real isolated load + real token generation evidence. This handoff closes only the control-plane delivery implementation gap.
