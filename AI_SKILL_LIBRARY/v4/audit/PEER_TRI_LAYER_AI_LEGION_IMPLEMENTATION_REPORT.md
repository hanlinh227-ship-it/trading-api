# Peer Tri-Layer AI Legion — Implementation Audit

Date: 2026-09-15
Status: implementation candidate; stable promotion intentionally blocked
Repository: `hanlinh227-ship-it/trading-api`
Branch: `github-brain-v4-afmm-implementation2`
Spec: `docs/superpowers/specs/2026-09-15-peer-tri-layer-ai-legion-design.md`
Plan: `docs/superpowers/plans/2026-09-15-peer-tri-layer-ai-legion.md`

## Executive result

The Peer Tri-Layer AI Legion architecture has been implemented on the isolated implementation branch as a bounded extension of GITHUB_BRAIN_V4. It does not replace the canonical router, does not create a second provider registry, and does not grant routing/reasoning authority to any model, agent, upstream framework, or generated skill.

The implementation is deliberately **not promoted to Stable** at this checkpoint. The active release pointer remains `4.8.1` because Adaptive Free Model Mesh (AFMM) release/snapshot/runtime dependency verification and the existing capability-fusion release manifest are not yet promoted together. Candidate release packaging is side-effect free and records `adaptive_free_model_mesh_verified=false` until that dependency is proven.

## Implemented components

1. **Peer learning policy**
   - Learning Layer A: `experience`
   - Learning Layer B: `curated`
   - Learning Layer C: `exploration`
   - All three have peer epistemic rights.
   - Fixed layer weights/priorities are forbidden.
   - Majority vote is forbidden as a truth rule.
   - Learning-layer identity is separate from Risk Class A/B/C/D.

2. **Typed AI Legion specialist registry**
   - Engineering builder
   - Security reviewer
   - Research scout
   - Data/RAG analyst
   - Creative prompt specialist
   - UX/UI reviewer
   - 3D asset validator
   - Automation integrator
   - Deployment verifier
   - Quant researcher
   - Business analyst
   - Game-system designer
   - Academic researcher
   - Independent checker
   - Each agent has typed domain/mode/tool/source/privacy/permission/risk/provenance/verification contracts.

3. **Bounded task graph**
   - Brain-owned decomposition and delegation only.
   - FAST: 0 Legion workers.
   - STANDARD: <= 2 concurrent workers.
   - DEEP: <= 4 concurrent workers.
   - Duplicate write ownership is rejected unless an explicit integrator owns the merge target.

4. **Peer Intelligence Bus**
   - Normalizes claims and provenance.
   - Links contradictions by content/evidence, not source layer.
   - Scores evidence without source-layer bonus.
   - A single well-verified exploration claim can beat multiple unsupported claims.
   - Material unresolved conflict blocks stable promotion.

5. **OpenCode bounded worker adapter**
   - Brain-native modes: plan, explore, research, patch, test, review.
   - Brain deny rules cannot be upgraded by worker configuration.
   - Plan/review/explore/research remain read-only as specified.
   - Patch is bounded and cannot git-push.
   - Results are source-SHA checked, path checked, permission checked, and credential checked.

6. **Awesome LLM Apps pattern fusion**
   - Single-specialist routing for simple bounded work.
   - Parallel specialist pattern for independent multi-domain work.
   - Maker/checker for material changes.
   - MCP specialist routing.
   - Agentic RAG and corrective RAG.
   - Multimodal team routing.
   - Patterns remain reference-only and do not become an authority/runtime dependency.

7. **Brain-native Skill Factory**
   - Triage: discard / improve / merge / create.
   - Candidate default state: incubating.
   - Lineage/provenance/eval plan required.
   - Merge cannot widen permission or downgrade risk.
   - Stable catalog mutation is promotion-pipeline-only.

8. **SkillEvo evolution engine**
   - Frozen replay sets.
   - Bounded mutation budget.
   - Protected eval rules.
   - Measured scoring; LLM judge alone cannot promote.
   - Protected regression and unchanged permission are mandatory.
   - Valid challengers become champion candidates only, not direct Stable replacements.

9. **Idle autonomous learning scheduler**
   - Yields immediately to active user work.
   - Allows only declared low-risk background jobs.
   - Enforces token/API/compute/concurrency/storage/network budgets.
   - Budget reservation is fail-closed/nonnegative.
   - Skill mutation budget is bounded.

10. **Cloud runtime status contracts**
   - Reuses existing `cloudflare-worker/skill-gateway-handler.js`; no parallel server.
   - Adds `/brain/legion/health`.
   - Adds `/brain/legion/capabilities`.
   - Adds `/brain/learning/status`.
   - `/brain/route` remains provider-free with `externalRoutingCalls=0`.
   - Status output is sanitized metadata only.

11. **Legion security validator**
   - Rejects untrusted prompt-injection instructions attempting privileged actions.
   - Rejects generated financial-execution capability.
   - Rejects permission/filesystem widening.
   - Rejects credential-like worker output.
   - Rejects high-risk/permission-changing idle jobs.
   - Enforces single commander and peer-layer invariants.
   - Wired into canonical `ci_validate.py` before release packaging.

