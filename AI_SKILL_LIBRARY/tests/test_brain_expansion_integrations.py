"""Brain Expansion integration contracts.

Covers the bounded adapter lanes registered in
``AI_SKILL_LIBRARY/v4/integrations/brain_expansion_architecture.yaml``:
Langfuse (observability), Ragas + DeepEval (evaluation), Browser Use
(sandbox execution), BAML (typed contracts), plus the three reference-only
architecture sources.

Every assertion here defends a canonical invariant: task_router stays the
only routing authority, Legion stays the multi-agent execution authority,
Model Mesh stays the model/provider selector, Memory Continuity stays the
memory authority, and no external repository gains reasoning authority.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"

RUNTIME_ADAPTERS = ("langfuse", "ragas", "deepeval", "browser_use", "baml")
REFERENCE_ONLY = ("microsoft_agent_framework", "letta", "agno")


def load_tool(name: str):
    path = TOOLS / f"{name}.py"
    if not path.is_file():
        raise AssertionError(f"missing brain expansion tool: {path.relative_to(ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def adapters_tool():
    return load_tool("brain_expansion_adapters")


def registry() -> dict:
    return adapters_tool().load_adapter_registry(root=ROOT)


# ---------------------------------------------------------------------------
# Task 1 + 2: upstream audit records and the shared adapter contract
# ---------------------------------------------------------------------------


class UpstreamAuditRecords(unittest.TestCase):
    def test_checkpoint_resolves_expansion_adapter_registry_and_tool(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        expected = {
            "brain_expansion_adapter_registry_path": "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_adapters.yaml",
            "brain_expansion_adapter_tool_path": "AI_SKILL_LIBRARY/v4/tools/brain_expansion_adapters.py",
            "brain_expansion_adapter_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_brain_expansion.py",
        }
        for key, rel in expected.items():
            self.assertEqual(checkpoint.get(key), rel, key)
            self.assertTrue((ROOT / rel).is_file(), key)

    def test_every_candidate_carries_verified_audit_provenance(self):
        reg = registry()
        for candidate_id in RUNTIME_ADAPTERS + REFERENCE_ONLY:
            with self.subTest(candidate=candidate_id):
                record = reg["candidates"][candidate_id]
                upstream = record["upstream"]
                self.assertRegex(upstream["repo"], r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
                # Pinned provenance: a 40-char commit SHA, never a floating branch.
                self.assertRegex(str(upstream["ref"]), r"^[0-9a-f]{40}$")
                self.assertTrue(str(upstream["tag"]).strip())
                self.assertTrue(str(upstream["default_branch"]).strip())
                self.assertIn(upstream["archived"], (True, False))
                self.assertFalse(upstream["archived"], "archived upstream must not be activated")
                self.assertTrue(str(upstream["license"]).strip())
                self.assertIn(upstream["license_status"], ("verified", "ambiguous"))
                self.assertTrue(str(upstream["audited_at"]).strip())
                for field in ("supply_chain_risk", "network_behavior", "overlap", "permission_ceiling", "rollback"):
                    self.assertTrue(str(record["audit"][field]).strip(), field)

    def test_ambiguous_license_blocks_executable_dependency(self):
        reg = registry()
        tool = adapters_tool()
        for candidate_id, record in reg["candidates"].items():
            with self.subTest(candidate=candidate_id):
                if record["upstream"]["license_status"] != "verified":
                    self.assertFalse(
                        record["executable_dependency_added"],
                        f"{candidate_id}: ambiguous license must not carry an executable dependency",
                    )
                    self.assertTrue(record["blockers"], f"{candidate_id}: ambiguous license must record a blocker")
        # Langfuse is the known mixed-license monorepo (MIT Expat + commercial ee/).
        langfuse = reg["candidates"]["langfuse"]
        self.assertEqual(langfuse["upstream"]["license_status"], "ambiguous")
        self.assertFalse(tool.may_add_executable_dependency(langfuse))

    def test_langfuse_license_reaudit_keeps_the_gate_closed(self):
        """The re-audit is recorded as evidence and does not relax anything."""
        reg = registry()
        tool = adapters_tool()
        langfuse = reg["candidates"]["langfuse"]
        self.assertEqual(langfuse["upstream"]["license_status"], "ambiguous")
        self.assertFalse(langfuse["enabled"])
        self.assertFalse(langfuse["executable_dependency_added"])
        self.assertFalse(tool.may_add_executable_dependency(langfuse))
        reaudit = langfuse["audit"]["license_reaudit"]
        for marker in ("ee/LICENSE", "pinned tag", "gate stays closed"):
            self.assertIn(marker, reaudit)

    def test_recorded_activation_path_is_documentation_not_activation(self):
        """A cleanly-licensed alternative upstream must not become an activation."""
        reg = registry()
        path = reg["candidates"]["langfuse"]["activation_path"]
        self.assertFalse(path["executable_dependency_added"])
        self.assertFalse(path["enabled"])
        self.assertRegex(str(path["ref"]), r"^[0-9a-f]{40}$")
        self.assertTrue(path["still_required_before_use"])
        # It is not a candidate, so it cannot be promoted through the registry.
        self.assertNotIn(path["candidate_upstream"], reg["candidates"])
        # And it does not change how the Langfuse candidate itself is classified.
        self.assertEqual(adapters_tool().activation_state(reg["candidates"]["langfuse"]), "sandbox_ready")

    def test_no_candidate_added_an_executable_dependency_in_this_change(self):
        reg = registry()
        for candidate_id, record in reg["candidates"].items():
            with self.subTest(candidate=candidate_id):
                self.assertFalse(record["executable_dependency_added"], candidate_id)
                self.assertFalse(record["network_execution_enabled"], candidate_id)
        requirements = (ROOT / "AI_SKILL_LIBRARY/requirements.txt").read_text(encoding="utf-8").lower()
        for banned in ("langfuse", "ragas", "deepeval", "browser-use", "browser_use", "baml", "letta", "agno"):
            self.assertNotIn(banned, requirements, f"{banned} must not enter validator requirements")


class SharedAdapterContract(unittest.TestCase):
    def test_every_runtime_adapter_exposes_the_normalized_contract(self):
        tool = adapters_tool()
        reg = registry()
        for adapter_id in RUNTIME_ADAPTERS:
            with self.subTest(adapter=adapter_id):
                contract = tool.adapter_contract(adapter_id, registry=reg)
                self.assertFalse(contract["enabled"], "runtime default must be disabled")
                self.assertTrue(str(contract["mode"]).strip())
                self.assertFalse(contract["authority"])
                self.assertFalse(contract["routing_authority"])
                self.assertFalse(contract["reasoning_authority"])
                self.assertFalse(contract["memory_authority"])
                self.assertFalse(contract["model_selection_authority"])
                self.assertFalse(contract["stable_mutation"])
                self.assertTrue(contract["independently_disableable"])
                self.assertIn(contract["health"], ("unknown", "healthy", "degraded", "unavailable"))
                self.assertIn(contract["failure"], ("none", "configuration", "upstream", "runtime"))
                self.assertTrue(str(contract["feature_flag"]).strip())
                self.assertTrue(str(contract["rollback"]).strip())
                self.assertRegex(str(contract["upstream"]["ref"]), r"^[0-9a-f]{40}$")

    def test_candidate_cannot_claim_routing_reasoning_or_memory_authority(self):
        tool = adapters_tool()
        for claim in ("routing_authority", "reasoning_authority", "memory_authority", "model_selection_authority"):
            with self.subTest(claim=claim):
                hostile = {
                    "mode": "sandbox",
                    "enabled": True,
                    claim: True,
                    "upstream": {"ref": "0" * 40},
                }
                errors = tool.validate_candidate_record("hostile", hostile)
                self.assertTrue(any(claim in err for err in errors), errors)
                # The normalized contract must neutralise the claim, never echo it.
                contract = tool.normalize_contract("hostile", hostile)
                self.assertFalse(contract[claim])

    def test_reference_only_candidate_cannot_become_executable(self):
        tool = adapters_tool()
        reg = registry()
        for candidate_id in REFERENCE_ONLY:
            with self.subTest(candidate=candidate_id):
                record = reg["candidates"][candidate_id]
                self.assertEqual(record["stage"], "reference_only")
                self.assertEqual(tool.activation_state(record), "reference_only")
                self.assertFalse(record["executable_dependency_added"])
                hostile = dict(record, executable_dependency_added=True)
                errors = tool.validate_candidate_record(candidate_id, hostile)
                self.assertTrue(
                    any("reference_only" in err for err in errors),
                    f"{candidate_id}: reference-only must not be promotable to executable: {errors}",
                )

    def test_unaudited_runtime_dependency_cannot_auto_activate(self):
        tool = adapters_tool()
        unaudited = {
            "stage": "sandbox_adapter",
            "mode": "sandbox",
            "enabled": True,
            "executable_dependency_added": True,
            "upstream": {"repo": "acme/thing", "ref": "main", "license_status": "ambiguous"},
        }
        errors = tool.validate_candidate_record("unaudited", unaudited)
        self.assertTrue(errors)
        self.assertFalse(tool.normalize_contract("unaudited", unaudited)["enabled"])

    def test_activation_states_are_distinct_and_never_overclaim_live(self):
        tool = adapters_tool()
        reg = registry()
        allowed = {"architecture_registered", "reference_only", "audited", "sandbox_ready", "enabled", "production_verified"}
        for candidate_id, record in reg["candidates"].items():
            with self.subTest(candidate=candidate_id):
                state = tool.activation_state(record)
                self.assertIn(state, allowed)
                # Nothing may claim runtime activation without runtime evidence.
                if state in ("enabled", "production_verified"):
                    self.assertTrue(record.get("runtime_evidence"), candidate_id)

    def test_stable_brain_operates_with_every_adapter_off(self):
        tool = adapters_tool()
        reg = registry()
        result = tool.stable_path_smoke(registry=reg, disabled=list(RUNTIME_ADAPTERS))
        self.assertTrue(result["stable_path_ok"])
        self.assertEqual(result["router_authority"], "task_router")
        self.assertEqual(result["execution_authority"], "legion")
        self.assertEqual(result["model_authority"], "model_mesh")
        self.assertEqual(result["memory_authority"], "memory_continuity")
        self.assertEqual(result["required_adapters"], [])

    def test_each_adapter_disables_independently(self):
        tool = adapters_tool()
        reg = registry()
        for adapter_id in RUNTIME_ADAPTERS:
            with self.subTest(adapter=adapter_id):
                result = tool.stable_path_smoke(registry=reg, disabled=[adapter_id])
                self.assertTrue(result["stable_path_ok"])
                self.assertNotIn(adapter_id, result["required_adapters"])


# ---------------------------------------------------------------------------
# Task 3: Langfuse sanitized observability
# ---------------------------------------------------------------------------


class LangfuseObservability(unittest.TestCase):
    FORBIDDEN = {
        "raw_prompt": "you are a helpful assistant ...",
        "prompt": "secret system prompt",
        "raw_private_chat": "user said something private",
        "raw_private_tool_payload": {"body": "private"},
        "private_tool_payload": {"body": "private"},
        "hidden_chain_of_thought": "step 1 ...",
        "chain_of_thought": "step 1 ...",
        "secrets": "s3cr3t",
        "credentials": "user:pass",
        "authentication_tokens": "Bearer abc123",
        "private_keys": "-----BEGIN PRIVATE KEY-----",
        "account_data": {"balance": 1234.5},
    }

    def test_forbidden_payloads_are_dropped_before_export(self):
        tool = adapters_tool()
        event = {
            "event_type": "route_outcome",
            "route": "engineering",
            "profile": "STANDARD",
            "latency_ms": 42,
            "verification": "passed",
            "failure_category": "none",
            **self.FORBIDDEN,
        }
        result = tool.langfuse_export(event, enabled=True, exporter=lambda payload: None)
        emitted = result["emitted"]
        self.assertIsNotNone(emitted)
        for field in self.FORBIDDEN:
            self.assertNotIn(field, emitted, f"{field} must never reach Langfuse")
            self.assertIn(field, result["dropped_fields"])
        self.assertEqual(emitted["route"], "engineering")
        self.assertEqual(emitted["latency_ms"], 42)
        self.assertFalse(emitted["authority"])
        self.assertTrue(emitted["diagnostic_only"])

    def test_forbidden_values_are_dropped_even_under_aliased_keys(self):
        tool = adapters_tool()
        event = {"event_type": "tool_outcome", "notes": "Bearer sk-live-abcdef0123456789", "route": "trading"}
        result = tool.langfuse_export(event, enabled=True, exporter=lambda payload: None)
        self.assertNotIn("notes", result["emitted"], "unknown fields must not be forwarded")
        self.assertIn("notes", result["dropped_fields"])

    def test_credential_shaped_values_are_dropped_from_otherwise_allowed_fields(self):
        tool = adapters_tool()
        for leaked in (
            "Bearer abc123def456",
            "s" + "k-live-abcdef0123456789",
            "-----BEGIN RSA PRIVATE KEY-----",
            "eyJhbGciOiJIUzI1NiJ9.payload",
        ):
            with self.subTest(value=leaked):
                result = tool.langfuse_export(
                    {"event_type": "tool_outcome", "status": leaked}, enabled=True, exporter=lambda payload: None
                )
                self.assertNotIn("status", result["emitted"], "credential-shaped value must not be exported")
                self.assertIn("status", result["dropped_fields"])
                self.assertNotIn(leaked, json.dumps(result["emitted"]))

    def test_disabled_adapter_emits_nothing(self):
        tool = adapters_tool()
        sent: list = []
        result = tool.langfuse_export({"event_type": "route_outcome", "route": "x"}, enabled=False, exporter=sent.append)
        self.assertEqual(sent, [])
        self.assertFalse(result["exported"])
        self.assertIsNone(result["emitted"])
        self.assertTrue(result["stable_path_ok"])

    def test_exporter_failure_does_not_break_the_stable_request_path(self):
        tool = adapters_tool()

        def boom(_payload):
            raise RuntimeError("langfuse unreachable")

        result = tool.langfuse_export({"event_type": "route_outcome", "route": "x"}, enabled=True, exporter=boom)
        self.assertFalse(result["exported"])
        self.assertTrue(result["stable_path_ok"], "telemetry failure must never fail the stable path")
        self.assertEqual(result["failure"], "upstream")
        self.assertEqual(result["health"], "unavailable")
        self.assertEqual(result["failure_category"], "none")

    def test_export_is_open_telemetry_aligned_and_bounded(self):
        tool = adapters_tool()
        observability = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/stable/observability.yaml").read_text(encoding="utf-8"))
        allowed = set(observability["universal_fabric"]["allowed_fields"])
        event = {key: "v" for key in allowed}
        event["event_type"] = "route_outcome"
        event["latency_ms"] = 5
        result = tool.langfuse_export(event, enabled=True, exporter=lambda payload: None)
        self.assertTrue(set(result["emitted"]).issubset(allowed | tool.LANGFUSE_ENVELOPE_FIELDS))
        huge = {"event_type": "route_outcome", "route": "r" * 10_000}
        capped = tool.langfuse_export(huge, enabled=True, exporter=lambda payload: None)
        self.assertLessEqual(len(capped["emitted"]["route"]), observability["limits"]["max_event_chars"])

    def test_langfuse_trace_is_never_authority(self):
        tool = adapters_tool()
        result = tool.langfuse_export(
            {"event_type": "route_outcome", "route": "x", "authority": True, "routing_authority": True},
            enabled=True,
            exporter=lambda payload: None,
        )
        self.assertFalse(result["emitted"]["authority"])
        self.assertNotIn("routing_authority", result["emitted"])


# ---------------------------------------------------------------------------
# Task 4: Ragas + DeepEval evaluation adapters
# ---------------------------------------------------------------------------


class EvaluationAdapters(unittest.TestCase):
    def test_production_request_path_never_depends_on_eval_adapters(self):
        tool = adapters_tool()
        reg = registry()
        for adapter_id in ("ragas", "deepeval"):
            with self.subTest(adapter=adapter_id):
                record = reg["candidates"][adapter_id]
                self.assertEqual(record["mode"], "offline_or_ci_eval_adapter")
                self.assertFalse(record["production_dependency"])
                for profile in ("FAST", "STANDARD", "DEEP"):
                    self.assertFalse(tool.production_path_requires(adapter_id, profile=profile, registry=reg))

    def test_normalized_metrics_map_to_the_existing_failure_taxonomy(self):
        tool = adapters_tool()
        evals = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/evals.yaml").read_text(encoding="utf-8"))
        taxonomy = set(evals["failure_taxonomy"])
        classes = set(evals["benchmark_classes"])

        ragas = tool.normalize_eval_result(
            "ragas",
            {"context_precision": 0.42, "context_recall": 0.51, "faithfulness": 0.88},
        )
        self.assertTrue(ragas["failure_categories"])
        self.assertTrue(set(ragas["failure_categories"]).issubset(taxonomy), ragas["failure_categories"])
        self.assertTrue(set(ragas["benchmark_classes"]).issubset(classes), ragas["benchmark_classes"])

        deepeval = tool.normalize_eval_result(
            "deepeval",
            {"hallucination": 0.31, "task_success": 0.40, "instruction_adherence": 0.55},
        )
        self.assertTrue(set(deepeval["failure_categories"]).issubset(taxonomy), deepeval["failure_categories"])
        self.assertTrue(set(deepeval["benchmark_classes"]).issubset(classes), deepeval["benchmark_classes"])

    def test_external_score_is_advisory_and_cannot_auto_promote(self):
        tool = adapters_tool()
        perfect = tool.normalize_eval_result("ragas", {"context_precision": 1.0, "context_recall": 1.0, "faithfulness": 1.0})
        self.assertTrue(perfect["advisory"])
        self.assertFalse(perfect["promotion_authority"])
        decision = tool.promotion_decision(external_results=[perfect], native_eval_passed=False)
        self.assertFalse(decision["promote"])
        self.assertEqual(decision["authority"], "repository_native_deterministic_evals")
        self.assertIn("native_eval_not_passed", decision["reasons"])
        # Even with native evals green, an external score alone adds no authority.
        allowed = tool.promotion_decision(external_results=[perfect], native_eval_passed=True)
        self.assertTrue(allowed["promote"])
        self.assertEqual(allowed["authority"], "repository_native_deterministic_evals")
        self.assertFalse(allowed["external_scores_counted"])

    def test_majority_vote_across_external_evaluators_is_not_truth(self):
        tool = adapters_tool()
        votes = [
            tool.normalize_eval_result("deepeval", {"task_success": 1.0}),
            tool.normalize_eval_result("deepeval", {"task_success": 1.0}),
            tool.normalize_eval_result("ragas", {"faithfulness": 1.0}),
        ]
        decision = tool.promotion_decision(external_results=votes, native_eval_passed=False)
        self.assertFalse(decision["promote"])

    def test_eval_adapter_failure_is_reported_not_silently_passed(self):
        tool = adapters_tool()
        result = tool.normalize_eval_result("ragas", {})
        self.assertEqual(result["status"], "no_evidence")
        self.assertFalse(result["passed"])


# ---------------------------------------------------------------------------
# Task 5: Browser Use sandbox execution
# ---------------------------------------------------------------------------


def ok_runner(_task):
    return {"ok": True, "url": "https://example.invalid/docs", "http_status": 200, "observed": "documentation page"}


class BrowserUseSandbox(unittest.TestCase):
    READ_ONLY = {"objective_id": "read_docs", "risk_class": "read_only", "domain": "example.invalid", "actions": ["navigate", "read"]}

    def _permissions(self, **overrides):
        base = {
            "routed_by": "task_router",
            "allowed_domains": ["example.invalid"],
            "explicit_user_request": False,
            "project_policy_allows_write": False,
            "explicit_approval": False,
            "financial_authorization": False,
        }
        base.update(overrides)
        return base

    def test_adapter_never_selects_its_own_objective(self):
        tool = adapters_tool()
        unrouted = dict(self.READ_ONLY)
        result = tool.execute_browser_task(unrouted, permissions=self._permissions(routed_by=None), runner=ok_runner)
        self.assertFalse(result["success"])
        self.assertEqual(result["denied_reason"], "task_not_routed_by_task_router")

    def test_read_only_is_the_default_and_is_allowed_when_routed(self):
        tool = adapters_tool()
        result = tool.execute_browser_task(self.READ_ONLY, permissions=self._permissions(), runner=ok_runner)
        self.assertTrue(result["success"])
        self.assertEqual(result["risk_class"], "read_only")
        self.assertTrue(result["runtime_verified"])

    def test_write_without_explicit_allowance_is_denied(self):
        tool = adapters_tool()
        task = dict(self.READ_ONLY, risk_class="reversible_write", actions=["navigate", "submit_form"])
        result = tool.execute_browser_task(task, permissions=self._permissions(), runner=ok_runner)
        self.assertFalse(result["success"])
        self.assertEqual(result["denied_reason"], "reversible_write_requires_explicit_user_request_and_project_policy")

    def test_reversible_write_allowed_only_with_request_and_project_policy(self):
        tool = adapters_tool()
        task = dict(self.READ_ONLY, risk_class="reversible_write", actions=["navigate", "submit_form"])
        perms = self._permissions(explicit_user_request=True, project_policy_allows_write=True)
        result = tool.execute_browser_task(task, permissions=perms, runner=ok_runner)
        self.assertTrue(result["success"])

    def test_destructive_action_without_approval_is_denied(self):
        tool = adapters_tool()
        task = dict(self.READ_ONLY, risk_class="destructive", actions=["delete_account"])
        perms = self._permissions(explicit_user_request=True, project_policy_allows_write=True)
        result = tool.execute_browser_task(task, permissions=perms, runner=ok_runner)
        self.assertFalse(result["success"])
        self.assertEqual(result["denied_reason"], "destructive_requires_explicit_approval")

    def test_financial_execution_through_generic_browser_adapter_is_always_forbidden(self):
        tool = adapters_tool()
        perms = self._permissions(
            explicit_user_request=True,
            project_policy_allows_write=True,
            explicit_approval=True,
            financial_authorization=True,
        )
        for actions in (["place_order"], ["withdraw_funds"], ["sign_transaction"], ["transfer"], ["swap"], ["bridge"]):
            with self.subTest(actions=actions):
                task = dict(self.READ_ONLY, risk_class="financial", actions=actions)
                result = tool.execute_browser_task(task, permissions=perms, runner=ok_runner)
                self.assertFalse(result["success"])
                self.assertEqual(result["denied_reason"], "financial_execution_forbidden_via_generic_browser_adapter")

    def test_financial_intent_is_detected_even_when_mislabelled_read_only(self):
        tool = adapters_tool()
        task = dict(self.READ_ONLY, risk_class="read_only", actions=["navigate", "place_order"])
        result = tool.execute_browser_task(task, permissions=self._permissions(), runner=ok_runner)
        self.assertFalse(result["success"])
        self.assertEqual(result["denied_reason"], "financial_execution_forbidden_via_generic_browser_adapter")

    def test_credential_persistence_attempt_is_denied_and_never_logged(self):
        tool = adapters_tool()
        task = dict(
            self.READ_ONLY,
            risk_class="credential_sensitive",
            actions=["navigate", "store_cookie"],
            credentials={"password": "hunter2", "token": "Bearer abc"},
            persist_credentials=True,
        )
        result = tool.execute_browser_task(task, permissions=self._permissions(), runner=ok_runner)
        self.assertFalse(result["success"])
        self.assertEqual(result["denied_reason"], "credential_persistence_forbidden")
        blob = json.dumps(result)
        self.assertNotIn("hunter2", blob)
        self.assertNotIn("Bearer abc", blob)

    def test_out_of_scope_domain_is_denied(self):
        tool = adapters_tool()
        task = dict(self.READ_ONLY, domain="evil.invalid")
        result = tool.execute_browser_task(task, permissions=self._permissions(), runner=ok_runner)
        self.assertFalse(result["success"])
        self.assertEqual(result["denied_reason"], "domain_out_of_scope")

    def test_success_is_not_claimed_without_runtime_verification(self):
        tool = adapters_tool()

        def plan_only_runner(_task):
            return {"ok": True, "plan": "I would navigate and read the page"}

        result = tool.execute_browser_task(self.READ_ONLY, permissions=self._permissions(), runner=plan_only_runner)
        self.assertFalse(result["success"], "a plausible plan is not a runtime result")
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(result["failure_category"], "browser_runtime_verification_regression")

    def test_runner_failure_is_reported_truthfully(self):
        tool = adapters_tool()

        def failing_runner(_task):
            raise RuntimeError("browser crashed")

        result = tool.execute_browser_task(self.READ_ONLY, permissions=self._permissions(), runner=failing_runner)
        self.assertFalse(result["success"])
        self.assertEqual(result["failure"], "runtime")
        self.assertFalse(result["runtime_verified"])

    def test_disabled_browser_adapter_executes_nothing(self):
        tool = adapters_tool()
        calls: list = []

        def counting_runner(task):
            calls.append(task)
            return ok_runner(task)

        result = tool.execute_browser_task(
            self.READ_ONLY, permissions=self._permissions(), runner=counting_runner, enabled=False
        )
        self.assertEqual(calls, [])
        self.assertFalse(result["success"])
        self.assertEqual(result["denied_reason"], "adapter_disabled")


# ---------------------------------------------------------------------------
# Task 6: BAML optional typed contracts
# ---------------------------------------------------------------------------


SCHEMA = {
    "type": "object",
    "required": ["symbol", "confidence"],
    "properties": {
        "symbol": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


class BamlTypedContracts(unittest.TestCase):
    def test_disabling_baml_preserves_business_semantics(self):
        tool = adapters_tool()
        for payload in (
            {"symbol": "BTCUSDT", "confidence": 0.8},
            {"symbol": "BTCUSDT"},
            {"symbol": 5, "confidence": 0.8},
            {"symbol": "BTCUSDT", "confidence": 3},
        ):
            with self.subTest(payload=payload):
                off = tool.validate_typed_output(payload, SCHEMA, baml_enabled=False)
                on = tool.validate_typed_output(payload, SCHEMA, baml_enabled=True)
                self.assertEqual(off["valid"], on["valid"])
                self.assertEqual(off["value"], on["value"])
                self.assertEqual(off["errors"], on["errors"])

    def test_canonical_json_schema_remains_the_validation_authority(self):
        tool = adapters_tool()
        result = tool.validate_typed_output({"symbol": "BTCUSDT", "confidence": 0.8}, SCHEMA, baml_enabled=True)
        self.assertTrue(result["valid"])
        self.assertEqual(result["authority"], "canonical_json_schema")
        self.assertFalse(result["baml_authority"])

    def test_baml_cannot_override_a_schema_rejection(self):
        tool = adapters_tool()
        result = tool.validate_typed_output(
            {"symbol": "BTCUSDT", "confidence": 42},
            SCHEMA,
            baml_enabled=True,
            baml_verdict={"valid": True, "value": {"symbol": "BTCUSDT", "confidence": 42}},
        )
        self.assertFalse(result["valid"], "BAML must not be able to bless an invalid payload")
        self.assertEqual(result["authority"], "canonical_json_schema")

    def test_baml_is_optional_and_absent_upstream_is_safe(self):
        tool = adapters_tool()
        result = tool.validate_typed_output(
            {"symbol": "BTCUSDT", "confidence": 0.8}, SCHEMA, baml_enabled=True, baml_available=False
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["baml_state"], "unavailable")
        self.assertTrue(result["stable_path_ok"])

    def test_no_provider_lock_in(self):
        reg = registry()
        self.assertFalse(reg["candidates"]["baml"]["provider_lock_in"])


# ---------------------------------------------------------------------------
# Task 7: reference-only architecture sources
# ---------------------------------------------------------------------------


class ReferenceOnlySources(unittest.TestCase):
    def test_reference_sources_hold_no_control_plane_authority(self):
        reg = registry()
        tool = adapters_tool()
        for candidate_id in REFERENCE_ONLY:
            with self.subTest(candidate=candidate_id):
                contract = tool.normalize_contract(candidate_id, reg["candidates"][candidate_id])
                for claim in (
                    "routing_authority",
                    "reasoning_authority",
                    "memory_authority",
                    "model_selection_authority",
                    "execution_authority",
                ):
                    self.assertFalse(contract[claim], f"{candidate_id}.{claim}")
                self.assertFalse(contract["enabled"])

    def test_letta_cannot_write_back_to_memory_continuity(self):
        tool = adapters_tool()
        reg = registry()
        letta = reg["candidates"]["letta"]
        self.assertFalse(letta["memory_writeback_allowed"])
        self.assertFalse(tool.may_write_memory("letta", registry=reg))
        self.assertFalse(tool.may_write_memory("agno", registry=reg))

    def test_reference_frameworks_do_not_replace_canonical_subsystems(self):
        reg = registry()
        for candidate_id, replaced in (
            ("microsoft_agent_framework", ("task_router", "legion", "model_mesh")),
            ("letta", ("memory_continuity",)),
            ("agno", ("task_router", "legion")),
        ):
            with self.subTest(candidate=candidate_id):
                record = reg["candidates"][candidate_id]
                for subsystem in replaced:
                    self.assertNotIn(subsystem, record.get("replaces", []) or [])
                self.assertEqual(record.get("replaces", []) or [], [])

    def test_reference_focus_and_provenance_are_recorded(self):
        reg = registry()
        for candidate_id in REFERENCE_ONLY:
            with self.subTest(candidate=candidate_id):
                record = reg["candidates"][candidate_id]
                self.assertTrue(str(record["focus"]).strip())
                self.assertEqual(record["upstream"]["license_status"], "verified")


# ---------------------------------------------------------------------------
# Cross-cutting: architecture invariants and release packaging
# ---------------------------------------------------------------------------


class ArchitectureInvariants(unittest.TestCase):
    def test_registry_matches_the_registered_architecture_candidates(self):
        arch = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_architecture.yaml").read_text(encoding="utf-8")
        )
        reg = registry()
        self.assertEqual(set(arch["candidates"]), set(reg["candidates"]))
        for candidate_id, arch_record in arch["candidates"].items():
            with self.subTest(candidate=candidate_id):
                self.assertEqual(reg["candidates"][candidate_id]["upstream"]["repo"], arch_record["repo"])
                self.assertEqual(
                    reg["candidates"][candidate_id]["upstream"]["default_branch"], arch_record["default_branch"]
                )

    def test_registry_declares_no_authority_at_the_top_level(self):
        reg = registry()
        self.assertFalse(reg["routing_authority"])
        self.assertFalse(reg["reasoning_authority"])
        self.assertFalse(reg["stable_mutation"])
        self.assertEqual(reg["brain_authority"], "GITHUB_BRAIN_V4")

    def test_validator_passes_on_the_committed_registry(self):
        tool = adapters_tool()
        self.assertEqual(tool.validate_registry(registry()), [])

    def test_release_packaging_is_deferred_behind_the_release_gate(self):
        """Packaging the expansion contract is blocked, and the block is recorded.

        Releases are immutable, so these files cannot join 4.13.0 in place, and
        cutting a successor would break the rollback-to-known-good invariant
        because history.yaml records 4.13.0 as known_good=false. The deferral is
        therefore explicit in the registry rather than silently forgotten, and
        this test fails the moment someone packages the files without also
        clearing the recorded blocker.
        """
        release = load_tool("release")
        packaged = {path for path, _role in release.RELEASE_FILES}
        expansion_files = {
            "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_architecture.yaml",
            "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_adapters.yaml",
            "AI_SKILL_LIBRARY/v4/tools/brain_expansion_adapters.py",
            "AI_SKILL_LIBRARY/v4/tools/validate_brain_expansion.py",
        }
        deferral = registry()["release_packaging"]
        if deferral["packaged_in_stable_release"]:
            self.assertTrue(expansion_files.issubset(packaged), sorted(expansion_files - packaged))
        else:
            self.assertEqual(
                expansion_files & packaged,
                set(),
                "registry says packaging is deferred but release.py packages these files",
            )
            self.assertTrue(str(deferral["blocked_by"]).strip())
            self.assertTrue(str(deferral["resolution"]).strip())
            self.assertEqual(deferral["resolved_via"], "checkpoint_pointers")

    def test_deferred_packaging_still_leaves_the_contract_resolvable(self):
        """Every expansion file the release does not carry must be checkpoint-resolved."""
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        pointers = {value for value in checkpoint.values() if isinstance(value, str)}
        for rel in (
            "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_architecture.yaml",
            "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_adapters.yaml",
            "AI_SKILL_LIBRARY/v4/tools/brain_expansion_adapters.py",
            "AI_SKILL_LIBRARY/v4/tools/validate_brain_expansion.py",
        ):
            with self.subTest(path=rel):
                self.assertIn(rel, pointers)
                self.assertTrue((ROOT / rel).is_file())

    def test_no_secret_material_in_the_expansion_surface(self):
        suspicious = ("sk-", "api_key:", "apikey:", "BEGIN PRIVATE KEY", "password:", "secret:")
        for rel in (
            "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_adapters.yaml",
            "AI_SKILL_LIBRARY/v4/tools/brain_expansion_adapters.py",
            "AI_SKILL_LIBRARY/v4/tools/validate_brain_expansion.py",
        ):
            with self.subTest(path=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                for token in suspicious:
                    self.assertNotIn(token, text, f"{rel} must not carry {token!r}")


if __name__ == "__main__":
    unittest.main()
