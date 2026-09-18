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

**A closed key set is not a bound.** The row's field set is the contract's,
and then *every declared field's value* is checked against the type, enum,
pattern or range the schema gives it - nested objects included. Closing the key
set alone bounds which fields exist, not what fits inside them, and an allowed
field whose value nothing bounds is a field wide enough to carry a credential
on every row in the registry. The checkers are ``manifest.py``'s rather than a
third copy of them, and ``PROVIDER_VALUE_CHECKS`` is driven off the schema's
property set by the tests, so a field added to the contract later cannot arrive
unchecked.

**The clock is an input, not a permission.** ``now`` is injectable so that the
answer is reproducible; it is not a boundary and it does not only narrow, since
an instant set in the past un-expires a lapsed free tier. It must come from the
mesh and never from anything being judged. An instant that cannot be resolved
quarantines rather than raising.

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

from AI_SKILL_LIBRARY.v4.storage import PRIVACY_CLASSES as _PRIVACY_CLASSES
from AI_SKILL_LIBRARY.v4.storage import STORAGE_TIERS as _STORAGE_TIERS
from AI_SKILL_LIBRARY.v4.storage import manifest as _manifest

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


def _parse_instant(value):
    """Parse an RFC 3339 instant into an aware datetime, or None.

    Pattern *and* parse. ``9999-99-99T99:99:99Z`` satisfies the pattern and is
    not a moment in any calendar, so a timestamp that is only ever matched is a
    timestamp nothing bounds.
    """
    if not (isinstance(value, str) and _TIMESTAMP_RE.match(value)):
        return None
    try:
        parsed = _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_datetime.timezone.utc)
    return parsed


def _clock(now):
    """Resolve the one clock input, or ``None`` when it cannot be resolved.

    ``now`` is the *evaluation instant*, and it is injectable so that every
    test here and the placement engine get a reproducible answer. Two things
    about it are worth stating plainly, because an earlier version of this
    docstring claimed something false and a reader who believed it would pass a
    caller-supplied ``now`` straight through:

    * it is **not** a permission boundary and it does **not** only narrow. A
      ``now`` set in the past un-expires a free tier that has already lapsed,
      which is a widening. Choosing the instant is a decision the caller owns,
      so the caller must own the instant: ``now`` comes from the mesh, never
      from a registry row, a provider response or anything else being judged;
    * an instant that cannot be resolved is not an instant. It quarantines -
      every state, zero headroom, no write - rather than raising, because Spec
      S14 requires this lane to degrade rather than crash and a broker that
      throws from the middle of a report takes the explanation down with it.
    """
    if now is None:
        return _datetime.datetime.now(_datetime.timezone.utc)
    if isinstance(now, _datetime.datetime):
        return now if now.tzinfo else now.replace(tzinfo=_datetime.timezone.utc)
    return _parse_instant(now)

#: manifest.py already carries correct, bounded, tested checkers for every
#: shape this record uses - class tokens, timestamps, evidence references,
#: bounded integers, and the credential-shape scan over values. capacity.py and
#: placement.py had each grown a weaker copy and dropped bounds along the way,
#: which is how findings 1 to 3 happened. They are *reused* here rather than
#: maintained a third time. Several of them are private to manifest.py and are
#: bound deliberately, at this one site, so the coupling is a single import
#: block a reader can see: manifest.py should export them.
_check_bounded_int = _manifest._check_bounded_int
_check_evidence_ref = _manifest._check_evidence_ref
assert_no_credential_material = _manifest.assert_no_credential_material

#: ``\Z`` rather than ``$`` throughout. Python's ``$`` also matches immediately
#: before a final newline, and JSON Schema's does not, so a mirrored pattern
#: anchored with ``$`` is looser than the contract it claims to mirror. These
#: are manifest.py's patterns, not second copies of them.
_CLASS_TOKEN_RE = _manifest._CLASS_TOKEN_RE
_HEX_TOKEN_RE = _manifest._HEX_TOKEN_RE
_TIMESTAMP_RE = _manifest._TIMESTAMP_RE

