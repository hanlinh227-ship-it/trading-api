# Brain V4 Selective Fusion — Verification Evidence

Date: 2026-09-14
PR: #260
Base SHA: `b594ea5e20f329322e7f8a6b3f5a914ec82e1fa8`

## Scope review

The candidate changes are limited to Brain authority/supporting contracts, source/eval registries, canonical skill output contracts, domain manifests, tests, quarantine evidence, generated retrieval/release metadata, the global Brain checkpoint, and approved design/plan documentation.

No Trading project authority file, live-price policy, wallet/order capability, production runtime switch, credential, or secret is modified.

## TDD evidence

- RED: PR CI on head `e44533cccb8af250434a795c38f902e5c3532018` ran 178 Brain tests with 9 expected failures from the missing Brain 4.7 selective-fusion contracts while baseline validators compiled and ran successfully.
- GREEN: the canonical one-shot generator on head `e239ce30e5a88a018f2fd8aadefe0f55366d74d4` generated release/index/snapshot state and reported `CI_VALIDATE=PASS failures=0`, `Ran 178 tests ... OK`, and `Ran 26 tests ... OK` after the generator workflow was removed from the mergeable worktree.
- Final checkpoint sync: the reindex workflow rebuilt the HOT/WARM/COLD retrieval index after `AI_GLOBAL_CHECKPOINT.md` advanced to 4.7 and again ran the full validation path on mergeable state.

## Protected invariants

- canonical routed skills: 109
- execution capsules: 109
- FAST external routing calls: 0
- FAST source candidates: 0
- new primary skills: 0
- normal local installation required: no
- upstream routing/reasoning authority: none
- Trading execution authority: unchanged/external project only
- Railway live-price research authority: unchanged

## Upstream intake

Approved bounded sources: `modelcontextprotocol/python-sdk`, `docling-project/docling`, `microsoft/graphrag`, `UKGovernmentBEIS/inspect_ai`, `ossf/scorecard`, `aquasecurity/trivy`, `Arize-ai/openinference`, and `microsoft/playwright`.

Deferred rather than duplicated: Microsoft Agent Framework, Graphiti, PyRIT, Syft, Storybook, Lighthouse, and NautilusTrader (already represented as design-reference-only).

## Merge gate

Merge remains blocked until the current human-authored PR head receives fresh GitHub Actions results and the final diff review finds no Critical/Important issue. Production completion remains blocked until the merged exact main SHA is deployed and `/runtime/contract`, `/brain/health`, and the route smoke matrix verify that exact SHA.
