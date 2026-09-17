# Brain Expansion 4.14.0 — Release Closure Checkpoint

Date: 2026-09-17
Architecture: GITHUB_BRAIN_V4
Status: PACKAGED / VALIDATED / NOT YET PRODUCTION KNOWN-GOOD
Target release: `4.14.0`
Previous known-good release: `4.13.0`
Pull request: `#416` (contract merged), release closure on `claude/modest-knuth-f0dby3`

## Scope

Close out the Brain Expansion release gate that PR #416 deliberately left open, and
package the bounded integration contract into the immutable stable release bundle.

This closure changes packaging and release metadata only. **No adapter is enabled,
no executable upstream dependency is added, and no network execution is turned on.**

## What unblocked the gate

PR #416 recorded a single blocker: the four Brain Expansion paths could not be
packaged because releases are immutable and cutting a successor would break the
rollback-to-known-good invariant, since `4.13.0` was `known_good: false`.

That blocker is now closed by real production evidence, not by lowering the gate.

### Production verification of `4.13.0`

The canonical gate described in `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md`
("canonical CI, Worker checks, exact-SHA deployment, `/brain/health`,
`/brain/mesh/health`, route/planner smoke and post-deploy verification") is
implemented by `.github/workflows/deploy-skill-mandatory-fast-gateway.yml`.

| Field | Value |
| --- | --- |
| Workflow | Deploy Skill-Mandatory Fast Gateway |
| Run | `35173044514` (run number 124) |
| Verified source SHA | `8c9499e23c0eee17229a80cb1884f0cb078643e2` |
| Production live revision | `8c9499e23c0eee17229a80cb1884f0cb078643e2` |
| Result | `SKILL_MANDATORY_FAST_GATEWAY_DEPLOY=PASS` |

Every gate step passed: exact-SHA deploy, revision + Skill Gateway + Model Mesh
health, Universal Brain adapter canary, `/brain/route` matrix, Model Mesh provider
canary, planner smoke, FREE_ONLY zero-cost guard, and the FAST/SECRET external
boundary proof. The "Record core gate failure" and "Roll back to previously live
exact revision" steps were **skipped**, and the final exact-SHA gate passed.

Recorded boundary values from that run:

```
FAST_EXTERNAL_ROUTING_CALLS=0
MODEL_MESH_MODE=FREE_ONLY
MODEL_MESH_ROUTING_AUTHORITY=false
RUNTIME_SWITCH_MUTATION=false
PROVIDER_SECRET_GENERATION=false
```

The verified SHA `8c9499e` carries the Brain Expansion merge `0ef2e62` as an
ancestor, and all three expansion source files are present at that SHA. What this
proves precisely: **the production brain runs healthy with the Brain Expansion
contract present and every adapter OFF.** It does not prove any adapter works;
no adapter was enabled during verification.

### Prior deploy of `0ef2e62` and its rollback

The deploy of the merge commit `0ef2e62` itself failed and auto-rolled back to
`dec4a3e` (run `35172706608`). Root cause from that run's log: the
`wrangler secret put` step failed with `fetch failed` (connectivity to the
Cloudflare API from the runner), which set `CORE_GATE_FAILED=1`.

This was infrastructure, not the diff: the same pipeline then ran `ci_validate`
(PASS), `prepare:skill-gateway` (109 skills), `prepare:model-mesh` (7 models) and
`wrangler deploy` successfully during the rollback, and the same secret-sync step
succeeded on the next run. The condition was superseded when `8c9499e` deployed
and verified clean.

## Actions taken

1. `evergreen.py mark-known-good --root .` — canonical tooling, not a manual flag
   flip. `4.13.0` is now `known_good: true` with `promotion.validated: true`.
2. `validate_v4.py` re-run immediately after the known-good mutation: 0 errors.
3. Added four paths to `release.py RELEASE_FILES`:
   `brain_expansion_architecture.yaml`, `brain_expansion_adapters.yaml`,
   `brain_expansion_adapters.py`, `validate_brain_expansion.py`.
4. `release.py build --version 4.14.0 --class feature --source brain_expansion_integrations`
   → `RELEASE_BUILD=PASS version=4.14.0 files=58`.
5. Rebuilt the retrieval index.
6. Recorded the closure in the adapter registry under `release_packaging`, with the
   production-evidence run id and the explicit note that no adapter was enabled
   during verification.

## Rollback chain

| Item | Value |
| --- | --- |
| Active pointer | `4.14.0` |
| History tail | `4.12.0` → `4.13.0` → `4.14.0` |
| `versions[-2]` | `4.13.0` |
| Last `known_good` | `4.13.0` |
| `4.14.0` `known_good` | `false` — correct; it is not production-verified yet |

`rollback_release()` therefore resolves to `4.13.0`, which is both the immediate
predecessor and a known-good release. The invariant that blocked PR #416 is
satisfied by evidence rather than by weakening it.

## Adapter state (unchanged by this closure)

| Candidate | State | Enabled | Executable dependency | Network execution |
| --- | --- | --- | --- | --- |
| langfuse | `sandbox_ready` | false | false | false |
| ragas | `sandbox_ready` | false | false | false |
| deepeval | `sandbox_ready` | false | false | false |
| browser_use | `sandbox_ready` | false | false | false |
| baml | `sandbox_ready` | false | false | false |
| microsoft_agent_framework | `reference_only` | false | false | false |
| letta | `reference_only` | false | false | false |
| agno | `reference_only` | false | false | false |

Nothing is `enabled` or `production_verified`. Langfuse remains blocked from an
executable dependency by its open-core licence; the audited MIT-safe path
(`langfuse/langfuse-python` `v4.15.4`) is recorded but not activated.

## Auto-activation (AUTO_ACTIVATE_WHEN_VERIFIED)

Adapters are no longer statically off; they evaluate themselves at boot and turn
on only when every condition they actually require is verified. There is no
always-on mode, and a test asserts the string `ALWAYS_ON` appears nowhere in the
adapter tool or registry.

Ten gates: `license_verified`, `dependency_audit`, `dependency_available`,
`security_policy`, `credential_present`, `network_allowed`,
`runtime_health_probe`, `sandbox_test`, `no_protected_regression`,
`rollback_verified`. Each adapter declares only the subset it needs.

| Adapter | Activation mode | Required gates |
| --- | --- | --- |
| langfuse | `SANITIZED_EXPORT` | all 10 |
| ragas | `OFFLINE_CI_EVAL` | 7 (no credential, no network) |
| deepeval | `OFFLINE_CI_EVAL` | 7 (no credential, no network) |
| baml | `OPTIONAL_TYPED_CONTRACT` | 7 (no credential, no network) |
| browser_use | `READ_ONLY_SANDBOX` | 8 (adds runtime health, no credential) |

Fail-closed semantics: `FAIL`, `UNKNOWN`, a missing probe and a probe that raises
all leave the adapter off. A definite failure on a hard gate (`license_verified`,
`security_policy`) is `blocked`; an unhealthy upstream alone is `degraded`;
anything else unmet is `disabled`. UNKNOWN never becomes `blocked`, because not
knowing is not a standing prohibition.

State machine: `reference_only`, `sandbox_ready`, `eligible`, `enabled`,
`degraded`, `disabled`, `blocked`. `production_verified` is never produced by
eligibility evaluation — it requires real runtime evidence.

Boot flow: FAST never probes upstreams, so routing latency is untouched; STANDARD
and DEEP probe, cache the verdict and revalidate after a 3600s TTL. A boot sweep
where every probe fails or raises still returns `stable_path_ok=True` with no
adapter enabled.

Langfuse resolves its activation upstream to `langfuse/langfuse-python` (MIT). An
edited `activation_path` pointing back at the open-core `langfuse/langfuse`
monorepo is rejected as `blocked`.

### Runtime evidence from this environment

A real probe of this environment produced, for every adapter, `enabled=false`
with `stable_path_ok=true` — `dependency_available` is the common unmet gate, and
Langfuse additionally lacks credentials and cannot verify egress.

One adapter was taken end to end as proof the mechanism actually flips. `baml-py`
`0.226.2` was installed, and with a real sandbox test (validation parity with the
adapter on and off across six payloads, plus a check that BAML cannot bless a
payload the canonical schema rejects) BAML evaluated to `state=enabled` with all
seven of its gates `PASS` and every authority claim false. This is environment-local
evidence: the committed registry keeps `enabled: false`, because activation is a
boot-time decision made where the brain actually runs, not a checked-in flag.

Optional pinned dependencies are recorded in
`AI_SKILL_LIBRARY/requirements-brain-expansion.txt`, which is deliberately not
installed by the brain validator CI.

## Boundaries unchanged

`task_router` remains the only routing authority, Legion the multi-agent execution
authority, Model Mesh the model/provider selector, and Memory Continuity the memory
authority. No expansion candidate holds routing, reasoning, memory, model-selection
or execution authority. Financial execution and credential persistence remain
hard-denied through the generic browser adapter. No secret, credential, private key
or auth token enters the repository or any trace.

Previous closure record: `CHECKPOINTS/FREE_IMAGE_RENDER_AGENT_V2_4_13_0_CANDIDATE_2026-09-16.md`.
