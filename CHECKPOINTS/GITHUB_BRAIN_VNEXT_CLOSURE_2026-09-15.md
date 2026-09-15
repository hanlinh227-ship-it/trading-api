# GITHUB BRAIN vNext — PHASES B–H CLOSURE (2026-09-15)

> Closure record for the ADAPTIVE GENERALIST BRAIN vNext work stream
> (phases B–H). Phase A closed earlier at release `4.9.2`. This file records
> what was merged, what was verified, and the default state every optional
> integration was left in.
>
> Evidence vocabulary matches `CHECKPOINTS/GITHUB_BRAIN_MASTER_HANDOFF_2026-09-15.md` §2:
> SOURCE VERIFIED / CI VERIFIED / PRODUCTION VERIFIED / NOT VERIFIED.

---

## 1. Final state

| Field | Value | Status |
|---|---|---|
| Release | `4.9.3` | SOURCE VERIFIED |
| `KNOWN_GOOD` | **YES** | PRODUCTION VERIFIED |
| Previous release | `4.9.2`, `known_good: true` (single-step rollback target) | SOURCE VERIFIED |
| vNext feature SHA on `main` | `4dfd012bac218f685b91ef40eaa45222b58ef9c9` | PRODUCTION VERIFIED |
| Production runtime revision at that SHA | `4dfd012bac218f685b91ef40eaa45222b58ef9c9` | PRODUCTION VERIFIED |
| Cloudflare Worker | `trading-v77-scanner` | SOURCE VERIFIED |
| Deployment authority | `deploy-skill-mandatory-fast-gateway.yml` (**sole**) | SOURCE VERIFIED |
| Merged PR | #351 `feat(vnext): complete adaptive generalist integrations B-H` | SOURCE VERIFIED |

### Verifying deployment run

Run **35001158446**, event `push`, head `4dfd012bac218f685b91ef40eaa45222b58ef9c9`, conclusion **success**.

```
FINAL_EXACT_SHA_GATE=PASS revision=4dfd012bac218f685b91ef40eaa45222b58ef9c9
PRODUCTION_LIVE_REVISION=4dfd012bac218f685b91ef40eaa45222b58ef9c9
ATTEMPTED_REVISION=4dfd012bac218f685b91ef40eaa45222b58ef9c9
SKILL_MANDATORY_FAST_GATEWAY_DEPLOY=PASS
PRIMARY_SKILL_REQUIRED=true
FAST_EXTERNAL_ROUTING_CALLS=0
MODEL_MESH_MODE=FREE_ONLY
MODEL_MESH_ROUTING_AUTHORITY=false
MODEL_MESH_MAX_PARALLEL=STANDARD=2 DEEP=4 FAST=0
RUNTIME_SWITCH_MUTATION=false
PROVIDER_SECRET_GENERATION=false
PROVIDER_SECRET_SYNC=ELIGIBLE_PROVIDERS_ONLY
TINYFISH_HEALTH=PASS optional=true
TINYFISH_CANARY=success (optional, non-gating)
```

The rollback step was **skipped** — production health was good, so no
rollback was required.

### Parity rule for this file

This closure commit and the `known_good: true` mutation advance `main` by one
commit beyond `4dfd012…`, and that commit is redeployed through the same sole
gated pipeline. A `main` SHA ahead of the number above is expected and is
**not** drift. Only a failed gate, or a production `runtimeRevision` that does
not equal `main`, is drift. Re-verify parity per master handoff §12.7 and trust
the repository over this file.

---

## 2. CI evidence on the merged head (`5af3a468cb3b96b55bd194884c086da9bf90da6f`)

| Workflow | Conclusion |
|---|---|
| AI Skill Library CI | success |
| Skill-Mandatory Fast Gateway CI | success |
| Zero Local Cloud Runtime | success |
| Cloudflare Research Runtime CI | success |
| Crypto Skill Registry Validate | success |
| AI Brain V4 Candidate Release | **skipped — expected** |

The Candidate Release skip is policy, not a missing execution: that workflow
gates on `startsWith(head.ref, 'evergreen/candidate/')` **and**
`pull_request.user.login == 'github-actions[bot]'`, or `workflow_dispatch`.
A human-authored feature branch can never satisfy it.

Local canonical validation on the merged tree: `CI_VALIDATE=PASS failures=0`
(372 tests, all validators, release check, retrieval freshness, consolidation
and exact-SHA finalization).

---

## 3. Integration default states — DO NOT SILENTLY CHANGE

Canonical policy: `AI_SKILL_LIBRARY/v4/integrations/policy.yaml`
(checkpoint key `vnext_integration_policy_path`). All upstreams are pinned to
exact audited commits; no floating `latest` is production authority.

