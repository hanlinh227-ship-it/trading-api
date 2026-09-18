"""The deploy script's judgements, tested without touching Railway.

Railway's docs are not reachable from the environment this was written in, so
the script verifies the API at runtime instead of trusting a remembered
mutation name. That makes its DECISIONS - which mutation to call, whether a
deployment is the one we asked for - the part worth testing here, and they need
no network.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = ROOT / ".github/scripts/railway_deploy_latest.py"

_spec = importlib.util.spec_from_file_location("railway_deploy_latest", _SCRIPT)
deploy = importlib.util.module_from_spec(_spec)
sys.modules["railway_deploy_latest"] = deploy
_spec.loader.exec_module(deploy)

SHA = "e26812c063603ac684aca2fa87f0509fb254af1f"


class MutationChoiceTests(unittest.TestCase):
    def test_a_mutation_without_a_commit_argument_is_not_used(self):
        """Deploying without naming a commit redeploys the snapshot already
        running, which is the exact behaviour this script exists to replace."""
        with self.assertRaises(deploy.Failure):
            deploy.choose_mutation({"serviceInstanceRedeploy":
                                    ["serviceId", "environmentId"]})

    def test_preference_order_is_honoured(self):
        available = {
            "serviceInstanceDeploy": ["serviceId", "environmentId", "commitSha"],
            "serviceInstanceDeployV2": ["serviceId", "environmentId", "commitSha"],
        }
        name, arg = deploy.choose_mutation(available)
        self.assertEqual(name, deploy.DEPLOY_MUTATION_PREFERENCE[0])
        self.assertEqual(arg, "commitSha")

    def test_an_alternate_commit_argument_name_is_accepted(self):
        name, arg = deploy.choose_mutation(
            {"serviceInstanceDeploy": ["serviceId", "environmentId", "commit"]})
        self.assertEqual((name, arg), ("serviceInstanceDeploy", "commit"))

    def test_an_unknown_api_fails_with_what_it_does_offer(self):
        """The failure has to be fixable from its own text."""
        with self.assertRaises(deploy.Failure) as caught:
            deploy.choose_mutation({"somethingDeployish": ["serviceId"]})
        message = str(caught.exception)
        self.assertIn("somethingDeployish", message)
        for name in deploy.DEPLOY_MUTATION_PREFERENCE:
            self.assertIn(name, message)

    def test_no_preference_entry_redeploys_a_snapshot(self):
        self.assertNotIn("serviceInstanceRedeploy", deploy.DEPLOY_MUTATION_PREFERENCE)


class DeployedShaTests(unittest.TestCase):
    def test_a_commit_is_read_from_any_known_meta_key(self):
        for key in ("commitHash", "commitSha", "commit"):
            self.assertEqual(deploy.deployed_sha({"meta": {key: SHA}}), SHA)

    def test_a_mixed_case_commit_is_normalised(self):
        self.assertEqual(deploy.deployed_sha({"meta": {"commitHash": SHA.upper()}}),
                         SHA)

    def test_an_unreadable_commit_is_unknown_never_matching(self):
        """Unknown must not be able to equal the target."""
        for meta in (None, {}, {"commitHash": ""}, {"commitHash": "not-a-sha"},
                     {"commitHash": SHA[:39]}, {"branch": "main"}):
            self.assertEqual(deploy.deployed_sha({"meta": meta}), "")

    def test_a_short_sha_is_not_accepted_as_the_target(self):
        self.assertNotEqual(deploy.deployed_sha({"meta": {"commitHash": SHA[:12]}}),
                            SHA)


class TerminalStatusTests(unittest.TestCase):
    def test_only_success_is_a_pass(self):
        self.assertEqual(deploy.TERMINAL_OK, ("SUCCESS",))
        for bad in ("FAILED", "CRASHED", "REMOVED", "SKIPPED"):
            self.assertIn(bad, deploy.TERMINAL_BAD)

    def test_the_two_terminal_sets_do_not_overlap(self):
        self.assertFalse(set(deploy.TERMINAL_OK) & set(deploy.TERMINAL_BAD))


class RefusalTests(unittest.TestCase):
    def test_a_short_sha_is_refused_before_any_call(self):
        self.assertEqual(deploy.main(["--sha", SHA[:12]]), 1)

    def test_missing_credentials_name_themselves(self, ):
        import io, contextlib, os
        saved = {k: os.environ.pop(k, None) for k in
                 ("RAILWAY_TOKEN", "RAILWAY_SERVICE_ID", "RAILWAY_ENVIRONMENT_ID")}
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = deploy.main(["--sha", SHA])
            self.assertEqual(rc, 1)
            for name in ("RAILWAY_TOKEN", "RAILWAY_SERVICE_ID",
                         "RAILWAY_ENVIRONMENT_ID"):
                self.assertIn(name, err.getvalue())
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


class WorkflowWiringTests(unittest.TestCase):
    """The gates around the deploy, asserted against the workflow itself."""

    @classmethod
    def setUpClass(cls):
        import yaml
        cls.wf = yaml.safe_load(
            (ROOT / ".github/workflows/zero-local-cloud-runtime.yml")
            .read_text(encoding="utf-8"))
        cls.jobs = cls.wf["jobs"]

    def test_the_deploy_waits_for_canonical_validation(self):
        self.assertEqual(self.jobs["deploy-latest"]["needs"], "validate")

    def test_the_deploy_runs_only_on_main_pushes(self):
        condition = self.jobs["deploy-latest"]["if"]
        self.assertIn("refs/heads/main", condition)
        self.assertIn("push", condition)

    def test_the_existing_smoke_gate_still_runs_when_the_deploy_fails(self):
        """Ordering it after the deploy must not make it skippable.

        A deploy failure that silently skipped the tree check would be a weaker
        board wearing a stricter shape.
        """
        smoke = self.jobs["production-smoke"]
        self.assertIn("deploy-latest", smoke["needs"])
        self.assertIn("always()", smoke["if"])
        self.assertIn("needs.validate.result == 'success'", smoke["if"])

    def test_the_deploy_is_serialised(self):
        self.assertEqual(self.jobs["deploy-latest"]["concurrency"]["group"],
                         "railway-deploy-latest-production")
        self.assertIs(
            self.jobs["deploy-latest"]["concurrency"]["cancel-in-progress"], False)

    def test_the_deploy_uses_the_validated_commit_not_current_main(self):
        body = "".join(str(s.get("run") or "") for s in
                       self.jobs["deploy-latest"]["steps"])
        self.assertIn("${GITHUB_SHA}", body)

    def test_health_is_checked_and_the_served_commit_compared(self):
        body = "".join(str(s.get("run") or "") for s in
                       self.jobs["deploy-latest"]["steps"])
        self.assertIn("/health", body)
        self.assertIn("deploymentCommitSha", body)
        self.assertIn("PROD_SHA_MATCH=PASS", body)


if __name__ == "__main__":
    unittest.main()
