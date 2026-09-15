# Peer Tri-Layer AI Legion Program Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development for execution. Use superpowers:executing-plans only when implementation is intentionally moved to a separate execution session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Coordinate the approved Peer Tri-Layer AI Legion program across Adaptive Free Model Mesh, branch-neutral learning, specialist agents/OpenCode, skill evolution, idle autonomy, release integration and production verification without authority races or overlapping file ownership.

**Architecture:** This is the program-level dependency and ownership map. It does not replace the detailed implementation plans. `GITHUB_BRAIN_V4` stays the sole authority; each subplan creates one bounded capability plane and hands validated artifacts to the final integration plan.

**Spec:** `docs/superpowers/specs/2026-09-15-peer-tri-layer-ai-legion-design.md`

## Executable subplans

1. `docs/superpowers/plans/2026-09-15-adaptive-free-model-mesh.md`
2. `docs/superpowers/plans/2026-09-15-peer-tri-layer-intelligence.md`
3. `docs/superpowers/plans/2026-09-15-ai-legion-opencode-runtime.md`
4. `docs/superpowers/plans/2026-09-15-skill-evolution-idle-learning.md`
5. `docs/superpowers/plans/2026-09-15-ai-legion-integration-release.md`

## Dependency graph

```text
AFMM remaining implementation
        |
        v
known-good Model Mesh release (intended 4.9.0)
        |
        +--------------------+----------------------+
        |                    |                      |
        v                    v                      v
Peer Intelligence     Legion/OpenCode       Skill Evolution
        |                    |                 + Idle Learning
        +--------------------+----------------------+
                             |
                             v
                 Integration + Protected Evals
                             |
                             v
                  Immutable V4 Legion Release
                             |
                             v
 shadow -> read_only -> isolated_write -> learning -> idle_autonomy
                             |
                             v
                     PRODUCTION_VERIFIED
                             |
                             v
                         KNOWN_GOOD
```

## Shared-file ownership

To prevent subagent collisions, the following files have a single integration owner until final merge:

| File / namespace | Primary owner |
|---|---|
| `AI_SKILL_LIBRARY/v4/model_mesh/**` | AFMM plan |
| `AI_SKILL_LIBRARY/v4/legion/policy.yaml`, `learning.yaml` | Peer Intelligence plan |
| `AI_SKILL_LIBRARY/v4/legion/agents.yaml`, `orchestration.yaml`, `opencode_runtime.yaml`, initial `upstreams.yaml` | Legion/OpenCode plan |
| `AI_SKILL_LIBRARY/v4/legion/evolution.yaml`, `autonomy.yaml` | Skill Evolution/Idle plan |
| `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml` | changed in plan-local commits; final reconciliation by Integration plan |
| `AI_SKILL_LIBRARY/evals.yaml` | changed in plan-local commits; final reconciliation by Integration plan |
| `AI_SKILL_LIBRARY/v4/index/workspace_map.yaml` | final reconciliation by Integration plan |
| `AI_SKILL_LIBRARY/checkpoint.json` | Integration plan only |
| `AI_SKILL_LIBRARY/v4/tools/ci_validate.py` | Integration plan only |
| `AI_SKILL_LIBRARY/v4/tools/release.py` and release pointer/history | Integration plan only |
| `crypto-research-gateway/src/server.ts` | Legion/OpenCode plan, then frozen except Integration fixes |
| `AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml` | no permission widening; existing research-gateway boundary remains unchanged |

If two subplans need the same shared file, the first implementation records a minimal additive patch; the Integration plan owns conflict reconciliation and protected regression validation before release.

## Phase gates

### Phase 0 — Baseline lock

- [ ] Refresh `checkpoint.json`, `AI_GLOBAL_CHECKPOINT.md`, current release pointer, Stable authority/security/budgets and project handoff where applicable.
- [ ] Verify implementation branch is isolated from `main`.
- [ ] Run canonical baseline CI before new behavior changes.
- [ ] Record exact baseline source SHA and Stable version.

Exit: baseline is reproducibly GREEN or implementation stops for root-cause repair.

### Phase 1 — Finish AFMM