12. **Checkpoint and non-promoting candidate release packaging**
   - Checkpoint resolves Legion/learning policy/tool paths.
   - Release tool exposes `CANDIDATE_EXTENSION_FILES` for Legion/learning contracts.
   - `build_candidate_manifest()` hashes Stable + Legion contracts without changing `current.json`.
   - Candidate promotion is blocked until declared dependencies are verified.

## Upstreams absorbed

### `anomalyco/opencode` — MIT
Absorbed patterns: Plan/Build separation, primary/subagent specialization, read-only exploration/research modes, granular permission ceilings, MCP/provider interoperability, isolated coding session lifecycle. OpenCode remains an optional worker, never authority.

### `Shubhamsaboo/awesome-llm-apps` — Apache-2.0 reference
The user-supplied `awesome-llm-apps/awesome-llm-apps` is a fork; maintained parent is used as the canonical pattern reference. Absorbed patterns include multi-agent specialists, Mixture-of-Agents diversity, MCP routing, agentic/corrective RAG, multimodal teams and research planner/executor concepts. The raw majority/aggregator pattern is not used for truth.

### `ECNU-ICALK/AutoSkill` / SkillEvo — MIT reference
Absorbed patterns: experience-driven skill mining, discard/improve/merge/create triage, lineage/versioning, frozen replay, bounded mutation, eval compilation, champion comparison and promotion testing. AutoSkill/SkillEvo cannot write Stable directly.

### Existing AFMM references
Models.dev/OpenCode provider discovery, Portkey metadata/gateway patterns, vLLM semantic routing, Microsoft Agent Framework bounded workflows and previously approved Brain references remain subordinate execution/evidence patterns.

## Authority invariants

- Sole commander: `GITHUB_BRAIN_V4`.
- Legion `routing_authority=false`.
- Legion `reasoning_authority=false`.
- External-framework authority=false.
- Generated skill stable write=false.
- Unbounded child authority tree=forbidden.
- AFMM remains the only model/provider execution registry.

## Peer-learning invariant

`experience`, `curated`, and `exploration` have equal rights to propose hypotheses, evidence, experiments, skill candidates and challenges. Branch identity carries no permanent weight. Evidence quality is evaluated per claim by provenance, freshness, contract authority, reproducibility, measured test/benchmark evidence and verification outcome.

## Permission and security gates

Always blocked or explicitly gated by higher Brain policy:

- live financial execution;
- transfers/withdrawals/wallet signing;
- credential/key mutation;
- permission widening;
- destructive production operations;
- disabling security controls;
- modifying Brain authority hierarchy;
- high-risk self-promotion;
- quota/access-control circumvention.

Secrets, credentials, private keys and hidden chain-of-thought are forbidden in learning datasets, public-model prompts, traces and generated skills.

## Test evidence

Focused Legion Branch TDD has verified component suites across policy, agents, task graph, Intelligence Bus, OpenCode adapter, Awesome LLM pattern fusion, Skill Factory, SkillEvo, idle learning, runtime contracts and adversarial security.

Verified green run after Legion validator correction:
- Workflow: `Legion Branch TDD`
- Run: `34938872179`
- Commit: `973db644be153b63d4426047ff2e53aac7a9b26e`
- Conclusion: `success`

The later canonical AI Skill Library CI reaches and passes:
- `validate_model_mesh.py`
- `validate_legion.py`
- Skill Gateway snapshot compile/validate
- Model Mesh snapshot compile/validate

Its remaining failures are pre-existing candidate-release/stable-release drift on this implementation branch: active `4.8.1` does not yet hash AFMM/reliability/reputation/capability-fusion candidate changes. This is an intentional promotion blocker, not evidence of a Legion security or component-test failure.

## AFMM dependency status

Status: **NOT YET VERIFIED FOR STABLE PROMOTION**.

Observed branch validation can compile/validate an empty safe Model Mesh snapshot, but the current stable release manifest is stale relative to the AFMM/capability-fusion changes on this implementation branch. Therefore the Legion candidate manifest must retain:

```yaml
dependencies:
  adaptive_free_model_mesh_verified: false
promotion:
  blocked: true
```

No claim of active free-provider production execution is made from this branch state.

## Runtime deployment status

No production deployment of Peer Tri-Layer AI Legion has been performed from this implementation branch. No production exact-SHA claim is made.

Runtime endpoints are implemented in the existing handler and are eligible for staging/exact-SHA verification only after branch validation/dependency gates permit it. Production `main` remains untouched by this implementation work.

## Known intentionally gated capabilities

- Autonomous live trading/financial execution.
- Credential/secret mutation.
- Production destructive writes.
- Production permission expansion.
- Self-modification of Brain authority hierarchy.
- Self-approval of high-risk promotion.
- Unbounded model/agent fan-out.
- Unlimited idle learning resource consumption.
- Provider quota/access-control bypass.

## Handoff rule

Continue development from `github-brain-v4-afmm-implementation2`. Before any Stable promotion:

1. resolve AFMM stable release/snapshot/runtime verification;
2. run focused Legion tests green at the final branch SHA;
3. run canonical V4/authority/security/Skill Gateway/Model Mesh/Legion validators;
4. build the Legion candidate manifest at exact source SHA;
5. confirm the active stable pointer is not changed until promotion is explicitly permitted by the existing release-risk policy;
6. if staging is deployed, verify `/brain/health`, `/brain/legion/health`, `/brain/learning/status`, `/brain/route` and exact source SHA;
7. only then prepare a Stable release/promotion PR.
