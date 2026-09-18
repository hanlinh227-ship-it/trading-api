import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_V4 = os.path.join(_LIB, "v4")
_TOOLS = os.path.join(_V4, "tools")
for p in (_V4, _TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

proof = importlib.import_module("survival_plane_proof")

KEYS = [
    "SURVIVAL_PLANE_READY",
    "DISASTER_RECOVERY_READY",
    "POLICY_ENFORCEMENT",
    "SECRET_REFERENCE_ONLY",
    "ARTIFACT_TRUST",
    "RESTORE_DRILL",
]


class SurvivalPlaneProofTests(unittest.TestCase):
    def test_missing_restore_drill_evidence_stays_fail(self):
        r = proof.evaluate(None)
        self.assertEqual(r["RESTORE_DRILL"], "FAIL")
        self.assertEqual(r["DISASTER_RECOVERY_READY"], "FAIL")

    def test_nonexistent_evidence_stays_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = proof.evaluate(os.path.join(tmp, "nope.json"))
        self.assertEqual(r["RESTORE_DRILL"], "FAIL")
        self.assertEqual(r["DISASTER_RECOVERY_READY"], "FAIL")

    def test_malformed_evidence_stays_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "bad.json")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("not json")
            r = proof.evaluate(p)
        self.assertEqual(r["RESTORE_DRILL"], "FAIL")
        self.assertEqual(r["DISASTER_RECOVERY_READY"], "FAIL")

    def test_incomplete_evidence_stays_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "partial.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"isolated": True}, fh)
            r = proof.evaluate(p)
        self.assertEqual(r["RESTORE_DRILL"], "FAIL")
        self.assertEqual(r["DISASTER_RECOVERY_READY"], "FAIL")

    def test_survival_ready_does_not_imply_dr(self):
        r = proof.evaluate(None)
        self.assertEqual(r["DISASTER_RECOVERY_READY"], "FAIL")
        self.assertEqual(r["RESTORE_DRILL"], "FAIL")

    def test_all_keys_present_and_binary(self):
        r = proof.evaluate(None)
        self.assertEqual(set(r.keys()), set(KEYS))
        for key in KEYS:
            self.assertIn(r[key], ("PASS", "FAIL"))

    def test_policy_fail_closed_when_adapter_missing(self):
        with mock.patch.object(proof, "_load", return_value=None):
            ok, _ = proof._policy_evidence()
        self.assertFalse(ok)

    def test_secret_fail_closed_when_module_missing(self):
        with mock.patch.object(proof, "_load", return_value=None):
            ok, _ = proof._secret_evidence()
        self.assertFalse(ok)

    def test_artifact_fail_closed_when_module_missing(self):
        with mock.patch.object(proof, "_load", return_value=None):
            ok, _ = proof._artifact_evidence()
        self.assertFalse(ok)

    def test_restore_drill_requires_explicit_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "dr.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "isolated": True,
                        "faithful": True,
                        "restore_verified": True,
                        "source": "restore_drill",
                    },
                    fh,
                )
            ok, _ = proof._restore_drill_evidence(p)
            self.assertTrue(ok)
            r = proof.evaluate(p)
        self.assertEqual(r["RESTORE_DRILL"], "PASS")
        self.assertEqual(r["DISASTER_RECOVERY_READY"], "PASS")

    def test_restore_drill_rejects_non_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "dr.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "isolated": False,
                        "faithful": True,
                        "restore_verified": True,
                        "source": "restore_drill",
                    },
                    fh,
                )
            ok, _ = proof._restore_drill_evidence(p)
        self.assertFalse(ok)

    def test_main_prints_contract(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = proof.main([])
        out = stdout.getvalue().strip().splitlines()
        self.assertEqual(rc, 0)
        self.assertEqual(
            out,
            [
                "SURVIVAL_PLANE_READY="
                + proof.evaluate(None)["SURVIVAL_PLANE_READY"],
                "DISASTER_RECOVERY_READY=FAIL",
                "POLICY_ENFORCEMENT=" + proof.evaluate(None)["POLICY_ENFORCEMENT"],
                "SECRET_REFERENCE_ONLY="
                + proof.evaluate(None)["SECRET_REFERENCE_ONLY"],
                "ARTIFACT_TRUST=" + proof.evaluate(None)["ARTIFACT_TRUST"],
                "RESTORE_DRILL=FAIL",
            ],
        )


if __name__ == "__main__":
    unittest.main()
