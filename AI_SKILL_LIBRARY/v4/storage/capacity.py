"""Federated Free Storage Mesh - the Capacity Broker.

Spec S10 gives every provider a runtime state, and this module is the single
place that decides which one a registry row is in. It answers three questions
and nothing else:

* ``provider_state`` - which of the seven names in Spec S10 describes this row;
* ``usable_headroom_bytes`` - how many bytes may still be written to it below
  the limits;
* ``admits_write`` - may an object of this size go there at all.

The broker is non-authoritative and subordinate to storage policy. It decides
no placement (that is ``placement.py``), performs no cryptography, activates no
provider account, touches no credential, holds no connection and changes
nothing anywhere. It reads a mapping and returns a string or an integer.

Three design decisions are worth stating, because each one is the answer to a
specific way a "free" mesh acquires a bill.

**Derivation may only narrow.** The row's declared ``health`` is evidence, and
evidence is the ceiling. A row that says NEAR_FULL stays NEAR_FULL however
empty its quota reads; a row that says HEALTHY becomes PRESSURED when its quota
says so. There is no input for which calling this module makes a provider look
better than the registry already said it was. That is what makes the broker
safe to consult from anywhere: it can only ever subtract permission.

**There is no UNKNOWN state, on purpose.** Spec S11 fixes
``UNKNOWN_COST_STATE=QUARANTINE``, and that is read literally and widely here.
An absent field, an enum value nobody defined, a field the contract does not
declare, a health claim with no probe behind it, a free tier that expired, a
free tier with no expiry date that was never shown to be recurring, a spillover
risk nobody ruled out, a hard stop nobody verified, a quota nobody can
compute - each of them is QUARANTINED. "We have not looked" and "we looked and
it is bad" produce the same refusal, which is the only arrangement in which the
first of the two cannot quietly be spent.

**The limits are integer arithmetic.** Spec S10 sets SOFT_LIMIT 80%,
HARD_LIMIT 92% and EMERGENCY_RESERVE 5%. The comparisons are done by scaling to
ten-thousandths and comparing whole numbers, because a threshold that moves
with the last bit of a double is not a threshold. Both limits are inclusive at
the bottom: 80% is PRESSURED, 92% is NEAR_FULL.

The emergency reserve is read as Spec S14 step 7 describes it - capacity held
back for critical evidence. The write ceiling is the hard limit; the last 5%
below that ceiling is visible only to a CRITICAL object. It is never a door
past the ceiling, and no reading of it admits paid usage, which is the point:
PAID_STORAGE_ALLOWED and OVERAGE_ALLOWED are false and nothing here can make
them anything else.
"""

from __future__ import annotations

import datetime as _datetime
import re
from collections.abc import Mapping

#: This module holds no authority of any kind. Denied by name rather than by
#: omission, so a later edit cannot acquire one by adding a key.
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

#: Spec S11. Stated here so that a reader of this module does not have to take
#: the rest of the lane on trust.
PAID_STORAGE_ALLOWED = False
OVERAGE_ALLOWED = False
UNKNOWN_COST_STATE = "QUARANTINE"

#: Spec S10, in the spec's own order.
PROVIDER_STATES = (
    "FREE", "HEALTHY", "PRESSURED", "NEAR_FULL", "READ_ONLY", "QUARANTINED",
    "OFFLINE",
)

#: How much permission each state carries, least restrictive first. Used to
#: combine a declared state with a derived one by taking the worse of the two.
_SEVERITY = {
    "FREE": 0,
    "HEALTHY": 1,
    "PRESSURED": 2,
    "NEAR_FULL": 3,
    "READ_ONLY": 4,
    "OFFLINE": 5,
    "QUARANTINED": 6,
}

#: policy.yaml ``writable_provider_health_states``. PRESSURED is the warning
#: state and stays writable; NEAR_FULL sits at the hard limit and does not.
WRITABLE_STATES = frozenset({"FREE", "HEALTHY", "PRESSURED"})