#: The closed enums of ``storage_provider.schema.json``. Mirrored here for a
#: stable import-time constant exactly as the package vocabularies are, and
#: ``test_storage_capacity`` walks the schema and asserts every one of them
#: agrees - the drift guard is the test, not the comment.
ADAPTER_TYPES = (
    "local_filesystem", "s3_compatible", "huggingface_hub", "google_drive_api",
    "microsoft_graph_api", "dropbox_api", "supabase_metadata",
)
FREE_STATUSES = (
    "UNVERIFIED", "DOCUMENTED_ONLY", "VERIFIED_FREE", "VERIFIED_RECURRING_FREE",
    "PAID_ONLY", "FREE_EXPIRED", "NOT_APPLICABLE",
)
ACCEPTABLE_USE_CLASSES = (
    "owned-storage", "object-storage", "ai-artifacts-only",
    "human-backup-only", "metadata-index-only",
)
EVIDENCE_CLASSES = (
    "none", "provider_documentation", "runtime_account_evidence",
    "not_applicable",
)

#: The schema's own numeric ceilings, per field rather than one global number:
#: ``requests_per_minute`` stops at a million and an object at a terabyte, and
#: reading them all as "some large int" is how a bound stops being a bound.
_MAX_OBJECT_BYTES = 1099511627776
_MAX_REQUESTS_PER_MINUTE = 1000000


# The bounded-value combinators below are the lane's shared vocabulary rather
# than this module's private one: ``placement.py`` builds its own per-field
# table out of exactly these, because two modules that bound the same shape
# differently are two modules neither of which bounds it. Anything with a
# checked-in checker in ``manifest.py`` is taken from there instead.


def is_bool(value):
    """Exactly ``True`` or ``False``. ``1`` is not a boolean to any validator."""
    return value is True or value is False


def is_class_token(value):
    """At most 40 lower-case characters, and not a long opaque hex run."""
    return (isinstance(value, str) and bool(_CLASS_TOKEN_RE.match(value))
            and not _HEX_TOKEN_RE.match(value))


def is_timestamp(value):
    """RFC 3339 by pattern *and* by parse.

    The pattern alone accepts ``9999-99-99T99:99:99Z``, which is not a moment
    in any calendar; a field checked by regex and never parsed is a field whose
    value nothing bounds.
    """
    return (isinstance(value, str) and bool(_TIMESTAMP_RE.match(value))
            and _parse_instant(value) is not None)


def passes(check, value, *, field):
    """Adapt one of manifest.py's raising checkers to a predicate."""
    try:
        check(value, field=field)
    except ValueError:
        return False
    return True


def nullable(check):
    """The schema writes several fields as ``["integer", "null"]``.

    ``null`` is a declared value and means "unknown"; every caller here already
    treats unknown as a refusal, so it is admitted as a shape and refused as an
    answer. It is not the same as the field being outside its type.
    """
    return lambda value: value is None or check(value)


def string_enum(allowed):
    return lambda value: isinstance(value, str) and value in allowed


def bounded_int(low, high):
    return lambda value: passes(
        lambda v, *, field: _check_bounded_int(v, low, high, field=field),
        value, field="value")


def enum_array(allowed, max_items):
    """An array whose *members* are checked, not merely its membership.

    ``privacy_classes_allowed=["PUBLIC", <2KB>]`` passed a "is the class in the
    list" test every time, because the test read the list and never read what
    was in it.
    """
    def check(value):
        if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (list, tuple)):
            return False
        if len(value) > max_items or len(set(value)) != len(value):
            return False
        return all(isinstance(item, str) and item in allowed for item in value)
    return check


def token_array(max_items):
    def check(value):
        if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (list, tuple)):
            return False
        if len(value) > max_items or len(set(value)) != len(value):
            return False
        return all(is_class_token(item) for item in value)
    return check


