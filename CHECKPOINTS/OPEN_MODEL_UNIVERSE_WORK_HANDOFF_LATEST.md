# Open Model Universe Work Handoff — B6/B5 Contract Ready

Date: 2026-09-17
Repository: `hanlinh227-ship-it/trading-api`
Branch: `codex/personal-ai-control-plane-contracts`
PR: `#429`
Current reconciled base main: `bc83f70f16de40be833f83702538479ede8157b1`
Reconciliation commit validated before this metadata-only refresh: `68faad329c105182e830227dd7ffd0348cc1e36a`
Runtime LIVE claim: **NO**

## Status

- `WORK_B6_CONTRACT_READY`
- `WORK_B5_ADMISSION_READY`
- `FIRST_VALID_MODEL_RECORD_READY` — structurally/provenance valid, deliberately **not admission-cleared** and not active.

## B6 governance/runtime ownership contract

Open Model Universe now owns governance states only:

- `DISCOVERED`
- `QUARANTINED`
- `QUARANTINED_UPDATE`
- `REGISTERED`
- `APPROVED`
- `AVAILABLE`
- `BLOCKED`
- `SUPERSEDED`
- `RETIRED`

Runtime residency is explicitly owned by `claude_local_runtime`. Open Model Universe has no runtime residency authority. The registry does not define `RUNNING`, `WARM`, or `SLEEPING` as governance states.

Canonical files:

- `AI_SKILL_LIBRARY/v4/tools/open_model_universe.py`
- `AI_SKILL_LIBRARY/v4/schemas/open_model_universe.schema.json`
- `AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml`
- `AI_SKILL_LIBRARY/v4/open_model_universe/admission_policy.yaml`

## Artifact identity contract

Authoritative runtime-acquisition identity is the nested `artifact_identity` object:

```yaml
artifact_identity:
  model_id: string
  family: string
  variant: string
  immutable_revision: 40-char git revision
  sha256: 64-char digest
  size_bytes: positive integer
  format: gguf | safetensors | mlx | other
  quantization: string
```

The validator rejects drift between top-level model metadata and artifact identity. `weights_source` must contain the immutable revision. Runtime projection may not mutate artifact identity.

## Admission evidence contract

Required metadata:

```yaml
admission_evidence:
  license_verified: bool
  provenance_verified: bool
  safe_format_verified: bool
  pickle_safe: bool | unknown
  trust_remote_code_required: bool | unknown
  custom_code_required: bool | unknown
  malware_scan_status: pass | fail | not_run | unknown
  isolated_first_load_required: bool
  first_load_egress_allowed: bool
  quarantine_status: clear | quarantined | blocked | unknown
```

A model can set `model_mesh_local_candidate_eligible: true` only when:

- governance state is `AVAILABLE`;
- license, provenance, safe-format, and pickle evidence are true;
- `trust_remote_code_required == false`;
- `custom_code_required == false`;
- `malware_scan_status == pass`;
- `quarantine_status == clear`.

Unknown critical evidence blocks candidate admission. Registry membership never implies activation.

## Model Mesh boundary

Canonical flow:

`Open Model Universe -> admission gate -> Model Mesh local candidate -> Claude runtime projection`

- routing authority remains `task_router`;
- model-selection authority remains `model_mesh`;
- ingress hardcoding of Qwen or any specific model is forbidden;
- Claude runtime may narrow capability based on observation but may not relax Work admission or change artifact identity.

## First model record

Path: `AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml`
Model: `Qwen/Qwen3-0.6B-GGUF`
Variant: `0.6B-Q8_0-GGUF`
Artifact: `Qwen3-0.6B-Q8_0.gguf`
Immutable artifact revision: `1eaf4d9657fe65ad10a51eab76a8db5b363bddaa`
SHA256: `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`
Size: `639446688` bytes
Format: `gguf`
Quantization: `Q8_0`
License: `Apache-2.0`
Runtime support evidence: llama.cpp / Ollama usage is documented by the official Qwen Hugging Face page.
Offline eligibility: true after artifact acquisition; no hosted API is required by the artifact/runtime contract.

The record remains:

- `lifecycle_state: QUARANTINED`
- `model_mesh_local_candidate_eligible: false`
- `malware_scan_status: not_run`
- `quarantine_status: quarantined`

This is intentional and fail-closed.

## Remaining unknowns for Claude/runtime lane

1. Exact source-model commit used to produce the official Qwen GGUF is not exposed in the evidence verified by Work; `lineage.source_revision` remains `null` and `conversion_verified=false`.
2. Malware scan has not been run on the exact 639,446,688-byte artifact.
3. Isolated first load has not been executed.
4. First-load egress denial has not been demonstrated in a real runtime.
5. No backend/model load/inference evidence exists yet. Do not call runtime LIVE.

Claude should consume this identity/admission contract, perform runtime-side security evidence and first-load work, and return evidence without changing governance ownership.

## Tests and reconciliation evidence

- RED contract commit: `441b19559f554d999e6df17357c31a6e9387de6d`.
- `AI_SKILL_LIBRARY/tests/test_open_model_universe_b6_b5_contracts.py` covers state ownership, artifact identity, fail-closed admission, and generic Model Mesh/Claude boundary.
- `AI_SKILL_LIBRARY/tests/test_open_model_universe.py` is aligned to the governance/admission split.
- Reconciliation commit `68faad329c105182e830227dd7ffd0348cc1e36a` merged current main `bc83f70f16de40be833f83702538479ede8157b1` into this branch with explicit resolution of the competing Qwen schema from PR #433.
- On reconciliation commit `68faad329c105182e830227dd7ffd0348cc1e36a`: AI Skill Library CI, Crypto Skill Registry Validate, Zero Local Cloud Runtime, Skill-Mandatory Fast Gateway CI, and Cloudflare Research Runtime CI all completed `success`.
- At that verification point PR #429 was `mergeable=true`, `mergeable_state=clean`, and `behind_by=0`.
