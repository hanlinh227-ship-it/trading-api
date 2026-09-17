# Claude Personal AI Runtime — Handoff

**Role:** Claude Code — PRIMARY IMPLEMENTATION WORKER
**Updated:** 2026-09-17

---

## Position

| Field | Value |
|---|---|
| origin/main | `94f302eaabfc7b365e2986c701d9549a2be5566e` (PR #428 merged) |
| Branch | `claude/magical-euler-uu98r8`, restarted from main after the merge |
| HEAD | `435ac4fb13677f5ea7547329e4981c42d5b01819` |
| behind_by / ahead_by | **0** / 1 |
| CI at exact head | **CI_VALIDATE=PASS failures=0** |
| Brain suite | 1154 passed, 4 skipped |
| Repo suite | 46 passed |
| Secret scan | 0 findings |

---

## B1 REAL_LOCAL_RUNTIME — BLOCKED, path fully operational

Everything downstream of the artifact is built, tested and exercised. B1 is
blocked on one external fact and nothing else.

### Canonical state, read from main

| Field | Value |
|---|---|
| model_id | `Qwen/Qwen3-0.6B-GGUF` |
| immutable_revision | `1eaf4d9657fe65ad10a51eab76a8db5b363bddaa` |
| sha256 | `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031` |
| size_bytes | `639446688` |
| format / quantization | `gguf` / `Q8_0` |
| lifecycle_state | **QUARANTINED** |
| malware_scan_status | **not_run** |
| quarantine_status | **quarantined** |
| model_mesh_local_candidate_eligible | **false** |

### Two independent blockers

**1. Transport.** Re-probed this session: `huggingface.co:443` and
`cdn-lfs.huggingface.co:443` both answer **403 CONNECT** at the environment
gateway. `hf-mirror.com` unreachable. No staged GGUF anywhere on the host. No
local AV engine (`clamscan`, `clamdscan`, `yara` all absent).

**2. Governance.** Even with the bytes, the row is `QUARANTINED` with
`malware_scan_status: not_run`, so `admission_policy.yaml` refuses it. Clearing
that is governance's act, not this lane's. The runtime will not relax it, and
`local_runtime_b1.py` has no flag to skip the check.

### Exact external action needed

Either transport route, **plus** the governance clearance:

```bash
# A. supply the artifact (either one)
#    - allow huggingface.co + cdn-lfs.huggingface.co in the ENVIRONMENT network policy, or
#    - place the file on disk by any other route, then:
python AI_SKILL_LIBRARY/v4/tools/local_runtime_intake.py \
    --staged /path/to/Qwen3-0.6B-Q8_0.gguf

# B. governance clears the row (Work lane, not this lane):
#    malware_scan_status: pass, quarantine_status: clear,
#    lifecycle_state: AVAILABLE, model_mesh_local_candidate_eligible: true

# C. then B1 runs itself:
python AI_SKILL_LIBRARY/v4/tools/local_runtime_b1.py --evidence /tmp/b1.json
```

No code change is needed at any step.

---

## What is operational now

### Staged-artifact intake (`staging.py`, `local_runtime_intake.py`)

Verifies against the canonical record, never against the file's own claims:
exact size, SHA-256 recomputed from the bytes on disk, GGUF magic, bounded
structural scan, format/filename consistency. Mismatches quarantine the file
(moved aside, not deleted — it is evidence) and stop. Cache is keyed by full
artifact identity, so two quantizations cannot collide.

**Proven on this host** against a real 1.7 MB GGUF:

```
status VERIFIED · digest_match true
expected   cedc56ca6e2e89f63e781696d1fd76b4b1d49e6720dee86463e915f6e90016ac
recomputed cedc56ca6e2e89f63e781696d1fd76b4b1d49e6720dee86463e915f6e90016ac
size 1766807 / 1766807 · structural_scan pass (v3, 0 tensors)
one-bit corruption of the same file -> DIGEST_MISMATCH, quarantined
```

**Defect found and fixed during that run:** staging a corrupt file over an
already-good cache returned `ALREADY_CACHED` without examining the staged
bytes — an operator handing over a bad file would have been told it was fine.
The staged file is now always verified when present.

### B1 runner (`local_runtime_b1.py`)

Enforced order: governance clearance → verified cached artifact → real backend
with proxy environment stripped (load and both inferences run with no egress).
Emits machine-readable evidence for artifact identity, backend identity, load
and inference latency, RAM/VRAM, residency, outputs, failure and fallback.

Current output against main:

```
b1_status REFUSED · refused_at governance_admission · real_generation false
reason: the canonical record is not cleared for placement
```

That is the tool working correctly.

### Backend

`llama-cpp-python 0.3.35`, built from source on this host, health PASS, real
CPU feature detection. Not added to `requirements.txt` — the adapter degrades
to unhealthy without it and every real-engine test skips rather than faking.

---

## B6 / B5 — unchanged, no regression

Re-verified against current main: 1154 brain tests and CI green. Not revisited.

---

## Next exact task

Blocked. When transport **and** governance clearance are both supplied, run the
three commands above; `b1_status: PASS` closes B1 and B2 follows immediately
(canonical route: ingress → task_router → Model Mesh → projection → scheduler →
llama.cpp → Qwen), which is wired and waiting on the same artifact.
