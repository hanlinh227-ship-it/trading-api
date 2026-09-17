# Claude Personal AI Runtime — Handoff

**Role:** Claude Code — sole owner of the remaining Personal AI Federation path.
**Updated:** 2026-09-17

---

## Position

| Field | Value |
|---|---|
| origin/main | `b236a615f0598a2d3b97559f403ae954eb32602d` |
| Branch / HEAD | `claude/magical-euler-uu98r8` / `a82f35c21fe928e2a85c65df297f98b9eb3aa809` |
| behind_by | 0 |
| PR | #439 |
| Suites | lane 564 · brain 1227+ · repo 46 |

---

## B1 — **PASS**, with real inference

The artifact arrived via GitHub Actions. Its storage backend
(`*.blob.core.windows.net`) is 403 at the environment gateway, as are all
Actions storage hosts — but **release assets are reachable**
(`release-assets.githubusercontent.com`). A workflow
(`.github/workflows/publish-model-release-asset.yml`, branch
`ops/publish-model-release`) republishes the same bytes from the existing
Actions artifact — never from Hugging Face — re-verifying size and SHA-256 on
the runner first.

Verified again locally, from the downloaded bytes:

```
size    639446688 == 639446688
sha256  9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031  MATCH
intake  VERIFIED · structural scan pass · GGUF v3 · 310 tensors · 28 kv
```

Real execution evidence (`CHECKPOINTS/evidence/B1_REAL_INFERENCE_EVIDENCE.json`):

| Field | Value |
|---|---|
| b1_status / real_generation | **PASS** / **true** |
| model_revision | `1eaf4d96…` |
| actual_quantization | Q8_0 |
| backend_version | llama-cpp-python/0.3.35 |
| cold load | 3362.6 ms |
| cold inference | 702.0 ms (total 4742.8 ms) |
| warm inference | 677.7 ms |
| peak_ram_mb / peak_vram_mb | 1825.36 / 0.0 (measured, CPU-only) |
| tokens in/out | 5 / 24 |
| failure / fallback_used | NONE / false |
| egress during load | denied (proxy stripped, NO_PROXY=\*) |
| residency | READY → WARM → READY |

Output: *"The capital of France is"* → **" Paris."** Warm reuse is real — 678 ms
against 3363 ms of cold load.

---

## B2 — **BLOCKED at a real gate** (this inverts the stated order)

The canonical route is wired and runs: ingress → task_router → Model Mesh →
governance-admitted candidate → projection → scheduler → llama.cpp, using the
canonical components rather than reimplementing them.

```
ingress               ok   model_named_at_ingress = false
task_router           ok   core / core_reasoning
governance_admission  ok   1 admitted
model_mesh            REFUSED
    -> below the capability floor for core/core_reasoning
```

**Why:** the registry declares `capabilities: {text_reasoning: 0.0}` with
`benchmark_profile: unverified`. The Model Mesh correctly refuses a candidate
declaring zero capability.

**This is the important finding.** A measured capability score *is* benchmark
evidence, so B2 cannot pass until Wave 0 has actually measured this model. The
critical path as stated (B1 → B2 → B3 → B4 → Wave 0 → baseline) has a real
dependency running the other way:

```
B1 (done) → Wave 0 measurement → registry capability updated
          → B2 → B3 → B4 → PERSONAL_AI_BASELINE_001
```

Benchmarking does not need mesh selection — it invokes the model directly, as B1
did. The mesh gate governs routed production traffic, which is what B2 tests.

I did not invent a capability number to make the route light up. A test pins the
refusal and skips itself once the capability is genuinely measured.

### Two real defects found by executing the route

* routing matched skill names as **substrings** — "the **capital** of France"
  routed to  because "capital" contains "api". Now whole-word.
* the mesh candidate used `privacy_class: private` / `usage_terms: permitted`,
  neither in the mesh's vocabularies. Both normalised silently to `unknown` and
  the FREE_ONLY gate rejected the candidate for a reason unrelated to its real
  eligibility — which would have read as "the mesh rejects local models".

Both were invisible until the route was actually run.

---

## Wave 1 — staged, not yet retrievable

Run `35201035730` produced all three artifacts (unexpired, expire 2026-09-18):

| Model | Artifact ID | Zip size |
|---|---|---|
| `qwen3-1.7b-q8_0` | 10487951643 | 1,758,481,337 |
| `qwen3-4b-q4_k_m` | 10487314513 | 2,428,084,775 |
| `granite-3.3-2b-instruct-q4_k_m` | 10488431786 | 1,518,664,881 |

They sit in the same blocked Actions storage. Retrieving them needs the same
release-asset republication used for 0.6B, extended to a matrix. ~5.7 GB total
against ~29 GB free — fits, but each model must earn its own admission and none
inherits Qwen3-0.6B's.

---

## Next automatic action

1. Run Wave 0 measurement against Qwen3-0.6B (direct invocation, no mesh needed)
   and record measured capability with raw-run evidence.
2. Update the registry capability from that measurement.
3. Re-run B2; it should then clear the mesh, and B3/B4 follow.
4. Extend the republish workflow to a matrix for Wave 1, then admit each model
   independently from QUARANTINED.
