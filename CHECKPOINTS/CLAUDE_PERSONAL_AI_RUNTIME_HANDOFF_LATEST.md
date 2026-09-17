# Claude Personal AI Runtime — Handoff

**Role:** Claude Code — sole owner of the remaining Personal AI Federation path.
**Updated:** 2026-09-17

## Position

| Field | Value |
|---|---|
| origin/main | `b236a615f0598a2d3b97559f403ae954eb32602d` |
| Branch | `claude/magical-euler-uu98r8` |
| PR | **#442** |
| AI CORE gate | **AI_CORE_RELEASE=PASS passed=9/9** |
| CI | **CI_VALIDATE=PASS failures=0** |
| Suites | brain 1543 passed · 5 skipped · 980 subtests |

## The gate to run first

```bash
python AI_SKILL_LIBRARY/v4/tools/ai_core_release_gate.py
```

Nine checks that re-read every proof **together**. Each part of this lane had
its own evidence and each was checked alone; nothing asked whether they still
hold against each other, which is the state in which a lane is most easily
believed finished. Absent evidence fails the check it belongs to, every recorded
run must name a digest that is a registry row, and no run may claim routing,
memory, merge or approval authority.

It grants nothing: PASS means the evidence holds, and cutting a release stays a
human decision. It also runs inside `ci_validate`, because holding together is
what stops being true silently.

## Gate status

| Gate | State | Evidence |
|---|---|---|
| B1 real local runtime | **PASS** | `evidence/B1_REAL_INFERENCE_EVIDENCE.json` |
| B2 canonical route | **PASS** | `evidence/B2_CANONICAL_ROUTE_EVIDENCE.json` |
| B3 / B4 golden E2E | **PASS** | `evidence/AI_CORE_E2E_EVIDENCE.json` — 14-stage chain, Legion before the mesh |
| Memory continuity | **RESUMED across processes** | `evidence/AI_CORE_RESUME_EVIDENCE.json` — pid 9016 wrote, pid 9034 resumed |
| Failure paths | **PROVEN 6/6** | `evidence/FAILURE_PATH_PROOF.json` |
| Self-development | **PROVEN 9/9** | `evidence/SELFDEV_CYCLE_EVIDENCE.json` |
| Open model gaps | **0 actionable** | `evidence/SELFDEV_OBSERVED_GAPS.json` (resolved 2) |
| PERSONAL_AI_BASELINE_001 | **NOT FROZEN** | `evidence/WAVE0_BASELINE_EVIDENCE.json` |

### Why the baseline is still not frozen

10 of 12 canonical Wave 0 tasks pass on Qwen3-0.6B; 12 of 12 are reproducible.
Two fail because the model is wrong, not the harness (`gr-02` answered "Oxygen";
`vi-03` answered "Bắc"). `freeze_baseline` refuses a wave that is not ready and
there is no override. Re-run it against a stronger admitted model.

## The model universe: 7 admitted, 2 refused by the runtime

| Model | State | Note |
|---|---|---|
| Qwen3-0.6B-Q8_0 | AVAILABLE | scan pass, capability 0.75 |
| Qwen3-1.7B-Q8_0 | AVAILABLE | |
| Qwen3-4B-Q4_K_M | AVAILABLE | |
| granite-3.3-2b-instruct-Q4_K_M | AVAILABLE | |
| SmolLM2-360M-Instruct-Q8_0 | AVAILABLE | |
| granite-4.2-3b-Q4_K_M | AVAILABLE | capability 0.833 |
| Phi-3-mini-4k-instruct-q4 | AVAILABLE | capability 0.917 |
| bitnet-b1.58-2B-4T (I2_S) | **QUARANTINED** | artifact intact; llama.cpp 0.3.35 rejects the format |
| Ministral-3-3B-Reasoning Q4_K_M | **QUARANTINED** | artifact intact; tokenizer scores missing |

The two refusals are **recorded, not cleared**:
`evidence/RUNTIME_INCOMPATIBILITY_EVIDENCE.json` holds each digest, the verbatim
runtime diagnostic, the runtimes tried, and what would reopen the gap. The
observer reports them as resolved rather than actionable, so they stop
generating work without the limitation being hidden. A different digest reopens
the gap.

