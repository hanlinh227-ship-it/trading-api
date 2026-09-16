# Universal Brain Fabric Implementation Plan — Self-Review Amendment

> **Status:** NORMATIVE AMENDMENT to `docs/superpowers/plans/2026-09-16-universal-brain-fabric-implementation.md`. The implementation executor must apply these corrections where they override the base plan.

## Self-review result

Spec coverage is complete, but three execution details in the base plan were too dynamic. This amendment removes those ambiguities and is mandatory during execution.

## A. Release manifest coverage is explicit

Task 2 must also modify `AI_SKILL_LIBRARY/v4/tools/release.py`.

Append the following rows to `RELEASE_FILES` so Stable release freshness covers the Universal Fabric authority/config files:

```python
("AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml", "universal_fabric_policy"),
("AI_SKILL_LIBRARY/v4/adapters/registry.yaml", "universal_adapter_registry"),
("AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py", "universal_fabric_validator"),
```

Task 3 must append these after the compiler exists:

```python
("AI_SKILL_LIBRARY/v4/tools/compile_universal_adapters.py", "universal_adapter_compiler"),
("AI_SKILL_LIBRARY/v4/runtime/generated/universal-adapters.json", "universal_adapter_snapshot"),
```

The associated test must call `build_manifest()` and assert all five paths are present. This prevents a release from being marked fresh while Universal Fabric policy or adapter metadata drift outside the manifest.

## B. Retrieval-index commands are exact

Replace Task 10 Step 4 with exactly:

```bash
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --write --root .
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --check --root .
```

Expected markers:

```text
RETRIEVAL_INDEX=WRITTEN
RETRIEVAL_INDEX=FRESH
```

Running the builder without `--write` only prints YAML and is not an implementation step.

## C. Candidate release version and command are fixed

The Universal Brain Fabric candidate release for this implementation is **4.11.0**.

Replace Task 10 Step 5 with exactly:

```bash
python AI_SKILL_LIBRARY/v4/tools/release.py build \
  --version 4.11.0 \
  --source universal_brain_fabric \
  --class feature \
  --validated \
  --root .
python AI_SKILL_LIBRARY/v4/tools/release.py check --root .
```

Do **not** pass `--known-good` before post-merge production verification. The build must create 4.11.0 with `known_good: false`; only Task 11 may mark it known-good after live canary and exact-SHA proof.

## D. Closure checkpoint path is fixed

Task 10 must create exactly:

`CHECKPOINTS/UNIVERSAL_BRAIN_FABRIC_2026-09-16.md`

It must record:

```yaml
architecture: GITHUB_BRAIN_V4
feature: UNIVERSAL_BRAIN_FABRIC
release: 4.11.0
candidate_known_good: false
production_workflow: .github/workflows/deploy-skill-mandatory-fast-gateway.yml
required_user_adapters: [chatgpt, claude, gemini]
fast_zero_rtt: true
paid_fallback: false
permission_widening: false
trading_authority_changed: false
```

and list the actual test/CI/deploy run IDs once produced. No alternate closure-checkpoint path is permitted for this phase.

## E. Evergreen integration uses the workflows that already exist

Task 7 must not introduce a second scheduler. It extends exactly:

- `.github/workflows/ai-brain-evergreen-scan.yml` — hourly source refresh already at `17 * * * *` and weekly audit at `23 3 * * 0`.
- `.github/workflows/ai-brain-evergreen-candidate.yml` — candidate cycle already at `41 * * * *`.

The scan workflow already emits:

- `/tmp/v4-quarantine-scan.json`
- `/tmp/v4-free-model-mesh-candidates.json`
- `/tmp/v4-intelligence-audit.json`

The new `run_upstream_watch.py` consumes `/tmp/v4-quarantine-scan.json` plus canonical `AI_SKILL_LIBRARY/sources.yaml`, normalizes only machine-readable source/capability metadata, and writes `/tmp/v4-upstream-watch.json`. The artifact is uploaded with the existing `v4-evergreen-source-refresh` bundle.

The candidate workflow must run `run_upstream_watch.py` after `evergreen.py scan` and before `evergreen.py materialize`. It may add candidate annotations/evidence only; `evergreen.py promote-class-a` remains the existing promotion path. It may not write Stable directly.

## F. Internal Evergreen principal is separate from user adapters

After Task 5 adds `evergreen`, the registry semantics are:

```yaml
user_adapter_ids: [chatgpt, claude, gemini]
internal_principal_ids: [evergreen]
```

`/brain/universal/capabilities` must expose user adapters separately and must never present `evergreen` as a user-facing AI client.

The Task 2 validator therefore reports:

```text
UNIVERSAL_FABRIC_VALIDATE=PASS user_adapters=3 internal_principals=1
```

after Task 5, while still rejecting any routing/reasoning authority claim.

## G. External-product boundary is a Definition-of-Done condition, not a hidden assumption

The repo can implement and deploy the Universal Brain endpoint, adapter SDK, OpenAPI contract, secrets, and production canary. It cannot by itself modify the consumer ChatGPT/Claude/Gemini products account-wide.

Therefore Task 11 closes in two layers:

1. `FABRIC_BACKEND_KNOWN_GOOD=PASS` — repo/cloud runtime is fully deployed and exact-SHA verified.
2. `CLIENT_CONNECTED=<client>` — recorded only after that external product has had its adapter/connector installed through a platform-supported connection mechanism.

Do not claim “every chat globally calls Brain” until all three client connections are actually verified. Backend known-good is allowed before external platform connection, but the distinction must be explicit in the closure checkpoint.

## Final self-review checklist

- Spec coverage: PASS after the overrides above.
- Placeholder/TBD/TODO scan: PASS; no implementation placeholder remains.
- Type/name consistency: PASS; `client_id`, `request_id`, `session_id`, `brain.route`, `brain.read_context`, `brain.submit_candidate_memory`, and `brain.review_candidate_memory` are used consistently.
- Authority check: PASS; no second Brain/router/promotion scheduler is introduced.
- FAST check: PASS; no synchronous state/telemetry/network dependency is added to FAST.
- Permission check: PASS; protected permission expansion remains approval-only.
- Release check: PASS; 4.11.0 and the exact release commands are fixed above.
