"""Federated Free Storage Mesh - the placement engine.

Given an object manifest and a set of provider registry rows, this module says
which backends may legitimately receive the object, in the order the spec
prefers them, and which single one should be its primary. It is the only place
in the lane where "where does this go?" is answered, and it holds no authority
while answering: GITHUB_BRAIN_V4 remains canonical, ``task_router`` remains the
router, ``policy.yaml`` remains the authority for every vocabulary named here,
and the Capacity Broker remains the authority on provider state.

It writes nothing, holds no connection, activates no provider account, touches
no credential, performs no cryptography and mutates none of its inputs. It
reads two mappings and returns a list.

The decision order is Spec S5, restated verbatim in the plan's Global
Constraints and checked in at ``policy.yaml`` ``placement_order``:

    privacy -> integrity/criticality -> free-only eligibility -> provider
    health -> quota headroom -> object size -> access frequency -> retention
    class -> latency -> backend choice

with three sentences underneath that are not tie-breaks but absolutes: capacity
never overrides privacy, free capacity never overrides integrity, latency never
overrides the zero-cost policy. Those three are the reason the first five
positions are implemented as *gates* rather than as weights. A provider that
loses on privacy is not ranked below one that wins on capacity - it is not in
the returned list at all, and there is no quantity of free terabytes that puts
it back. A weighted score with a large enough capacity term would eventually
sell the privacy rule for storage, and the arithmetic would look reasonable
while it happened.

So: positions 1 to 6 exclude. Positions 2, 4, 5, 7 and 8 also order, among the
providers that survived. Position 9, latency, has no evidence behind it -
nothing in ``storage_provider.schema.json`` records a latency, and inventing a
proxy for one would be inventing a fact - so it is a documented no-op and ties
fall through to position 10, which is the provider id and is what makes the
result deterministic.

Determinism matters enough to state plainly: the same inputs produce the same
order. Nothing here iterates a set, depends on dict insertion order or consults
a clock of its own. The single time-dependent input is the free-tier expiry
check inside the Capacity Broker, which is injectable through ``now`` and can
only ever withdraw a permission.

Two refusals are worth calling out because they are what a careless
implementation gets wrong.

**LOCAL_ONLY is unreachable, not discouraged.** A LOCAL_ONLY object is admitted
only on a row that says ``external`` is exactly ``False`` *and* whose id is in
the reserved ``local_`` namespace. An omitted flag, a non-boolean flag, an
external row that lists LOCAL_ONLY in its allowances, an external row calling
itself ``local_r2``, an empty dict, ``None`` - each of them fails. There is no
default, no fallback and no "unknown provider" path by which the class leaves
owned storage.

**Nothing unbounded comes back out.** Exclusion reasons are a closed vocabulary
of codes and no caller-supplied string is ever interpolated into one. An
explanation gets logged, and a log is exactly where an unbounded string becomes
a leaked credential. For the same reason a provider row carrying a field the
contract does not declare is refused before any of its values are read: an
undeclared field is the only way an unbounded string reaches a provider record
at all.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from AI_SKILL_LIBRARY.v4.storage import capacity

#: This module holds no authority of any kind. Denied by name rather than by
#: omission, matching the rest of the lane.
AUTHORITY = False
AUTHORITY_FLAGS = {
    "storage_authority": False,
    "routing_authority": False,
    "reasoning_authority": False,
    "model_selection_authority": False,
    "admission_authority": False,
    "scheduling_authority": False,
    "merge_authority": False,
    "trading_authority": False,
}
CANONICAL_AUTHORITY = "GITHUB_BRAIN_V4"
ROUTED_BY = "task_router"

#: Spec S11, restated locally so a reader of this module need not take the rest
#: of the lane on trust. Nothing here can change them.
PAID_STORAGE_ALLOWED = False
OVERAGE_ALLOWED = False
UNKNOWN_COST_STATE = "QUARANTINE"

#: policy.yaml ``placement_order``, in the spec's order.
PLACEMENT_ORDER = (
    "privacy", "integrity_criticality", "free_only_eligibility",
    "provider_health", "quota_headroom", "object_size", "access_frequency",
    "retention_class", "latency", "backend_choice",
)

#: policy.yaml ``placement_precedence``. The three absolutes.
PLACEMENT_PRECEDENCE = {
    "capacity_overrides_privacy": False,
    "free_capacity_overrides_integrity": False,
    "latency_overrides_zero_cost": False,
}

#: Spec S5 position 9. There is no latency evidence in the provider contract,
#: so this position orders nothing and ties fall through to backend choice.
#: Recorded rather than silently skipped, because a reader comparing this module
#: to the spec should find the gap named.
LATENCY_EVIDENCE_AVAILABLE = False

PRIVACY_CLASSES = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY")
CRITICALITY_CLASSES = ("CRITICAL", "IMPORTANT", "REPRODUCIBLE", "EPHEMERAL")
STORAGE_TIERS = ("CANONICAL", "HOT", "WARM", "COLD", "HUMAN_BACKUP", "METADATA")
LIFECYCLE_STATES = (
    "RAW", "SANITIZED", "DEDUPED", "AGGREGATED", "COMPRESSED", "ARCHIVED",
    "EXPIRED",
)
ENCRYPTION_STATES = ("NONE", "CLIENT_SIDE_ENCRYPTED")

#: Spec S6. CANONICAL lives on GitHub and METADATA is an index; both hold
#: pointers, not payloads. No object is ever placed into either, so neither is
#: reachable through this module whatever a registry row claims to serve.
NON_PLACEABLE_TIERS = frozenset({"CANONICAL", "METADATA"})

#: policy.yaml ``provider_roles.acceptable_use_classes`` (Spec S17).
ACCEPTABLE_USE_CLASSES = (
    "owned-storage", "object-storage", "ai-artifacts-only",
    "human-backup-only", "metadata-index-only",
)

#: Spec S17: Hugging Face is for models, datasets, AI artifacts and benchmark
#: corpora. It must not be used as a generic log dump, so the surface admits a
#: closed set of object classes and an object that does not declare one is not
#: given the benefit of the doubt.
AI_ARTIFACT_OBJECT_CLASSES = frozenset({
    "model", "dataset", "ai-artifact", "benchmark-bundle", "benchmark-corpus",
})

#: policy.yaml ``encryption.allowed_algorithms``. Named, never chosen: no
#: cryptography is implemented, invented or performed anywhere in this module.
ENCRYPTION_ALGORITHMS = frozenset({
    "aead-standard-library", "aes-256-gcm", "aes-256-gcm-siv",
    "chacha20-poly1305", "xchacha20-poly1305",
})
_ENCRYPTION_FIELDS = frozenset({
    "algorithm", "scheme_version", "key_ref", "key_rotation_generation",
    "nonce", "tag",
})

#: The manifest schema's other closed objects. Refused structurally for the
#: same reason as the top level: a nested object is the second place an
#: undeclared - and therefore unbounded - string tries to enter.
_PROVENANCE_FIELDS = frozenset({"origin_class", "producer_id", "evidence_ref"})
_VERIFICATION_FIELDS = frozenset({
    "hash_verified", "verified_replica_count", "last_probe_at", "evidence_ref",
})
_AUTHORITY_FLAG_FIELDS = frozenset(AUTHORITY_FLAGS)

#: Spec S22: the key *locations* the spec permits. An object-storage URL is not
#: among them, which is how key/ciphertext separation is a control rather than
#: a recommendation.
_KEY_REF_RE = re.compile(
    r"^(env|secretstore|worker-secret|kms)://[A-Za-z0-9][A-Za-z0-9._/-]{2,180}\Z")

#: storage_object_manifest.schema.json is ``additionalProperties: false``. Same
#: reasoning as ``capacity.PROVIDER_FIELDS``: an unbounded string can only reach
#: a manifest through a field nobody declared.
MANIFEST_FIELDS = frozenset({
    "version", "authority", "authority_flags", "object_id", "object_class",
    "content_sha256", "size_bytes", "mime_type", "privacy_class",
    "criticality", "storage_tier", "retention_class", "encryption_state",
    "encryption_scheme_version", "encryption", "primary_backend",
    "replica_backends", "created_at", "last_accessed_at", "last_verified_at",
    "lifecycle_state", "source_provenance", "reproducible", "verification",
})

#: policy.yaml ``bulk_object_threshold_bytes`` and the schema's size ceiling.
BULK_OBJECT_THRESHOLD_BYTES = 1048576
_MAX_OBJECT_BYTES = 1099511627776

#: The reserved namespace that makes the LOCAL_ONLY rule airtight (Spec S4).
LOCAL_BACKEND_PREFIX = "local_"

#: ``\Z`` rather than ``$`` throughout: Python's ``$`` also matches before a
#: final newline, and a validator looser than the schema it mirrors is the bug
#: class this lane keeps closing.
_PROVIDER_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}\Z")
_CLASS_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,39}\Z")

#: What a report calls a row whose identifier is not a bounded token. The
#: identifier is the only caller-supplied string a report ever shows, so it is
#: shown only when it is provably small and provably tame.
UNNAMED_PROVIDER = "UNNAMED_PROVIDER"

#: The closed vocabulary of exclusion reasons. Codes, not sentences: a reason is
#: produced by this module alone and can never carry a fragment of its input.
EXCLUSION_REASONS = (
    "OBJECT_NOT_PLACEABLE",
    "PROVIDER_NOT_A_RECORD",
    "PROVIDER_IDENTIFIER_INVALID",
    "PROVIDER_IDENTIFIER_DUPLICATED",
    "PRIVACY_CLASS_NOT_ADMITTED",
    "PRIVACY_LOCAL_ONLY_REQUIRES_OWNED_STORAGE",
    "PRIVACY_EXTERNAL_RESIDENCY_NOT_VERIFIED",
    "PRIVACY_ENCRYPTION_REQUIRED",
    "INTEGRITY_USE_CLASS_UNKNOWN",
    "INTEGRITY_USE_CLASS_FORBIDS_OBJECT",
    "INTEGRITY_TIER_NOT_SERVED",
    "INTEGRITY_BULK_BACKEND_REQUIRED",
    "ZERO_COST_AUTONOMOUS_WRITE_NOT_GRANTED",
    "PROVIDER_STATE_NOT_WRITABLE",
    "CAPACITY_HEADROOM_EXHAUSTED",
    "OBJECT_SIZE_ABOVE_PROVIDER_LIMIT",
    "OBJECT_SIZE_BELOW_PROVIDER_LIMIT",
)


# --- input validation -------------------------------------------------------

def _is_byte_count(value, ceiling=_MAX_OBJECT_BYTES):
    return (isinstance(value, int) and not isinstance(value, bool)
            and 0 <= value <= ceiling)


def _is_class_token(value):
    return isinstance(value, str) and bool(_CLASS_TOKEN_RE.match(value))


def _closed(value, fields):
    """A nested object is absent, or a mapping with no key outside ``fields``."""
    if value is None:
        return True
    return isinstance(value, Mapping) and not (set(value) - fields)


def _encryption_metadata_is_sound(record):
    """Shape only. This module names encryption fields and checks nothing else.

    It chooses no algorithm, derives no key and verifies no ciphertext; that is
    the encryption contract's job and it lives elsewhere.
    """
    meta = record.get("encryption")
    if not isinstance(meta, Mapping) or (set(meta) - _ENCRYPTION_FIELDS):
        return False
    if meta.get("algorithm") not in ENCRYPTION_ALGORITHMS:
        return False
    version = meta.get("scheme_version")
    if not (isinstance(version, int) and not isinstance(version, bool)
            and 1 <= version <= 4096):
        return False
    key_ref = meta.get("key_ref")
    return isinstance(key_ref, str) and bool(_KEY_REF_RE.match(key_ref))


def _object_is_placeable(record):
    """Is this a manifest the engine can reason about at all?

    Everything absent, undeclared or outside its vocabulary makes the object
    unplaceable rather than placeable-by-default. An object nobody has fully
    described is an object nobody has decided is safe to send anywhere.
    """
    if not isinstance(record, Mapping):
        return False
    if set(record) - MANIFEST_FIELDS:
        return False

    if record.get("privacy_class") not in PRIVACY_CLASSES:
        return False
    if record.get("criticality") not in CRITICALITY_CLASSES:
        return False
    if record.get("storage_tier") not in STORAGE_TIERS:
        return False
    # Spec S6. CANONICAL is GitHub's and METADATA is the index's; neither
    # carries object payloads, so an object declaring one has no placement to
    # make rather than a backend to find. Enforced on the object rather than on
    # the provider so that a registry row claiming to serve CANONICAL cannot
    # create the path by claiming it.
    if record["storage_tier"] in NON_PLACEABLE_TIERS:
        return False
    if record.get("encryption_state") not in ENCRYPTION_STATES:
        return False
    if not _is_byte_count(record.get("size_bytes")):
        return False

    if "lifecycle_state" in record and record["lifecycle_state"] not in LIFECYCLE_STATES:
        return False
    if not _closed(record.get("source_provenance"), _PROVENANCE_FIELDS):
        return False
    if not _closed(record.get("verification"), _VERIFICATION_FIELDS):
        return False
    if not _closed(record.get("authority_flags"), _AUTHORITY_FLAG_FIELDS):
        return False
    for field in ("object_class", "retention_class"):
        if field in record and not _is_class_token(record[field]):
            return False

    # The two halves of the encryption claim have to agree before anything is
    # decided about where the object may go.
    if record["encryption_state"] == "CLIENT_SIDE_ENCRYPTED":
        if not _encryption_metadata_is_sound(record):
            return False
    elif "encryption" in record:
        return False

    return True


def _display_id(row):
    """The only caller-supplied string a report ever shows, and only if bounded."""
    if isinstance(row, Mapping):
        provider_id = row.get("provider_id")
        if isinstance(provider_id, str) and _PROVIDER_ID_RE.match(provider_id):
            return provider_id
    return UNNAMED_PROVIDER


# --- the decision order -----------------------------------------------------

def _privacy_reasons(record, row):
    """Spec S5 position 1. Evaluated first and never overturned below."""
    reasons = []
    privacy_class = record["privacy_class"]
    external = row.get("external")
    allowed = row.get("privacy_classes_allowed")

    if not isinstance(allowed, Sequence) or isinstance(allowed, str) \
            or privacy_class not in allowed:
        reasons.append("PRIVACY_CLASS_NOT_ADMITTED")

    if privacy_class == "LOCAL_ONLY":
        # Both halves are required. ``external is False`` alone would trust a
        # row's own word; the reserved namespace alone would be a naming
        # convention. Together they are a control.
        provider_id = row.get("provider_id")
        if external is not False or not (
                isinstance(provider_id, str)
                and provider_id.startswith(LOCAL_BACKEND_PREFIX)):
            reasons.append("PRIVACY_LOCAL_ONLY_REQUIRES_OWNED_STORAGE")
        return reasons

    if external is False:
        return reasons

    # From here the object is leaving owned storage.
    if external is not True or row.get("free_status") not in capacity.VERIFIED_FREE_STATUSES:
        # Spec S4: PUBLIC may go to any *admitted* backend whose terms and
        # health are verified; INTERNAL is verified-only; CONFIDENTIAL is
        # encrypted-verified-only. Every external residency needs a verified
        # row, not merely a listed one.
        reasons.append("PRIVACY_EXTERNAL_RESIDENCY_NOT_VERIFIED")

    required = row.get("encryption_required_classes")
    requires_ciphertext = (
        isinstance(required, Sequence) and not isinstance(required, str)
        and privacy_class in required)
    if privacy_class == "CONFIDENTIAL":
        if not requires_ciphertext:
            reasons.append("PRIVACY_ENCRYPTION_REQUIRED")
        if record["encryption_state"] != "CLIENT_SIDE_ENCRYPTED":
            reasons.append("PRIVACY_ENCRYPTION_REQUIRED")
    elif requires_ciphertext and record["encryption_state"] != "CLIENT_SIDE_ENCRYPTED":
        reasons.append("PRIVACY_ENCRYPTION_REQUIRED")

    return reasons


def _integrity_reasons(record, row):
    """Spec S5 position 2. Free capacity never overrides integrity."""
    reasons = []
    tier = record["storage_tier"]
    use_class = row.get("acceptable_use_class")

    if use_class not in ACCEPTABLE_USE_CLASSES:
        reasons.append("INTEGRITY_USE_CLASS_UNKNOWN")
    elif use_class == "metadata-index-only":
        # Spec S6/S17: Supabase holds the manifest, never the objects.
        reasons.append("INTEGRITY_USE_CLASS_FORBIDS_OBJECT")
    elif use_class == "human-backup-only" and tier != "HUMAN_BACKUP":
        # Spec S6: backup surfaces, not canonical runtime object stores.
        reasons.append("INTEGRITY_USE_CLASS_FORBIDS_OBJECT")
    elif use_class == "ai-artifacts-only" and \
            record.get("object_class") not in AI_ARTIFACT_OBJECT_CLASSES:
        reasons.append("INTEGRITY_USE_CLASS_FORBIDS_OBJECT")

    served = row.get("tiers_allowed")
    if not isinstance(served, Sequence) or isinstance(served, str) \
            or tier not in served:
        reasons.append("INTEGRITY_TIER_NOT_SERVED")

    # Every placeable tier is a bulk object tier, so a backend that is not one
    # cannot hold an object at all. mesh_validator draws the same line.
    if row.get("bulk_object_backend_allowed") is not True:
        reasons.append("INTEGRITY_BULK_BACKEND_REQUIRED")

    return reasons


def _size_reasons(record, row):
    """Spec S5 position 6, against the provider's own declared bounds."""
    reasons = []
    size = record["size_bytes"]
    limits = row.get("object_size_limits")
    if limits is None:
        return reasons
    if not isinstance(limits, Mapping):
        reasons.append("OBJECT_SIZE_ABOVE_PROVIDER_LIMIT")
        return reasons

    ceiling = limits.get("max_object_bytes")
    if _is_byte_count(ceiling) and size > ceiling:
        reasons.append("OBJECT_SIZE_ABOVE_PROVIDER_LIMIT")
    floor = limits.get("min_object_bytes")
    if _is_byte_count(floor) and size < floor:
        reasons.append("OBJECT_SIZE_BELOW_PROVIDER_LIMIT")
    return reasons


