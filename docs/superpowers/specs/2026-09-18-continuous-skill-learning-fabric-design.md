# Continuous Skill Learning Fabric — Design

Date: 2026-09-18
Status: APPROVED DESIGN
Scope: PR #442 / AI Core Phase 6 extension
Architecture path: Option B — Skill Curriculum + Experience Learning + Promotion Gates

## 1. Objective

Increase the effective intelligence of the entire admitted model fleet by teaching models how to use the existing skill system better, continuously learning from measured execution outcomes, and improving role/model/skill selection over time without introducing a second Brain, router, scheduler, model authority, or evidence authority.

This design explicitly does not require continuous weight training. The primary learning mechanism is governed runtime learning through curriculum, replay, evidence, benchmark, routing refinement, skill evolution, and promotion gates. Weight fine-tuning is a later optional path for eligible open models only.

## 2. Immutable Authorities

The following remain authoritative:

- GITHUB_BRAIN_V4: sole Brain authority
- task_router: sole routing authority
- AI Legion: specialist-role orchestration
- Model Mesh: sole model/provider selection authority
- Open Model Universe: sole model admission/governance authority
- existing runtime scheduler: sole placement/execution scheduling authority
- existing lifecycle manager: acquire/load/unload/cache/evict
- existing verifier/evidence path: sole proof/reconciliation authority
- existing memory continuity subsystem: authority over continuity state

The Learning Fabric has no routing, admission, scheduling, permission, trading, or merge authority.

## 3. Existing Components Reused

The implementation must extend, not replace:

- AI_SKILL_LIBRARY/v4/learning/policy.yaml
- AI_SKILL_LIBRARY/v4/learning/skill_evo.yaml
- AI_SKILL_LIBRARY/v4/learning/skill_factory.yaml
- AI_SKILL_LIBRARY/v4/learning/failure_ledger.json
- AI_SKILL_LIBRARY/v4/control_plane/self_development.py
- AI_SKILL_LIBRARY/v4/control_plane/benchmark.py
- AI_SKILL_LIBRARY/v4/control_plane/verifier.py
- AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml
- existing eval, replay, evidence, promotion, and checkpoint machinery

No duplicate learning control plane is permitted.

## 4. Learning Model

The Fabric has three layers:

### 4.1 Skill Curriculum Learning

Every canonical skill can be converted into a curriculum contract containing:

- skill_id
- supported role branches
- trigger conditions
- required capabilities
- allowed tools
- input contract
- expected output contract
- positive examples
- negative/failure examples
- protected invariants
- benchmark tasks
- verifier requirements
- permission ceiling
- privacy constraints
- promotion class

A curriculum is training/evaluation material for orchestration behavior, not a new source of authority.

### 4.2 Experience Learning

Every eligible execution may emit sanitized observable evidence:

- request class
- selected role
- selected skill(s)
- selected model/provider/worker
- latency
- success/failure class
- verifier result
- retry/escalation path
- fallback path
- user correction signal where explicitly available
- resource/quota impact
- outcome score

The system must not persist hidden chain-of-thought, raw secrets, or unnecessary private prompt content.

### 4.3 Optional Weight Fine-Tuning

Weight updates are out of the default Phase 6 learning loop.

They may be introduced later only for eligible open models with:

- explicit licensing compatibility
- provenance
- dataset governance
- isolated evaluation
- rollback
- no authority widening

The Continuous Skill Learning Fabric must be useful even if no model is ever fine-tuned.

## 5. Core Data Flow

USER/EVENT
→ GITHUB_BRAIN_V4
→ task_router
→ AI Legion role
→ Skill Resolver
→ Model Mesh
→ scheduler
→ worker/provider/model
→ verifier
→ evidence reconciliation
→ response
→ sanitized experience intake
→ curriculum/replay evaluator
→ skill/model candidate update
→ protected regression suite
→ promotion gate
→ stable update or rejection

The learning path is downstream of execution and cannot bypass the canonical request path.

## 6. New Canonical Artifacts

Prefer extending equivalent files if they already exist. Otherwise add:

- AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml
- AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json
- AI_SKILL_LIBRARY/v4/learning/experience_ledger.json
- AI_SKILL_LIBRARY/v4/learning/learning_cycles.yaml
- AI_SKILL_LIBRARY/v4/learning/promotion_evidence.json

These are data/evidence surfaces, not new authorities.

## 7. Skill Competency Matrix

The system maintains measured competency across:

MODEL × SKILL × ROLE

Suggested states:

- NOT_TESTED
- ELIGIBLE
- LEARNING
- MEASURED
- PROFICIENT
- PRIMARY
- FALLBACK
- QUARANTINED

Each row must include:

- model_id
- skill_id
- role_id
- evidence_refs
- measured_score
- verifier_pass_rate
- protected_regression_status
- latency/resource observations
- last_measured_at
- promotion_state

No model may be marked proficient or primary for a skill without measured evidence.

## 8. Curriculum Compiler

A curriculum compiler should transform canonical skill metadata plus existing tests/evals into replayable learning/evaluation units.

It must:

- preserve original skill permissions
- preserve original privacy restrictions
- preserve authority boundaries
- inherit negative examples and failure cases
- attach verifier criteria
- generate no synthetic permission widening
- not mutate stable skills directly

The compiler produces candidate curriculum units, not production behavior by itself.

## 9. Learning Cycles

A learning cycle is bounded and replay-driven.

Cycle:

1. observe a gap or opportunity
2. select relevant skills/roles/models
3. freeze replay/eval set
4. execute candidate behavior
5. compare to current champion/baseline
6. run verifier
7. run protected regression suite
8. produce promotion evidence
9. promote, reject, merge, or quarantine candidate

