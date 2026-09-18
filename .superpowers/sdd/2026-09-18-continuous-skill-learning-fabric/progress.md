# SDD ledger — plan: docs/superpowers/plans/2026-09-18-continuous-skill-learning-fabric.md

Spec (binding): docs/superpowers/specs/2026-09-18-continuous-skill-learning-fabric-design.md
Controller session: session_01K2S3Pd (sole controller; implementers may not spawn subagents)
Branch: claude/magical-euler-uu98r8 — PR #442 — NO MERGE

## Preconditions verified before Task 1

Base SHA at start: da3197d37ed7bb5f8c816e9d757a8a0386a307f0

Existing components the plan says to extend, confirmed present (not recreated):
- AI_SKILL_LIBRARY/v4/learning/{policy,skill_evo,skill_factory}.yaml, failure_ledger.json
- AI_SKILL_LIBRARY/v4/control_plane/{self_development,benchmark,verifier}.py
- AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml
- AI_SKILL_LIBRARY/v4/tools/{skill_forge,evaluate_skill_candidate}.py

## Ruling 001 — SDD skill not installed
Decision: follow the method as specified in the directive (implement -> tests -> self-review
-> independent reviewer -> fix -> scoped re-review -> commit -> ledger) rather than halting.
Reason: `superpowers:subagent-driven-development` is not among this session's available
skills and is not present in the repo; the directive states the loop in full.
Cost if wrong: the loop differs in some detail from the packaged skill. Mitigated by
following the directive's own numbered steps literally and recording every task here.

## Ruling 002 — local engine cannot execute here
Decision: no task may depend on running a local model in this container.
Reason: detect_llama_cpp_python() terminates the interpreter with SIGILL on this host
(recorded in WORKER_EXECUTION_LIVENESS.json, host 93891604e58e2451985a873a94b53e49).
Anything needing real local inference must be evidence-driven from recorded runs, or
deferred to CI. Cost if wrong: a task that silently needs inference would fail late;
mitigated by keeping all learning artifacts evidence-reading rather than model-running.

## Task log

| task | status | base sha | commits | tests | review | notes |
|------|--------|----------|---------|-------|--------|-------|

## Ruling 003 — release-pinned files, one rebuild at the end
Four files the plan requires modifying are sha256-pinned by release manifest 4.17.0:
learning/policy.yaml, learning/skill_evo.yaml, learning/skill_factory.yaml and
stable/continuous_intelligence.yaml. Editing any of them fails RELEASE_CHECK until the
manifest records the new digests. Tasks 1, 2, 5 and 6 each touch one.

Decision: do NOT rebuild the manifest per task. Commit the tasks, and refresh the release
record once, after the last pinned file is final, before the branch is pushed green.
Reason: an immutable release should record a finished state, not be re-cut four times
mid-plan; and four rebuilds would each need their own digest churn and review.
Cost if wrong: the working tree carries a known stale digest for several commits, so
RELEASE_CHECK is red locally in that window. Mitigated by not pushing until it is
refreshed, and by recording the exact failing digest here.

Known-stale digest opened at Task 1:
  AI_SKILL_LIBRARY/v4/learning/policy.yaml expected=83eeac08... actual=ee872569...

The Task 1 implementer was right to refuse to run release.py build itself: cutting a
release is a gate decision, not an implementer's, and it is outside the task's file list.

Note: the promotion judgement (known_good / promotion.validated) stays the operator's.
Refreshing content digests is not the same act as promoting a release, and this plan
does neither on its own authority.

## Task 1 — review round 1: CHANGES-REQUIRED

Independent reviewer (fresh agent, did not write the code) returned 2 BLOCKER, 7 SHOULD-FIX,
2 NIT. I reproduced every finding myself before acting rather than taking the report:

- BLOCKER 1: privacy was structural only for *unknown field names*. Five allowed fields
  (request_class, failure_class, resource_observation, quota_impact, evidence_ref) plus the
  id fields are unbounded strings: a 2 KB value containing `API_KEY=sk-live-...` validates
  in every one. Arrays and the `experiences` array itself have no maxItems.