def checked_mapping(checks, *, required=()):
    """A nested object: closed key set *and* a checker for every value.

    The key set alone was the whole of the old check, which is the defect this
    module is being fixed for. ``None`` is not admitted: the schema types these
    as objects, and an absent nested object is absent, not null.
    """
    def check(value):
        if not isinstance(value, Mapping):
            return False
        if set(value) - set(checks):
            return False
        if set(required) - set(value):
            return False
        return all(checks[key](nested) for key, nested in value.items())
    return check


def is_provider_id(value):
    """The schema's ``provider_id``: 2 to 64 lower-case, underscore-only.

    Defined once, here, and used by ``placement`` too - a registry key that two
    modules bound differently is a registry key neither of them bounds.
    """
    return isinstance(value, str) and bool(_PROVIDER_ID_RE.match(value))


_PROVIDER_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}\Z")

_EVIDENCE_CHECKS = {
    "evidence_class": string_enum(EVIDENCE_CLASSES),
    "verified_at": is_timestamp,
    "evidence_ref": lambda value: passes(
        _check_evidence_ref, value, field="evidence_ref"),
    "observed_by": is_class_token,
}

_OBJECT_SIZE_LIMIT_CHECKS = {
    field: nullable(bounded_int(0, _MAX_OBJECT_BYTES))
    for field in ("max_object_bytes", "min_object_bytes",
                  "multipart_required_above_bytes")
}

_RATE_LIMIT_CHECKS = {
    "requests_per_minute": nullable(bounded_int(0, _MAX_REQUESTS_PER_MINUTE)),
    "bytes_per_day": nullable(bounded_int(0, _MAX_QUOTA_BYTES)),
    "verified": is_bool,
}

#: Every flag is ``const: false`` in the schema. Denied by name rather than by
#: omission on the record too, so a row cannot declare ``storage_authority:
#: true`` and be admitted by a broker that only checked the key set.
_AUTHORITY_FLAG_CHECKS = {
    flag: lambda value: value is False for flag in AUTHORITY_FLAGS
}


def _is_spillover(value):
    """Tri-state: ``true``, ``false`` or the string ``"unknown"``.

    ``0`` and ``1`` are not booleans here, and anything else is not the enum.
    """
    return value is True or value is False or (
        isinstance(value, str) and value == "unknown")


#: One checker per property of ``storage_provider.schema.json``. A table rather
#: than a run of ``if`` statements so that *completeness is checkable*: the
#: tests walk the schema's property set and assert every one of them has an
#: entry here. This is the fix for the class rather than for the instances -
#: a field added to the contract later cannot arrive unchecked, because the
#: structural test fails the moment the two sets differ.
PROVIDER_VALUE_CHECKS = {
    "provider_id": is_provider_id,
    "adapter_type": string_enum(ADAPTER_TYPES),
    "external": is_bool,
    "free_status": string_enum(FREE_STATUSES),
    "free_status_evidence": checked_mapping(_EVIDENCE_CHECKS,
                                     required=("evidence_class",)),
    "free_expiry_at": nullable(is_timestamp),
    "quota_reset_semantics": is_class_token,
    "quota_total": nullable(bounded_int(0, _MAX_QUOTA_BYTES)),
    "quota_used": nullable(bounded_int(0, _MAX_QUOTA_BYTES)),
    "quota_reserved": nullable(bounded_int(0, _MAX_QUOTA_BYTES)),
    "hard_stop_verified": is_bool,
    "paid_spillover_possible": _is_spillover,
    "privacy_classes_allowed": enum_array(_PRIVACY_CLASSES, 4),
    "encryption_required_classes": enum_array(_PRIVACY_CLASSES, 4),
    "health": string_enum(PROVIDER_STATES),
    "autonomous_write_allowed": is_bool,
    "read_enabled": is_bool,
    "write_enabled": is_bool,
    "bulk_object_backend_allowed": is_bool,
    "tiers_allowed": enum_array(_STORAGE_TIERS, 6),
    "preferred_tiers": enum_array(_STORAGE_TIERS, 6),
    "object_size_limits": checked_mapping(_OBJECT_SIZE_LIMIT_CHECKS),
    "rate_limits": checked_mapping(_RATE_LIMIT_CHECKS),
    "lifecycle_support": token_array(8),
    "retention_policy_class": is_class_token,
    "acceptable_use_class": string_enum(ACCEPTABLE_USE_CLASSES),
    "last_probe_at": nullable(is_timestamp),
    "authority": lambda value: value is False,
    "authority_flags": checked_mapping(_AUTHORITY_FLAG_CHECKS,
                                required=tuple(AUTHORITY_FLAGS)),
}