def _evaluate(record, row, *, now):
    """Walk the decision order once and collect every reason to refuse.

    Returns ``(state, reasons)``. Reasons are collected rather than
    short-circuited so a report explains a provider fully, but they are
    produced in spec order, so the first one is always the highest-precedence
    objection.
    """
    reasons = []
    reasons.extend(_privacy_reasons(record, row))          # 1. privacy
    reasons.extend(_integrity_reasons(record, row))        # 2. integrity

    # 3. free-only eligibility. The cost evidence itself - verified free tier,
    # hard stop, spillover, expiry - is the Capacity Broker's quarantine; what
    # is left here is the explicit grant.
    if row.get("autonomous_write_allowed") is not True:
        reasons.append("ZERO_COST_AUTONOMOUS_WRITE_NOT_GRANTED")

    state = capacity.provider_state(row, now=now)           # 4. provider health
    if state not in capacity.WRITABLE_STATES:
        reasons.append("PROVIDER_STATE_NOT_WRITABLE")

    # 5. quota headroom. Spec S14 step 7: the emergency reserve is held for
    # critical evidence, so only a CRITICAL object may see into it.
    if not capacity.admits_write(
            row, record["size_bytes"],
            reserve_exempt=record["criticality"] == "CRITICAL", now=now):
        reasons.append("CAPACITY_HEADROOM_EXHAUSTED")

    reasons.extend(_size_reasons(record, row))             # 6. object size
    return state, reasons