- BLOCKER 2: FALLBACK is entirely ungated. A row can be FALLBACK with empty evidence_refs
  and protected_regression_status FAIL and still validate.
- Placeholder evidence (`["   "]`, `["n/a"]`), `last_measured_at: "tomorrow"`, and
  PRIMARY with measured_score 0 / verifier_pass_rate 0 all validate.
- learning_cycles.yaml and promotion_evidence.json can be set `authority: true` with all
  21 tests still green, because the test helper falls through a scalar.
- The role-pattern test never asserts a rejection: widening the pattern to `^.*$` keeps
  every test green.

Note on my own verification: I had checked named private fields, unknown fields, and
PRIMARY/PROFICIENT gating, and reported Task 1 sound. I did not check allowed-but-unbounded
fields or FALLBACK, and both were holes. The reviewer earned its place; a self-review would
have shipped this.

Fix round dispatched to a fresh implementer, TDD per finding. Schemas and tests are new and
unpinned, so the fixes do not touch the release manifest.

## Ruling 004 — who refreshes the stale digest
CI on 64f13df7 is red: CI_VALIDATE=FAIL failures=3, all three the same policy.yaml digest
mismatch. Everything else passes, including AI_CORE_RELEASE=PASS 9/9 and the Phase 6 gate.

Decision: after the Task 1 fixes land, refresh the release record so the manifest states
the truth about content that legitimately changed under an approved plan, and push once,
green. Leave `promotion.validated` and `known_good` exactly as they are.
Reason: I caused this red and the drive-to-green posture makes it mine; the failing check
itself names `release.py build` as the remedy; and a digest refresh is bookkeeping, not the
promotion judgement I earlier told the operator was theirs. That distinction is the whole
basis for acting here, so the promotion fields stay untouched.
Cost if wrong: a release record is rewritten by an agent. Mitigated by changing no
promotion field, by recording both digests here, and by the change being a recomputation
anyone can reproduce with the repo's own tool.

## Task 1 — COMPLETE

| field | value |
|---|---|
| base sha | da3197d3 |
| commits | 64f13df7 (artifacts), fc4f8276/1587bc9e (fix round + digest), 86157cad (fixture hygiene) |
| tests | 21 -> 46, all green; 85 green across curriculum + authority + security + release |
| review | CHANGES-REQUIRED (2 BLOCKER, 7 SHOULD-FIX, 2 NIT) -> all 8 actionable findings fixed |
| fix rounds | 1 |
| gates | RELEASE_CHECK=PASS 4.17.0, AI_CORE_RELEASE=PASS 9/9 |

Controller process error, recorded because it nearly mattered: I committed the fix
round while the implementer was still running, having checked the tests were green at a
moment I happened to look rather than waiting for its hand-back. The snapshot was
coherent, so nothing broke, and the two trailing edits it made afterwards (desensitising
a live-key-shaped test fixture) went in as 86157cad. The implementer was right not to
unwind a commit it did not make. Gate commits on hand-back, not on a green check.

Choices worth knowing, from the fix round:
- The capability floor 0.35 is read from model_mesh/domain_capabilities.yaml, not
  invented, and a test fails if the two ever drift apart.
- evidence_ref requires a scheme or a path with a file extension. That is what actually
  rejects "n/a" and "TODO"; a charset pattern alone does not. It also rejects a bare
  directory ref or a bare git sha, which is the likeliest false negative to bite later.
- class_token is lower-case ASCII only, so a Vietnamese classifier string would be
  rejected. Deliberate, but this repo has a Vietnamese-retention protected dimension, so
  it is written down rather than left to be discovered.

Remaining gap, honestly flagged by the implementer rather than hidden: learning_cycles.yaml
and promotion_evidence.json still have no schema. The helper now catches a scalar
authority:true on both, so the authority hole is closed, but their record shapes are
unconstrained. Carry into a later task rather than calling Task 1 more complete than it is.
