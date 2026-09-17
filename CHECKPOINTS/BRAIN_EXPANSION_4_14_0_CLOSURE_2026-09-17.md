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

## Boundaries unchanged

`task_router` remains the only routing authority, Legion the multi-agent execution
authority, Model Mesh the model/provider selector, and Memory Continuity the memory
authority. No expansion candidate holds routing, reasoning, memory, model-selection
or execution authority. Financial execution and credential persistence remain
hard-denied through the generic browser adapter. No secret, credential, private key
or auth token enters the repository or any trace.

Previous closure record: `CHECKPOINTS/FREE_IMAGE_RENDER_AGENT_V2_4_13_0_CANDIDATE_2026-09-16.md`.