#: Spec S16/S20: the only two statuses runtime account evidence can produce,
#: and therefore the only two that mean anything.
VERIFIED_FREE_STATUSES = frozenset({"VERIFIED_FREE", "VERIFIED_RECURRING_FREE"})
RECURRING_FREE_STATUS = "VERIFIED_RECURRING_FREE"

#: policy.yaml ``capacity``. Mirrored for a stable import-time constant exactly
#: as the package enums are; ``test_storage_capacity`` asserts they agree.
SOFT_LIMIT_RATIO = 0.80
HARD_LIMIT_RATIO = 0.92
EMERGENCY_RESERVE_RATIO = 0.05

_SCALE = 10000
_SOFT_LIMIT_SCALED = 8000
_HARD_LIMIT_SCALED = 9200
_EMERGENCY_RESERVE_SCALED = 500

#: storage_provider.schema.json is ``additionalProperties: false``, so a row
#: carrying a key that is not here never validated against the contract. This
#: is also the credential gate: an unbounded string can only enter a provider
#: record through a field nobody declared, so a row carrying one is refused
#: before any value is read.
PROVIDER_FIELDS = frozenset({
    "provider_id", "adapter_type", "external", "free_status",
    "free_status_evidence", "free_expiry_at", "quota_reset_semantics",
    "quota_total", "quota_used", "quota_reserved", "hard_stop_verified",
    "paid_spillover_possible", "privacy_classes_allowed",
    "encryption_required_classes", "health", "autonomous_write_allowed",
    "read_enabled", "write_enabled", "bulk_object_backend_allowed",
    "tiers_allowed", "preferred_tiers", "object_size_limits", "rate_limits",
    "lifecycle_support", "retention_policy_class", "acceptable_use_class",
    "last_probe_at", "authority", "authority_flags",
})

#: The schema's ``required`` list. A row missing one of these never validated
#: against the contract either, and the missing field is always one that
#: decides privacy or cost - which privacy classes are admitted, whether the
#: free tier was verified, whether a hard stop exists. Absent is not permissive.
REQUIRED_PROVIDER_FIELDS = frozenset({
    "provider_id", "adapter_type", "external", "free_status",
    "free_status_evidence", "quota_total", "quota_used", "hard_stop_verified",
    "paid_spillover_possible", "privacy_classes_allowed",
    "encryption_required_classes", "health", "autonomous_write_allowed",
    "authority", "authority_flags",
})

#: The closed field sets of the schema's nested objects. A key outside one of
#: these never validated either, and a nested object is the obvious second
#: place to try hiding an undeclared string once the top level refuses one.
_EVIDENCE_FIELDS = frozenset({
    "evidence_class", "verified_at", "evidence_ref", "observed_by",
})
_OBJECT_SIZE_LIMIT_FIELDS = frozenset({
    "max_object_bytes", "min_object_bytes", "multipart_required_above_bytes",
})
_RATE_LIMIT_FIELDS = frozenset({"requests_per_minute", "bytes_per_day", "verified"})
_AUTHORITY_FLAG_FIELDS = frozenset(AUTHORITY_FLAGS)

#: The provider record's free-form string fields, as opposed to its enums. Each
#: one is a ``class_token`` in the schema: at most 40 characters, lower-case,
#: and explicitly not a long hex run. They are checked here because an allowed
#: *unbounded* string is how a credential gets into a record that otherwise has
#: no field wide enough to hold one.
_CLASS_TOKEN_FIELDS = ("quota_reset_semantics", "retention_policy_class")
_CLASS_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,39}\Z")
_HEX_TOKEN_RE = re.compile(r"^[0-9a-f]{16,}\Z")

#: ``\Z`` rather than ``$`` throughout. Python's ``$`` also matches immediately
#: before a final newline, and JSON Schema's does not, so a mirrored pattern
#: anchored with ``$`` is looser than the contract it claims to mirror.
_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"([.][0-9]{1,9})?(Z|[+-][0-9]{2}:[0-9]{2})\Z")

