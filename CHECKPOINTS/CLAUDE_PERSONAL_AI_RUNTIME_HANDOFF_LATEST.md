# Claude Personal AI Runtime — Handoff

**Role:** Claude Code — sole owner of the remaining Personal AI Federation path.
**Updated:** 2026-09-17

## Position

| Field | Value |
|---|---|
| origin/main | `b236a615f0598a2d3b97559f403ae954eb32602d` |
| Branch | `claude/magical-euler-uu98r8` |
| behind_by | 0 |
| PR | #439 |
| Suites | lane 642 · brain 1271+ · repo 46 · CI_VALIDATE=PASS failures=0 |

## Gate status

| Gate | State | Evidence |
|---|---|---|
| B1 real local runtime | **PASS** | `evidence/B1_REAL_INFERENCE_EVIDENCE.json` |
| B2 canonical route | **PASS** | `evidence/B2_CANONICAL_ROUTE_EVIDENCE.json` |
| B3 golden E2E | **PASS** | `evidence/B3_B4_GOLDEN_E2E_EVIDENCE.json` |
| B4 offline E2E | **PASS** | same run — `offline` observed, not asserted |
| Wave 0 capability | **MEASURED 0.75** | `evidence/WAVE0_CAPABILITY_EVIDENCE.json` |
| PERSONAL_AI_BASELINE_001 | **NOT FROZEN** | `evidence/WAVE0_BASELINE_EVIDENCE.json` |

### Why the baseline is not frozen

10 of 12 canonical Wave 0 tasks pass; 12 of 12 are reproducible. Two fail
because the model is wrong, not the harness:

* `gr-02` — which gas plants absorb → answered "Oxygen"
* `vi-03` — which direction the sun rises → answered "Bắc" (north)

`freeze_baseline` refuses a wave that is not ready and there is no override.
A 0.6B model missing a 12/12 bar is the clearest argument for Wave 1.

## Wave 1 — transport solved, admission not started

All three artifacts are republished as GitHub **release assets** (Actions blob
storage stays 403 at the gateway) and each carries an **immutable revision
proven by LFS OID** to serve the staged digest:

| Model | Revision | Release | Note |
|---|---|---|---|
| Qwen3-1.7B-Q8_0 | `90862c4b` | `staged-model-qwen3-1.7b-q8_0` | 1,834,426,016 B |
| Qwen3-4B-Q4_K_M | `bc640142` | `staged-model-qwen3-4b-q4_k_m` | 2 parts — over the 2 GiB asset cap |
| granite-3.3-2b-instruct-Q4_K_M | `7cdf86cc` | `staged-model-granite-…` | 1,545,303,328 B |

Reachability verified from this runtime: HTTP 206 range request returns GGUF
magic. None of them is admitted, none inherits Qwen3-0.6B's approval, and each
needs its own licence, scan/acceptance, intake, first load, inference and
capability measurement.

## Anti-fabrication rules now enforced

* a capability score above zero requires a measurement whose score equals it,
  whose run had no errors, and which is **bound to that artifact's digest**
  (`validate_open_model_universe.py`), so a score can never be inherited by
  different bytes;
* benchmark suites and prompt sets are frozen by content hash;
* `supported: true` is set only from digest-matching evidence — never False,
  which would claim a model was tested and failed;
* the mesh ledger `v4/model_mesh/capability_evidence.json` is **release-sealed**
  and was deliberately not written to; a benchmark result is not a reason to
  mutate a sealed release.

## Design work

`docs/superpowers/specs/2026-09-17-brain-fast-reasoning-optimization-design.md`
— design only, nothing implemented. Headline: FAST/SMART/DEEP **already exists**
as FAST/STANDARD/DEEP in `stable/budgets.yaml`; the bottleneck is measured
evidence, not architecture. Cold load is ~80% of first-response latency
(2.8 s vs 0.7 s inference), and 8 of 10 models in `active.json` carry a
capability score justified by a documentation URL.

## Next automatic action

1. Admit Wave 1 models one at a time from QUARANTINED, each on its own evidence.
2. Re-run the baseline against the strongest admitted model; freeze
   PERSONAL_AI_BASELINE_001 only if it genuinely reaches 12/12.
3. Then migration step 1 of the design spec: populate the capability index from
   verified evidence only.
