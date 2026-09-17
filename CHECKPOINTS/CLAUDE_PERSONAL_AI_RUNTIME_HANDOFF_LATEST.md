# Claude Personal AI Runtime — Handoff

**Lane:** Claude Code, implementation-heavy runtime lane
**Project:** Open Model Universe / Personal AI Federation
**Updated:** 2026-09-17

---

## Position

| Field | Value |
|---|---|
| Repository | `hanlinh227-ship-it/trading-api` |
| Branch | `claude/magical-euler-uu98r8` |
| HEAD SHA | `51d2afcb2a3b8dc0da7a13a2ae2add4a7930ee73` |
| Base main SHA | `bc83f70f16de40be833f83702538479ede8157b1` |
| behind_by | **0** |
| ahead_by | 9 |
| PR | [#428](https://github.com/hanlinh227-ship-it/trading-api/pull/428) — open, mergeable, not for automatic merge |
| Rollback point | `063c6217d00800a497ffd6b2e118d2cf5f72e5e8` |

Main moved twice during this session (`c5ad9112` → `2e3a8f6e` → `063c6217`).
The coordinator's quoted `8acafcf2` was already stale on arrival; the branch is
reconciled against the newest `origin/main` above, not that SHA. Integration was
by **merge**, not rebase: the branch is published and PR #428 references it, so
rewriting its history would invalidate every existing checkout and review anchor.

---

## Blocker status

| ID | Status | Note |
|---|---|---|
| **B6 RUNTIME_MAIN_RECONCILIATION** | **CLOSED** | behind_by=0; lifecycle split landed; CI_VALIDATE=PASS |
| **B5 SAFE_MODEL_ADMISSION** | **CLOSED (runtime side)** | format allowlist, pickle refusal, remote-code policy gate, first-load sandbox + egress deny, quarantine |
| **B1 REAL_LOCAL_RUNTIME** | **PARTIAL** | real llama.cpp engine installed and driven; no canonical artifact to load |
| **B2 REAL_CANONICAL_INFERENCE** | **BLOCKED** | see *The one blocker* below |
| B3 GOLDEN_E2E / B4 OFFLINE_E2E | blocked behind B2 | |

---

## Canonical model record: MERGED and consumed

The first canonical row landed on main via PR #433 and is consumed end to end
through the normal contracts — no value copied from chat, all read from
`AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml`.

| Field | Value (read from main) |
|---|---|
| model_id | `qwen3-0.6b-q8_0-gguf` |
| family / variant | `Qwen3` / `0.6B-Q8_0-GGUF` |
| immutable_revision | `1eaf4d9657fe65ad10a51eab76a8db5b363bddaa` |
| artifact.filename | `Qwen3-0.6B-Q8_0.gguf` |
| artifact.sha256 | `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031` |
| artifact.size_bytes | `639446688` |
| artifact.format / quantization | `gguf` / `Q8_0` |
| runtime_support | `llama_cpp` → `llama.cpp` |
| context_window | `32768` |
| lifecycle_state | `APPROVED` |

Measured result of running the seam against it:

```
projection        ADMITTED     acquisition_eligible=true
identity          complete     fingerprint=6c8e7c1b87fbc658c806a49440bc5426
artifact_admitted true         (safe format, no pickle, no remote code)
preconditions     ()           all acquisition gates pass
acquisition       FAILED_TRANSPORT
                  "URLError: Tunnel connection failed: 403 Forbidden"
```

Two findings worth the Work lane's attention, both fail-closed and both correct:

* `capabilities: {}` means placement refuses **any** stated capability
  requirement. The runtime will not assume a text model does text.
* `minimum_ram_gb: null` blocks ordinary placement entirely. That is the
  first-load chicken-and-egg the record's own `quarantine_policy` describes —
  measurement comes from a separate budgeted run. The fix is never to let the
  scheduler guess a RAM figure, and a test pins both behaviours.

PR #434 is superseded and was not used.

## The one blocker: no model artifact is reachable from this environment

This is environmental, not a code gap. Measured, not inferred:

```
huggingface.co:443      CONNECT -> 403  (agent proxy: "policy denial")
cdn-lfs.huggingface.co  unreachable
hf-mirror.com           unreachable
modelscope.cn           unreachable
github.com release assets -> 403
raw.githubusercontent.com -> 200  (works, but hosts no complete GGUF)
pypi.org / files.pythonhosted.org -> 200 (allow-listed)
```

The proxy's own status endpoint reports the denial explicitly:
`{"kind":"connect_rejected","detail":"gateway answered 403 to CONNECT (policy
denial or upstream failure)","host":"huggingface.co:443"}`.

What that permitted, and what it did not:

* **Permitted.** A genuine llama.cpp was built from source via PyPI
  (`llama-cpp-python 0.3.35`, compiled with cmake/gcc on this host). It reports
  real CPU feature detection from the compiled library:
  `AVX512 = 1 | AVX512_VNNI = 1 | AMX_INT8 = 1 | LLAMAFILE = 1 | OPENMP = 1`.
  A real GGUF was fetched from `raw.githubusercontent.com` and verified by magic
  bytes, and real llama.cpp was driven against it.
* **Not permitted.** Any complete, generative model. The only GGUF files
  reachable are llama.cpp's committed *vocab-only* fixtures, which carry no
  tensors. Loading one produces a real, correctly-normalized failure
  (`ValueError: Failed to load model` → `CAPABILITY_MISMATCH`) — genuine
  evidence that the guard works, and not generation.

**A tiny randomly-initialised GGUF was deliberately not built.** It would have
produced a green "real inference" line, but random weights are synthetic bytes
and the output would be meaningless. That would be a fabricated milestone, which
is worse than a blocked one.

### FIRST_VALID_MODEL_RECORD_REQUIRED

**Egress was requested twice in-session and is still denied.** The gateway
answered 403 to CONNECT for both `huggingface.co:443` and
`cdn-lfs.huggingface.co:443` after each request. This cannot be lifted from
inside the session: the policy is enforced by the environment's egress gateway,
chosen when the environment was created, and no code in this repository can
reach it. (Note the correct host is `cdn-lfs.huggingface.co` — `.co`, not
`.com`.)

Unblocking needs either an egress allowance applied to the **environment's
network policy**, or the artifact securely staged into the filesystem by another
route. Either path works: the runtime verifies size and SHA-256 against the
bytes it actually has, so a staged artifact is accepted on identical evidence to
a downloaded one. The registry row is no longer a gap — it carries:

```
model_id, family, variant, upstream_revision (immutable, not main/latest/head),
artifact_filename, artifact_format, artifact_sha256, artifact_size_bytes,
quantization, runtime_support, hardware_profile, context_window,
privacy_class, cost_class, license_verified, source_evidence
```

The candidate named by the integration lane (Qwen3-0.6B, Q8_0, GGUF) and the
SHA-256 quoted in chat are **recorded here as unverified** and are deliberately
not written into any code path. Per instruction, that value is not canonical
evidence; the runtime will consume whatever the Work record publishes and will
verify the digest itself against the bytes it downloads.

### Zero code change needed when it arrives

The activation hook is live: set `LOCAL_RUNTIME_TEST_GGUF` to a complete GGUF
and `AI_SKILL_LIBRARY/tests/test_local_runtime_real_backend.py::RealGenerationTests`
loads it, generates, asserts on real output, proves warm residency on the second
call, and emits a populated evidence envelope. It currently reports
`skipped: no real GGUF artifact available`.

---

## What landed this session

| § | Item | Module | Status |
|---|---|---|---|
| B6 | Governance/residency split | `residency.py` | done |
| B6 | Plane boundary, one entry door | `reconciliation.py` | done |
| 3 | Immutable artifact identity | `identity.py` | done |
| B5 | Safe-artifact admission | `admission.py` | done |
| 5 | Acquisition contract extension | `acquisition.py` | done |
| 2/4 | Registry projection seam | `projection.py` | done |
| 3/5 | Projection + placement plan CLI | `v4/tools/local_runtime_plan.py` | done |
| 4 | Execution evidence envelope | `evidence.py` | done |
| 9 | Observation envelope | `telemetry.py` | done |
| 8 | llama.cpp CLI adapter | `backends/llama_cpp.py` | done |
| 2 | llama.cpp in-process adapter | `backends/llama_cpp_python.py` | **real engine driven** |

### Evaluator gap status

| Gap | Status |
|---|---|
| 001 genuine adapter + real generation | adapter real and driven; **generation blocked on artifact** |
| 002 worker binding | done — `worker_id` on the envelope |
| 003 revision + sha256 binding | done — carried from identity through to evidence |
| 004 actual quantization | done — `actual_quantization` is the loaded one; the probe advertises an empty supported-set on purpose |
| 005 backend version identity | **done with real data** — `llama-cpp-python/0.3.35` |
| 006 queue_wait_ms | done — measured from admission, not estimated |
| 007 load_latency_ms | done — measured around the real load |
| 008 inference_latency_ms | done — measured around the real call |
| 009 start/end/total | done — monotonic durations, UTC stamps, separately |
| 010 peak RAM/VRAM | done — `PeakSampler` threads RSS sampling; a snapshot pair is not a peak |
| 011 normalized failures | done — full evaluator vocabulary, `fallback_used`, `attempted_runtimes` |

---

## Tests

```
python -m unittest discover -s AI_SKILL_LIBRARY/tests -p "test_local_runtime_*.py"
  -> 353 passed, 1 skipped (the real-generation hook, awaiting an artifact)

python -m unittest discover -s AI_SKILL_LIBRARY/tests -p "test_*.py"
  -> 988 passed, 4 skipped

python -m unittest discover -s tests -p "test_*.py"     -> 46 passed

python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --root . --source-sha $(git rev-parse HEAD)
  -> CI_VALIDATE=PASS failures=0
     (authority, router, security, runtime, V4, Model Mesh, Legion,
      Open Model Universe, Brain Expansion, skill gateway, release,
      retrieval index, consolidation all PASS)
```

The lane adds no dependency to the repository. `llama-cpp-python` was installed
into this session's interpreter to prove the backend and is deliberately **not**
added to `requirements.txt`: the adapter degrades to unhealthy without it, and
every test skips rather than substituting a fake.

---

## Design decisions worth carrying forward

1. **Governance and residency are different questions.** A model can be
   `APPROVED` and `COLD` at once. One enum forced a choice between facts that
   were both true.
2. **A registry row is a claim; a claim is not evidence.** Rows start
   INELIGIBLE and earn admission. A row claiming `RUNNING` means somebody typed
   `RUNNING` into YAML.
3. **Identity is a tuple, never a name.** `model_id` does not say which bytes
   ran; revision + quantization + content hash do.
4. **Null is unknown; zero is a measurement.** `peak_vram_mb: 0.0` means measured
   and unused. `null` means nobody looked.
5. **Measured, never estimated.** The scheduler's `estimated_start_s` is a
   planning figure and never reaches evidence.
6. **A checksum proves identity, not safety.** Hence the first-load sandbox and
   egress denial, independent of provenance review.
7. **Absent evidence is a refusal.** An unreadable format field is exactly where
   guessing is worst.

---

## Boundaries held

* No registry, catalog or governance file was modified. `registry.yaml` remains
  the research lane's, with `models: []` untouched.
* `AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml` was **not** changed. Its
  `local_install_required: false` / `local_cli_execution: false` still sit in
  tension with a local-first federation; that policy belongs to the canonical
  Brain. This plane stays non-authoritative, opt-in and unresolvable from the
  checkpoint, so nothing depends on the answer.
* No fabricated model rows, revisions or checksums were written anywhere.
* `task_router` remains sole routing authority; every new class declares
  `routing_authority = False` and a test asserts it.

---

## Next exact task

Blocked on the artifact, not on code. When a model record and reachable artifact
exist:

```bash
git fetch origin && git checkout claude/magical-euler-uu98r8
export LOCAL_RUNTIME_TEST_GGUF=/path/to/<artifact>.gguf
python -m unittest AI_SKILL_LIBRARY.tests.test_local_runtime_real_backend -v
python AI_SKILL_LIBRARY/v4/tools/local_runtime_plan.py --root . --output /tmp/plan.json
```

The first command produces the real generation and the populated evidence
envelope. The second shows the registry row projecting into a placement plan.