#: The schema caps an evidence reference at 200 characters. The second
#: alternative is quantified rather than left open: ``[A-Za-z0-9._/-]`` is a
#: superset of URL-safe base64 and of hex, so an unbounded run there is a field
#: that can carry a key. Bounded here and length-checked below.
_EVIDENCE_REF_MAX = 200
_EVIDENCE_REF_RE = re.compile(
    r"^(?:[a-z][a-z0-9+.-]{1,31}://[A-Za-z0-9][A-Za-z0-9._~:/-]{2,180}"
    r"|[A-Za-z0-9][A-Za-z0-9._/-]{0,150}/[A-Za-z0-9][A-Za-z0-9._-]{0,60}"
    r"[.][A-Za-z0-9]{1,16})\Z")

#: The largest quota the schema will hold, so an absurd number is refused here
#: too rather than turning into an absurd amount of headroom.
_MAX_QUOTA_BYTES = 1125899906842624

_MISSING = object()

#: What ``_quota`` reports when the numbers are absent, and when they are
#: present but cannot be true. The two are different: an unknown quota is a
#: cost risk only where somebody could send a bill, while an impossible one is
#: a broken record wherever it appears.
_UNKNOWN = object()
_INCOHERENT = object()


def _is_byte_count(value):
    """A whole, non-negative number of bytes - and not a bool.

    ``bool`` subclasses ``int`` in Python, so ``True`` would otherwise read as
    one byte used and sail through every numeric check below it.
    """
    return (isinstance(value, int) and not isinstance(value, bool)
            and 0 <= value <= _MAX_QUOTA_BYTES)


def _valid_timestamp(value):
    return isinstance(value, str) and bool(_TIMESTAMP_RE.match(value))


def _parse_instant(value):
    """Parse an RFC 3339 instant into an aware datetime, or None."""
    if not _valid_timestamp(value):
        return None
    try:
        parsed = _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_datetime.timezone.utc)
    return parsed


def _now(now):
    """The one clock input, and it is injectable.

    The free-tier expiry check is the only time-dependent decision in the
    broker, and it can only ever narrow: a date in the past withdraws a
    permission, it never grants one. Callers that need a reproducible answer -
    every test here, and the placement engine - pass ``now`` explicitly.
    """
    if now is None:
        return _datetime.datetime.now(_datetime.timezone.utc)
    if isinstance(now, _datetime.datetime):
        return now if now.tzinfo else now.replace(tzinfo=_datetime.timezone.utc)
    parsed = _parse_instant(now)
    if parsed is None:
        raise ValueError("now must be an RFC 3339 instant or a datetime")
    return parsed


def _is_class_token(value):
    """At most 40 lower-case characters, and not a long opaque hex run."""
    return (isinstance(value, str) and bool(_CLASS_TOKEN_RE.match(value))
            and not _HEX_TOKEN_RE.match(value))


def _closed(value, fields):
    """A nested object is absent, or a mapping with no key outside ``fields``."""
    if value is None:
        return True
    return isinstance(value, Mapping) and not (set(value) - fields)


def _is_record(provider):
    """A mapping shaped like the contract, all the way down.

    Keys exactly the contract's - no more, no fewer - nested objects closed the
    same way, and every free-form string bounded. A row that fails any of these
    is a row that never validated against ``storage_provider.schema.json``, and
    a broker that reasons about one anyway is reasoning about a document nobody
    agreed to.
    """
    if not isinstance(provider, Mapping):
        return False
    keys = set(provider)
    if (keys - PROVIDER_FIELDS) or (REQUIRED_PROVIDER_FIELDS - keys):
        return False

    if not _closed(provider.get("object_size_limits"), _OBJECT_SIZE_LIMIT_FIELDS):
        return False
    if not _closed(provider.get("rate_limits"), _RATE_LIMIT_FIELDS):
        return False
    if not _closed(provider.get("authority_flags"), _AUTHORITY_FLAG_FIELDS):
        return False

    for field in _CLASS_TOKEN_FIELDS:
        value = provider.get(field)
        if value is not None and not _is_class_token(value):
            return False
    support = provider.get("lifecycle_support")
    if support is not None:
        if isinstance(support, str) or not isinstance(support, (list, tuple)):
            return False
        if not all(_is_class_token(item) for item in support):
            return False
    return True


