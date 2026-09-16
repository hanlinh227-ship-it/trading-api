# Final Hardening 4.11.1 — Production Closure Checkpoint

Date: 2026-09-16
Architecture: GITHUB_BRAIN_V4
Status: PRODUCTION KNOWN-GOOD / EXACT-SHA VERIFIED
Target release: `4.11.1`
Previous known-good release: `4.11.0` (production SHA `0e89cd69b7aef699f4b37844141705b51a7f9ce8`, deploy run 35067636598)
Production source SHA: `b9774d83f877309f9b4eaed5acc2097ef62e79bd` (main after PR #380 `cf930d9a` + PR #381 `b9774d83`)
Production workflow run: `35073895563` (FINAL_EXACT_SHA_GATE=PASS; run `35072895068` at `cf930d9a` failed closed on a self-heal/canary probe race and rolled back to `0e89cd69`, fixed by PR #381)

## Scope of this hardening round

Audit-driven fixes only; no re-architecture, no second Brain/router/registry, no change to
Trading authority or execution safety, no change to the FAST/STANDARD/DEEP contract.

| Area | Defect fixed | Regression guard |
|---|---|---|
| Router | financial/destructive/credential/permission vocabulary (en + vi, accented + unaccented) routed FAST without authority | `test-skill-gateway-snapshot.mjs`, `test_skill_mandatory_policy.py` |
| Universal entry | explicit `requested_action_class` could downgrade an inferred high-impact class and unlock safe-degraded serving | `test-universal-entry-contract.mjs`, `test_universal_entry.py` |
| Memory | client-controlled candidate key allowed cross-client overwrite and post-promotion reset; no review state machine; secret scan covered only `content`; key-delimiter collisions; python `candidate -> active` hop | `test-memory-candidate.mjs`, `test-memory-context-handler.mjs`, `test_memory_lifecycle.py` |
| Model Mesh | manual probe bypassed the shared self-heal claim (cron re-probe + RMW race → overlay canary flake); quarantined models re-probed every cycle | `test-model-mesh-handler.mjs`, `test-scheduled-health.mjs`, `test-model-mesh-resilience.mjs` |
| Evergreen | scan hits self-verified provenance; admission against empty catalog; no permission allowlist; release workflow merged its own candidate PR | `test_v4_skill_admission.py`, `test_v4_evergreen_workflow.py` |
| Release tooling | builder could not reproduce the 4.11.0 manifest (2 rows missing); non-atomic manifest/history writes; unvalidated history chain; generated adapter snapshot not ignored | `test_v4_consolidation.py`, `test_v4_release.py`, `test_compile_universal_adapters.py` |
| Authority docs | checkpoint-registered docs asserted 4.9.1 / 4.8.1 / 4.9.8 as current | `test_v4_consolidation.py` |
| Deploy workflow | cron shared the deploy concurrency group; mojibake canary text; secret sync before rollback capture; vacuous FAST proof; PASS verdict on unverified revision; missing SHA drift check | `test-deploy-safety.mjs`, `tests/test_cloud_runtime_policy.py` |

## Invariants preserved

- `GITHUB_BRAIN_V4` remains sole routing/reasoning authority; the compiled snapshot is the only router.
- Model Mesh stays FREE_ONLY, workers only, STANDARD ≤ 2 / DEEP ≤ 4 / FAST = 0, SECRET and unknown data class fail closed.
- Overlay canary keeps the causal (superset) invariant from PR #379.
- Trading authority, runtime switches and execution safety are untouched.

## Known-good procedure

1. PR merges to `main` after green CI on the exact PR head.
2. `Deploy Skill-Mandatory Fast Gateway` deploys exact main and runs every production canary.
3. Only after `FINAL_EXACT_SHA_GATE=PASS` at the merged SHA: `release.py`/`evergreen.py mark-known-good` sets `promotion.validated` and `known_good`, and this record is updated with the production SHA and run id.

Previous closure record: `CHECKPOINTS/UNIVERSAL_BRAIN_FABRIC_4_11_0_CLOSURE_2026-09-16.md`.