Every cycle must have a unique ID and reproducible evidence references.

## 10. Candidate Types

Learning may propose:

- trigger refinement
- instruction refinement
- example expansion
- negative guard expansion
- tool-selection refinement
- role mapping refinement
- model preference change
- fallback change
- benchmark/eval expansion
- merge of overlapping skills
- creation of a new skill candidate

Strengthening an existing skill is preferred over creating a new primary skill.

## 11. Promotion Classes

Reuse existing risk classes and evergreen/self-development gates.

Class A:
- low-risk content/instruction optimization
- may auto-promote only through existing evidence gates

Class B:
- bounded orchestration/skill improvement
- may auto-promote only with sandbox + existing gates

Class C:
- sensitive permission/privacy/runtime behavior
- requires human approval

Class D:
- authority/security/trading/financial execution changes
- never auto-promote

Learning must never lower a risk class itself.

## 12. Protected Regressions

A candidate cannot promote if it regresses protected dimensions, including:

- reliability
- security
- instruction adherence
- Vietnamese retention
- privacy policy
- authority invariants
- provenance requirements

For protected dimensions, tolerance is zero unless an existing canonical policy explicitly says otherwise.

## 13. User Feedback and Corrections

User feedback may become evidence only after normalization.

Allowed:

- explicit correction
- explicit preference
- accepted/rejected output
- successful task outcome
- repeated failure pattern

Disallowed:

- inferring hidden preferences from unrelated data
- treating one correction as global truth
- storing secrets/raw private content unnecessarily
- bypassing evaluation because the user liked one answer

User feedback is a signal, not promotion authority.

## 14. ChatGPT as Mentor/Critic

ChatGPT may contribute:

- skill critique
- curriculum suggestions
- failure analysis
- benchmark ideas
- verifier rubrics
- instruction improvements
- candidate examples

These contributions must enter as external candidate evidence and cannot directly write stable behavior.

The system must not depend on copying large volumes of ChatGPT output into model-weight training. ChatGPT-derived suggestions are governed as candidate instructional/evaluation material.

## 15. Model Intelligence Growth

"Smarter models" in this design means improving effective system performance through:

- better skill selection
- better role selection
- better tool selection
- better prompts/instructions
- better model-role matching
- better escalation
- better verifier behavior
- better replay from prior failures
- better fallback selection
- better evidence-grounded specialization

It does not imply that base model weights changed.

## 16. Conflict Prevention

The Learning Fabric must not:

- change routing authority
- create a second router
- create a second Brain
- create a second scheduler
- bypass Model Mesh
- admit models directly
- modify stable skills directly
- self-approve permission expansion
- self-approve authority change
- enable paid APIs
- execute trades
- mutate main
- merge its own PR
- persist hidden reasoning
- persist secrets without authorization

Any attempted violation must fail closed and be tested.

## 17. Phase 6 Integration

The Fabric integrates with Phase 6 role specialization:

- role branches define responsibilities
- skill curriculum defines methods/competencies
- Model Mesh chooses measured models
- residency/capacity systems decide where execution runs
- experience evidence updates role/model/skill competency
- promotion updates candidate mappings only after gates

This means model specialization can improve over time without changing the topology of the federation.

## 18. 24/7 Operation

Background learning must be event-driven or scheduled with bounded work.

Allowed background tasks:

- aggregate telemetry
- detect repeated failures
- refresh competency measurements
- replay frozen eval sets
- propose candidates
- refresh promotion evidence
- update non-authoritative ledgers

Forbidden:

- busy loops
- unbounded autonomous mutation
- direct stable writes
- uncontrolled retraining
- repeated provider hammering

## 19. Failure Handling

On learning-cycle failure:

- preserve current champion
- mark candidate rejected/quarantined
- record evidence
- retain rollback target
- do not degrade stable behavior

On ambiguous verifier result:

- block promotion

On missing evidence:

- remain NOT_TESTED/INCUBATING

On security/authority conflict:

- reject candidate

## 20. Testing Requirements

Add/extend tests proving:

1. every promoted competency has measured evidence
2. no skill candidate bypasses verifier
3. stable direct write remains forbidden
4. permission widening cannot be learned
5. risk class cannot be silently downgraded
6. authority cannot be reassigned by learning
7. hidden reasoning is not persisted
8. secrets/private prompt content are not persisted
9. protected regressions block promotion
10. user feedback alone is insufficient for promotion
11. model-role preference changes require evidence
12. rejected candidates do not affect stable routing
13. rollback remains available
14. learning continues to operate when no weight fine-tuning exists
15. Phase 6 role branches remain non-authoritative
16. finance/trading authority remains unchanged

## 21. Success Criteria

The design is complete when:

- all canonical skills are discoverable by the curriculum layer
- every admitted model can be evaluated against relevant skills
- a competency matrix exists and is evidence-backed
- learning cycles are reproducible
- successful cycles can improve candidate skill/model-role behavior
- failed cycles cannot damage stable behavior
- protected regressions block promotion
- no duplicate authority exists
- no stable direct write exists
- no trading authority is introduced
- CI_VALIDATE and AI Core release gates remain passing

## 22. Non-Goals

This phase does not:

- train a frontier model from scratch
- guarantee all models become equally capable
- keep all models resident
- automatically merge changes
- replace existing skill/eval systems
- start live trading
- remove human gates for sensitive changes
- redefine AI_CORE_DONE semantics

## 23. Final Principle

The system should become more capable by accumulating verified competence, not by accumulating ungoverned mutations.

Learning is allowed to propose.
Evidence is required to prove.
Existing authorities decide what becomes stable.