def _quota(provider):
    """Return ``(total, committed)``, or ``_UNKNOWN`` / ``_INCOHERENT``.

    ``committed`` is used plus reserved: reserved bytes are spoken for, so a
    provider at 50% used and 40% reserved has 90% of its quota committed.
    """
    reserved = provider.get("quota_reserved")
    if reserved is None:
        reserved = 0
    if not _is_byte_count(reserved):
        return _INCOHERENT

    total = provider.get("quota_total", _MISSING)
    used = provider.get("quota_used", _MISSING)
    if total is _MISSING or used is _MISSING or total is None or used is None:
        return _UNKNOWN
    if not _is_byte_count(total) or not _is_byte_count(used):
        return _INCOHERENT
    if total <= 0:
        return _INCOHERENT

    committed = used + reserved
    if committed > total:
        return _INCOHERENT
    return total, committed


def _cost_is_verified_free(provider, now):
    """Spec S11. Is writing here provably free, for this account, today?

    Owned storage is exempt because nobody bills a disk we already have. Every
    other answer - including "we have not looked" - is no.
    """
    external = provider.get("external")
    if external is False:
        return True
    # Anything that did not say "this backend is ours" is somebody else's.
    if external is not True:
        return False

    if provider.get("free_status") not in VERIFIED_FREE_STATUSES:
        return False

    evidence = provider.get("free_status_evidence")
    if not _closed(evidence, _EVIDENCE_FIELDS) or evidence is None:
        return False
    observed_by = evidence.get("observed_by")
    if observed_by is not None and not _is_class_token(observed_by):
        return False
    if evidence.get("evidence_class") != "runtime_account_evidence":
        return False
    if not _valid_timestamp(evidence.get("verified_at")):
        return False
    ref = evidence.get("evidence_ref")
    if not isinstance(ref, str) or len(ref) > _EVIDENCE_REF_MAX \
            or not _EVIDENCE_REF_RE.match(ref):
        return False

    if provider.get("hard_stop_verified") is not True:
        return False
    # Spec S11 BILLABLE_SPILLOVER_UNVERIFIED=NO_AUTONOMOUS_WRITE. "unknown" and
    # True land in the same place.
    if provider.get("paid_spillover_possible") is not False:
        return False

    expiry = provider.get("free_expiry_at", _MISSING)
    if expiry is _MISSING:
        return False
    if expiry is None:
        # Spec S11 FREE_EXPIRY_UNKNOWN=NO_AUTONOMOUS_WRITE unless the provider
        # is known recurring-free. "Free today, no idea about tomorrow" is not
        # a free tier one may plan a mesh around.
        return provider.get("free_status") == RECURRING_FREE_STATUS
    parsed = _parse_instant(expiry)
    if parsed is None:
        return False
    return parsed > _now(now)


