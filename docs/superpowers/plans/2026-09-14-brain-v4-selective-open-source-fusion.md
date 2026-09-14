# Brain V4 Selective Open-Source Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the existing 109-skill GitHub Brain with vetted MCP, document-intelligence, graph-retrieval, eval, supply-chain, observability, and browser-verification patterns without adding a second authority chain, widening permissions, or introducing mandatory local runtime dependencies.

**Architecture:** Keep Brain V4's router, authority chain, source registry, canonical catalog, execution capsules, Evergreen gates, and release system intact. Add vetted upstreams as bounded RAG/reference sources, absorb their patterns into existing declarative contracts, prove the changes with the existing open-source-fusion test suite plus CI validators, then rebuild generated index/snapshot/release artifacts using canonical tools only.

**Tech Stack:** YAML declarative contracts, Python 3.12 validators/unit tests, GitHub Actions, existing Brain V4 release/index/snapshot tooling.

**Spec:** `docs/superpowers/specs/2026-09-14-brain-v4-selective-open-source-fusion-design.md`

## Global Constraints

- Canonical routed skill count remains exactly `109`.
- Exactly one primary skill and one validated execution capsule remain required per routed request.
- FAST keeps `max_external_routing_calls: 0`, `max_source_candidates: 0`, HOT-only retrieval, and no synchronous upstream refresh.
- New upstream repositories are evidence/reference only; routing authority and reasoning authority remain false.
- No wallet, credential, destructive, production-write, order-execution, or Trading/G9 authority expansion.
- No mandatory user-local installation or mandatory external framework/runtime dependency.
- No upstream code reuse by default; only normalized capability patterns are absorbed.
- Source registry caps remain `max_sources_per_category: 20` and `max_total_sources: 96`; do not raise them to fit candidates.
- `software` is already at its category cap, so new engineering/tooling candidates are classified under existing `code` capacity where semantically acceptable.
- Generated retrieval indexes, Skill Gateway snapshots, and release hashes are produced by canonical tools, never hand-edited.
- Release at implementation start is `4.6.0`; target feature release is `4.7.0` only if the pointer still resolves to `4.6.0` immediately before release build.

---

### Task 1: RED tests for the selective-fusion contract

**Files:**
- Modify: `AI_SKILL_LIBRARY/tests/test_brain_4_6_open_source_fusion.py`
- Create: `AI_SKILL_LIBRARY/v4/evergreen/quarantine/brain_4_7_selective_fusion.yaml`

**Interfaces:**
- Consumes: existing `load_yaml()` helper and `compile_snapshot()` in the current test module.
- Produces: regression assertions that later declarative changes must satisfy; quarantine metadata with zero authority and zero permission expansion.

- [ ] **Step 1: Add failing tests before implementation**

Extend the existing test class with assertions equivalent to:

```python
    def test_47_selective_sources_are_vetted_without_new_authority(self):
        registry = load_yaml("AI_SKILL_LIBRARY/sources.yaml")
        fusion = load_yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        by_repo = {row["repo"]: row for row in registry["sources"]}
        expected = {
            "modelcontextprotocol/python-sdk": "RAG_ONLY",
            "docling-project/docling": "RAG_ONLY",
            "microsoft/graphrag": "REFERENCE_ONLY",
            "UKGovernmentBEIS/inspect_ai": "RAG_ONLY",
            "ossf/scorecard": "RAG_ONLY",
            "aquasecurity/trivy": "RAG_ONLY",
            "Arize-ai/openinference": "RAG_ONLY",
            "microsoft/playwright": "RAG_ONLY",
        }
        for repo, tier in expected.items():
            self.assertIn(repo, by_repo)
            self.assertEqual(by_repo[repo]["usage_tier"], tier)
            self.assertIn(repo, fusion["upstream_pattern_map"])
            row = fusion["upstream_pattern_map"][repo]
            self.assertFalse(row.get("routing_authority", False))
            self.assertFalse(row.get("mandatory_runtime_dependency", False))
            self.assertFalse(row.get("code_reuse", False))

    def test_47_contracts_cover_mcp_documents_graph_eval_intake_observability_browser(self):
        fusion = load_yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        retrieval = load_yaml("AI_SKILL_LIBRARY/v4/stable/retrieval.yaml")
        observability = load_yaml("AI_SKILL_LIBRARY/v4/stable/observability.yaml")
        evals = load_yaml("AI_SKILL_LIBRARY/evals.yaml")
        self.assertTrue(fusion["mcp_interoperability"]["permission_ceiling_required"])
        self.assertTrue(fusion["document_intelligence"]["structured_extraction_before_ocr"])
        self.assertFalse(retrieval["graph_retrieval"]["routing_authority"])
        self.assertEqual(retrieval["graph_retrieval"]["profiles"], ["STANDARD", "DEEP"])
        self.assertTrue(observability["ai_semantics"]["sensitive_payloads_forbidden"])
        required = {
            "mcp_contract_integrity", "document_fidelity", "graph_retrieval_safety",
            "oss_intake_security", "observability_sanitization", "browser_runtime_verification",
        }
        self.assertTrue(required.issubset(set(evals["benchmark_classes"])))

    def test_47_keeps_skill_count_fast_and_trading_invariants(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-14T00:00:00Z")
        budgets = load_yaml("AI_SKILL_LIBRARY/v4/stable/budgets.yaml")
        trading = load_yaml("AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml")
        self.assertEqual(len(snapshot["skills"]), 109)
        self.assertEqual(len(snapshot["capsules"]), 109)
        self.assertEqual(budgets["profiles"]["FAST"]["max_external_routing_calls"], 0)
        self.assertEqual(budgets["profiles"]["FAST"]["max_source_candidates"], 0)
        self.assertEqual(trading["permissions"], ["read_only"])
        self.assertFalse(trading["research_may_grant_execution"])
```

- [ ] **Step 2: Commit the RED test/quarantine candidate**

Commit message:

```text
test: define Brain 4.7 selective fusion contract
```

- [ ] **Step 3: Run/observe RED**

Run locally when a cloud checkout is available, otherwise open the PR and use the existing `AI Skill Library CI` workflow:

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_brain_4_6_open_source_fusion -v
```

Expected: FAIL because the 4.7 source rows and new contract sections/eval classes do not yet exist. Record the failing assertions before implementation.

### Task 2: Source intake and normalized capability fusion

**Files:**
- Modify: `AI_SKILL_LIBRARY/sources.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/evergreen/quarantine/brain_4_7_selective_fusion.yaml`

**Interfaces:**
- Consumes: source registry policy and harmonization gates.
- Produces: eight vetted source records plus normalized pattern mappings; no new router entry or primary skill.

- [ ] **Step 1: Add approved source rows without exceeding category caps**

Add under an engineering/tooling subsection, using `code` category to avoid overflowing `software`:

```yaml
  - {<<: *rag_only, category: code, repo: modelcontextprotocol/python-sdk, license: MIT, focus: "official MCP client/server contracts, protocol negotiation and typed tool/resource/prompt interoperability"}
  - {<<: *rag_only, category: code, repo: docling-project/docling, license: MIT, focus: "structure-aware document parsing, hierarchy, layout and table extraction patterns"}
  - {<<: *reference_only, category: code, repo: microsoft/graphrag, license: MIT, focus: "bounded entity/relationship extraction and local/global graph-retrieval patterns; no mandatory graph runtime"}
  - {<<: *rag_only, category: code, repo: UKGovernmentBEIS/inspect_ai, license: MIT, focus: "reproducible LLM/agent evaluation task, dataset, solver and scorer separation"}
  - {<<: *rag_only, category: code, repo: ossf/scorecard, license: Apache-2.0, focus: "open-source security-health and maintenance posture signals for candidate intake"}
  - {<<: *rag_only, category: code, repo: aquasecurity/trivy, license: Apache-2.0, focus: "vulnerability, secret, misconfiguration, SBOM and dependency-risk scan semantics"}
  - {<<: *rag_only, category: code, repo: Arize-ai/openinference, license: Apache-2.0, focus: "OpenTelemetry-aligned AI observability semantic conventions with sanitized tracing"}
  - {<<: *rag_only, category: code, repo: microsoft/playwright, license: Apache-2.0, focus: "browser and end-to-end runtime verification patterns across Chromium, Firefox and WebKit"}