- [ ] Resume the existing AFMM plan from its current verified task checkpoint; do not restart completed RED/GREEN tasks.
- [ ] Complete remaining discovery/runtime/eval/release tasks.
- [ ] Require exact-SHA validation and known-good release before Legion production activation.

Exit: Adaptive Free Model Mesh is known-good; expected release is `4.9.0` unless canonical version history has advanced.

### Phase 2 — Build the three independent capability planes

The following may be developed with separate subagents when their file ownership does not overlap:

- [ ] Peer Tri-Layer Intelligence: normalized claims/evidence, conflict resolution, immutable intelligence snapshot.
- [ ] AI Legion/OpenCode: agent catalog, task graph, Awesome LLM Apps pattern fusion, Legion snapshot, isolated OpenCode worker and gateway client.
- [ ] Skill Evolution/Idle Learning: sanitized experience mining, replay/mutations, champion selection, autonomy policy and durable scheduler/control plane.

Each task follows RED -> minimum GREEN -> task-scoped review -> regression. No subplan may promote Stable or edit release pointers.

Exit: all three planes pass their plan-local tests and canonical validators with no unresolved shared-file conflict.

### Phase 3 — Integration

- [ ] Register checkpoint roots and WARM lookup paths.
- [ ] Reconcile additive changes to `capability_fusion.yaml`, `evals.yaml` and `workspace_map.yaml`.
- [ ] Compile and validate Skill Gateway, Model Mesh, Legion Runtime and Peer Intelligence snapshots against one exact source SHA.
- [ ] Run protected end-to-end evals.
- [ ] Verify existing research gateway still has no shell/process spawning; only isolated OpenCode worker has managed sandbox process capability.
- [ ] Verify Cloudflare autonomy is control/scheduling only and cannot execute provider/coding work directly.
- [ ] Verify Stable continues when every optional plane is unavailable.

Exit: canonical `ci_validate.py` and all service test/typecheck suites are GREEN.

### Phase 4 — Immutable release

- [ ] Use `release.py` to build the next unused V4 minor release; never hand-edit hashes/pointer.
- [ ] Rebuild retrieval index.
- [ ] Verify previous known-good rollback target.
- [ ] Re-run canonical validation using exact release commit SHA.

Exit: release bundle is CI_VERIFIED but not yet called production live.

### Phase 5 — Production rollout

Advance only one stage at a time:

```text
shadow
  -> read_only
  -> isolated_write
  -> learning
  -> idle_autonomy
```

- [ ] Deploy exact approved SHA to applicable services.
- [ ] Verify health endpoints report the approved source SHA.
- [ ] Smoke required behavior and optional-plane failure behavior.
- [ ] Check FAST latency/external-routing invariants after every stage.
- [ ] Roll back immediately on protected regression.

Exit: all required services are PRODUCTION_VERIFIED and the release is marked KNOWN_GOOD only with fresh runtime evidence.

## Program-wide stop conditions

Stop the affected promotion/deployment path, preserve last-known-good Stable, and investigate before proceeding if any of these occurs:

- authority or permission widening not explicitly covered by the approved spec;
- hidden reasoning, secret, credential, raw private prompt or sensitive payload enters a durable artifact;
- Learning branch identity becomes a fixed truth weight;
- provider/agent majority vote determines truth;
- FAST gains an external routing/model/learning call;
- concurrency exceeds Stable hard limits;
- OpenCode can write outside its allowed isolated workspace/path or push to `main`;
- idle autonomy can enqueue financial, credential, destructive production or permission-widening work;
- live-price/trading execution authority changes implicitly;
- exact deployed SHA cannot be proven;
- protected regression fails.

## Completion evidence

The program is complete only when all of the following are available:

- canonical release manifest generated by tools;
- fresh canonical CI PASS on exact source SHA;
- Peer Intelligence + Legion + Skill Evolution protected eval PASS;
- Gateway/OpenCode/Autonomy service tests and typechecks PASS;
- exact-SHA health verification from deployed services;
- staged smoke evidence;
- known-good rollback target;
- operations runbook with independent kill switches;
- current release marked KNOWN_GOOD only after production verification.
