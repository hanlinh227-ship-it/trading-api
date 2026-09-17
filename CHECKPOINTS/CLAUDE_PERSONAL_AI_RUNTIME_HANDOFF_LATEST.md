# Claude Personal AI Runtime — Handoff

**Role:** Claude Code — owns the entire remaining Personal AI Federation path.
**Updated:** 2026-09-17

---

## Position

| Field | Value |
|---|---|
| origin/main | `b236a615f0598a2d3b97559f403ae954eb32602d` |
| Branch / HEAD | `claude/magical-euler-uu98r8` / `a57088597b1b8f885a1336c7176853887e0fe107` |
| behind_by | **0** |
| PR | #439 |
| CI at exact head | **CI_VALIDATE=PASS failures=0** |
| Suites | brain 1214 · repo 46 · lane 537 |

---

## Governance: CLEARED by recorded operator decision

The operator explicitly accepted the residual risk of running the canonical
Qwen3-0.6B-Q8_0 GGUF without a signature-based malware scan, on the basis of
verified provenance, immutable revision, exact size, SHA-256, format validation
and structural scan.

**This is recorded as a decision, never as a scan.**

```
admission_evidence.malware_scan_status : not_run     <- unchanged, still true
operator_risk_acceptance.covers        : [malware_scan_status]
operator_risk_acceptance.scope         : single_artifact
operator_risk_acceptance.artifact_sha256: 9465e63a…  <- bound to these bytes
operator_risk_acceptance.is_a_scan_result: false
projection.risk_accepted_gaps          : ('malware_scan_status',)
projection.cleared_by_evidence_only    : false
```

Gates the acceptance cleared: `lifecycle_state AVAILABLE`,
`quarantine_status clear`, `privacy_class local_only`, mesh candidate eligible.

### Four constraints, each enforced not documented

1. **Covers one gate.** Licence, provenance, format safety, pickle safety,
   remote-code restrictions and the structural scan can never be accepted away —
   the policy lists them as permanent exclusions.
2. **Bound to one artifact by digest.** It cannot be recycled onto other bytes
   or become a blanket "skip scanning".
3. **Covers a known absence only.** `not_run` is acceptable by decision;
   `fail` is a finding and `unknown` is unexplained, and neither is. *This gap
   was found by an existing contract test during this change and closed in both
   the runtime policy and the canonical validator.*
4. **An invalid acceptance is a named fault**, not a silent no-op.

The artifact gate remains fully independent: intake still refuses bytes whose
size or digest disagree with the record, so clearing governance cannot admit a
wrong file.

---

## Blocker status

| ID | Status |
|---|---|
| **B6** RUNTIME_MAIN_RECONCILIATION | **CLOSED** |
| **B5** SAFE_MODEL_ADMISSION | **CLOSED** |
| **Governance admission** | **CLEARED** (operator acceptance, recorded) |
| B1 REAL_LOCAL_RUNTIME | **BLOCKED — artifact bytes only** |
| B2 / B3 / B4 / Wave 0 / baseline | behind B1 |

B1 runner has advanced:

```
before: REFUSED  refused_at=governance_admission
now:    REFUSED  refused_at=artifact
        "no verified artifact is cached for this identity"
```

---

## The single remaining external fact

Transport is exhausted and proven, not assumed. The proxy allowlist is Anthropic
APIs plus package registries only (`registry.npmjs.org`, `jsr.io`, `pypi.org`,
`files.pythonhosted.org`, `index.crates.io`, `proxy.golang.org`).
`huggingface.co:443` and `cdn-lfs.huggingface.co:443` answer **403 CONNECT**.
Registries were searched: the "qwen gguf" hits are tooling and providers, not
weights. No registry carries the artifact; its canonical source is Hugging Face
only.

**One action, either route:**

1. add `huggingface.co` and `cdn-lfs.huggingface.co` to the **environment's
   network policy** (not changeable from inside the session), or
2. place `Qwen3-0.6B-Q8_0.gguf` anywhere on this filesystem.

Then B1 completes with no further input:

```bash
python AI_SKILL_LIBRARY/v4/tools/local_runtime_intake.py --staged <path>
python AI_SKILL_LIBRARY/v4/tools/local_runtime_b1.py --evidence /tmp/b1.json
```

The clearance step is no longer needed — governance is already cleared.

---

## Canonical tests changed — flagged for review

Two tests authored by the control-plane lane asserted *where the single row
happened to be* rather than what must be true of it, so both broke the moment an
operator legitimately advanced it. They now assert the rule, which is stronger
than the value they replaced:

* a mesh-eligible model must carry **either** a passing malware scan **or** a
  valid, digest-bound operator acceptance recording what was not checked;
* an acceptance must never be recorded as though it were a scan
  (`malware_scan_status` must still read `not_run`, `is_a_scan_result` false).

Several lane tests had the same defect — borrowing the live row's governance
state — and now construct their own quarantined fixtures.

---

## Next exact task

Supply the artifact. Everything downstream is built, tested and cleared.
