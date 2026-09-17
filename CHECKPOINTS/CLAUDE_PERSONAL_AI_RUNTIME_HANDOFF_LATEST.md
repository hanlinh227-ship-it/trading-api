# Claude Personal AI Runtime — Handoff

**Role:** Claude Code — owns the entire remaining Personal AI Federation path.
No step is delegated to another lane.
**Updated:** 2026-09-17

---

## Position

| Field | Value |
|---|---|
| origin/main | `b236a615f0598a2d3b97559f403ae954eb32602d` |
| Branch / HEAD | `claude/magical-euler-uu98r8` / `cec41ddb68e7ba9a00325a8d8fd81454b67e3c72` |
| behind_by | **0** |
| PR | #439 |
| CI at exact head | **CI_VALIDATE=PASS failures=0** |
| Brain / repo / lane suites | 1186 / 46 / 511 passed |

---

## The single external fact blocking everything

**The canonical artifact cannot be obtained from this environment, and that is
now proven rather than assumed.**

The proxy's allowlist is Anthropic APIs plus package registries only:

```
registry.npmjs.org  jsr.io  npm.jsr.io  pypi.org
files.pythonhosted.org  index.crates.io  proxy.golang.org
api.anthropic.com (+ staging/preview/mcp)
```

`huggingface.co:443` and `cdn-lfs.huggingface.co:443` answer **403 CONNECT**.
`hf-mirror.com` unreachable. GitHub release assets 403. Package registries were
searched — the npm hits for "qwen gguf" are tooling and providers
(`@huggingface/gguf`, `termux-llamacpp`, `@qwen-code/*`), not weights. No
registry carries `Qwen3-0.6B-Q8_0.gguf`, and its canonical source is Hugging
Face only.

There is no remaining route to try. Everything below is built so that the moment
the bytes exist, the rest runs with no code change.

### Exactly one external action

Either:

1. add `huggingface.co` and `cdn-lfs.huggingface.co` to the **environment's
   network policy** (not changeable from inside the session), or
2. place `Qwen3-0.6B-Q8_0.gguf` anywhere on this filesystem.

Then, with nothing else needed from anyone:

```bash
python AI_SKILL_LIBRARY/v4/tools/local_runtime_intake.py --staged <path>   # verify + cache
python AI_SKILL_LIBRARY/v4/tools/local_runtime_clearance.py --apply        # scan + clear
python AI_SKILL_LIBRARY/v4/tools/local_runtime_b1.py --evidence /tmp/b1.json
```

**Caveat on step 2, stated plainly:** this host has no signature engine
(`clamscan`/`clamdscan` absent, not installable from the allowed registries).
`--apply` will therefore report `INSUFFICIENT_EVIDENCE` and change nothing.
Clearing then additionally needs a signature engine installed, or an explicit
human decision to accept the model on provenance alone — which is a decision,
not something the tooling will infer.

---

## Blocker status

| ID | Status |
|---|---|
| **B6** RUNTIME_MAIN_RECONCILIATION | **CLOSED** |
| **B5** SAFE_MODEL_ADMISSION | **CLOSED** |
| B1 REAL_LOCAL_RUNTIME | **BLOCKED** — artifact unobtainable |
| B2 / B3 / B4 / Wave 0 / baseline | blocked behind B1 |

---

## Owned end to end, nothing delegated

| Step | Module / tool | State |
|---|---|---|
| Registry projection | `projection.py` | done |
| Artifact identity | `identity.py` | done, lossless |
| Admission policy | `admission_policy.py` | done, cannot self-relax |
| Safe-artifact boundary | `admission.py` | done |
| Structural scan | `scanner.py` | done, verified on a real GGUF |
| **Governance clearance** | `clearance.py` + CLI | **done — was the hand-off, now mine** |
| Staged intake | `staging.py` + CLI | done, verified on real bytes |
| Acquisition | `acquisition.py` | done |
| Cache / eviction | `cache.py` | done |
| Scheduler, wake/sleep | `scheduler.py` | done |
| Runtime mesh, negotiation | `runtime.py` | done |
| llama.cpp backend | `backends/llama_cpp_python.py` | **real engine, health PASS** |
| Execution evidence | `evidence.py` | done |
| B1 runner | `local_runtime_b1.py` | done, every stage exercised |
| Self-development | `selfdev.py` | done |

### Clearance — the honest boundary

A structural scan proves the container is well-formed. It is **not** a malware
scan and cannot stand in for one. `malware_scan_status` becomes `pass` only
when a signature engine actually ran and actually passed; a missing engine, an
engine error, or an engine that raises are all `not_run`, and the tool refuses
to clear. `--apply` is refused for any non-CLEARED result.

Verified on this host: `NO_ARTIFACT` → `--apply` refused → registry
byte-identical.

---

## Next exact task

Supply the artifact (one of the two routes above). Everything downstream is
built, tested, and waiting. No code change is required at any step.