def provider_state(provider, *, now=None):
    """Spec S10: which runtime state this provider row is in.

    Always one of ``PROVIDER_STATES``. Everything unknown, undeclared,
    unprobed, unverified or incoherent is ``QUARANTINED``.
    """
    if not _is_record(provider):
        return "QUARANTINED"

    declared = provider.get("health")
    if declared not in PROVIDER_STATES:
        return "QUARANTINED"
    if declared == "QUARANTINED":
        return "QUARANTINED"

    # A health value with no probe behind it is a claim, not evidence. Matching
    # mesh_validator, which refuses the same pairing in the registry.
    if not _valid_timestamp(provider.get("last_probe_at")):
        return "QUARANTINED"

    if not _cost_is_verified_free(provider, now):
        return "QUARANTINED"

    quota = _quota(provider)
    if quota is _INCOHERENT:
        return "QUARANTINED"
    if quota is _UNKNOWN and provider.get("external") is not False:
        return "QUARANTINED"

    # The declared state is the ceiling; everything below can only add a worse
    # candidate to the list, never a better one.
    candidates = [declared]

    if quota is not _UNKNOWN:
        total, committed = quota
        scaled = committed * _SCALE
        if scaled >= total * _HARD_LIMIT_SCALED:
            candidates.append("NEAR_FULL")
        elif scaled >= total * _SOFT_LIMIT_SCALED:
            candidates.append("PRESSURED")

    # A backend nobody says is readable is one from which no copy can be hash-
    # verified (Spec S15) and no replica can be served after a failure (Spec
    # S19). That is not a write-only store, it is a store with no evidence path.
    if provider.get("read_enabled") is not True:
        candidates.append("OFFLINE")
    elif provider.get("write_enabled") is not True:
        candidates.append("READ_ONLY")

    return max(candidates, key=_SEVERITY.__getitem__)


def usable_headroom_bytes(provider, *, reserve_exempt=False, now=None):
    """Bytes still writable below the limits. Zero whenever that is unknowable.

    The ceiling is the hard limit. Below it, ``EMERGENCY_RESERVE_RATIO`` of the
    quota is withheld from ordinary objects and shown only to CRITICAL evidence
    (Spec S14 step 7), which is what ``reserve_exempt`` selects. The reserve is
    carved out below the ceiling, never above it, so a CRITICAL object gets
    earlier access to the same capacity - not more of it.
    """
    if provider_state(provider, now=now) not in WRITABLE_STATES:
        return 0
    quota = _quota(provider)
    if quota is _UNKNOWN or quota is _INCOHERENT:
        return 0
    total, committed = quota
    ceiling = total * _HARD_LIMIT_SCALED // _SCALE
    reserve = 0 if reserve_exempt else total * _EMERGENCY_RESERVE_SCALED // _SCALE
    return max(0, ceiling - reserve - committed)


def admits_write(provider, size_bytes, *, reserve_exempt=False, now=None):
    """May an object of exactly this size be written here right now?

    Not "is there room somewhere" - this provider, this object, this moment.
    A size that is not a whole non-negative number of bytes is not a size.
    """
    if not _is_byte_count(size_bytes):
        return False
    if not _is_record(provider):
        return False
    if provider.get("autonomous_write_allowed") is not True:
        return False
    if provider_state(provider, now=now) not in WRITABLE_STATES:
        return False

    quota = _quota(provider)
    if quota is _INCOHERENT:
        return False
    if quota is _UNKNOWN:
        # An unknown quota is a *cost* risk only where somebody could send a
        # bill. mesh_validator draws the line in the same place; drawing it
        # anywhere else would leave the local cache Spec S6 relies on with no
        # admissible home anywhere in the mesh.
        return provider.get("external") is False

    return usable_headroom_bytes(
        provider, reserve_exempt=reserve_exempt, now=now) >= size_bytes


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "PAID_STORAGE_ALLOWED", "OVERAGE_ALLOWED", "UNKNOWN_COST_STATE",
    "PROVIDER_STATES", "WRITABLE_STATES", "VERIFIED_FREE_STATUSES",
    "RECURRING_FREE_STATUS", "SOFT_LIMIT_RATIO", "HARD_LIMIT_RATIO",
    "EMERGENCY_RESERVE_RATIO", "PROVIDER_FIELDS", "REQUIRED_PROVIDER_FIELDS",
    "provider_state", "usable_headroom_bytes", "admits_write",
]
