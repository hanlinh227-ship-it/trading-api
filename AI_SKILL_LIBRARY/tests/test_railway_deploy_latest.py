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


class AuthDiagnosisTests(unittest.TestCase):
    """The first real main run failed here, and the message sent the operator to
    the wrong place.

    `authenticate` caught every Failure alike, so "Railway refused this token"
    and "Railway was never reached" both printed "check RAILWAY_TOKEN". That is
    one label covering two different facts - the same defect this branch has now
    found repeatedly - and the cost is real: it invites rotating a credential
    that was never broken while the actual cause (endpoint, egress, an API that
    is not this API) goes unexamined.

    Each test below DAMAGES one case and demands the diagnosis distinguish it.
    """

    def _authenticate_with(self, responder):
        original = deploy._post
        deploy._post = responder
        try:
            return deploy.authenticate("token-value")
        finally:
            deploy._post = original

    def test_a_401_is_an_auth_rejection_and_the_other_scheme_is_tried(self):
        seen = []

        def responder(query, variables, token, scheme):
            seen.append(scheme)
            if scheme == "bearer":
                raise deploy.Failure("Railway API returned HTTP 401",
                                     auth_rejected=True)
            return {}

        self.assertEqual(self._authenticate_with(responder), "project")
        self.assertEqual(seen, ["bearer", "project"])

    def test_both_schemes_refused_says_refused_and_names_each_reason(self):
        def responder(query, variables, token, scheme):
            raise deploy.Failure("HTTP 403 for %s" % scheme, auth_rejected=True)

        with self.assertRaises(deploy.Failure) as caught:
            self._authenticate_with(responder)
        message = str(caught.exception)
        self.assertIn("refused", message)
        self.assertIn("RAILWAY_TOKEN", message)
        self.assertIn("HTTP 403 for bearer", message)
        self.assertIn("HTTP 403 for project", message)
        self.assertTrue(caught.exception.auth_rejected)

    def test_an_unreachable_api_is_not_reported_as_a_bad_token(self):
        """The case that would have misdirected a real operator."""
        def responder(query, variables, token, scheme):
            raise deploy.Failure("Railway API unreachable: URLError",
                                 auth_rejected=False)

        with self.assertRaises(deploy.Failure) as caught:
            self._authenticate_with(responder)
        message = str(caught.exception)
        self.assertIn("NOT an authentication failure", message)
        self.assertFalse(caught.exception.auth_rejected)

    def test_a_non_auth_failure_stops_immediately_without_trying_the_other(self):
        """A wrong endpoint fails identically under both schemes, so retrying
        only buys a second misleading line."""
        seen = []

        def responder(query, variables, token, scheme):
            seen.append(scheme)
            raise deploy.Failure("Railway API returned HTTP 404",
                                 auth_rejected=False)

        with self.assertRaises(deploy.Failure):
            self._authenticate_with(responder)
        self.assertEqual(seen, ["bearer"])

    def _post_against_http(self, code):
        """Drive the real `_post` into an HTTPError of `code` and return what it
        decided, so the classification is tested rather than restated."""
        import urllib.error
        import urllib.request

        def raiser(request, timeout=None):
            raise urllib.error.HTTPError(
                deploy.ENDPOINT, code, "boom", {}, None)

        original = urllib.request.urlopen
        urllib.request.urlopen = raiser
        try:
            with self.assertRaises(deploy.Failure) as caught:
                deploy._post("query { __typename }", {}, "tok", "bearer")
            return caught.exception
        finally:
            urllib.request.urlopen = original

    def test_http_401_and_403_classify_as_auth_rejections(self):
        for code in (401, 403):
            with self.subTest(code=code):
                self.assertTrue(self._post_against_http(code).auth_rejected)

    def test_other_http_statuses_never_claim_the_token_was_rejected(self):
        """A 404 from a stale endpoint and a 500 from a bad day are both the API
        failing to judge the token, not judging it badly."""
        for code in (400, 404, 429, 500, 502):
            with self.subTest(code=code):
                failure = self._post_against_http(code)
                self.assertFalse(failure.auth_rejected)
                self.assertIn(str(code), str(failure))

    def test_graphql_wording_decides_when_the_status_cannot(self):
        """Railway phrases some refusals in the body with a 200 status, so the
        status alone cannot classify them."""
        self.assertTrue(deploy._AUTH_REJECTION_RE.search("Not Authorized"))
        self.assertTrue(deploy._AUTH_REJECTION_RE.search("unauthenticated"))
        self.assertTrue(deploy._AUTH_REJECTION_RE.search("Invalid token"))
        self.assertIsNone(deploy._AUTH_REJECTION_RE.search(
            "Cannot query field \"nope\" on type \"Mutation\""))

    def test_a_schema_error_is_not_mistaken_for_an_auth_problem(self):
        failure = deploy.Failure("Cannot query field x", auth_rejected=False)
        self.assertFalse(failure.auth_rejected)


class AnonymousControlTests(unittest.TestCase):
    """A refusal cannot say whether it is ABOUT the token.

    The real run refused our token with 403 under both schemes. An endpoint that
    answers EVERYONE with 403 would look exactly the same, and the two call for
    opposite actions: rotate a credential, or stop touching the credential and
    look at the endpoint. The anonymous request is the control that separates
    them, so these tests damage it and require the message still distinguish.
    """

    def _both_refused_message(self, anonymous):
        def responder(query, variables, token, scheme):
            raise deploy.Failure("Railway API returned HTTP 403",
                                 auth_rejected=True)

        original_post, original_anon = deploy._post, deploy._unauthenticated_status
        deploy._post = responder
        deploy._unauthenticated_status = lambda: anonymous
        try:
            with self.assertRaises(deploy.Failure) as caught:
                deploy.authenticate("token-value")
            return str(caught.exception)
        finally:
            deploy._post, deploy._unauthenticated_status = original_post, original_anon

    def test_the_anonymous_result_is_reported_alongside_the_refusals(self):
        message = self._both_refused_message("HTTP 401")
        self.assertIn("HTTP 401", message)
        self.assertIn("UNAUTHENTICATED", message)

    def test_the_message_names_both_readings_so_neither_is_assumed(self):
        message = self._both_refused_message("HTTP 403")
        self.assertIn("read and rejected", message)
        self.assertIn("not the thing", message)

    def test_the_control_never_replaces_the_failure_it_explains(self):
        """If the control probe itself explodes, the refusal must still be
        raised - diagnostics that can mask the fault they describe are worse
        than none."""
        original = deploy.urllib.request.urlopen

        def boom(request, timeout=None):
            raise RuntimeError("control probe exploded")

        deploy.urllib.request.urlopen = boom
        try:
            status = deploy._unauthenticated_status()
        finally:
            deploy.urllib.request.urlopen = original
        self.assertIn("unreachable", status)
        self.assertIn("RuntimeError", status)

    def test_the_control_sends_no_credential(self):
        """It is only a control if it carries nothing; a probe that leaked the
        token would answer a different question and expose it to a wrong host."""
        captured = {}

        def capture(request, timeout=None):
            captured["headers"] = dict(request.headers)
            raise deploy.urllib.error.HTTPError(
                deploy.ENDPOINT, 401, "no", {}, None)

        original = deploy.urllib.request.urlopen
        deploy.urllib.request.urlopen = capture
        try:
            deploy._unauthenticated_status()
        finally:
            deploy.urllib.request.urlopen = original
        lowered = {k.lower() for k in captured["headers"]}
        self.assertNotIn("authorization", lowered)
        self.assertNotIn("project-access-token", lowered)


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
