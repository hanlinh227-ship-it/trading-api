# Brain Expansion 4.15.0 — Browser Use Isolated Runtime Closure

Date: 2026-09-17
Architecture: GITHUB_BRAIN_V4
Status: PACKAGED / VALIDATED / BROWSER RUNTIME EVIDENCE CAPTURED
Target release: `4.15.0`
Previous known-good release: `4.14.0`

## Scope

Close the last open Brain Expansion activation blocker. `browser_use` was the
one runtime adapter still sitting at `dependency_available=FAIL`, and it was the
only thing standing between four live adapters and five.

The cause was never the adapter contract. `browser-use` pulls Playwright and a
downloaded Chromium build, and resolving that beside a distribution-managed
interpreter has to replace packages the system package manager owns — PyJWT
among them. The honest outcome of that install is a broken image, so the probe
correctly reported FAIL.

The fix is a *dedicated interpreter*, never a forced install.

## The runtime, exactly

| Property | Value |
| --- | --- |
| Isolation | dedicated `python -m venv` (`.browser-runtime`), owns its whole dependency tree |
| Pins | `browser-use==0.13.10`, `playwright==1.56.0`, in `AI_SKILL_LIBRARY/requirements-brain-expansion-browser.txt` |
| Engine | Chromium, installed with `playwright install --with-deps chromium` inside the venv |
| Egress | loopback and `data:` only — no external request in any probe |
| Health probe | real Chromium launch, `data:text/html` render, title read back, browser closed |
| Sandbox probe | static page served on `127.0.0.1`, loaded through `execute_browser_task` under the read-only contract, HTTP 200 observed |
| Persistence | a second fresh context must report zero cookies and zero storage origins |
| Probe timeout | 20 000 ms; a probe that does not answer is UNKNOWN, which fails closed |
| Retry | none inside a probe — revalidation on the eligibility TTL is the retry |
| Default mode | `READ_ONLY_SANDBOX` |

What was explicitly **not** done: no `--ignore-installed`, no
`--break-system-packages`, no edit to the system PyJWT or any other system
package, and no bulk upgrade of unrelated dependencies. The CI job asserts the
system interpreter afterwards: `browser_use` must **not** be importable there.

Priority B (a separate container image) was not needed — the venv resolved
cleanly on the first attempt, in this environment and on the runner image.

### Why `network_allowed` is not one of its gates

Egress is *forbidden* for this adapter, not merely unverified. Both probes drive
a real browser without a single external request, so a passing `network_allowed`
would describe a capability the sandbox contract denies. The registry records
this under `runtime_contract.egress: loopback_and_data_url_only`, and a test
asserts the gate list and the contract agree.

## Activation evidence

`browser_use`, probed in the isolated runtime, with a real Chromium process:

```
browser_use: state=enabled enabled=True
  license_verified=PASS   dependency_audit=PASS      dependency_available=PASS
  security_policy=PASS    runtime_health_probe=PASS  sandbox_test=PASS
  no_protected_regression=PASS  rollback_verified=PASS
```

All eight required gates PASS; every authority claim false; `stable_path_ok=true`.

Merged across both interpreters with `merge_activation_reports.py`:

| Adapter | State | Proved in |
| --- | --- | --- |
| ragas | enabled | validator runtime |
| deepeval | enabled | validator runtime |
| baml | enabled | validator runtime |
| browser_use | enabled | browser runtime |
| langfuse | needs `LANGFUSE_*` repository secrets | validator runtime (CI only) |

Langfuse reaches `enabled` only where the credentials live, which is the
scheduled CI job, not a developer checkout. Locally it reports
`credential_present=FAIL` and stays off, which is the design.

The committed registry still carries `enabled: false` for every adapter.
Activation is a boot-time decision made where the brain runs; the generated
reports are gitignored and published as CI artifacts, never checked in.

## Baseline and rollback

The browser runtime proves the stable path *before* it proves the adapter:
`activate_brain_expansion.py --no-env --no-probe` runs no probe at all, so every
condition is UNKNOWN and every adapter is off — even in an image where the
optional dependencies are installed. That run must still report
`stable_path_ok=true` with `enabled=[]`.

`rollback_verified` remains an exhaustive check: the stable path is re-smoked for
every subset of the five runtime adapters being disabled.

## Release packaging

`4.14.0` is now `known_good: true`, on production evidence rather than a flag
flip. The canonical gate (`Deploy Skill-Mandatory Fast Gateway`) passed on
`affb99b9c3bbf17b674fc12807dec29a4ce8709e`, run `35177762069` (run number 131),
whose active release pointer is `4.14.0`: exact-SHA deploy, revision and Skill
Gateway and Model Mesh health, adapter canary, route matrix, provider canary,
planner smoke, FREE_ONLY guard and the FAST/SECRET boundary proof all passed, and
the failure-record and rollback steps were skipped.

`4.15.0` adds three paths to the release manifest: the activation runtime, the
new merge tool, and the updated adapter registry. Rollback resolves to `4.14.0`,
which is both the immediate predecessor and known-good.

## Boundaries unchanged

`task_router` remains the only routing authority. Browser Use is an execution
adapter and nothing else: it never selects an objective, never routes, never
plans, never holds memory, never picks a model or provider, and never persists a
credential, session or cookie. Financial execution and credential persistence are
hard-denied and ungrantable through it — the sandbox test proves both are refused
*before* any browser is launched. Microsoft Agent Framework, Letta and Agno stay
`reference_only`. No secret enters the repository, and the activation reports are
scanned for credential material before they are published.

Previous closure record: `CHECKPOINTS/BRAIN_EXPANSION_4_14_0_CLOSURE_2026-09-17.md`.
