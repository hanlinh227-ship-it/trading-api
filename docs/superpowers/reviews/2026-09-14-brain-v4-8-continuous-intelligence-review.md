# Brain V4.8 Continuous Intelligence — Review Evidence

## Scope

This review covers the approved Brain 4.8 Continuous Intelligence & Autonomous Improvement implementation on feature branch `brain-v4-continuous-intelligence-4-8` against baseline `main` SHA `c561c9f29b131d20e6ac8c7c1a7beddd45c0b039`.

The implementation extends the existing GITHUB_BRAIN_V4 dual-plane architecture. It does not create a second reasoning authority and does not change Trading/G9 execution authority, Railway live-price execution authority, wallet/order permissions, credential access, secret handling, or production-write permission ceilings.

## Authority and architecture invariants

- Canonical Brain authority remains `GITHUB_BRAIN_V4`.
- Stable Runtime Plane remains independent from Evergreen Update Plane health.
- Default canonical routed skills remain `109` and default execution capsules remain `109`.
- FAST routing remains zero external routing calls.
- Trading project authority remains separate and unchanged.
- Railway live-price research runtime remains separate and unchanged.
- External repositories remain evidence/reference inputs only and do not gain routing/reasoning authority.
- Continuous Intelligence cannot widen financial, wallet, credential, destructive, secret-access, security-bypass, or production-write permissions.
- Class A/B are eligible for unattended promotion only after required gates; Class B additionally requires sandbox evidence.
- Class C/D require explicit human authorization before Stable promotion.

## Implemented capability

Brain 4.8 adds an immutable Stable contract at `AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml` and checkpoint wiring at `stable_continuous_intelligence_path`.

Continuous Intelligence capabilities implemented in `AI_SKILL_LIBRARY/v4/tools/evergreen.py`:

- patch-only automatic V4 release increment via `next_patch_version`;
- source lifecycle evaluation (`active`, `stale`, `reverify`, `deprecated`, `archived`);
- evidence-backed deterministic gap detection;
- sanitized verified failure-to-regression conversion;
- baseline-vs-candidate comparison with zero protected-regression tolerance;
- explicit Class C manual-authorization decision;
- continuous intelligence audit report generation.

Scheduled operation:

- every 6 hours: current release validation, V4 validation, real remote upstream registry validation, GitHub candidate discovery, audit artifact;
- daily: isolated Class A candidate scan/materialization/promotion attempt, retrieval-index rebuild, full tests/V4/CI validation before branch publication, candidate audit artifact;
- weekly: deep read-only 4.8 contract/release/canonical-CI audit within the existing Evergreen Scan workflow;
- event-driven failure intake is supported by the sanitization/regression contract when verified sanitized failure evidence is supplied.

The weekly audit was deliberately consolidated into the existing Evergreen Scan workflow to preserve the repository consolidation invariant that active workflow count must remain below 120.

## TDD RED evidence

RED contract test commit:

`57606152bacdf7bc368e0d0d1e1dea09fa7a8fa5`

AI Skill Library CI run:

`34798501559`

Job:

`103836206744`

Observed RED state:

- legacy validators/release/index checks remained healthy;
- 179 tests were discovered;
- the new Brain 4.8 test failed because the Continuous Intelligence helper interface did not yet exist (`ImportError` for `compare_candidate`).

This establishes a real pre-implementation failure for the new contract.

## Debugging evidence

An intermediate full-CI run exposed two repository-level invariant failures:

1. Retrieval index remained on release `4.7.0` because the canonical builder was executed without `--write`.
2. Adding a standalone weekly audit workflow increased active workflow count from 119 to exactly 120, violating the consolidation requirement `< 120`.

Root-cause fixes:

- regenerate the committed retrieval index with canonical `build_retrieval_index.py --root . --write`;
- permanently rebuild the retrieval index before future Evergreen candidate validation;
- remove the extra standalone workflow and place the weekly audit as a separate job/schedule in `ai-brain-evergreen-scan.yml`.

Current retrieval index is release `4.8.0` with:

- HOT: 130
- WARM: 138
- COLD: 45

## Release generation evidence

Brain 4.8.0 was generated with the canonical release tool, not hand-authored hashes.

Temporary generation workflow run:

`34798911244`

Job:

`103837402106`

Observed generation evidence:

- `RELEASE_BUILD=PASS version=4.8.0 files=20`
- retrieval index rebuilt by canonical builder;
- active release verify: zero errors / zero warnings;
- `RELEASE_CHECK=PASS version=4.8.0`;
- dedicated Brain 4.8 contract tests passed.

