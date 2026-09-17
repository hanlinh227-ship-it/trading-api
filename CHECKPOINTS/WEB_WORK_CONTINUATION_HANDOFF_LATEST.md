# WEB_WORK_CONTINUATION_HANDOFF

status: WORK_CONTINUATION_ACTIVE
updated_utc: 2026-09-17T05:20:00Z

## Canonical state

- repository: `hanlinh227-ship-it/trading-api`
- canonical branch: `main`
- current main SHA at refresh: `bc83f70f16de40be833f83702538479ede8157b1`
- current Brain release pointer: `4.15.0`
- PR #427: merged
- PR #428: open, Claude runtime lane
- PR #433: merged, first pinned local model record
- this Web continuation PR: #435 (draft until verification closes)

## FIRST_VALID_LOCAL_MODEL_RECORD

- model_id: `qwen3-0.6b-q8_0-gguf`
- family: `Qwen3`
- variant: `0.6B-Q8_0-GGUF`
- base model: `Qwen/Qwen3-0.6B`
- immutable revision: `1eaf4d9657fe65ad10a51eab76a8db5b363bddaa`
- artifact: `Qwen3-0.6B-Q8_0.gguf`
- artifact reference: `https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/1eaf4d9657fe65ad10a51eab76a8db5b363bddaa/Qwen3-0.6B-Q8_0.gguf`
- artifact SHA-256: `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`
- artifact size: `639446688` bytes
- artifact format: `GGUF`
- quantization: `Q8_0`
- runtime support: `llama_cpp`
- runtime minimum: `llama.cpp >= b5092`
- CPU viable: `true`
- Apple Silicon viable: `UNKNOWN` in canonical record pending empirical confirmation
- GPU viable: `UNKNOWN` in canonical record pending empirical confirmation
- minimum RAM: `UNKNOWN` pending empirical measurement
- recommended RAM: `UNKNOWN` pending empirical measurement
- minimum VRAM: `UNKNOWN` pending empirical measurement
- recommended VRAM: `UNKNOWN` pending empirical measurement
- context window: `32768`
- license: `Apache-2.0`
- license class: `permissive`
- commercial use: `true`
- self-hostable: `true`
- zero paid token: `true`
- offline_ready: `false` until verified artifact is locally cached
- privacy class: `local_only`
- governance admission status: `APPROVED`
- authority: `false`

### Security/admission metadata

- revision_pinned: `true`
- digest published upstream: `true`
- digest independently recomputed after acquisition: `false`
- safe_format: `true`
- pickle_risk: `false`
- trust_remote_code_required: `false`
- custom_code_required: `false`
- license_verified: `true`
- provenance_verified: `true`
- malware_scan_status: `UNKNOWN`
- isolated_load_required: `true`
- egress_required_for_acquisition: `true`
- rollback_artifact_available: `UNKNOWN`

### Runtime projection input

```yaml
runtime_projection:
  model_id: qwen3-0.6b-q8_0-gguf
  family: Qwen3
  revision: 1eaf4d9657fe65ad10a51eab76a8db5b363bddaa
  artifact_hash: 9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031
  artifact_size: 639446688
  quantization: Q8_0
  runtime_support:
    - llama_cpp
  minimum_ram: UNKNOWN
  recommended_ram: UNKNOWN
  minimum_vram: UNKNOWN
  recommended_vram: UNKNOWN
  cpu_viable: true
  privacy_class: local_only
  zero_cost_eligible: true
  admission_status: APPROVED
```

### Exact Claude handoff

Use this record as input to the existing ModelProfile projection path. Do not alter canonical registry semantics.

The remaining blocker is artifact acquisition/execution evidence, not model identity/provenance metadata. Do not fabricate empirical RAM/VRAM/latency or mark `offline_ready=true` before verified acquisition.

## ChatGPT → Brain ingress contract

Branch/PR #435 adds the authority-free control-plane contract at:

- `AI_SKILL_LIBRARY/v4/control_plane/chatgpt_brain_contract.yaml`
- `AI_SKILL_LIBRARY/v4/schemas/chatgpt_brain_contract.schema.json`
- `AI_SKILL_LIBRARY/v4/tools/validate_brain_ingress_contract.py`
- `AI_SKILL_LIBRARY/tests/test_brain_ingress_contract.py`

Ingress required fields:

`source`, `request`, `project_context`, `conversation_context`, `desired_depth`, `attachments`, `constraints`, `privacy_class`

Canonical flow remains:

`ingress → task_router → project/domain resolution → memory → skills → Model Mesh → runtime scheduler → verifier → synthesis → response`

Ingress cannot choose a model, bypass `task_router`, or widen permissions.

Response fields:

`request_id`, `task_id`, `route`, `selected_model_ref`, `runtime_ref`, `verification_status`, `result`, `evidence_refs`, `limitations`, `runtime_metrics_ref`

No hidden reasoning is part of the response contract.

Privacy defaults:

- `SECRET`: local-only
- `CONFIDENTIAL`: local-preferred; external only under verified policy
- sensitive content does not default to free external providers

## Lane boundaries

This Web lane does not implement or own:

- scheduler
- lifecycle mechanics
- runtime adapters
- cache/eviction
- model download manager
- worker registration
- resource detection
- failover
- empirical benchmark scoring
- merge coordination

## Current status labels

- first local model: `FIRST_MODEL_READY`
- registry projection: `REGISTRY_PROJECTION_READY`
- ingress contract: `INGRESS_READY` pending PR #435 verification/merge
- model universe: `MODEL_UNIVERSE_EXPANDING`
- runtime: **not claimed LIVE**

## Remaining Work blockers

1. PR #435 verification and integration by Integration Coordinator.
2. Claude PR #428 requires actual pinned artifact acquisition to execute canonical real inference and collect empirical resource metrics.
3. Broader model/repo catalog remains P1/P2 and must not block first E2E.
4. Champion/challenger assignments remain unset until Web Eval provides empirical comparator evidence.

## Next exact task

After PR #435 verification: expand a small diversified P1 set with explicit lineage/license/provenance metadata and create the supporting repo registry without enabling discovered repos by default.