# --- ranking ----------------------------------------------------------------

_HEALTH_RANK = {"FREE": 0, "HEALTHY": 1, "PRESSURED": 2}

#: Spec S8: which residency each criticality prefers. CRITICAL and IMPORTANT
#: want independent provider copies, REPRODUCIBLE wants one durable cloud copy,
#: and all three are best served by a dedicated object store; EPHEMERAL is
#: "cache/local only where possible" and is handled separately below.
_USE_CLASS_RANK = {
    "object-storage": 0,
    "owned-storage": 1,
    "ai-artifacts-only": 2,
    "human-backup-only": 3,
}


def _criticality_fit(record, row):
    """Spec S5 position 2, as an ordering among the providers that survived it."""
    if record["criticality"] == "EPHEMERAL":
        return 0 if row.get("external") is False else 1
    return _USE_CLASS_RANK.get(row.get("acceptable_use_class"), len(_USE_CLASS_RANK))


def _access_frequency_fit(record, row):
    """Spec S5 position 7. The tiers *are* the access-frequency classes (S6)."""
    preferred = row.get("preferred_tiers")
    if isinstance(preferred, Sequence) and not isinstance(preferred, str):
        return 0 if record["storage_tier"] in preferred else 1
    return 1


def _retention_fit(record, row):
    """Spec S5 position 8.

    There is no retention-policy table in the lane yet, so the only honest
    signal is whether the provider's declared retention class is the object's.
    Providers that declare none are neutral rather than penalised.
    """
    declared = row.get("retention_policy_class")
    if declared is None:
        return 1
    return 0 if declared == record.get("retention_class") else 1