| Integration | Default state | Bounded role |
|---|---|---|
| **Agent Skills** | `enabled: true`, `mode: compatibility_import_to_quarantine` | `SKILL.md` → normalize → Evergreen admission → quarantine. `auto_promote: false`. Never routing or reasoning authority. |
| **Graphify** | `enabled: true`, derived adapter | Derived knowledge graph only: exact source SHA required, stale detection, bounded nodes, secrets excluded. Source/spec/tests always win conflicts. `authority: false`. |
| **Ponytail** | `enabled: true`, advisory | Simplicity critic. Cannot remove requirements, weaken security, bypass tests, widen permissions, or replace architecture authority. |
| **OmniRoute** | **`enabled: false`** | Sandbox-only provider adapter. `network_execution_enabled: false`, routing/reasoning authority false, fusion/pipeline/autonomous orchestration/paid fallback/auto purchase all false, trial and promo never counted as recurring free. Off/unavailable/empty/stale are all safe. |
| **Free-model discovery** | Reuses canonical Evergreen / Model Mesh | No parallel discovery authority. Eligibility requires configured + entitlement + free-eligible + fresh health + quota + privacy + terms + capability. A provider claim is never auto-promoted to verified evidence. |
| **Legion** | Reuses canonical Legion runtime | Subordinate specialist executor only. Routing and reasoning authority false. Executes Brain-issued task graphs. FAST 0 / STANDARD 2 / DEEP 4. Same-family workers are not independent verification. |
| **Adaptive execution** | Bounded | FAST 0, STANDARD ≤2, DEEP ≤4 external workers. |
| **Speculative execution** | **OFF by default** | Only with explicit policy enable, and only DEEP + public-compatible data class + AVAILABLE health + quota + headroom threshold. |
| **Early exit** | Deterministic | `majority_vote: false`. Requires schema pass, security pass, permissions pass, required evidence, checker ACCEPT, and a checker from a distinct model family, with no unresolved conflict. |
| **Hard capability gates** | Still default-off | Unchanged from Phase A. |

---

## 4. Release packaging contract

`AI_SKILL_LIBRARY/v4/tools/release.py` now packages the load-bearing vNext
artifacts in `VNEXT_INTEGRATION_FILES`, appended to the stable scope:

```
AI_SKILL_LIBRARY/v4/integrations/policy.yaml        vnext_integration_policy
AI_SKILL_LIBRARY/v4/tools/agent_skill_compat.py     agent_skill_compatibility_tool
AI_SKILL_LIBRARY/v4/tools/integration_adapters.py   vnext_integration_adapter_tool
AI_SKILL_LIBRARY/v4/tools/adaptive_execution.py     adaptive_execution_tool
AI_SKILL_LIBRARY/v4/tools/discover_free_models.py   free_model_discovery_tool
AI_SKILL_LIBRARY/v4/tools/legion.py                 legion_runtime_tool
AI_SKILL_LIBRARY/v4/tools/admission.py              evergreen_admission_tool
```

Every entry is either checkpoint-resolved or declared under
`existing_subsystems_reused` in the integration policy. Nothing was added
speculatively. Release `4.9.3` contains 50 files.

`AI_SKILL_LIBRARY/tests/test_vnext_integrations.py::test_stable_release_packages_all_vnext_runtime_dependencies`
is the regression that keeps this contract honest.

---

## 5. Invariants re-confirmed

- GitHub Brain is the **single** routing and reasoning authority. No second
  Brain, router, Model Mesh or skill registry was introduced.
- Model Mesh mode `FREE_ONLY`; no paid fallback, no auto-purchase.
- FAST external workers = **0**. SECRET external execution = **0**.
- Family dedupe intact; no majority vote anywhere.
- Active Candidate Index intact; hard capability gates still default-off.
- Zero-Local observer (`cloudflare-zero-local-runtime-observer`) and production
  deploy (`cloudflare-zero-local-runtime-production`) hold **separate**
  concurrency groups. The deadlock regression
  `test_production_deploy_and_zero_local_observer_use_isolated_locks` passes.
  Do not re-merge these groups.
- Optional integrations fail gracefully: off, unavailable, empty and stale are
  all safe states and never become Brain failure.
- Cloud-first / zero-local preserved; no local machine is a required runtime.

---

## 6. Known issues (non-blocking, carried forward)

Both are inherited from the master handoff §6 and were **not** introduced or
resolved by this work stream:

1. `gemini_developer_api` returns 404 on model listing.
2. The `*/10` Model Mesh health-refresh schedule has never fired.

Neither gates the exact-SHA production contract.

No new blockers were opened by phases B–H.

---

## 7. Next session start procedure

Unchanged: `AGENTS.md` → `AI_SKILL_LIBRARY/checkpoint.json` →
`AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` →
`CHECKPOINTS/GITHUB_BRAIN_MASTER_HANDOFF_2026-09-15.md` → this file →
`CHECKPOINTS/MODEL_MESH_PRODUCTION_VERIFICATION.md`.

Re-verify current `main` SHA, release version, `known_good`, and production
`runtimeRevision` parity before trusting any number written here.