def _is_record(provider):
    """A mapping shaped like the contract, all the way down.

    Keys exactly the contract's - no more, no fewer - and then *every declared
    field's value* against the type, enum, pattern or range the schema gives
    it, nested objects included. The key set alone was the old check, and a
    closed key set bounds which fields exist, not what fits inside them: an
    allowed field whose value nothing bounds is a field wide enough for a
    credential, and it is the same defect whichever field it is.

    A row that fails any of this is a row that never validated against
    ``storage_provider.schema.json``, and a broker that reasons about one
    anyway is reasoning about a document nobody agreed to.
    """
    if not isinstance(provider, Mapping):
        return False
    keys = set(provider)
    if (keys - PROVIDER_FIELDS) or (REQUIRED_PROVIDER_FIELDS - keys):
        return False
    return all(PROVIDER_VALUE_CHECKS[field](value)
               for field, value in provider.items())


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


def _cost_is_verified_free(provider, clock):
    """Spec S11. Is writing here provably free, for this account, today?

    Owned storage is exempt because nobody bills a disk we already have. Every
    other answer - including "we have not looked" - is no.

    ``clock`` is already resolved. The *shape* of every field read here has
    been settled by ``_is_record``; what is left is the evidence question.
    """
    if clock is None:
        return False

    external = provider.get("external")
    if external is False:
        return True
    # Anything that did not say "this backend is ours" is somebody else's.
    if external is not True:
        return False

    if provider.get("free_status") not in VERIFIED_FREE_STATUSES:
        return False

    evidence = provider.get("free_status_evidence")
    if not isinstance(evidence, Mapping):
        return False
    if evidence.get("evidence_class") != "runtime_account_evidence":
        return False
    # Spec S16/S20: a VERIFIED_* status is reachable only with a dated,
    # referenced observation. Both are optional to the schema and neither is
    # optional here.
    if "verified_at" not in evidence or "evidence_ref" not in evidence:
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
    return parsed > clock


def provider_state(provider, *, now=None):
    """Spec S10: which runtime state this provider row is in.

    Always one of ``PROVIDER_STATES``. Everything unknown, undeclared,
    unprobed, unverified or incoherent is ``QUARANTINED`` - including an
    evaluation instant that cannot be resolved, which refuses rather than
    raises.
    """
    clock = _clock(now)
    if clock is None:
        return "QUARANTINED"
    if not _is_record(provider):
        return "QUARANTINED"

    declared = provider.get("health")
    if declared == "QUARANTINED":
        return "QUARANTINED"

    # A health value with no probe behind it is a claim, not evidence. Matching
    # mesh_validator, which refuses the same pairing in the registry. The
    # timestamp is parsed rather than merely matched, and a probe dated after
    # the evaluation instant is not evidence either: the calendar-impossible
    # ``9999-99-99T99:99:99Z`` and the simply-untrue ``3000-01-01T00:00:00Z``
    # were both accepted as freshness while the field was only pattern-checked.
    # The spec sets no staleness window, so none is invented here; a probe from
    # the past is still a probe.
    probe = _parse_instant(provider.get("last_probe_at"))
    if probe is None or probe > clock:
        return "QUARANTINED"

    if not _cost_is_verified_free(provider, clock):
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
    "PROVIDER_VALUE_CHECKS", "ADAPTER_TYPES", "FREE_STATUSES",
    "ACCEPTABLE_USE_CLASSES", "EVIDENCE_CLASSES", "is_provider_id",
    "is_bool", "is_class_token", "is_timestamp", "passes", "nullable",
    "string_enum", "bounded_int", "enum_array", "token_array",
    "checked_mapping",
    "provider_state", "usable_headroom_bytes", "admits_write",
]
