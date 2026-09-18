"""Backup/restore contract for the Survival Plane (Task 5).

This module defines a bounded, deterministic recovery manifest and a
fail-closed restore verifier. It never stores raw object contents or
plaintext secret payloads; only paths, hashes and metadata are recorded.

External mechanics (restic, OpenTofu, Ansible) sit behind this contract and
are not required by this module or its tests.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

MANIFEST_VERSION = 1

# Fields every object entry must carry for a faithful restore to be verifiable.
REQUIRED_OBJECT_FIELDS = ("path", "sha256", "size_bytes")

# Authority flags that must never be granted by recovery.
AUTHORITY_FLAGS = (
    "routing_authority",
    "reasoning_authority",
    "scheduling_authority",
    "merge_authority",
    "deployment_authority",
    "trading_authority",
)


@dataclass(frozen=True)
class RecoveryReport:
    """Outcome of a restore verification. Authoritative for readiness."""

    success: bool
    reasons: List[str] = field(default_factory=list)
    checked_objects: int = 0
    missing_objects: List[str] = field(default_factory=list)
    unexpected_objects: List[str] = field(default_factory=list)
    hash_mismatches: List[str] = field(default_factory=list)
    malformed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "reasons": list(self.reasons),
            "checked_objects": self.checked_objects,
            "missing_objects": list(self.missing_objects),
            "unexpected_objects": list(self.unexpected_objects),
            "hash_mismatches": list(self.hash_mismatches),
            "malformed": self.malformed,
        }


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_path(path: Any) -> Optional[str]:
    if not isinstance(path, str):
        return None
    cleaned = path.strip().replace("\\", "/")
    if not cleaned or cleaned.startswith("/") or ".." in cleaned.split("/"):
        return None
    return cleaned


def _coerce_object(obj: Any) -> Optional[Dict[str, Any]]:
    """Return a bounded metadata-only object entry, or None if unusable."""
    if not isinstance(obj, Mapping):
        return None
    path = _normalize_path(obj.get("path"))
    if path is None:
        return None
    entry: Dict[str, Any] = {"path": path}
    sha = obj.get("sha256")
    if isinstance(sha, str) and len(sha) == 64:
        entry["sha256"] = sha.lower()
    size = obj.get("size_bytes")
    if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
        entry["size_bytes"] = size
    kind = obj.get("kind")
    if isinstance(kind, str) and kind:
        entry["kind"] = kind
    return entry


def create_recovery_manifest(
    objects: Iterable[Mapping[str, Any]],
    *,
    backup_id: str = "",
    created_at: str = "",
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a bounded, deterministic, metadata-only recovery manifest.

    ``objects`` entries may carry ``path``, ``sha256``, ``size_bytes`` and
    ``kind``. Raw contents and secret payloads are never copied. Entries are
    sorted by path so identical inputs yield identical manifests.
    """
    entries: List[Dict[str, Any]] = []
    seen: set = set()
    for obj in objects or ():
        entry = _coerce_object(obj)
        if entry is None:
            continue
        if entry["path"] in seen:
            continue
        seen.add(entry["path"])
        entries.append(entry)
    entries.sort(key=lambda e: e["path"])

    manifest: Dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "backup_id": str(backup_id),
        "created_at": str(created_at),
        "object_count": len(entries),
        "objects": entries,
        "authority": {flag: False for flag in AUTHORITY_FLAGS},
    }
    if policy is not None:
        manifest["policy"] = {
            "allow_unexpected_objects": bool(
                policy.get("allow_unexpected_objects", False)
            ),
            "require_sha256": bool(policy.get("require_sha256", True)),
            "require_size_bytes": bool(policy.get("require_size_bytes", True)),
        }
    return manifest


def _manifest_objects(manifest: Any) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(manifest, Mapping):
        return None
    objects = manifest.get("objects")
    if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
        return None
    out: List[Dict[str, Any]] = []
    for obj in objects:
        if not isinstance(obj, Mapping):
            return None
        out.append(dict(obj))
    return out


def verify_restore(
    restored: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> RecoveryReport:
    """Fail-closed verification that ``restored`` faithfully matches ``expected``.

    Never raises for missing or malformed fields; returns a RecoveryReport
    with ``success=False`` and explicit reasons instead.
    """
    reasons: List[str] = []
    missing: List[str] = []
    unexpected: List[str] = []
    mismatches: List[str] = []
    malformed = False

    expected_objects = _manifest_objects(expected)
    if expected_objects is None:
        return RecoveryReport(
            success=False,
            reasons=["malformed_expected_manifest"],
            malformed=True,
        )

    restored_objects = _manifest_objects(restored)
    if restored_objects is None:
        return RecoveryReport(
            success=False,
            reasons=["malformed_restored_manifest"],
            malformed=True,
        )

    policy = expected.get("policy") if isinstance(expected, Mapping) else None
    allow_unexpected = False
    require_sha256 = True
    require_size = True
    if isinstance(policy, Mapping):
        allow_unexpected = bool(policy.get("allow_unexpected_objects", False))
        require_sha256 = bool(policy.get("require_sha256", True))
        require_size = bool(policy.get("require_size_bytes", True))

    expected_by_path: Dict[str, Dict[str, Any]] = {}
    for obj in expected_objects:
        path = _normalize_path(obj.get("path"))
        if path is None:
            malformed = True
            reasons.append("malformed_expected_object_path")
            continue
        expected_by_path[path] = obj

    restored_by_path: Dict[str, Dict[str, Any]] = {}
    for obj in restored_objects:
        path = _normalize_path(obj.get("path"))
        if path is None:
            malformed = True
            reasons.append("malformed_restored_object_path")
            continue
        restored_by_path[path] = obj

    checked = 0
    for path, exp in expected_by_path.items():
        checked += 1
        got = restored_by_path.get(path)
        if got is None:
            missing.append(path)
            continue

        exp_sha = exp.get("sha256")
        got_sha = got.get("sha256")
        if require_sha256:
            if not isinstance(exp_sha, str) or len(exp_sha) != 64:
                malformed = True
                reasons.append("incomplete_expected_metadata:sha256:%s" % path)
                continue
            if not isinstance(got_sha, str) or len(got_sha) != 64:
                malformed = True
                reasons.append("incomplete_restored_metadata:sha256:%s" % path)
                continue
            if exp_sha.lower() != got_sha.lower():
                mismatches.append(path)
                continue

        if require_size:
            exp_size = exp.get("size_bytes")
            got_size = got.get("size_bytes")
            if not isinstance(exp_size, int) or isinstance(exp_size, bool):
                malformed = True
                reasons.append("incomplete_expected_metadata:size_bytes:%s" % path)
                continue
            if not isinstance(got_size, int) or isinstance(got_size, bool):
                malformed = True
                reasons.append("incomplete_restored_metadata:size_bytes:%s" % path)
                continue
            if exp_size != got_size:
                mismatches.append(path)
                continue

    for path in restored_by_path:
        if path not in expected_by_path:
            unexpected.append(path)

    if missing:
        reasons.append("missing_objects")
    if mismatches:
        reasons.append("hash_or_size_mismatch")
    if unexpected and not allow_unexpected:
        reasons.append("unexpected_objects")

    success = not (missing or mismatches or malformed or (unexpected and not allow_unexpected))
    return RecoveryReport(
        success=success,
        reasons=reasons,
        checked_objects=checked,
        missing_objects=missing,
        unexpected_objects=unexpected,
        hash_mismatches=mismatches,
        malformed=malformed,
    )


def manifest_to_json(manifest: Mapping[str, Any]) -> str:
    """Deterministic JSON serialization of a recovery manifest."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"))