def _rank(record, row, state, *, now):
    """The Global Constraints order, as a sort key.

    Positions 1, 3 and 6 are pure gates and appear nowhere here; position 9,
    latency, has no evidence behind it; position 10 is the provider id, which
    is what makes two otherwise-identical providers order the same way on every
    machine, every run.
    """
    return (
        _criticality_fit(record, row),                                   # 2
        _HEALTH_RANK[state],                                             # 4
        -capacity.usable_headroom_bytes(                                 # 5
            row, reserve_exempt=record["criticality"] == "CRITICAL", now=now),
        _access_frequency_fit(record, row),                              # 7
        _retention_fit(record, row),                                     # 8
        row["provider_id"],                                              # 10
    )


# --- public interface -------------------------------------------------------

def _duplicated_ids(providers):
    """Ids claimed by more than one row.

    Two rows claiming one identity make every later statement about "that
    provider" ambiguous - which quota, which health, which free tier - so both
    are refused rather than one of them silently winning.
    """
    seen = {}
    for row in providers:
        if isinstance(row, Mapping):
            provider_id = row.get("provider_id")
            if isinstance(provider_id, str):
                seen[provider_id] = seen.get(provider_id, 0) + 1
    return {provider_id for provider_id, count in seen.items() if count > 1}


def _rows(providers):
    if isinstance(providers, Sequence) and not isinstance(providers, (str, bytes)):
        return list(providers)
    return []