```

Do not add `microsoft/agent-framework`, Graphiti, PyRIT, Syft, Storybook, Lighthouse, or a duplicate NautilusTrader row.

- [ ] **Step 2: Add normalized native contracts to capability fusion**

Add top-level sections with bounded semantics:

```yaml
mcp_interoperability:
  external_framework_required: false
  routing_authority: false
  discovery_separate_from_invocation: true
  protocol_compatibility_required: true
  typed_input_output_contracts: true
  permission_ceiling_required: true
  unknown_capability_action: fail_closed
  permission_widening_action: fail_closed
  credentials_are_external_restricted_state: true

document_intelligence:
  external_framework_required: false
  structured_extraction_before_ocr: true
  preserve_hierarchy: true
  preserve_page_section_provenance: true
  preserve_table_structure_when_material: true
  distinguish_extraction_from_inference: true
  ocr_is_degraded_fallback: true

oss_intake_firewall:
  external_scanner_required_for_stable_requests: false
  posture_is_evidence_not_authority: true
  high_score_never_auto_promotes: true
  unresolved_critical_risk_may_block_promotion: true
  signals: [archived_or_disabled, maintenance, spdx_license, dependency_vulnerability, secret_scanning, sbom_or_inventory, release_provenance]

browser_runtime_verification:
  external_framework_required: false
  prefer_runnable_flow_when_environment_exists: true
  checks: [navigation, state_transition, visible_outcome, accessibility_state, network_failure_handling, cross_browser_when_material]
```

Add all eight repositories to `upstream_pattern_map` with verified license, `routing_authority: false`, `mandatory_runtime_dependency: false`, and `code_reuse: false`.

- [ ] **Step 3: Fill quarantine candidate evidence**

Record for each candidate: repository, verified license, provenance, maintenance status, domains, RAG/reference decision, active-registry eligibility, absorbed patterns, `code_reuse: false`, `permission_expansion: false`. Record explicit deferred candidates and dedupe reasons.

- [ ] **Step 4: Run registry/fusion focused validation**

```bash
python AI_SKILL_LIBRARY/validate_registry.py
python AI_SKILL_LIBRARY/validate_registry.py --check-remote
python -m unittest AI_SKILL_LIBRARY.tests.test_brain_4_6_open_source_fusion -v
```

Expected after this task: source/fusion assertions pass; later contract/eval assertions may still fail.

- [ ] **Step 5: Commit**

```text
feat: register vetted selective fusion sources
```

### Task 3: Strengthen existing native skill, retrieval, observability, and eval contracts

**Files:**
- Modify: `AI_SKILL_LIBRARY/skills/catalog.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/retrieval.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/observability.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/stable/harmonization.yaml`
- Modify: `AI_SKILL_LIBRARY/evals.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/engineering/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/data_docs/manifest.yaml`
- Modify: `AI_SKILL_LIBRARY/v4/skills/design_2d/manifest.yaml`

**Interfaces:**
- Consumes: existing skill IDs only.
- Produces: stronger output/eval contracts without adding skill IDs or trigger owners.

- [ ] **Step 1: Strengthen existing catalog rows only**

Update existing output contracts, without changing IDs/triggers:

- `api`: require typed capability/schema compatibility and permission ceiling when MCP/tool protocols are material.
- `automation`: require discovery/invocation separation and fail-closed permission handling for external capabilities.
- `skill_engineering`: add MCP/tool-contract compatibility and OSS intake posture evidence.
- `eval_engineering`: explicitly separate task/case-set/solver/scorer/baseline/candidate/protected-regression boundaries.
- `research`: require source-traceable graph synthesis when graph retrieval is used.
- `verification`: require runnable-flow evidence for browser-facing claims when an executable environment exists.
- `web_app`, `debugging`: prefer browser/E2E reproduction for browser-facing behavior when available.
- `ux_ui`, `product_design`: include executable state/flow verification when implementation is in scope.
- `data_analysis`, `report`, `docx`, `pdf`, `slides`, `spreadsheet`: structured/native extraction before OCR, hierarchy/table/page provenance, and explicit separation of extracted content from inference.

Do not add `mcp_engineering`, `document_intelligence`, `graph_retrieval`, or any other new primary skill.

- [ ] **Step 2: Add optional graph retrieval contract**

In `retrieval.yaml` add:

```yaml
graph_retrieval:
  enabled: optional
  routing_authority: false
  reasoning_authority: false
  profiles: [STANDARD, DEEP]
  fast_enabled: false
  use_when: [entity_relationships_material, corpus_wide_synthesis_material]
  require_source_traceability: true
  authority_filter_before_expansion: true
  freshness_filter_before_expansion: true
  bounded_by_profile_budget: true
  mandatory_graph_database: false
  on_conflict: prefer_authoritative_verified_source
