# Cognitive Harmonization Design

## Goal
Integrate selected Groktopus agent-loop concepts into the existing GitHub Brain without creating a second reasoning authority or bypassing the current router, security, project authority, evidence, or release gates.

## Scope
Adopt five mechanisms: bounded agent loop, maker/checker separation, independent grader for DEEP/high-impact work, evidence harmonization before conclusion, and artifact-pyramid shaping. Reuse the existing canonical skills and do not add duplicate reasoning skills.

## Authority model
`current_runtime > current_project_authority > current_first_party > fresher_equal_authority > approved_reference > scoped_verified_memory > model_background` remains unchanged. External frameworks and provider outputs are evidence/reference inputs only.

## Runtime behavior
FAST remains unchanged. STANDARD may use a lightweight checker only when materially useful. DEEP may use maker/checker and an independent grader with bounded retries/replans. No loop may widen permissions, bypass security, mutate financial state, or persist hidden chain-of-thought.

## Harmonization contract
1. Normalize claims before comparison.
2. Preserve provenance and freshness.
3. Never majority-vote or silently average conflicting claims.
4. Resolve by authority/freshness when possible.
5. Escalate unresolved material conflicts; fail closed for high-consequence dependent conclusions.
6. Distill only verified reusable lessons into candidate memory/skills through Evergreen promotion gates.

## Artifact pyramid
Responses may be shaped as `summary -> analysis -> evidence/dossier`, but response format never changes authority or verification requirements.

## Safety and compatibility
Trading/live execution rules, zero-local runtime constraints, primary-skill/capsule requirements, max supporting skills, and current project authority remain unchanged. New behavior is additive and release-gated.

## Verification
Add a regression contract test and validator checks for the new policy, then run the existing Brain validators/tests/CI. Promotion requires no protected regression.