def placement_report(obj, providers, *, now=None):
    """Explain every provider: eligible or not, its state, and why.

    One entry per input row, ordered by displayed identifier so the report is
    as deterministic as the placement it explains. Reasons are drawn only from
    ``EXCLUSION_REASONS``; no value from ``obj`` or from a provider row is ever
    echoed into one.
    """
    rows = _rows(providers)
    placeable = _object_is_placeable(obj)
    duplicated = _duplicated_ids(rows)
    entries = []

    for row in rows:
        display = _display_id(row)
        reasons = []
        if not isinstance(row, Mapping):
            state = "QUARANTINED"
            reasons.append("PROVIDER_NOT_A_RECORD")
        else:
            state = capacity.provider_state(row, now=now)
            if display == UNNAMED_PROVIDER:
                reasons.append("PROVIDER_IDENTIFIER_INVALID")
            elif display in duplicated:
                reasons.append("PROVIDER_IDENTIFIER_DUPLICATED")
            if not placeable:
                reasons.append("OBJECT_NOT_PLACEABLE")
            elif not reasons:
                state, gate_reasons = _evaluate(obj, row, now=now)
                reasons.extend(gate_reasons)
        entries.append({
            "provider_id": display,
            "eligible": not reasons,
            "state": state,
            "reasons": tuple(reasons),
        })

    entries.sort(key=lambda entry: entry["provider_id"])
    return entries