The temporary generation workflow was deleted after generated artifacts were committed.

## Final GREEN evidence before review-evidence commit

Feature head verified before this review file:

`9bb1050ae0097753d43ef833780774d62488a772`

Relevant GitHub Actions results on that exact feature head:

- AI Skill Library CI — SUCCESS — run `34799373948`
- Cloudflare Research Runtime CI — SUCCESS — run `34799373944`
- Skill-Mandatory Fast Gateway CI — SUCCESS — run `34799373949`
- Zero Local Cloud Runtime — SUCCESS — run `34799373951`
- Crypto Skill Registry Validate — SUCCESS — run `34799373934`
- AI Brain V4 Candidate Release — SKIPPED as expected by its PR condition — run `34799373946`

Canonical AI Skill Library CI job `103838749571` reported:

- registry validator PASS;
- Brain validator PASS;
- router validator PASS;
- authority validator PASS;
- adaptive runtime validator PASS;
- V3 compatibility PASS;
- V4 validator PASS;
- skill registry PASS;
- Skill Gateway validator PASS;
- Skill Gateway snapshot compile/validation PASS;
- `RELEASE_CHECK=PASS version=4.8.0`;
- `RETRIEVAL_INDEX=FRESH hot=130 warm=138 cold=45`;
- consolidation validator PASS;
- `Ran 189 tests ... OK` in `AI_SKILL_LIBRARY/tests`;
- `Ran 26 tests ... OK` in root `tests`;
- `CI_VALIDATE=PASS failures=0`.

## Remote-source reality check

Final canonical CI also ran real GitHub remote validation and reported 0 errors with 3 non-blocking warnings:

- `continuedev/continue` is intentionally marked archived;
- `f/awesome-chatgpt-prompts` canonical repository name is now `f/prompts.chat`;
- `facebook/react` canonical repository name is now `react/react`.

Brain 4.8 wires this remote registry validation into the six-hour source-refresh job so upstream maintenance/rename status is periodically rechecked. The audit is uploaded as an artifact; the system does not silently rewrite the source registry from warnings.

## Changed-file safety review

The implementation diff is confined to Brain policy/tooling/tests/workflows/release/index/docs. It does not modify:

- Trading authority files;
- Railway live-price execution code/authority;
- wallet/order write capability;
- secrets or credentials;
- Cloudflare runtime-switch variables;
- financial execution permissions.

Primary changed areas:

- `.github/workflows/ai-brain-evergreen-candidate.yml`
- `.github/workflows/ai-brain-evergreen-scan.yml`
- `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md`
- `AI_SKILL_LIBRARY/checkpoint.json`
- `AI_SKILL_LIBRARY/evals.yaml`
- Brain 4.8 regression tests
- `AI_SKILL_LIBRARY/v4/evergreen/*`
- `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml`
- `AI_SKILL_LIBRARY/v4/releases/4.8.0/*`
- `AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml`
- `AI_SKILL_LIBRARY/v4/tools/evergreen.py`
- `AI_SKILL_LIBRARY/v4/tools/release.py`
- approved design/implementation documents.

## Known limitations / truthful boundaries

1. Class B is policy-eligible for unattended promotion after sandbox evidence, but the concrete scheduled candidate workflow currently materializes/promotes Class A candidates only. Brain 4.8 must not be described as having a fully automated Class B executor.
2. Failure-to-regression machinery is implemented and tested, but no production telemetry source is fabricated. Learning from production failures occurs only when verified sanitized evidence is actually supplied.
3. Source lifecycle evaluation exists and upstream registry revalidation runs every six hours, but the current source registry does not persist a per-source `last_verified` timestamp. Therefore Brain 4.8 provides recurring remote revalidation/evidence artifacts, not a claim of durable per-source freshness timestamps.
4. This release improves knowledge/workflow/eval/routing/tool-use intelligence. It does not retrain foundation-model weights.

## Rollback

The previous verified Stable release `4.7.0` remains the rollback target until Brain 4.8.0 is merged and exact-main production deployment is independently verified.

Continuous Intelligence/update-plane failure must leave the last known-good Stable request path operational.

## Merge / production gate

This review file itself changes the feature head. Therefore no merge/completion claim is valid until all relevant PR CI is re-run and green on the exact review-evidence head.

After merge, Brain 4.8.0 may be called production-live only after the exact-main Cloudflare Skill Gateway deployment verifies the merged SHA through its runtime contract, Brain health, and route matrix. Railway live-price verification remains a separate runtime/authority check.
