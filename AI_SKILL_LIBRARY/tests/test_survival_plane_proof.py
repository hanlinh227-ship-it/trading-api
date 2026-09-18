import importlib
import json
import os
import sys


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


def test_missing_restore_drill_evidence_stays_fail():
    r = proof.evaluate(None)
    assert r["RESTORE_DRILL"] == "FAIL"
    assert r["DISASTER_RECOVERY_READY"] == "FAIL"


def test_nonexistent_evidence_stays_fail(tmp_path):
    r = proof.evaluate(str(tmp_path / "nope.json"))
    assert r["RESTORE_DRILL"] == "FAIL"
    assert r["DISASTER_RECOVERY_READY"] == "FAIL"


def test_malformed_evidence_stays_fail(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    r = proof.evaluate(str(p))
    assert r["RESTORE_DRILL"] == "FAIL"
    assert r["DISASTER_RECOVERY_READY"] == "FAIL"


def test_incomplete_evidence_stays_fail(tmp_path):
    p = tmp_path / "partial.json"
    p.write_text(json.dumps({"isolated": True}), encoding="utf-8")
    r = proof.evaluate(str(p))
    assert r["RESTORE_DRILL"] == "FAIL"
    assert r["DISASTER_RECOVERY_READY"] == "FAIL"


def test_survival_ready_does_not_imply_dr():
    r = proof.evaluate(None)
    assert r["DISASTER_RECOVERY_READY"] == "FAIL"
    assert r["RESTORE_DRILL"] == "FAIL"


def test_all_keys_present_and_binary():
    r = proof.evaluate(None)
    assert set(r.keys()) == set(KEYS)
    for k in KEYS:
        assert r[k] in ("PASS", "FAIL")


def test_policy_fail_closed_when_adapter_missing(monkeypatch):
    monkeypatch.setattr(proof, "_load", lambda name: None)
    ok, _ = proof._policy_evidence()
    assert ok is False


def test_secret_fail_closed_when_module_missing(monkeypatch):
    monkeypatch.setattr(proof, "_load", lambda name: None)
    ok, _ = proof._secret_evidence()
    assert ok is False


def test_artifact_fail_closed_when_module_missing(monkeypatch):
    monkeypatch.setattr(proof, "_load", lambda name: None)
    ok, _ = proof._artifact_evidence()
    assert ok is False


def test_restore_drill_requires_explicit_evidence(tmp_path):
    p = tmp_path / "dr.json"
    p.write_text(
        json.dumps(
            {
                "isolated": True,
                "faithful": True,
                "restore_verified": True,
                "source": "restore_drill",
            }
        ),
        encoding="utf-8",
    )
    ok, _ = proof._restore_drill_evidence(str(p))
    assert ok is True
    r = proof.evaluate(str(p))
    assert r["RESTORE_DRILL"] == "PASS"
    assert r["DISASTER_RECOVERY_READY"] == "PASS"


def test_restore_drill_rejects_non_isolated(tmp_path):
    p = tmp_path / "dr.json"
    p.write_text(
        json.dumps(
            {
                "isolated": False,
                "faithful": True,
                "restore_verified": True,
                "source": "restore_drill",
            }
        ),
        encoding="utf-8",
    )
    ok, _ = proof._restore_drill_evidence(str(p))
    assert ok is False


def test_main_prints_contract(capsys):
    rc = proof.main([])
    out = capsys.readouterr().out.strip().splitlines()
    assert rc == 0
    assert out == [
        "SURVIVAL_PLANE_READY=" + proof.evaluate(None)["SURVIVAL_PLANE_READY"],
        "DISASTER_RECOVERY_READY=FAIL",
        "POLICY_ENFORCEMENT=" + proof.evaluate(None)["POLICY_ENFORCEMENT"],
        "SECRET_REFERENCE_ONLY=" + proof.evaluate(None)["SECRET_REFERENCE_ONLY"],
        "ARTIFACT_TRUST=" + proof.evaluate(None)["ARTIFACT_TRUST"],
        "RESTORE_DRILL=FAIL",
    ]
