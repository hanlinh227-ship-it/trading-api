"""Authority regression: one Brain, one router, one of each plane.

This session added a dozen modules and as many tools. Each was written not to
claim authority, but "written not to" is a statement about intent, and intent
does not survive the next change. These assertions are about the repository as
it stands, so a future component that quietly becomes a second router fails
here rather than in production.

Scoped to the local runtime lane and the evidence it produces, because that is
what this lane is responsible for. It does not attempt to police the whole
repository's history.
"""

import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LANE = ROOT / "AI_SKILL_LIBRARY/v4/local_runtime"
TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"
EVIDENCE = ROOT / "CHECKPOINTS/evidence"

CANONICAL_ROUTER = "AI_SKILL_LIBRARY/v4/stable/router.yaml"


def lane_sources():
    return sorted(p for p in LANE.rglob("*.py") if "__pycache__" not in p.parts)


def evidence_docs():
    for path in sorted(EVIDENCE.rglob("*.json")):
        try:
            yield path, json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue


class SingleRouterTests(unittest.TestCase):
    def test_only_the_canonical_router_config_is_read(self):
        """A second router would begin as a second routing config.

        Checked over string *constants* rather than raw text, because prose
        referring to the router is exactly what these modules should contain -
        a first version of this flagged a docstring saying "reading
        stable/router.yaml", which is documentation of the right behaviour.
        """
        import ast

        offenders = []
        for path in lane_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                    doc = ast.get_docstring(node, clean=False)
                    if doc:
                        docstrings.add(doc)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                if node.value in docstrings or "router.yaml" not in node.value:
                    continue
                if node.value != CANONICAL_ROUTER:
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}: {node.value!r}")
        self.assertEqual(offenders, [])

    def test_no_lane_module_declares_itself_a_routing_authority(self):
        offenders = []
        for path in lane_sources():
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "routing_authority" in stripped and "True" in stripped:
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}: {stripped}")
        self.assertEqual(offenders, [])

    def test_every_evidence_document_naming_a_router_names_task_router(self):
        wrong = []
        for path, doc in evidence_docs():
            value = doc.get("routing_authority") if isinstance(doc, dict) else None
            if isinstance(value, str) and value != "task_router":
                wrong.append(f"{path.name}: {value}")
            if isinstance(doc, dict) and doc.get("routed_by") not in (None, "task_router"):
                wrong.append(f"{path.name}: routed_by={doc.get('routed_by')}")
        self.assertEqual(wrong, [])


class SingleAuthorityPerPlaneTests(unittest.TestCase):
    def test_the_registry_holds_no_authority_at_all(self):
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8"))
        self.assertTrue(all(value is False for value in registry["authority"].values()))
        for model in registry["models"]:
            with self.subTest(model_id=model["model_id"]):
                self.assertFalse(model["authority"])

    def test_the_registry_names_the_canonical_brain_and_router(self):
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8"))
        integration = registry["integration"]
        self.assertEqual(integration["brain_authority"], "GITHUB_BRAIN_V4")
        self.assertEqual(integration["routed_by"], "task_router")
        self.assertEqual(integration["model_selection_authority"], "model_mesh")

    def test_model_selection_is_always_attributed_to_the_mesh(self):
        wrong = []
        for path, doc in evidence_docs():
            if not isinstance(doc, dict):
                continue
            value = doc.get("model_selection_authority")
            if value is not None and value != "model_mesh":
                wrong.append(f"{path.name}: {value}")
        self.assertEqual(wrong, [])

    def test_registry_membership_never_implies_activation(self):
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8"))
        self.assertFalse(registry["policy"]["registry_implies_activation"])
        self.assertFalse(registry["policy"]["auto_download"])
        self.assertFalse(registry["integration"]["registry_membership_is_activation"])

    def test_residency_authority_stays_with_the_local_runtime(self):
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8"))
        contract = registry["integration"]["runtime_residency_contract"]
        self.assertEqual(contract["owner"], "claude_local_runtime")
        self.assertFalse(contract["open_model_universe_has_runtime_residency_authority"])


class NoSecondLifecycleTests(unittest.TestCase):
    def test_residency_tiers_target_existing_residency_states(self):
        """A tier vocabulary that named its own states would be a second lifecycle."""
        from AI_SKILL_LIBRARY.v4.local_runtime.residency import ResidencyState
        from AI_SKILL_LIBRARY.v4.local_runtime.residency_policy import TARGET_STATE

        known = {state.value for state in ResidencyState}
        for tier, target in TARGET_STATE.items():
            with self.subTest(tier=tier):
                self.assertIn(target, known)

    def test_governance_states_never_appear_as_runtime_states(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.residency import ResidencyState
        from AI_SKILL_LIBRARY.v4.local_runtime.reconciliation import GOVERNANCE_ONLY_STATES

        runtime_names = {state.value for state in ResidencyState}
        for state in GOVERNANCE_ONLY_STATES:
            with self.subTest(state=state):
                self.assertNotIn(getattr(state, "value", str(state)), runtime_names)


class NoSelfApprovalTests(unittest.TestCase):
    def test_the_gap_observer_can_only_read(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.gap_observer import observe

        capabilities = observe(ROOT)["capabilities"]
        for forbidden in ("writes_code", "edits_registry", "runs_models",
                          "starts_autodev_runs", "approves_anything"):
            with self.subTest(capability=forbidden):
                self.assertFalse(capabilities[forbidden])

    def test_self_development_has_no_merged_state(self):
        """Automation proposes; merging is somebody else's act."""
        from AI_SKILL_LIBRARY.v4.local_runtime.selfdev import AutoDevState

        self.assertNotIn("MERGED", {state.name for state in AutoDevState})

    def test_no_evidence_document_claims_a_vote_decided_anything(self):
        """Truth is evidence-based; a majority is not evidence."""
        for path, doc in evidence_docs():
            if isinstance(doc, dict) and "resolved_by_vote" in doc:
                with self.subTest(evidence=path.name):
                    self.assertFalse(doc["resolved_by_vote"])


class NoPaidFallbackTests(unittest.TestCase):
    def test_the_registry_forbids_paid_fallback(self):
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8"))
        self.assertEqual(registry["policy"]["paid_fallback"], "NO_PAID_FALLBACK")
        self.assertEqual(registry["policy"]["cost_policy"], "OPEN_MODEL_ZERO_TOKEN_FIRST")

    def test_no_admitted_model_requires_a_paid_token(self):
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8"))
        for model in registry["models"]:
            with self.subTest(model_id=model["model_id"]):
                self.assertFalse(model["paid_token_required"])
                self.assertFalse(model["api_required"])

    def test_every_execution_record_ran_offline_or_says_why_not(self):
        for path, doc in evidence_docs():
            if not isinstance(doc, dict):
                continue
            runtime = doc.get("runtime_evidence")
            if isinstance(runtime, dict) and "offline" in runtime:
                with self.subTest(evidence=path.name):
                    self.assertTrue(runtime["offline"])


if __name__ == "__main__":
    unittest.main()
