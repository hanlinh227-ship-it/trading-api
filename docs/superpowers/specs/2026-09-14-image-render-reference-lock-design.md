# IMAGE_RENDER Reference-Lock — Design Spec

## Goal
Extend the approved Curious Beyond Windows Worker with a bounded `IMAGE_RENDER` production path that can batch-render scene images through local ComfyUI while conditioning on user-supplied character references, automatically reject obvious failures, retry within limits, and package accepted outputs plus provenance into a ZIP manifest.

## Authority and security
This feature remains subordinate to `2026-09-14-ai-money-ecosystem-autopilot-v1-design.md` and Brain 4.6 authority.

- No arbitrary shell commands from chat.
- `IMAGE_RENDER` is an allowlisted job type.
- Workspace paths must remain inside the Worker sandbox.
- Paid APIs, cloud GPU, credit spending, auto-purchase, and paid fallback remain disabled.
- User-supplied references are treated as project assets; the Worker does not infer third-party commercial rights.
- No upload/publication behavior is added by this feature.

## Input contract
An `IMAGE_RENDER` job contains:
- `project_id`
- `job_id`
- `output_width`, `output_height` (default production target 16:9)
- `scenes[]`
- `references[]`
- `workflow_profile`
- `max_attempts_per_scene`
- `package_name`

Each scene contains:
- stable scene number/name
- source prompt text
- required character reference IDs
- negative constraints
- optional seed policy

Each reference contains:
- stable reference ID
- local project-relative asset path
- character label
- immutable identity role

## Character consistency strategy
Prompt-only generation is explicitly insufficient for the approved Max workflow. The Worker uses a reference-conditioned ComfyUI workflow when the required local nodes/model are available. The adapter is provider-neutral at the job boundary; ComfyUI-specific node IDs remain in a workflow profile rather than the job schema.

The system must not claim pixel-identical reproduction. The operational target is high visual identity consistency: stable silhouette, face structure, palette, clothing/accessories, species/robot structure, and recurring character-specific traits.

For multi-character scenes, each scene declares exactly which references are allowed. Extra characters and reference mixing are QA failures.

## Low-VRAM profile
Target hardware is GTX 1650 4 GB VRAM / 32 GB RAM.

Rules:
- prefer SD1.5-class low-VRAM compatible workflows;
- render one scene at a time;
- no parallel GPU render;
- unload/reuse models between scene attempts where supported;
- fail closed on CUDA OOM and record the reason;
- do not silently switch to cloud generation.

## ComfyUI adapter
The Worker communicates with the already-probed local ComfyUI API at `127.0.0.1:8188`.

Responsibilities:
1. validate workflow profile and required local model/node availability;
2. copy/reference approved source images into the ComfyUI input area without escaping the sandbox policy;
3. inject scene prompt, dimensions, seed and reference bindings into the workflow template;
4. submit one render;
5. poll bounded execution status;
6. retrieve produced image(s);
7. normalize deterministic scene filenames;
8. return structured render metadata.

No UI mouse automation is required.

## QA and retry
Every rendered scene receives deterministic QA before acceptance:
- output file exists and decodes;
- expected width/height or approved equivalent aspect ratio;
- no empty/near-empty output;
- required scene number maps to exactly one accepted primary image;
- reference bindings used by the render match the scene declaration;
- no duplicate accepted filename/hash;
- ComfyUI execution reports no error.

Reference/semantic QA is recorded separately. Automated image similarity may rank/reject gross identity drift when a compatible local embedding model is available, but absence of such a model must not be disguised as a passed identity check. The manifest must label identity QA as `VERIFIED`, `HEURISTIC`, or `UNVERIFIED`.

A failed scene retries up to `max_attempts_per_scene` with a deterministic seed change. Exhausted scenes make the batch `PARTIAL`/`FAILED`; they are never silently omitted.

## Packaging
Accepted assets are written to a job-specific output directory and packaged as:

`<package_name>.zip`

ZIP contents:
- `scene_01.png` ... `scene_N.png` for accepted scenes;
- `manifest.json`;
- `failed_scenes.json` when applicable.

Manifest records:
- job/project IDs;
- source prompt per scene;
- reference IDs used;
- workflow profile;
- model/checkpoint identifier when detectable;
- dimensions;
- seed/attempt count;
- SHA-256 per image;
- QA status including identity-QA level;
- local artifact path;
- zero-paid-service assertion.

## Artifact return
Git is used only for compact job/result metadata, not large generated image payloads. Large ZIP/image artifacts stay on the Windows Worker or are transferred through a bounded artifact-return mechanism that does not require committing multi-megabyte binaries to the repository. Until a transport is configured, the result reports the exact local ZIP path rather than pretending the binary is available in ChatGPT.

## Max batch acceptance criteria
For the supplied Max project:
- scene count comes from the uploaded prompt source, not an invented count;
- every scene retains its source prompt;
- only declared character references are bound to each scene;
- all accepted outputs are 16:9;
- no paid/cloud fallback;
- missing reference-conditioning dependencies stop the render with actionable diagnostics;
- a ZIP and manifest are produced when at least one scene is accepted;
- the system never labels characters as `VERIFIED` unless an actual local identity check ran.

## Tests
Unit/contract tests cover:
- allowlisted `IMAGE_RENDER` job validation;
- path traversal rejection;
- reference declaration validation;
- workflow profile validation;
- ComfyUI request construction with mocked HTTP;
- bounded polling/timeouts;
- retry/exhaustion behavior;
- output dimension/hash QA;
- manifest status truthfulness;
- ZIP packaging;
- no paid/cloud fallback configuration.

Integration test uses a fake ComfyUI server. Real-GPU validation is performed by the connected Windows Worker after deployment.