## Governance: the Qwen3-0.6B acceptance is retired

The operator risk acceptance is **gone**, replaced by a real finding:

```
admission_evidence.malware_scan_status : pass
malware_scan_reference.engine          : ClamAV 1.5.3/28126
malware_scan_reference.artifact_sha256 : 9465e63a…   <- bound to these bytes
engine_data_scanned                    : 1.27 GiB over 609.82 MiB read
```

Keeping both would have left the row asserting that no scan ran beside the scan
that did — which is exactly the state it was found in, with two comments reading
"malware_scan_status still reads not_run" above a field reading `pass`.

**Root cause, now gated:** the validator consulted the acceptance rules only
when `malware_scan_status` was *not* pass, so an acceptance stopped being
checked at all once a scan closed its gap, and could outlive it indefinitely.
`_admission_refusals` refuses a row carrying both. An acceptance is still
accepted where no scan ran — the missing-engine route stays open.

## Transport: the block that had already lifted

An earlier version of this file recorded B1 as blocked on artifact bytes, with
`huggingface.co` 403 at the gateway and no reachable mirror. That was true of
HuggingFace and remains true. What it missed is that the bytes had since been
published to **this repository's own releases**, and `api.github.com` is
reachable and scoped to this repository:

```
releases/tags/canonical-qwen3-0.6b-q8_0 → Qwen3-0.6B-Q8_0.gguf (639446688 B)
```

Fetched through the release asset API, sha256 `9465e63a…` on arrival, intake
VERIFIED byte for byte, B1 re-run to PASS on this container: cold load 576 ms,
32 tokens in 1.9 s, peak RAM 1155 MB, egress denied, no fallback.

**Worth keeping:** the blocker was written down as "the artifact cannot be
obtained" when what had been established was "HuggingFace is unreachable". Those
are not the same claim. A route that opened later went unnoticed because the
conclusion had been recorded as final.

## Self-development has carried a real change

`AutoDev` had unit tests proving it refuses what it says it refuses, and had
never carried anything. `v4/tools/local_runtime_selfdev_cycle.py` runs it over a
real git worktree with gates that are real commands whose exit codes decide the
result.

The accepted run reached `READY_TO_MERGE` on four passing gates and stopped —
approval as `auto_dev` was attempted and refused. The rejected run disabled the
self-approval guard for real; the tests gate caught it, and the properties that
matter were demonstrated rather than assumed: `READY_TO_MERGE` unreachable
afterwards, the failed gate not overwritable with a pass, and rollback verified
by an empty `git status` against the base.

The change it carried landed: `autorun` printed a bare `{"status":
"NO_RECORD"}` for any registry holding more than one model — which it has since
Wave 1 — so its own documented no-argument invocation named neither cause nor
remedy.

## Anti-fabrication rules enforced

* a capability score above zero requires a measurement whose score equals it,
  whose run had no errors, and which is bound to that artifact's digest, so a
  score can never be inherited by different bytes;
* admission refuses `context_window: 0` rather than writing an invalid number
  that reads like a measured one;
* benchmark suites and prompt sets are frozen by content hash;
* the mesh ledger `v4/model_mesh/capability_evidence.json` is release-sealed and
  was deliberately not written to.

## Two cautions for whoever picks this up

**A second session worked this branch concurrently.** Commits for the same work
landed from both sides and were reconciled by hand. Fetch before assuming local
state is current, and prefer the stronger of two versions of a test rather than
whichever arrived last.

**Tests that assert where a row is, rather than what must be true of it, break
the moment the row legitimately moves.** Three did so this session — pinning an
acceptance to a named model id, matching a context window against any cached
artifact, and borrowing the live row's scan status in a fixture about unscanned
artifacts. Each now asserts the rule, which is stronger than the value it
replaced.

## Next automatic action

1. Re-run `PERSONAL_AI_BASELINE_001` against Phi-3-mini (highest measured
   capability, 0.917) and freeze only if it genuinely reaches 12/12.
2. Populate the capability index from verified evidence only — migration step 1
   of `docs/superpowers/specs/2026-09-17-brain-fast-reasoning-optimization-design.md`.

## Not started

Trading work. Untouched by design.
