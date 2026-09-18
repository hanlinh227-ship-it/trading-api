"""Federated Free Storage Mesh - compaction, and the counts it must conserve.

Spec S12 asks the mesh to reduce growth *before* adding providers, and Spec S13
asks it to deduplicate by content hash. Both are ways of removing rows, which
makes this the second module in the lane that can lose data. The first one -
``replication.rebalance_object`` - loses it loudly: an object is gone and
somebody notices. This one loses it quietly. A compaction that drops a run
leaves a number that is simply wrong from then on, and nothing in the system
can tell that it used to be a different number.

So the contract this module is built around is not "fewer rows". It is:

    sum(row["run_count"] for row in aggregate_experience(records, window))
        == len(records)

for every window in the vocabulary, for duplicate rows, for out-of-order rows,
for rows sitting exactly on a window boundary, and for rows that share every
field. Compaction that loses a run is data loss wearing a different hat. The
invariant holds because a record that cannot be validated is *refused* rather
than skipped: skipping is the dangerous option, because a skipped row is a run
that silently never happened.

Four properties, each the answer to a specific way this goes wrong.

**Dedupe is content-addressed, and the content is the whole record.** Two rows
merge when the canonical encodings of their validated forms are identical, and
never otherwise. Not the id, not the name, not the timestamp: a dedupe keyed on
any of those passes a happy-path test and then merges two different runs that
happened to share a key. The digest is computed here; a row arriving with its
own ``content_sha256`` is refused, because a check that consults its subject for
the answer is not a check.

**Every field this module does not explicitly aggregate is part of the group
key.** There is no third category. A field that is neither aggregated nor
grouped would be a field two rows could differ in and still be merged, which is
exactly the silent loss above. The consequence is that the compaction *ratio*
is a property of the data rather than of a field quietly being dropped, and
that is the right way round.

**The field set is closed and every field is bounded.** An experience record is
written by the thing that just ran a prompt, so it is the single most likely
place in this repository for a raw prompt, a chain-of-thought trace or an API
key to arrive. ``policy.yaml`` ``forbidden_content`` names all three. The
defence is shape, not discipline: an unknown field is refused, and every
admitted field is bounded by pattern *and* length, mirroring
``experience_ledger.schema.json`` and tightening it wherever this lane's own
checkers are stricter.

**Nothing leaks through an exception.** The per-field checkers are borrowed from
``manifest.py``, which quite reasonably echoes the offending value into its
error message - useful in a manifest, fatal here, because here the offending
value may *be* the credential. Every validation failure is therefore re-raised
as ``CompactionInputError`` with ``from None``, which drops ``__context__`` so
that the original message cannot reappear in ``traceback.format_exc()``. Unknown
*keys* are counted, never named, because an unknown key is precisely where a
credential arrives as a key.

This module opens no connection, reads no credential, writes no file, deletes
nothing and performs no cryptography beyond hashing its own input to address it.
It returns new lists; the caller with the authority decides what to do with them.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS as _AUTHORITY_FLAG_NAMES
from AI_SKILL_LIBRARY.v4.storage import CANONICAL_AUTHORITY, ROUTED_BY
from AI_SKILL_LIBRARY.v4.storage import manifest as _manifest
from AI_SKILL_LIBRARY.v4.storage import metadata as _metadata

#: No authority of any kind, denied by name rather than by omission.
AUTHORITY = False
AUTHORITY_FLAGS = {flag: False for flag in _AUTHORITY_FLAG_NAMES}

#: This module decides what a compacted row *would* be. It removes nothing,
#: writes nothing and reaches nothing.
PERFORMS_DELETION_HERE = False
PERFORMS_NETWORK_IO_HERE = False
ENCRYPTION_IMPLEMENTED_HERE = False

AGGREGATE_VERSION = 1

#: ``experiences`` is bounded at 10000 items by the ledger schema. Mirrored
#: rather than parsed so that compaction stays a pure function, and asserted
#: against the schema by the tests. A caller with more rows than this chunks
#: them; growing the bound instead is how a "compaction" pass becomes the thing
#: that has to hold the whole ledger in memory.
MAX_INPUT_RECORDS = 10000

#: The widest string any admitted field can hold, which is ``evidence_ref``'s
#: 200-character bound from ``manifest.py``. Nothing this module emits is wider,
#: and the tests assert that rather than trusting it.
MAX_STRING_LENGTH = _manifest._EVIDENCE_REF_MAX

#: Distinct failure classes in one aggregate row. A histogram whose key set is
#: unbounded is an unbounded string store with a respectable name.
MAX_HISTOGRAM_KEYS = 64

#: Evidence references carried forward onto an aggregate. Spec S12 lists
#: ``evidence refs`` among the fields a long-term record keeps; it does not ask
#: for all of them, and an unbounded list of 200-character references is bulk.
MAX_EVIDENCE_REFS = 16

#: Latency in milliseconds, bounded at one day. A run that took longer than a
#: day is a runtime incident, not a latency sample.
MAX_LATENCY_MS = 86400000
MAX_RETRY_COUNT = 1024

#: Schema array bounds, mirrored.
MAX_SKILL_IDS = 32
MAX_PATH_ITEMS = 16

#: Aggregation windows. A closed vocabulary, because "window" is the one
#: parameter that decides which rows are the same row, and a caller that can
#: pass an arbitrary duration can pass one that merges a year.
WINDOWS = ("hour", "day", "week")

_WINDOW_LENGTHS = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(days=7),
}


class CompactionError(RuntimeError):
    """Base class for compaction failures."""


class CompactionInputError(CompactionError, ValueError):
    """A record, a key or a window this module will not work from.

    Raised - never returned, never swallowed into a skipped row - because a
    skipped row is a run that silently never happened, and the count invariant
    is the whole point of the module. Its message names fields and counts and
    never values: the value is the thing that might be the credential.
    """


# --- mirrored patterns --------------------------------------------------------

#: ``\Z`` rather than ``$``. Python's ``$`` also matches immediately before a
#: final newline, so a mirrored pattern using it is *looser* than the schema it
#: mirrors - the bug this lane has already had to fix once. The tests assert
#: these are the schema's own patterns with that one substitution.
_ROLE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*_BRANCH\Z")
_IDENTIFIER_RE = re.compile(r"^@?[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,127}\Z")

_VERIFIER_RESULTS = (True, False, "unknown")
_FEEDBACK_SIGNALS = ("none", "accepted", "rejected", "corrected",
                     "preference_stated")


# --- per-field checkers -------------------------------------------------------


def _check_identifier(value, *, field):
    """The schema's ``identifier``, plus the content rules a pattern cannot make.

    128 characters of ``[A-Za-z0-9_.:/+-]`` is wide enough to hold a base64 key
    with the padding stripped, and this field set carries five of them. The
    length bound alone is therefore not the control; the same two content rules
    ``validate_object_name`` applies - no bare hex run, no credential-shaped
    value - are applied here, at the boundary that would otherwise persist one.
    """
    if not isinstance(value, str) or isinstance(value, bool):
        raise ValueError(f"{field} must be a string identifier")
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(
            f"{field} is not a bounded identifier: at most 128 characters of "
            "[A-Za-z0-9_.:/+-] with an optional leading '@', which excludes "
            "whitespace, '=' and every other shape a KEY=VALUE pair has")
    if _manifest._HEX_TOKEN_RE.match(value):
        raise ValueError(
            f"{field} is a bare hex run, which is indistinguishable from key "
            "material wherever it appears")
    _manifest.assert_no_credential_material(value, where=field)


def _check_role_id(value, *, field):
    if not isinstance(value, str) or not _ROLE_ID_RE.match(value):
        raise ValueError(
            f"{field} must be a role branch id such as 'CODING_BRANCH'; the "
            "canonical list lives in model_mesh/role_branches.yaml and is "
            "matched by shape here rather than copied")
    if len(value) > 64:
        raise ValueError(f"{field} exceeds the 64-character bound")


def _check_nullable_classifier(value, *, field):
    """``failure_class``: a class of failure, never the failure text.

    The schema types it ``["string", "null"]`` and null is meaningful - it is
    how a successful run says "no failure" - so it is the one field here where
    ``None`` is admitted rather than refused. An exception message or a stack
    trace is prose and would carry whatever the caller had in scope, which is
    why the non-null branch goes through the classifier bound.
    """
    if value is None:
        return
    _manifest._check_classifier(value, field=field)


def _check_latency_ms(value, *, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number of milliseconds")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{field} must be a finite number of milliseconds")
    if not 0 <= value <= MAX_LATENCY_MS:
        raise ValueError(f"{field} is outside 0..{MAX_LATENCY_MS}")


def _check_retry_count(value, *, field):
    _manifest._check_bounded_int(value, 0, MAX_RETRY_COUNT, field=field)


def _check_verifier_passed(value, *, field):
    for allowed in _VERIFIER_RESULTS:
        if type(value) is type(allowed) and value == allowed:
            return
    raise ValueError(
        f"{field} must be true, false or the string 'unknown'; 'unknown' is a "
        "third answer rather than a missing one, and collapsing it into false "
        "is how an unverified run becomes a failed one")


def _check_feedback_signal(value, *, field):
    if value not in _FEEDBACK_SIGNALS or isinstance(value, bool):
        raise ValueError(
            f"{field} must be one of {_FEEDBACK_SIGNALS}; feedback is a "
            "normalized signal, never the user's words verbatim")


def _is_array(value):
    """The predicate that admits a container field, stated once.

    ``_admit`` normalises on this same predicate rather than on a narrower
    ``isinstance(value, (list, tuple))``. Normalising on a narrower test than
    the one that *accepted* the value is how a foreign ``Sequence`` subclass
    passes validation and is then carried verbatim into the emitted row, with
    whatever state is attached to it - state that rides on an attribute, where
    ``_encode``, ``validate_aggregate_record`` and any walker that descends only
    dict/list are all blind to it.
    """
    return not isinstance(value, (str, bytes, bytearray)) and isinstance(
        value, Sequence)


def _bounded_array(check, *, max_items, unique=False):
    """A checker that also *returns* the normalised list it admitted.

    Returning the normalisation from the checker is what keeps the admitting
    predicate and the normalising predicate from ever being two different
    predicates again.
    """
    def checker(value, *, field):
        if not _is_array(value):
            raise ValueError(
                f"{field} must be a sequence; a string is iterated one "
                "character at a time, and ``bytes`` is a Sequence too")
        # The bound is checked against the value's own length *before* it is
        # materialised: a foreign Sequence that merely claims to hold a billion
        # entries must be refused, not built.
        if len(value) > max_items:
            raise ValueError(
                f"{field} holds {len(value)} entries, over the {max_items} the "
                "schema allows")
        items = list(value)
        if len(items) > max_items:
            raise ValueError(
                f"{field} materialised {len(items)} entries, over {max_items}")
        if unique and len(set(items)) != len(items):
            raise ValueError(f"{field} repeats an entry")
        for index, item in enumerate(items):
            check(item, field=f"{field}[{index}]")
        return items
    return checker


#: One bounded checker per property of ``experience_ledger.schema.json``'s
#: experience row. A table rather than a run of ``if`` statements so that
#: completeness is *checkable*: the tests walk the schema's property set and
#: assert every one of them has an entry here, and that nothing here is absent
#: from the schema. A field admitted by name and validated by nothing is the
#: hole this lane has now had four times.
#:
#: Where this lane already owns a bounded checker it is bound here by identity
#: rather than restated. ``manifest.py``'s classifier is 40 characters where the
#: ledger schema allows 64, and its evidence reference is 200 where the schema
#: allows 256; the tighter of the two wins, and there is only ever one copy of
#: each rule to drift.
EXPERIENCE_VALUE_CHECKS = {
    "experience_id": _check_identifier,
    "timestamp": _manifest._check_timestamp,
    "request_class": _manifest._check_classifier,
    "role_id": _check_role_id,
    "skill_ids": _bounded_array(_check_identifier, max_items=MAX_SKILL_IDS,
                                unique=True),
    "model_id": _check_identifier,
    "provider_id": _check_identifier,
    "worker_id": _check_identifier,
    "latency_ms": _check_latency_ms,
    "success": _metadata._check_bool,
    "failure_class": _check_nullable_classifier,
    "verifier_passed": _check_verifier_passed,
    "retry_count": _check_retry_count,
    "escalation_path": _bounded_array(_check_identifier,
                                      max_items=MAX_PATH_ITEMS),
    "fallback_path": _bounded_array(_check_identifier,
                                    max_items=MAX_PATH_ITEMS),
    "resource_observation": _manifest._check_classifier,
    "quota_impact": _manifest._check_classifier,
    "user_feedback_signal": _check_feedback_signal,
    "evidence_ref": _manifest._check_evidence_ref,
}

EXPERIENCE_FIELDS = tuple(EXPERIENCE_VALUE_CHECKS)

REQUIRED_EXPERIENCE_FIELDS = ("experience_id", "timestamp", "request_class",
                              "success")

#: --- the partition -----------------------------------------------------------
#:
#: Every property of the schema is in exactly one of the four tables below, and
#: the tests drive that from the schema on disk. A property added to the
#: contract later lands in none of them and fails on the day it is added, rather
#: than becoming a field two different runs can differ in while being merged.

#: The window key. One field, in its own table, because it is neither grouped
#: verbatim nor reduced to a statistic: it is floored to the window and becomes
#: ``period_start``/``period_end``.
WINDOW_FIELDS = {
    "timestamp": (
        "floored to the aggregation window and emitted as period_start/"
        "period_end; the window is start-inclusive and end-exclusive so that a "
        "run sitting exactly on a boundary is counted once and in the window it "
        "opens"),
}

#: Reduced to a statistic, and named here with the statistic it becomes. These
#: are the only fields two rows may differ in and still be merged.
AGGREGATED_FIELDS = {
    "success": "run_count, success_count and success_rate (Spec S12)",
    "verifier_passed": (
        "verifier_pass_count/verifier_fail_count/verifier_unknown_count and "
        "verifier_pass_rate; 'unknown' is counted, never folded into a failure"),
    "latency_ms": "latency_p50 and latency_p95 by nearest rank (Spec S12)",
    "failure_class": "failure_histogram, a bounded count per class (Spec S12)",
    "retry_count": "retry_count_total",
    "evidence_ref": "evidence_refs, a bounded sorted set (Spec S12)",
}

#: Carried through verbatim and part of the group key. Everything the module
#: does not explicitly aggregate is here, which is what makes "two rows that
#: differ in a field nobody aggregates are never merged" true by construction
#: rather than by review.
GROUPING_FIELDS = (
    "request_class", "role_id", "skill_ids", "model_id", "provider_id",
    "worker_id", "escalation_path", "fallback_path", "resource_observation",
    "quota_impact", "user_feedback_signal",
)

#: The other half of the partition, with the reason attached.
REFUSED_FROM_AGGREGATE = {
    "experience_id": (
        "a per-row identifier cannot survive aggregation: carried onto the "
        "group it would name one run as though it described all of them, and "
        "it is the one field in the row that is evidence about nothing once "
        "the row is gone"),
}

#: --- the aggregate row --------------------------------------------------------


def _check_aggregate_version(value, *, field):
    _metadata._check_const(AGGREGATE_VERSION, field=field)(value, field=field)


def _check_aggregate_authority(value, *, field):
    _metadata._check_const(False, field=field)(value, field=field)


def _check_window(value, *, field):
    _manifest._check_enum(value, WINDOWS, field=field)


def _check_lifecycle_state(value, *, field):
    _manifest._check_enum(value, ("AGGREGATED",), field=field)


def _check_count(value, *, field):
    _manifest._check_bounded_int(value, 0, MAX_INPUT_RECORDS, field=field)


def _check_retry_total(value, *, field):
    _manifest._check_bounded_int(
        value, 0, MAX_RETRY_COUNT * MAX_INPUT_RECORDS, field=field)


def _check_rate(value, *, field):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, float):
        raise ValueError(f"{field} must be a float or None")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} {value} is outside 0.0..1.0")


def _check_optional_latency(value, *, field):
    if value is None:
        return
    _check_latency_ms(value, field=field)


def _check_histogram(value, *, field):
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    if len(value) > MAX_HISTOGRAM_KEYS:
        raise ValueError(
            f"{field} holds {len(value)} classes, over the "
            f"{MAX_HISTOGRAM_KEYS} bound; a histogram with an unbounded key set "
            "is an unbounded string store with a respectable name")
    for key, count in value.items():
        _manifest._check_classifier(key, field=f"{field} key")
        _check_count(count, field=f"{field} value")


def _optional(check):
    def checker(value, *, field):
        if value is None:
            return
        check(value, field=field)
    return checker


#: One bounded checker per field of the row this module *emits*, for the same
#: reason the input has one: an output field that is merely "a string" is a slot
#: a later edit can put bulk into, and this row is destined for long-term
#: retention while the raw rows behind it expire.
AGGREGATE_VALUE_CHECKS = {
    "version": _check_aggregate_version,
    "authority": _check_aggregate_authority,
    "lifecycle_state": _check_lifecycle_state,
    "window": _check_window,
    "period_start": _manifest._check_timestamp,
    "period_end": _manifest._check_timestamp,
    "run_count": _check_count,
    "success_count": _check_count,
    "success_rate": _check_rate,
    "verifier_pass_count": _check_count,
    "verifier_fail_count": _check_count,
    "verifier_unknown_count": _check_count,
    "verifier_sample_count": _check_count,
    "verifier_pass_rate": _check_rate,
    "latency_sample_count": _check_count,
    "latency_p50": _check_optional_latency,
    "latency_p95": _check_optional_latency,
    "retry_count_total": _check_retry_total,
    "failure_histogram": _check_histogram,
    "evidence_refs": _bounded_array(_manifest._check_evidence_ref,
                                    max_items=MAX_EVIDENCE_REFS, unique=True),
    "request_class": _optional(_manifest._check_classifier),
    "role_id": _optional(_check_role_id),
    "skill_ids": _optional(EXPERIENCE_VALUE_CHECKS["skill_ids"]),
    "model_id": _optional(_check_identifier),
    "provider_id": _optional(_check_identifier),
    "worker_id": _optional(_check_identifier),
    "escalation_path": _optional(EXPERIENCE_VALUE_CHECKS["escalation_path"]),
    "fallback_path": _optional(EXPERIENCE_VALUE_CHECKS["fallback_path"]),
    "resource_observation": _optional(_manifest._check_classifier),
    "quota_impact": _optional(_manifest._check_classifier),
    "user_feedback_signal": _optional(_check_feedback_signal),
}

AGGREGATE_FIELDS = tuple(AGGREGATE_VALUE_CHECKS)


def validate_aggregate_record(row):
    """Re-check a row this module emitted. Raises ``CompactionInputError``."""
    if not isinstance(row, Mapping):
        raise CompactionInputError("an aggregate row must be a mapping")
    try:
        unknown = len(set(row) - set(AGGREGATE_VALUE_CHECKS))
    except Exception:  # noqa: BLE001 - an unhashable key is an unknown key
        raise CompactionInputError(
            "an aggregate row has a key that cannot be compared") from None
    if unknown:
        raise CompactionInputError(
            f"an aggregate row carries {unknown} unknown field(s); the names "
            "are not echoed, because an unknown key is where a credential "
            "arrives as a key")
    for field, check in AGGREGATE_VALUE_CHECKS.items():
        if field not in row:
            raise CompactionInputError(f"an aggregate row is missing {field}")
        try:
            check(row[field], field=field)
        except Exception:  # noqa: BLE001 - see the module docstring
            raise CompactionInputError(
                f"an aggregate row's {field} is outside its bound") from None
    out = dict(row)
    # The output-side assertion. Every field above passed a bounded checker, and
    # a row can still hold a foreign object that no checker and no string-walker
    # can see, because the payload rides on an attribute rather than in the
    # structure. A row this module emits is a row that round-trips through JSON;
    # anything else is not a row, it is a carrier.
    if json.loads(_encode(out)) != out:
        raise CompactionInputError(
            "an aggregate row does not survive a JSON round-trip; the value is "
            "not echoed")
    return out


# --- input admission ----------------------------------------------------------


def _records(records):
    """The caller's argument as a real list of mappings, or a refusal.

    ``bytes`` is a ``collections.abc.Sequence``, which is how a byte string
    reached a loop expecting records in Task 3; it is refused by name here
    alongside ``str``. A generator is refused too - not out of strictness, but
    because the count invariant is stated against ``len(records)`` and an
    argument that can only be counted by consuming it cannot be checked twice.
    """
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(
            records, Sequence):
        raise CompactionInputError(
            "records must be a list or tuple of mappings; a str or bytes is a "
            "Sequence too and would be walked one element at a time")
    if len(records) > MAX_INPUT_RECORDS:
        raise CompactionInputError(
            f"{len(records)} records is over the {MAX_INPUT_RECORDS} the "
            "ledger schema bounds a batch to; a larger batch is chunked, not "
            "admitted")
    return list(records)


def _admit(record):
    """Validate one experience row and return a fresh, ordered copy.

    Every failure path leaves through ``CompactionInputError`` with
    ``from None``. The borrowed checkers echo the offending value into their
    messages - correct in a manifest, fatal here, where the offending value may
    be the credential - and ``from None`` suppresses ``__context__`` so the
    original cannot reappear in ``traceback.format_exc()``.
    """
    if not isinstance(record, Mapping):
        raise CompactionInputError(
            "an experience record must be a mapping, got "
            f"{type(record).__name__}")
    try:
        unknown = len(set(record) - set(EXPERIENCE_VALUE_CHECKS))
    except Exception:  # noqa: BLE001 - an unhashable key is an unknown key
        raise CompactionInputError(
            "an experience record has a key that cannot be compared; the field "
            "set is closed and the key is not echoed") from None
    if unknown:
        raise CompactionInputError(
            f"an experience record carries {unknown} unknown field(s). The "
            "names are deliberately not echoed: an unknown key is exactly "
            "where a credential or a prompt arrives, as the key rather than as "
            "the value. 'content_sha256' is refused for the same reason - the "
            "digest is computed here or it is not present")
    missing = sorted(set(REQUIRED_EXPERIENCE_FIELDS) - set(record))
    if missing:
        raise CompactionInputError(
            f"an experience record is missing required field(s) {missing}")

    admitted = {}
    for field in EXPERIENCE_FIELDS:
        if field not in record:
            continue
        value = record[field]
        try:
            normalised = EXPERIENCE_VALUE_CHECKS[field](value, field=field)
        except Exception:  # noqa: BLE001 - see this function's docstring
            raise CompactionInputError(
                f"an experience record's {field} is outside the bound the "
                "ledger schema sets for it; the value is not echoed") from None
        # The checker that admitted a container returns the normalised list, so
        # the admitting predicate and the normalising predicate are the same
        # predicate by construction. The belt-and-braces branch below covers a
        # checker that returns nothing, and uses ``_is_array`` - the predicate
        # ``_bounded_array`` admits on - rather than a narrower type test.
        if normalised is None and _is_array(value):
            normalised = list(value)
        admitted[field] = value if normalised is None else normalised
    return admitted


def _encode(record):
    """The canonical encoding a content address is taken over.

    A value that will not serialise leaves through ``CompactionInputError`` like
    every other refusal. A bare ``TypeError`` out of ``json`` would be an
    undeclared exception type from a module that promises exactly one, and the
    value is not echoed because the thing that would not serialise may be the
    thing carrying the credential.
    """
    try:
        return json.dumps(record, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True)
    except Exception:  # noqa: BLE001 - see this function's docstring
        raise CompactionInputError(
            "a record does not survive a JSON round-trip; the value is not "
            "echoed") from None


# --- Spec S13: content dedupe --------------------------------------------------


def dedupe(records):
    """Collapse rows that are the same row, and nothing else (Spec S13).

    Two records merge when the canonical encodings of their validated forms are
    byte-identical. That is the whole rule, and it is deliberately not clever:
    a dedupe keyed on the id, the name or the timestamp will pass a happy-path
    test and then merge two different runs that happened to share a key.

    Returns a new list in first-seen order. Each row is the admitted record plus
    ``content_sha256`` - the address it was grouped by - and ``duplicate_count``,
    which is the only thing this function aggregates. Everything else is
    identical across the group by construction.

    This function proposes nothing and removes nothing from anywhere. A
    duplicate *ingest* of one event is collapsed here; a provider copy of one
    object is a replica and is not this function's business at all (Spec S13:
    "a provider copy counts as a replica, not a duplicate to delete"). Object
    identity in this mesh is already the content digest - ``manifest.py`` builds
    it - so there is no second, looser notion of sameness in this module for an
    object-level caller to reach for.

    Raises ``CompactionInputError`` for anything it will not work from. A
    malformed row is refused rather than skipped: a skipped row is a run that
    silently never happened.
    """
    admitted = [_admit(record) for record in _records(records)]

    order = []
    groups = {}
    for record in admitted:
        digest = hashlib.sha256(_encode(record).encode("utf-8")).hexdigest()
        if digest not in groups:
            groups[digest] = dict(record)
            groups[digest]["content_sha256"] = digest
            groups[digest]["duplicate_count"] = 0
            order.append(digest)
        groups[digest]["duplicate_count"] += 1
    return [groups[digest] for digest in order]


# --- Spec S12: aggregation -----------------------------------------------------

#: Stands in for "this field was absent" inside a group key. A control
#: character cannot appear in any admitted string, so it cannot collide with a
#: real value - and an absent field must not key the same group as a present
#: one, or two rows that differ would be merged.
_ABSENT = "\x00absent"


def _instant(value):
    """An RFC 3339 instant as an aware UTC ``datetime``, or a refusal."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001 - the pattern already passed; this is arithmetic
        raise CompactionInputError(
            "a timestamp passed its pattern and is not a resolvable "
            "instant") from None
    if parsed.tzinfo is None:
        raise CompactionInputError("a timestamp carries no offset")
    return parsed.astimezone(timezone.utc)