def placement_candidates(obj, providers, *, now=None):
    """Every backend that may legitimately receive this object, best first.

    The returned rows are the rows that were passed in, so a caller can carry
    its own registry metadata through. Nothing is copied and nothing is
    mutated. An object that is not fully described, or a provider set that is
    not a sequence of records, yields an empty list rather than a guess.
    """
    rows = _rows(providers)
    if not _object_is_placeable(obj):
        return []

    duplicated = _duplicated_ids(rows)
    ranked = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        provider_id = row.get("provider_id")
        if not (isinstance(provider_id, str) and _PROVIDER_ID_RE.match(provider_id)):
            continue
        if provider_id in duplicated:
            continue
        state, reasons = _evaluate(obj, row, now=now)
        if reasons:
            continue
        ranked.append((_rank(obj, row, state, now=now), row))

    ranked.sort(key=lambda pair: pair[0])
    return [row for _, row in ranked]


def select_primary(obj, providers, *, now=None):
    """The single backend this object's primary copy should go to, or None.

    ``None`` is a real answer and the common one today: the shipped registry
    has been probed nowhere, so nothing external is admitted, and a mesh that
    cannot honestly place an object says so rather than picking somewhere.
    """
    candidates = placement_candidates(obj, providers, now=now)
    return candidates[0] if candidates else None


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "PAID_STORAGE_ALLOWED", "OVERAGE_ALLOWED", "UNKNOWN_COST_STATE",
    "PLACEMENT_ORDER", "PLACEMENT_PRECEDENCE", "LATENCY_EVIDENCE_AVAILABLE",
    "PRIVACY_CLASSES", "CRITICALITY_CLASSES", "STORAGE_TIERS",
    "NON_PLACEABLE_TIERS", "ACCEPTABLE_USE_CLASSES",
    "AI_ARTIFACT_OBJECT_CLASSES", "ENCRYPTION_ALGORITHMS", "MANIFEST_FIELDS",
    "BULK_OBJECT_THRESHOLD_BYTES", "LOCAL_BACKEND_PREFIX", "UNNAMED_PROVIDER",
    "EXCLUSION_REASONS", "placement_report", "placement_candidates",
    "select_primary",
]
