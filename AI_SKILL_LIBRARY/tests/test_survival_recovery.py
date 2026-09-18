"""Tests for the Survival Plane backup/restore contract (Task 5).

No network access and no external tools (restic/OpenTofu/Ansible) required.
"""

import hashlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from AI_SKILL_LIBRARY.v4.survival.recovery import (  # noqa: E402
    AUTHORITY_FLAGS,
    RecoveryReport,
    create_recovery_manifest,
    manifest_to_json,
    verify_restore,
)

SECRET_PAYLOAD_ALPHA_7F9C = "SECRET_PAYLOAD_ALPHA_7F9C"
SECRET_PAYLOAD_BETA_3D1E = "SECRET_PAYLOAD_BETA_3D1E"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _objects():
    return [
        {"path": "state/checkpoint.json", "sha256": _sha(b"a"), "size_bytes": 1},
        {"path": "state/shared_state.yaml", "sha256": _sha(b"bb"), "size_bytes": 2},
    ]


def test_manifest_is_deterministic_and_metadata_only():
    objs = _objects()
    m1 = create_recovery_manifest(objs, backup_id="b1", created_at="t1")
    m2 = create_recovery_manifest(list(reversed(objs)), backup_id="b1", created_at="t1")
    assert manifest_to_json(m1) == manifest_to_json(m2)
    assert m1["object_count"] == 2
    assert [o["path"] for o in m1["objects"]] == sorted(o["path"] for o in m1["objects"])


def test_manifest_never_contains_raw_contents_or_secret_payloads():
    objs = [
        {
            "path": "state/checkpoint.json",
            "sha256": _sha(SECRET_PAYLOAD_ALPHA_7F9C.encode()),
            "size_bytes": len(SECRET_PAYLOAD_ALPHA_7F9C),
            "contents": SECRET_PAYLOAD_ALPHA_7F9C,
            "secret": SECRET_PAYLOAD_BETA_3D1E,
        }
    ]
    manifest = create_recovery_manifest(objs, backup_id="b1", created_at="t1")
    blob = manifest_to_json(manifest)
    assert SECRET_PAYLOAD_ALPHA_7F9C not in blob
    assert SECRET_PAYLOAD_BETA_3D1E not in blob
    assert "contents" not in manifest["objects"][0]
    assert "secret" not in manifest["objects"][0]


def test_manifest_authority_flags_all_false():
    manifest = create_recovery_manifest(_objects())
    for flag in AUTHORITY_FLAGS:
        assert manifest["authority"][flag] is False


def test_verify_restore_success():
    expected = create_recovery_manifest(_objects(), backup_id="b1", created_at="t1")
    restored = create_recovery_manifest(_objects(), backup_id="b1", created_at="t1")
    report = verify_restore(restored, expected)
    assert isinstance(report, RecoveryReport)
    assert report.success is True
    assert report.reasons == []


def test_verify_restore_missing_object_fails_closed():
    expected = create_recovery_manifest(_objects())
    restored = create_recovery_manifest(_objects()[:1])
    report = verify_restore(restored, expected)
    assert report.success is False
    assert "missing_objects" in report.reasons
    assert report.missing_objects


def test_verify_restore_unexpected_object_fails_closed():
    expected = create_recovery_manifest(_objects())
    extra = _objects() + [
        {"path": "state/extra.bin", "sha256": _sha(b"x"), "size_bytes": 1}
    ]
    restored = create_recovery_manifest(extra)
    report = verify_restore(restored, expected)
    assert report.success is False
    assert "unexpected_objects" in report.reasons


def test_verify_restore_hash_mismatch_fails_closed():
    expected = create_recovery_manifest(_objects())
    tampered = _objects()
    tampered[0] = dict(tampered[0], sha256=_sha(b"tampered"))
    restored = create_recovery_manifest(tampered)
    report = verify_restore(restored, expected)
    assert report.success is False
    assert "hash_or_size_mismatch" in report.reasons
    assert report.hash_mismatches


def test_verify_restore_missing_sha256_does_not_raise():
    expected = create_recovery_manifest(_objects())
    restored = create_recovery_manifest(
        [{"path": "state/checkpoint.json", "size_bytes": 1}]
    )
    report = verify_restore(restored, expected)
    assert isinstance(report, RecoveryReport)
    assert report.success is False
    assert any("sha256" in r for r in report.reasons)


def test_verify_restore_missing_size_does_not_raise():
    expected = create_recovery_manifest(_objects())
    restored = create_recovery_manifest(
        [{"path": "state/checkpoint.json", "sha256": _sha(b"a")}]
    )
    report = verify_restore(restored, expected)
    assert isinstance(report, RecoveryReport)
    assert report.success is False
    assert any("size_bytes" in r for r in report.reasons)


def test_verify_restore_malformed_manifest_fails_closed():
    expected = create_recovery_manifest(_objects())
    report = verify_restore({"objects": "not-a-list"}, expected)
    assert report.success is False
    assert report.malformed is True
    assert "malformed_restored_manifest" in report.reasons


def test_verify_restore_malformed_expected_fails_closed():
    report = verify_restore({}, {"objects": None})
    assert report.success is False
    assert report.malformed is True
    assert "malformed_expected_manifest" in report.reasons


def test_verify_restore_incomplete_expected_metadata_fails_closed():
    expected = {
        "manifest_version": 1,
        "objects": [{"path": "state/checkpoint.json", "size_bytes": 1}],
    }
    restored = create_recovery_manifest(
        [{"path": "state/checkpoint.json", "sha256": _sha(b"a"), "size_bytes": 1}]
    )
    report = verify_restore(restored, expected)
    assert report.success is False
    assert any("incomplete_expected_metadata" in r for r in report.reasons)


def test_backup_creation_success_is_not_readiness():
    expected = create_recovery_manifest(_objects())
    restored = create_recovery_manifest(_objects()[:1])
    report = verify_restore(restored, expected)
    assert report.success is False