def _floor(moment, window):
    """The start of the window containing ``moment``. Start-inclusive."""
    if window == "hour":
        return moment.replace(minute=0, second=0, microsecond=0)
    day = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "day":
        return day
    return day - timedelta(days=day.weekday())


def _iso(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _percentile(samples, quantile):
    """Nearest rank, on a sorted copy. Deterministic and never interpolated.

    Interpolation would invent a latency nobody observed; nearest rank returns
    one that was.
    """
    if not samples:
        return None
    ordered = sorted(samples)
    rank = -(-int(quantile * 100) * len(ordered) // 100)
    return ordered[min(len(ordered) - 1, max(0, rank - 1))]


def _group_key(record, period_start):
    parts = [period_start]
    for field in GROUPING_FIELDS:
        value = record.get(field, _ABSENT)
        parts.append(tuple(value) if _is_array(value) else value)
    try:
        hash(tuple(parts))
    except Exception:  # noqa: BLE001 - an unhashable group key is a refusal
        raise CompactionInputError(
            "a grouping field holds a value that cannot key a group; the value "
            "is not echoed") from None
    return tuple(parts)


def aggregate_experience(records, window):
    """Roll experience rows up by window and by everything not aggregated.

    Spec S12: aggregate by skill, model, role and time window into a long-term
    record carrying ``run_count``, ``success_rate``, ``verifier_pass_rate``,
    latency percentiles, a failure histogram, evidence references and the
    period. The raw rows may then have a short retention while this survives.

    The contract is conservation. ``sum(row["run_count"])`` over the result
    equals ``len(records)``, always: two records merge only when they fall in
    the same window and agree on every field this module does not explicitly
    aggregate, and a record that cannot be validated is refused rather than
    skipped. The compaction ratio is therefore a property of the data and never
    of a field quietly being dropped.

    Returns a new list ordered by period and then by group, so the same input in
    any order gives the same output. Raises ``CompactionInputError`` for an
    unknown window or a record it will not work from.
    """
    if window not in WINDOWS or isinstance(window, bool):
        raise CompactionInputError(
            f"window must be one of {WINDOWS}; the window decides which rows "
            "are the same row, so it is a closed vocabulary rather than a "
            "duration a caller can widen")

    admitted = [_admit(record) for record in _records(records)]

    groups = {}
    for record in admitted:
        moment = _instant(record["timestamp"])
        start = _floor(moment, window)
        key = _group_key(record, _iso(start))
        bucket = groups.get(key)
        if bucket is None:
            bucket = groups[key] = {
                "start": start, "members": [], "record": record}
        bucket["members"].append(record)

    if len(groups) > MAX_INPUT_RECORDS:  # pragma: no cover - bounded by input
        raise CompactionInputError("too many aggregate rows")

    out = []
    for key in sorted(groups, key=lambda k: _encode([str(part) for part in k])):
        bucket = groups[key]
        out.append(_summarise(bucket["members"], bucket["start"], window))
    return out


def _summarise(members, start, window):
    """One aggregate row from the members of one group."""
    run_count = len(members)
    success_count = sum(1 for row in members if row["success"] is True)

    # ``verifier_passed`` is optional in ``experience_ledger.schema.json`` - the
    # required set is only experience_id/timestamp/request_class/success - so a
    # schema-valid row may omit it. A subscript here answers such a row with a
    # bare ``KeyError`` from a module that promises only ``CompactionInputError``.
    verifier_pass = sum(1 for row in members
                        if row.get("verifier_passed") is True)
    verifier_fail = sum(1 for row in members
                        if row.get("verifier_passed") is False)
    verifier_unknown = sum(1 for row in members
                           if row.get("verifier_passed") == "unknown")
    verifier_sample = verifier_pass + verifier_fail

    latencies = [row["latency_ms"] for row in members if "latency_ms" in row]

    histogram = {}
    for row in members:
        failure = row.get("failure_class")
        if failure is None:
            continue
        histogram[failure] = histogram.get(failure, 0) + 1
    if len(histogram) > MAX_HISTOGRAM_KEYS:
        raise CompactionInputError(
            f"a group produced {len(histogram)} distinct failure classes, over "
            f"the {MAX_HISTOGRAM_KEYS} bound; that is a free-text field wearing "
            "a classifier's name")

    refs = sorted({row["evidence_ref"] for row in members if "evidence_ref" in row})

    template = members[0]
    row = {
        "version": AGGREGATE_VERSION,
        "authority": False,
        "lifecycle_state": "AGGREGATED",
        "window": window,
        "period_start": _iso(start),
        "period_end": _iso(start + _WINDOW_LENGTHS[window]),
        "run_count": run_count,
        "success_count": success_count,
        "success_rate": round(success_count / run_count, 6),
        "verifier_pass_count": verifier_pass,
        "verifier_fail_count": verifier_fail,
        "verifier_unknown_count": verifier_unknown,
        "verifier_sample_count": verifier_sample,
        "verifier_pass_rate": (round(verifier_pass / verifier_sample, 6)
                               if verifier_sample else None),
        "latency_sample_count": len(latencies),
        "latency_p50": _percentile(latencies, 0.50),
        "latency_p95": _percentile(latencies, 0.95),
        "retry_count_total": sum(row.get("retry_count", 0) for row in members),
        "failure_histogram": histogram,
        # Spec S12 keeps evidence refs on the long-term record. Bounded, because
        # an unbounded list of 200-character references is bulk, and truncation
        # here loses a pointer rather than a count.
        "evidence_refs": refs[:MAX_EVIDENCE_REFS],
    }
    for field in GROUPING_FIELDS:
        value = template.get(field)
        row[field] = list(value) if _is_array(value) else value
    return validate_aggregate_record(row)


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "PERFORMS_DELETION_HERE", "PERFORMS_NETWORK_IO_HERE",
    "ENCRYPTION_IMPLEMENTED_HERE", "AGGREGATE_VERSION", "MAX_INPUT_RECORDS",
    "MAX_STRING_LENGTH", "MAX_HISTOGRAM_KEYS", "MAX_EVIDENCE_REFS",
    "WINDOWS", "CompactionError", "CompactionInputError",
    "EXPERIENCE_VALUE_CHECKS", "EXPERIENCE_FIELDS",
    "REQUIRED_EXPERIENCE_FIELDS", "GROUPING_FIELDS", "AGGREGATED_FIELDS",
    "WINDOW_FIELDS", "REFUSED_FROM_AGGREGATE", "AGGREGATE_VALUE_CHECKS",
    "AGGREGATE_FIELDS", "validate_aggregate_record", "dedupe",
    "aggregate_experience",
]
