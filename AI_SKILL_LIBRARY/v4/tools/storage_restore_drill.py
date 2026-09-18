"""Did protected state actually come back after the primary was destroyed?

    python AI_SKILL_LIBRARY/v4/tools/storage_restore_drill.py \\
        --source-sha "$(git rev-parse HEAD)" \\
        --evidence CHECKPOINTS/evidence/STORAGE_RESTORE_DRILL.json

``DISASTER_RECOVERY_READY`` is the gate a schema check can most easily
impersonate. A recovery manifest parses, a backup contract validates, and the
gate reads green while nobody has ever reconstructed a byte. The closure rule
is one sentence: no schema/manifest-only check may set this gate without a real
restore drill - and a drill that restores an empty directory, or restores into
a location that already held the answer, is a failed drill dressed as a pass.

So this tool runs the thing itself, inside one temporary directory:

  1. it writes real non-empty state through the *existing* contract - a
     ``StorageObject`` record in a real ``MetadataStore``, exported by
     ``storage.recovery.export_recovery_snapshot`` and indexed by
     ``survival.recovery.create_recovery_manifest``;
  2. it deletes the primary, and then *looks* to see whether it is gone;
  3. it creates a different destination and *lists* it to see that it is empty;
  4. it restores from the backup alone, through
     ``storage.recovery.restore_into_store``, which runs the production
     snapshot cleanliness gate and the production rebuild before any record is
     written into the destination index;
  5. it re-hashes the restored bytes, re-reads the restored revision, and runs
     ``survival.recovery.verify_restore`` on a manifest scanned from what is
     actually on disk.

**Emptiness and removal are observations here, never constants.**
``primary_removed_before_restore`` is ``not primary.exists()`` read after the
delete and before the restore; ``restore_destination_was_empty`` is a directory
listing. A field that is assigned ``True`` proves nothing, which is the entire
failure mode this gate exists to prevent.

**There is no second backup framework.** Every check that decides the outcome
is the one production recovery already runs; the only things added for the
drill are a temporary JSON-file metadata adapter and the two hooks the real
drill needed (``restore_into_store``, ``scan_objects``). A drill that bypassed
the real checks would prove something about itself and nothing about recovery.

**Fail closed, everywhere.** A corrupt backup, a missing backup, an empty
backup object, a tampered snapshot, an empty restored state, a content or
revision mismatch, a destination that was not empty, a primary still present,
an unreadable revision - each is ``ready=false``, reported rather than raised.
An absent fact is never a pass.

**This tool reports. It does not repair, promote or decide.** It writes one
evidence file with the nine fields the closure plan names, and every string in
it comes from a fixed vocabulary: no input, path, payload or exception text is
echoed into the document, because a restore drill handles protected state and
an error message is the shortest route out of a process for something that
should not leave it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

# Run as a script as well as imported as a module, like the other tools here.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.storage import manifest as storage_manifest
from AI_SKILL_LIBRARY.v4.storage import metadata as storage_metadata
from AI_SKILL_LIBRARY.v4.storage import recovery as storage_recovery
from AI_SKILL_LIBRARY.v4.survival import recovery as survival_recovery
from AI_SKILL_LIBRARY.v4.tools.worker_execution_liveness import (
    current_source_sha, utc_now,
)

#: This tool reports a fact. It grants nothing, repairs nothing, promotes
#: nothing, and is not the authority that reads its evidence.
AUTHORITY = False
AUTHORITY_FLAGS = {
    "storage_authority": False,
    "routing_authority": False,
    "reasoning_authority": False,
    "model_selection_authority": False,
    "scheduling_authority": False,
    "merge_authority": False,
    "deployment_authority": False,
    "evidence_authority": False,
    "trading_authority": False,
}

GATE = "DISASTER_RECOVERY_READY"
DEFAULT_EVIDENCE = "CHECKPOINTS/evidence/STORAGE_RESTORE_DRILL.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

#: The protected state the closure plan names, verbatim. Real, non-empty, and
#: carrying a revision, because "the restore produced a file" is not the claim -
#: "the restore produced *this* state at *that* revision" is.
SAMPLE_STATE = {
    "project_id": "e2e-closure-test",
    "revision": 7,
    "payload": {"marker": "restore-me"},
}

SNAPSHOT_NAME = "recovery_snapshot.json"
BACKUP_MANIFEST_NAME = "backup_manifest.json"
INDEX_NAME = "index.json"
OBJECTS_DIR = "objects"

#: The drill's own storage classification for its sample object: owned local
#: storage, never external, never encrypted, and CRITICAL so that the export
#: path that carries the critical-object index is the one exercised.
PRIVACY_CLASS = "LOCAL_ONLY"
CRITICALITY = "CRITICAL"
STORAGE_TIER = "HOT"
BACKEND_ID = storage_manifest.DEFAULT_BACKEND_ID

NO_FAULT = "none"

#: The faults a drill run may inject into its own backup before restoring.
#: They exist so that fail-closed behaviour is *demonstrated* rather than
#: asserted: each one must produce ``ready=false`` without raising.
FAULTS = (NO_FAULT, "corrupt_backup", "missing_backup", "empty_backup",
          "tampered_snapshot")

# --- bounds -----------------------------------------------------------------
# Every anchored pattern ends in ``\Z`` and never in ``$``. Python's ``$`` also
# matches immediately before a trailing newline, so ``"abc\n"`` passes a
# ``$``-anchored check and rides on as a longer string than the bound allowed.
# This repository has already paid for that bug in the storage manifest.

MAX_SHA = 64
MAX_GATE = 64
#: ``obj_`` + 64 hex + ``@sha256:`` + 64 hex = 76 + 64 = 140 characters.
MAX_IDENTITY = 140
MAX_PROOF = 120
MAX_PROOFS = 32

UNKNOWN_SHA = "unknown"
NO_IDENTITY = "unavailable"

SHA_RE = re.compile(r"(?:[0-9a-f]{7,64}|unknown)\Z")
GATE_RE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
IDENTITY_RE = re.compile(
    r"(?:obj_[0-9a-f]{64}@sha256:[0-9a-f]{64}|unavailable)\Z")
#: A proof is ``<observation>=pass`` or ``<observation>=fail`` and nothing else.
#: There is no free-text field in this document at all: the vocabulary is
#: closed, so no path, payload, credential or exception message has a way out.
PROOF_RE = re.compile(r"[a-z][a-z0-9_]{0,110}=(?:pass|fail)\Z")

#: The observations the drill must make, every one of which must pass before
#: the gate can be true. They are emitted in this order, always all of them:
#: a proof that is simply absent is the shape a false pass takes.
REQUIRED_PROOFS = (
    "backup_written_through_recovery_contract",
    "manifest_verification_ran",
    "primary_removed_before_restore",
    "restore_destination_was_empty",
    "restored_state_non_empty",
    "content_identity_matches_backup",
    "revision_matches_recorded_revision",
    "restored_manifest_verified",
    "evidence_bound_to_source_sha",
)

#: The subset that decides ``integrity_verified``: what the restored bytes are,
#: what revision they carry, that there are any, and that the production
#: verifier agreed.
INTEGRITY_PROOFS = (
    "restored_state_non_empty",
    "content_identity_matches_backup",
    "revision_matches_recorded_revision",
    "restored_manifest_verified",
)

#: Everything a failed stage may raise, caught so the drill reports rather than
#: throws. An exception escaping a readiness tool reads, to a shell, exactly
#: like a crash - and to a careless caller, like anything but a false gate.
_STAGE_ERRORS = (
    ValueError, TypeError, KeyError, IndexError, AttributeError,
    OSError, json.JSONDecodeError,
    storage_metadata.MetadataStoreError,
)


class EvidenceRejected(ValueError):
    """Evidence that cannot be trusted is refused, never repaired."""


def _bounded_string(value: Any, pattern: re.Pattern[str], limit: int, *,
                    field: str) -> str:
    if not isinstance(value, str):
        raise EvidenceRejected(
            f"{field} must be a string, got {type(value).__name__}")
    if len(value) > limit:
        raise EvidenceRejected(
            f"{field} is {len(value)} characters, over the {limit}-character bound")
    if not pattern.fullmatch(value):
        raise EvidenceRejected(f"{field} does not match {pattern.pattern}")
    return value


def _string(pattern: re.Pattern[str], limit: int) -> Callable[..., str]:
    def check(value: Any, *, field: str) -> str:
        return _bounded_string(value, pattern, limit, field=field)
    return check


def _check_bool(value: Any, *, field: str) -> bool:
    if value is not True and value is not False:
        raise EvidenceRejected(
            f"{field} must be literally true or false, got {type(value).__name__}; "
            "a truthy value is not an observation")
    return value


def _check_gate(value: Any, *, field: str) -> str:
    name = _bounded_string(value, GATE_RE, MAX_GATE, field=field)
    if name != GATE:
        raise EvidenceRejected(f"{field} must be {GATE}")
    return name


def _check_proofs(value: Any, *, field: str) -> list:
    if not isinstance(value, list):
        raise EvidenceRejected(
            f"{field} must be a list, got {type(value).__name__}")
    if not value:
        raise EvidenceRejected(
            f"{field} is empty; a drill that recorded no observation recorded "
            "no drill")
    if len(value) > MAX_PROOFS:
        raise EvidenceRejected(
            f"{field} holds {len(value)} entries, over the {MAX_PROOFS} bound")
    seen = []
    for index, item in enumerate(value):
        token = _bounded_string(item, PROOF_RE, MAX_PROOF, field=f"{field}[{index}]")
        seen.append(token.rsplit("=", 1)[0])
    if sorted(seen) != sorted(REQUIRED_PROOFS):
        raise EvidenceRejected(
            f"{field} must name every one of the {len(REQUIRED_PROOFS)} required "
            "observations exactly once, passed or failed; an absent observation "
            "is not a pass")
    return list(value)


#: One validator per permitted field of the evidence document. A table rather
#: than a run of ``if`` statements, so the permitted field set can be *derived*
#: from it: ``EVIDENCE_FIELDS`` is this table's keys, and a field that is
#: allowed but validated by nothing therefore cannot exist. This repository has
#: found that exact shape several times - a name on an allow-list with no
#: checker behind it - and the tests drive the field list from the data
#: contract in both directions so a field added later cannot repeat it.
FIELD_CHECKS: dict[str, Callable[..., Any]] = {
    "gate": _check_gate,
    "ready": _check_bool,
    "source_sha": _string(SHA_RE, MAX_SHA),
    "backup_identity": _string(IDENTITY_RE, MAX_IDENTITY),
    "restored_identity": _string(IDENTITY_RE, MAX_IDENTITY),
    "integrity_verified": _check_bool,
    "primary_removed_before_restore": _check_bool,
    "restore_destination_was_empty": _check_bool,
    "proofs": _check_proofs,
}

#: Derived, not declared a second time.
EVIDENCE_FIELDS = tuple(FIELD_CHECKS)

#: The pattern-bounded string fields and their bounds, exposed so the tests can
#: assert the anchor and the length of every one without repeating the list.
FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "gate": GATE_RE,
    "source_sha": SHA_RE,
    "backup_identity": IDENTITY_RE,
    "restored_identity": IDENTITY_RE,
}
FIELD_MAX_LENGTHS: dict[str, int] = {
    "gate": MAX_GATE,
    "source_sha": MAX_SHA,
    "backup_identity": MAX_IDENTITY,
    "restored_identity": MAX_IDENTITY,
    "proofs": MAX_PROOF,
}


def assert_evidence_is_clean(evidence: Any) -> dict:
    """Refuse evidence that is malformed, unbounded or internally contradictory.

    Run by the drill on its own output before it is written, and available to
    anything that reads the file afterwards. The cross-field rules are the ones
    no single field can state: a document may not claim ``ready`` while an
    observation failed, while the primary was still present, while the
    destination was not empty, or while the two identities disagree.
    """
    if not isinstance(evidence, dict):
        raise EvidenceRejected(
            f"evidence must be a mapping, got {type(evidence).__name__}")
    unknown = sorted(set(evidence) - set(FIELD_CHECKS))
    if unknown:
        raise EvidenceRejected(
            f"evidence rejects unknown field(s) {unknown}: the field set is "
            f"closed to {list(EVIDENCE_FIELDS)}, so a field nobody wrote a "
            "checker for cannot ride into the document")
    missing = sorted(set(EVIDENCE_FIELDS) - set(evidence))
    if missing:
        raise EvidenceRejected(f"evidence is missing field(s) {missing}")

    for field in EVIDENCE_FIELDS:
        FIELD_CHECKS[field](evidence[field], field=field)

    passed = {token.rsplit("=", 1)[0]: token.endswith("=pass")
              for token in evidence["proofs"]}
    all_passed = all(passed[name] for name in REQUIRED_PROOFS)
    if evidence["ready"] is not all_passed:
        raise EvidenceRejected(
            "ready must be exactly whether every required observation passed; "
            "a gate that disagrees with its own proofs is not evidence")
    if evidence["integrity_verified"] is not all(
            passed[name] for name in INTEGRITY_PROOFS):
        raise EvidenceRejected(
            "integrity_verified must be exactly whether the content, revision, "
            "non-emptiness and restore-verification observations passed")
    for field in ("primary_removed_before_restore", "restore_destination_was_empty"):
        if evidence[field] is not passed[field]:
            raise EvidenceRejected(
                f"{field} contradicts the observation recorded in proofs")
        if evidence["ready"] and evidence[field] is not True:
            raise EvidenceRejected(
                f"ready cannot be true while {field} is false: a restore into a "
                "destination that already held the answer, or beside a primary "
                "that was never removed, proves nothing")
    if evidence["ready"]:
        if evidence["backup_identity"] != evidence["restored_identity"]:
            raise EvidenceRejected(
                "ready requires the restored artifact to be the backed-up one; "
                "the two identities differ")
        if evidence["restored_identity"] == NO_IDENTITY:
            raise EvidenceRejected(
                "ready requires a named restored artifact identity")
        if evidence["source_sha"] == UNKNOWN_SHA:
            raise EvidenceRejected(
                "ready requires evidence bound to a known source revision")
    return evidence


# --- the drill ----------------------------------------------------------------


def sample_state_bytes() -> bytes:
    """The protected state, serialised deterministically, as bytes."""
    return json.dumps(SAMPLE_STATE, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _identity(object_id: str, digest: str) -> str:
    """The exact artifact, named by what it is rather than where it was."""
    return f"{object_id}@sha256:{digest}"


class JsonFileMetadataStore(storage_metadata.MetadataStore):
    """A metadata index in one JSON file, for a drill inside a temp directory.

    It subclasses the real ``MetadataStore`` deliberately: every write goes
    through ``put_manifest``'s validation and health gate, so a restore into
    this store is validated exactly as a restore into any other adapter. A
    hand-rolled double would let the drill pass while the validation that makes
    the restored index mean anything went unexercised.
    """

    def __init__(self, path: Any):
        self._path = Path(path)
        # The directory is the index's own; making it here keeps "unhealthy"
        # meaning "cannot be written" rather than "has never been written".
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        rows = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(rows, dict):
            raise storage_metadata.MetadataStoreError(
                "the index file does not hold a mapping of object id to record")
        return rows

    def _save(self, rows: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n",
                              encoding="utf-8")

    def _probe_healthy(self):
        return self._path.parent.is_dir()

    def _put_record(self, object_id, record):
        rows = self._load()
        rows[object_id] = record
        self._save(rows)

    def _get_record(self, object_id):
        return self._load().get(object_id)

    def _all_records(self):
        return list(self._load().values())


def _prepare_workspace(workspace: Any) -> Path:
    """The one directory this drill may write in, checked before it is used."""
    work = Path(workspace).resolve()
    if work == REPOSITORY_ROOT or REPOSITORY_ROOT in work.parents:
        raise ValueError(
            "the restore drill writes only inside a temporary directory; a "
            "workspace inside the repository would put drill state next to real "
            "repository state, which is the one thing a drill must never touch")
    if not work.is_dir():
        raise ValueError("the drill workspace must be an existing directory")
    if any(work.iterdir()):
        raise ValueError(
            "the drill workspace must be empty; a drill that starts beside "
            "earlier state cannot prove what it restored")
    return work


def _normalise_sha(source_sha: Any) -> str:
    if isinstance(source_sha, str) and re.fullmatch(r"[0-9a-f]{7,64}", source_sha):
        return source_sha
    return UNKNOWN_SHA


def _observe_backup(objects_dir: Path, observed_at: str) -> list:
    """What a provider scan can actually see in the backup: ids and real hashes.

    The digest is measured from the bytes on disk, which is what makes a
    corrupt backup fail: the production rebuild admits an object only when the
    observed hash and size match the snapshot pointer.
    """
    rows = []
    for path in sorted(objects_dir.iterdir()):
        if not path.is_file():
            raise ValueError("the backup object directory holds a non-file entry")
        payload = path.read_bytes()
        rows.append({
            "backend_id": BACKEND_ID,
            "object_id": path.name,
            "content_sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            "observed_at": observed_at,
        })
    if not rows:
        raise ValueError("the backup holds no object to restore from")
    return rows


def _inject(fault: str, backup_root: Path, object_id: str) -> None:
    """Damage this drill's own backup, inside the temporary workspace only."""
    snapshot_path = backup_root / SNAPSHOT_NAME
    object_path = backup_root / OBJECTS_DIR / object_id
    if fault == "corrupt_backup" and object_path.exists():
        object_path.write_bytes(b'{"project_id":"e2e-closure-test","revision":0}')
    elif fault == "missing_backup":
        if snapshot_path.exists():
            snapshot_path.unlink()
        if (backup_root / OBJECTS_DIR).is_dir():
            shutil.rmtree(backup_root / OBJECTS_DIR)
    elif fault == "empty_backup" and object_path.exists():
        object_path.write_bytes(b"")
    elif fault == "tampered_snapshot" and snapshot_path.exists():
        document = json.loads(snapshot_path.read_text(encoding="utf-8"))
        # A field the production cleanliness gate validates, set to a value it
        # refuses. If the drill had its own looser copy of that gate, this
        # would sail through - which is exactly what this fault is for.
        document["entry_count"] = 99
        snapshot_path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def run_drill(*, workspace: Any, source_sha: Any, fault: str = NO_FAULT) -> dict:
    """Run the whole drill in ``workspace`` and return what was observed.

    Never raises for a failed drill - only for a workspace or a fault argument
    that is not usable, because those are the caller's mistakes rather than the
    drill's findings.
    """
    if fault not in FAULTS:
        raise ValueError(f"fault must be one of {list(FAULTS)}")
    work = _prepare_workspace(workspace)
    sha = _normalise_sha(source_sha)
    now = utc_now()

    passed = dict.fromkeys(REQUIRED_PROOFS, False)
    passed["evidence_bound_to_source_sha"] = sha != UNKNOWN_SHA

    primary_root = work / "primary"
    backup_root = work / "backup"
    destination_root = work / "restore"
    written: list[str] = []

    payload = sample_state_bytes()
    object_id = f"{storage_manifest.OBJECT_ID_PREFIX}" \
                f"{hashlib.sha256(payload).hexdigest()}"
    restored_path = destination_root / OBJECTS_DIR / object_id

    backup_identity = NO_IDENTITY
    restored_identity = NO_IDENTITY
    recorded_revision = None
    restored_revision = None
    backup_manifest = None
    destination_store = None

    # 1. Persist real, non-empty state through the existing contract.
    try:
        record = storage_manifest.StorageObject.from_bytes(
            payload,
            privacy_class=PRIVACY_CLASS,
            criticality=CRITICALITY,
            storage_tier=STORAGE_TIER,
            primary_backend=BACKEND_ID,
            replica_backends=(),
            created_at=now,
            lifecycle_state="RAW",
            mime_type="application/json",
        ).to_manifest()
        primary_store = JsonFileMetadataStore(primary_root / INDEX_NAME)
        primary_store.put_manifest(record)
        primary_object = primary_root / OBJECTS_DIR / object_id
        primary_object.parent.mkdir(parents=True, exist_ok=True)
        primary_object.write_bytes(payload)
        written.extend([str(primary_store.path), str(primary_object)])

        # Read back from the primary rather than from the constant: the
        # revision this drill will require is the one that was really stored.
        recorded_revision = json.loads(
            primary_object.read_bytes().decode("utf-8"))["revision"]

        snapshot = storage_recovery.export_recovery_snapshot(
            primary_store, generated_at=now)
        backup_object = backup_root / OBJECTS_DIR / object_id
        backup_object.parent.mkdir(parents=True, exist_ok=True)
        backup_object.write_bytes(payload)
        snapshot_path = backup_root / SNAPSHOT_NAME
        snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        backup_manifest = survival_recovery.create_recovery_manifest(
            survival_recovery.scan_objects(backup_root / OBJECTS_DIR),
            backup_id=object_id, created_at=now,
            policy={"require_sha256": True, "require_size_bytes": True})
        manifest_path = backup_root / BACKUP_MANIFEST_NAME
        manifest_path.write_text(
            survival_recovery.manifest_to_json(backup_manifest), encoding="utf-8")
        written.extend([str(backup_object), str(snapshot_path), str(manifest_path)])

        entry = snapshot["entries"][0]
        backup_identity = _identity(entry["object_id"], entry["content_sha256"])
        passed["backup_written_through_recovery_contract"] = (
            entry["object_id"] == object_id
            and entry["content_sha256"] == hashlib.sha256(payload).hexdigest()
            and backup_object.read_bytes() == payload)
    except _STAGE_ERRORS:
        pass

    _inject(fault, backup_root, object_id)

    # 2. Remove the primary, and then look.
    try:
        if primary_root.exists():
            shutil.rmtree(primary_root)
    except OSError:
        pass
    passed["primary_removed_before_restore"] = not primary_root.exists()

    # 3. A different destination, observed empty before anything is restored.
    destination_listing: list[str] = []
    try:
        destination_root.mkdir(parents=True, exist_ok=True)
        destination_listing = sorted(p.name for p in destination_root.iterdir())
        passed["restore_destination_was_empty"] = destination_listing == []
    except OSError:
        destination_listing = [".unreadable"]

    # 4. Restore from the backup alone, through the production path.
    may_restore = (passed["backup_written_through_recovery_contract"]
                   and passed["primary_removed_before_restore"]
                   and passed["restore_destination_was_empty"])
    if may_restore:
        try:
            snapshot_on_disk = json.loads(
                (backup_root / SNAPSHOT_NAME).read_text(encoding="utf-8"))
            storage_recovery.assert_snapshot_is_clean(snapshot_on_disk)
            passed["manifest_verification_ran"] = True

            observations = _observe_backup(backup_root / OBJECTS_DIR, now)
            destination_store = JsonFileMetadataStore(destination_root / INDEX_NAME)
            report = storage_recovery.restore_into_store(
                destination_store, observations, snapshot_on_disk)
            if report["restored"] != [object_id]:
                raise ValueError("the restore did not reproduce the named object")
            written.append(str(destination_store.path))

            restored_record = destination_store.get_manifest(object_id)
            if restored_record is None:
                raise ValueError("the restored index does not hold the object")
            source_bytes = (backup_root / OBJECTS_DIR / object_id).read_bytes()
            if hashlib.sha256(source_bytes).hexdigest() != \
                    restored_record["content_sha256"]:
                raise ValueError("the backup bytes do not match the restored record")
            restored_path.parent.mkdir(parents=True, exist_ok=True)
            restored_path.write_bytes(source_bytes)
            written.append(str(restored_path))

            restored_bytes = restored_path.read_bytes()
            restored_digest = hashlib.sha256(restored_bytes).hexdigest()
            restored_state = json.loads(restored_bytes.decode("utf-8"))
            passed["restored_state_non_empty"] = bool(restored_bytes) and bool(
                isinstance(restored_state, dict) and restored_state)

            restored_identity = _identity(object_id, restored_digest)
            passed["content_identity_matches_backup"] = (
                backup_identity != NO_IDENTITY
                and restored_identity == backup_identity)

            restored_revision = restored_state.get("revision")
            passed["revision_matches_recorded_revision"] = (
                isinstance(restored_revision, int)
                and not isinstance(restored_revision, bool)
                and recorded_revision is not None
                and restored_revision == recorded_revision)

            restored_manifest = survival_recovery.create_recovery_manifest(
                survival_recovery.scan_objects(destination_root / OBJECTS_DIR),
                backup_id=object_id, created_at=now,
                policy={"require_sha256": True, "require_size_bytes": True})
            verification = survival_recovery.verify_restore(
                restored_manifest, backup_manifest)
            passed["restored_manifest_verified"] = verification.success is True
        except _STAGE_ERRORS:
            # Reported, never re-raised and never echoed: the document has no
            # free-text field, so nothing from an exception can reach it.
            pass

    integrity = all(passed[name] for name in INTEGRITY_PROOFS)
    ready = all(passed[name] for name in REQUIRED_PROOFS)
    evidence = {
        "gate": GATE,
        "ready": ready,
        "source_sha": sha,
        "backup_identity": backup_identity,
        "restored_identity": restored_identity,
        "integrity_verified": integrity,
        "primary_removed_before_restore": passed["primary_removed_before_restore"],
        "restore_destination_was_empty": passed["restore_destination_was_empty"],
        "proofs": [f"{name}={'pass' if passed[name] else 'fail'}"
                   for name in REQUIRED_PROOFS],
    }
    assert_evidence_is_clean(evidence)
    return {
        "evidence": evidence,
        "fault": fault,
        "object_id": object_id,
        "workspace": work,
        "primary_root": primary_root,
        "backup_root": backup_root,
        "destination_root": destination_root,
        "destination_listing_before_restore": destination_listing,
        "destination_store": destination_store,
        "restored_path": restored_path,
        "recorded_revision": recorded_revision,
        "restored_revision": restored_revision,
        "paths_written": written,
    }


def evidence_from(result: Any) -> dict:
    """The nine-field evidence document, copied out of a drill result."""
    if isinstance(result, dict) and "evidence" in result:
        result = result["evidence"]
    if not isinstance(result, dict):
        raise EvidenceRejected("no evidence document in this result")
    return {field: result[field] for field in EVIDENCE_FIELDS if field in result}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-sha", dest="source_sha")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE)
    parser.add_argument("--fault", choices=FAULTS, default=NO_FAULT,
                        help="inject a fault into the drill's own backup, to "
                             "demonstrate fail-closed behaviour")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero when the gate is not ready")
    args = parser.parse_args(argv)

    source_sha = args.source_sha or current_source_sha(REPOSITORY_ROOT)
    with tempfile.TemporaryDirectory(prefix="storage-restore-drill-") as tmp:
        result = run_drill(workspace=Path(tmp), source_sha=source_sha,
                           fault=args.fault)
    evidence = assert_evidence_is_clean(evidence_from(result))

    out = Path(args.evidence)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(evidence, indent=2))
    print(f"{GATE}={'true' if evidence['ready'] else 'false'}")
    return 1 if (args.strict and not evidence["ready"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