```

Do not change FAST stages or budgets.

- [ ] **Step 3: Add sanitized AI observability semantics**

In `observability.yaml` add:

```yaml
ai_semantics:
  open_telemetry_aligned: true
  optional_fields: [operation_class, role, model_provider_id, duration_ms, status, verification_outcome]
  roles: [model, tool, retriever, evaluator, guardrail]
  sensitive_payloads_forbidden: true
  raw_prompts_forbidden: true
  raw_private_tool_payloads_forbidden: true
  hidden_reasoning_forbidden: true
  diagnostic_not_authority: true
```

Keep existing telemetry forbidden fields and size limits unchanged.

- [ ] **Step 4: Extend harmonization with optional security-posture normalization**

Add `security_posture` to normalization dimensions and a bounded advisory block under candidate intake stating that posture evidence is optional when unavailable, never grants authority, and unresolved critical evidence may block promotion. Do not make external scanners mandatory on Stable request paths.

- [ ] **Step 5: Add eval classes and concrete assertions**

Extend `benchmark_classes` with:

```yaml
  - mcp_contract_integrity
  - document_fidelity
  - graph_retrieval_safety
  - oss_intake_security
  - observability_sanitization
  - browser_runtime_verification
```

Add a `selective_fusion_47_evals` mapping requiring fail-closed schema/permission behavior, structured-document provenance, graph authority/freshness filtering, no auto-promotion from security scores, trace redaction, and runnable-flow verification.

- [ ] **Step 6: Attach eval classes to existing domain manifests**

- engineering: add `mcp_contract_integrity`, `oss_intake_security`, `observability_sanitization`, `browser_runtime_verification`.
- data_docs: add `document_fidelity`.
- design_2d: add `browser_runtime_verification`.
- core/research behavior remains represented through global evals; do not widen core permissions.

- [ ] **Step 7: Run focused tests**

```bash
python -m unittest AI_SKILL_LIBRARY.tests.test_brain_4_6_open_source_fusion -v
python AI_SKILL_LIBRARY/validate_brain.py
python AI_SKILL_LIBRARY/validate_router.py
python AI_SKILL_LIBRARY/validate_authority.py
python AI_SKILL_LIBRARY/validate_v4.py
```

Expected: GREEN with skill count/capsule count still 109.

- [ ] **Step 8: Commit**

```text
feat: strengthen native Brain contracts for selective fusion
```

### Task 4: Regenerate canonical artifacts and build release 4.7.0

**Files:**
- Generated: `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml`
- Generated/validated: `AI_SKILL_LIBRARY/v4/runtime/generated/skill-gateway-snapshot.json` when committed policy requires it
- Generated: `AI_SKILL_LIBRARY/v4/releases/4.7.0/manifest.yaml`
- Generated: `AI_SKILL_LIBRARY/v4/releases/current.json`
- Generated: `AI_SKILL_LIBRARY/v4/releases/history.yaml`

**Interfaces:**
- Consumes: all canonical declarative files from Tasks 1-3.
- Produces: fresh deterministic index/snapshot and immutable release metadata.

- [ ] **Step 1: Resolve current release pointer immediately before build**

```bash
python - <<'PY'
import json
p=json.load(open('AI_SKILL_LIBRARY/v4/releases/current.json'))
assert p['version']=='4.6.0', p
print(p['version'])
PY
```

If `main`/branch has moved to another release, derive the next feature version from that current pointer rather than overwriting an existing release.

- [ ] **Step 2: Rebuild retrieval index**

```bash
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --root .
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --check --root .
```

- [ ] **Step 3: Compile and validate exact-SHA Skill Gateway snapshot**

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
python AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py --source-sha "$SOURCE_SHA" --output AI_SKILL_LIBRARY/v4/runtime/generated/skill-gateway-snapshot.json
python AI_SKILL_LIBRARY/v4/tools/validate_skill_gateway_snapshot.py AI_SKILL_LIBRARY/v4/runtime/generated/skill-gateway-snapshot.json
```

- [ ] **Step 4: Build immutable feature release using the canonical release tool**

```bash
python AI_SKILL_LIBRARY/v4/tools/release.py build --version 4.7.0 --source brain_4_7_selective_open_source_fusion --class feature --validated --root .
```

Do not pass `--known-good` until CI/canary verification has actually passed.

- [ ] **Step 5: Run single validation entrypoint**

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$SOURCE_SHA"
```

Expected: `CI_VALIDATE=PASS failures=0`.

- [ ] **Step 6: Commit generated artifacts**

```text
release: build Brain 4.7 selective fusion candidate
```

### Task 5: PR, CI evidence, merge, and production verification

**Files:**
- No hand-authored production runtime changes expected.
- PR targets `main` from `brain-v4-selective-fusion-20260914`.

**Interfaces:**
- Consumes: candidate branch exact head SHA and release candidate.
- Produces: reviewed/merged canonical source and verified production state, or a fail-closed stop with the previous verified release still authoritative.

- [ ] **Step 1: Open PR with explicit evidence**

PR body must state: eight promoted sources and verified licenses, deferred duplicates, no new primary skill, 109/109 invariant, zero-local preserved, FAST unchanged, Trading/G9 untouched, RED-to-GREEN evidence, validator result, rollback target.

- [ ] **Step 2: Verify GitHub Actions**

Require green `AI Skill Library CI` and any other triggered Brain checks. Inspect job logs on failure; fix causal defects rather than weakening validators.

- [ ] **Step 3: Review diff before merge**

Confirm no unintended changes to Trading authority, live-price policies, wallet/order permissions, secrets, or runtime switches. Confirm only canonical/generated files expected by the plan changed.

- [ ] **Step 4: Merge with expected-head protection**

Merge only if the PR head SHA matches the reviewed/green SHA. Prefer squash unless repository policy requires otherwise.

- [ ] **Step 5: Post-merge production verification**

After main deploy, verify `/runtime/contract` and `/brain/health` expose the intended exact main SHA; require `primarySkillRequired=true`, `capsuleRequired=true`, `externalRoutingCalls=0`, and pass the existing representative route smoke matrix. Railway live-price authority is not modified or redeployed by this work.

- [ ] **Step 6: Mark release known-good only after successful verification**

Use the existing release/evergreen tooling or release workflow to persist known-good metadata after the canary/production checks. If any protected check fails, keep/restore 4.6.0 as rollback target and do not claim completion.
