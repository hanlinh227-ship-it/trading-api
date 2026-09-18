"""Federated Free Storage Mesh - the pressure response, as ordered gates.

Spec S14 lists eight responses to storage pressure and then, in case the list
read as advice, states the point of the list: **the system must degrade instead
of crashing**. Three of those eight steps can destroy data, which makes this the
module in the lane with the most ways to be quietly wrong.

**This module proposes; it does not perform.** ``lifecycle_actions`` returns
``Action`` values. It opens no connection, writes no file, calls no method on
the metadata store it is handed, and removes nothing from anywhere. Returning an
``Action`` is not executing one. The distinction is meant to be visible rather
than implied: ``PERFORMS_DELETION_HERE`` is ``False``, every ``Action`` carries
``proposal_only`` and the destructive ones carry ``requires_authorization``, and
the only thing this module does with a ``MetadataStore`` is ask
``can_perform_destructive_lifecycle`` whether the index is certain enough for
somebody *else* to act.

**The eight steps are gates, not weights.** ``PRESSURE_STEPS`` is Spec S14's
list in Spec S14's order, and the rule is that the first step with anything to
propose is the only step that proposes. A later step never runs before an
earlier one is exhausted, and no amount of pressure reorders them: pressure is
part of a step's *trigger*, never part of a comparison between steps. This is
``placement.py``'s shape - an ordered run of gates rather than a score - and for
the same reason: a weighting can be tuned until capacity outranks integrity,
and an ordered gate cannot.

**A CRITICAL object is never capacity-deleted.** Not at NEAR_FULL, not in
degraded mode, not when every provider is full. The classes that may never be
deleted for capacity are read from ``policy.yaml``
(``auto_delete_for_capacity: false``, which covers IMPORTANT as well as
CRITICAL) rather than mirrored here, and the rule is enforced twice: inside the
destructive steps, and again as a post-condition over everything the steps
returned. The second one is not redundancy for its own sake - it is the check
that still holds if a step is added later by somebody who has not read this
paragraph.

**A claim is not a copy.** Spec S15 step 7 asks for the final replica count to
be *verified*. A record's own ``replica_backends`` is a claim: the mesh
registered those backends at some point and nothing has looked since. Task 5 was
found deleting on the strength of that claim. This module cannot look - it
performs no I/O - so it does not guess: the caller passes ``confirmed_copies``,
the ``{object_id: {backend_id}}`` mapping that something which *can* look has
already head-verified, and without it no deletion is ever proposed. An absent
fact is never permission.

**Uncertain evidence fails closed**, as ``policy.yaml`` requires
(``destructive_action_on_uncertain_evidence: FAIL_CLOSED``, Spec S18). An absent
or unhealthy metadata store, a malformed record, a provider whose state does not
resolve, an evaluation instant that will not parse, a missing or unparseable
``last_verified_at`` - each one on its own stops every destructive proposal.

**Nothing here raises.** A function that decides how to respond to exhaustion is
a function called on the worst day, and one that can raise is one whose caller
has to remember to catch. ``lifecycle_actions`` returns a list for every input in
the universe, including the ones that are not objects, not providers and not
mappings.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence, Set
from types import MappingProxyType
from typing import ClassVar

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS as _AUTHORITY_FLAG_NAMES
from AI_SKILL_LIBRARY.v4.storage import (
    CANONICAL_AUTHORITY,
    CRITICALITY_CLASSES,
    ROUTED_BY,
)
from AI_SKILL_LIBRARY.v4.storage import capacity as _capacity
from AI_SKILL_LIBRARY.v4.storage import mesh_validator as _mesh_validator
from AI_SKILL_LIBRARY.v4.storage import metadata as _metadata
from AI_SKILL_LIBRARY.v4.storage import replication as _replication

#: No authority of any kind, denied by name rather than by omission.
AUTHORITY = False
AUTHORITY_FLAGS = {flag: False for flag in _AUTHORITY_FLAG_NAMES}

#: The declaration the rest of this module is built to make true.
PROPOSAL_ONLY = True
PERFORMS_DELETION_HERE = False
PERFORMS_NETWORK_IO_HERE = False
ENCRYPTION_IMPLEMENTED_HERE = False

#: An EPHEMERAL object untouched for longer than this has outlived its purpose
#: (Spec S8: "TTL expiration"). One day, stated once here rather than derived
#: from a per-object field, because no manifest field carries a TTL and
#: inventing one from ``retention_class`` would be reading a policy decision out
#: of a classifier.
EPHEMERAL_TTL_SECONDS = 86400

#: Bounds. A pressure response that can return an unbounded list is a pressure
#: response that can exhaust the thing it was called to protect.
MAX_OBJECTS = 4096
MAX_PROVIDERS = 256
MAX_ACTIONS = 4096
MAX_ACTION_BYTES = 1024

#: Object classes whose growth Spec S14 step 2 answers with compaction rather
#: than with deletion. A closed vocabulary: "compact whatever looks like a log"
#: is how a benchmark bundle gets aggregated into a rate.
TELEMETRY_OBJECT_CLASSES = frozenset({
    "telemetry", "telemetry-summary", "experience", "experience-ledger",
    "learning-experience", "replay-bundle",
})

#: Lifecycle states from which compaction still has somewhere to go (Spec S12).
COMPACTABLE_STATES = frozenset({"RAW", "SANITIZED", "DEDUPED"})

#: ...and from which compression does.
COMPRESSIBLE_STATES = frozenset({"RAW", "SANITIZED", "DEDUPED", "AGGREGATED"})

#: Tiers whose contents are not this module's to move. CANONICAL lives in
#: GitHub and METADATA is the index; neither is bulk object data (Spec S6).
IMMOVABLE_TIERS = frozenset({"CANONICAL", "METADATA"})

ACTION_KINDS = (
    # The one destructive kind. Singular on purpose: one word to grep for, one
    # guard to write, and no second spelling for a reviewer to miss.
    "DELETE",
    "COMPACT",
    "COMPRESS",
    "REBALANCE",
    "PAUSE_NON_CRITICAL_LEARNING_WRITES",
    "RESERVE_CAPACITY_FOR_CRITICAL",
    "ENTER_DEGRADED_READ_ONLY",
    # Not one of the eight: the answer when a record cannot be read at all.
    "HOLD_UNCERTAIN_RECORD",
)

DESTRUCTIVE_KINDS = frozenset({"DELETE"})

#: A closed vocabulary. A reason assembled from the input would be a string
#: field with no bound, sitting in the one structure that gets logged.
REASONS = (
    "EPHEMERAL_TTL_ELAPSED",
    "REDUNDANT_REPRODUCIBLE_COPY",
    "TELEMETRY_COMPACTION_AVAILABLE",
    "COLD_EVIDENCE_UNCOMPRESSED",
    "PROVIDER_UNDER_PRESSURE",
    "NON_CRITICAL_WRITES_PAUSED",
    "EMERGENCY_RESERVE_FOR_CRITICAL",
    "NO_SAFE_FREE_CAPACITY_REMAINS",
    "MALFORMED_RECORD",
)


# --- which classes may never be deleted for capacity ---------------------------


def _never_capacity_deleted():
    """Read from ``policy.yaml`` rather than mirrored as a literal.

    ``criticality.CRITICAL.auto_delete_for_capacity`` is ``false`` and so is
    IMPORTANT's; REPRODUCIBLE carries ``evictable_under_capacity_pressure`` and
    EPHEMERAL carries ``ttl_expiry``. A second statement of those four facts is
    a second statement to drift, and the looser of the two would be the one a
    deletion consults.

    Everything unknown is in the never-delete set: a class the policy does not
    describe, a policy that will not load, a value that is not the boolean it
    should be. Over-stating the protection retains data nobody needed;
    under-stating it deletes data somebody did.
    """
    try:
        declared = _mesh_validator.load_policy().get("criticality") or {}
    except Exception:  # noqa: BLE001 - an unreadable policy is not a permission
        return frozenset(CRITICALITY_CLASSES)
    never = set()
    for name in CRITICALITY_CLASSES:
        rules = declared.get(name)
        if not isinstance(rules, Mapping):
            never.add(name)
            continue
        if rules.get("auto_delete_for_capacity") is False:
            never.add(name)
            continue
        if rules.get("evictable_under_capacity_pressure") is True:
            continue
        if rules.get("ttl_expiry") is True:
            continue
        never.add(name)
    return frozenset(never)


NEVER_CAPACITY_DELETED = _never_capacity_deleted()


# --- the structural guard ------------------------------------------------------
#
# Every property of ``storage_object_manifest.schema.json`` is either read by a
# decision below, with the checker ``metadata.py`` already wrote for it, or in
# ``IGNORED_MANIFEST_FIELDS`` with the reason a lifecycle decision must not
# consult it. The tests drive that partition from the schema on disk, so a
# property added to the contract later is in neither table and fails on the day
# it is added - rather than becoming a field this module silently does not read
# while deciding whether to delete something.

_DECISION_FIELD_NAMES = (
    "object_id",
    "criticality",
    "reproducible",
    "lifecycle_state",
    "storage_tier",
    "privacy_class",
    "object_class",
    "size_bytes",
    "primary_backend",
    "replica_backends",
    "created_at",
    "last_accessed_at",
    "last_verified_at",
    "verification",
)

#: Bound by identity to ``metadata.py``'s table rather than restated. A sixth
#: independently-written copy of "what a bounded timestamp looks like" is a copy
#: that will drift, and the looser of the two is the one a deletion gets to use.
DECISION_VALUE_CHECKS = {
    field: _metadata._RECORD_FIELD_CHECKS[field]
    for field in _DECISION_FIELD_NAMES
}

DECISION_FIELDS = tuple(DECISION_VALUE_CHECKS)

IGNORED_MANIFEST_FIELDS = {
    "version": (
        "the record format's version is checked by the validator that admitted "
        "the record; a lifecycle decision that branched on it would be a second "
        "migration path nobody maintains"),
    "authority": (
        "a manifest record asserts no authority, and a decision that read one "
        "from a record would be taking permission from the thing being decided "
        "about (Spec S2)"),
    "authority_flags": (
        "the eight authorities are denied by name in every record; reading them "
        "here would imply there is a value of them that unlocks something, and "
        "there is not"),
    "content_sha256": (
        "the digest is object identity and is already carried by object_id; "
        "nothing in the pressure response is decided by the content of an "
        "object, only by its class, age and confirmed copies"),
    "encryption_state": (
        "whether an object is ciphertext does not change whether it may be "
        "expired, evicted, compressed or moved; treating encryption as a "
        "lifecycle exemption is how ciphertext becomes undeletable clutter"),
    "encryption_scheme_version": (
        "a scheme version is an encryption-contract concern owned elsewhere, "
        "and reading it here would be this module having an opinion about "
        "cryptography it does not implement"),
    "encryption": (
        "encryption metadata carries key_ref, nonce and tag. Spec S22 keeps key "
        "material away from everything that is logged, and a proposal is "
        "exactly the sort of structure that gets logged"),
    "mime_type": (
        "the media type describes the payload, and no step of Spec S14 is "
        "selected by payload type; a decision that read it would be classifying "
        "content this module deliberately never looks at"),
    "retention_class": (
        "a free-form classifier is not a duration, and reading a TTL out of one "
        "would be inventing a policy number from a label - EPHEMERAL_TTL_SECONDS "
        "is stated here instead, in the open"),
    "source_provenance": (
        "provenance names a producer and an evidence reference; who made an "
        "object is not evidence about whether a copy of it may be removed, and "
        "an opaque reference in a proposal is a pointer somebody can follow"),
}


# --- the proposal --------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Action:
    """One proposed response. A value, never a call.

    Nothing in this class performs anything: there is no ``apply``, no
    ``execute`` and no handle to a store or a provider. ``destructive`` says
    whether carrying it out would remove data and ``requires_authorization``
    says that the caller doing so needs explicit authorization and the
    applicable project policy first. Both are stated on the value rather than
    inferred from ``kind`` by the reader.
    """

    step: int
    kind: str
    object_id: "str | None"
    provider_id: "str | None"
    reason: str
    destructive: bool
    requires_authorization: bool
    evidence: Mapping

    #: Not a field: it is a property of the type, and a caller must not be able
    #: to construct one that claims otherwise.
    proposal_only: ClassVar[bool] = True

    def __post_init__(self):
        object.__setattr__(self, "evidence",
                           MappingProxyType(dict(self.evidence)))

    def as_dict(self):
        return {
            "step": self.step,
            "kind": self.kind,
            "object_id": self.object_id,
            "provider_id": self.provider_id,
            "reason": self.reason,
            "destructive": self.destructive,
            "requires_authorization": self.requires_authorization,
            "proposal_only": True,
            "evidence": dict(self.evidence),
        }


# --- admission -----------------------------------------------------------------


def _records(objects):
    """``(validated records, indices that could not be read)``.

    A record that will not validate is not skipped and not guessed at: it comes
    back as an index, and the caller sees a ``HOLD_UNCERTAIN_RECORD``. Skipping
    is the dangerous option - a record nobody could read is exactly the record
    whose criticality nobody knows.

    ``bytes`` is a ``collections.abc.Sequence``; it is refused by name here
    alongside ``str``, because a byte string walked one element at a time was a
    real bug in Task 3.
    """
    if isinstance(objects, (str, bytes, bytearray)) or not isinstance(
            objects, Sequence):
        return [], []
    good = []
    held = []
    for index, record in enumerate(objects[:MAX_OBJECTS]):
        try:
            good.append(_metadata.validate_metadata_record(record))
        except Exception:  # noqa: BLE001 - unreadable is not readable
            held.append(index)
    return good, held


def _provider_entries(provider_states):
    """``{provider_id: state or None}``. ``None`` means "nobody knows".

    A value may be a state name from ``capacity.PROVIDER_STATES`` or a whole
    provider record, in which case the state comes from
    ``capacity.provider_state`` rather than from a second opinion written here.
    Everything else - a number, a list, a boolean, a name that is not a provider
    id - resolves to ``None``, and ``None`` blocks every destructive proposal.
    """
    if not isinstance(provider_states, Mapping):
        return {}
    entries = {}
    try:
        items = list(provider_states.items())[:MAX_PROVIDERS]
    except Exception:  # noqa: BLE001 - an unusable mapping names no providers
        return {}
    for name, value in items:
        try:
            if not _capacity.is_provider_id(name):
                continue
            if isinstance(value, str) and not isinstance(value, bool):
                entries[name] = (value if value in _capacity.PROVIDER_STATES
                                 else None)
            elif isinstance(value, Mapping):
                entries[name] = _capacity.provider_state(value)
            else:
                entries[name] = None
        except Exception:  # noqa: BLE001 - an unresolvable row is unknown
            entries[name] = None
    return entries


def _confirmed(confirmed_copies):
    """``{object_id: frozenset(backend_id)}``, or nothing at all.

    Only a mapping of object ids to a *collection* of backend ids counts. A
    string is refused even though it is a Sequence: ``"cloudflare_r2"`` iterated
    one character at a time would "confirm" thirteen copies that do not exist,
    which is the most expensive way this could be wrong.
    """
    if not isinstance(confirmed_copies, Mapping):
        return {}
    table = {}
    try:
        items = list(confirmed_copies.items())
    except Exception:  # noqa: BLE001 - an unusable mapping confirms nothing
        return {}
    for object_id, backends in items:
        if not isinstance(object_id, str):
            continue
        if isinstance(backends, (str, bytes, bytearray)):
            continue
        if not isinstance(backends, (Sequence, Set)):
            continue
        names = {name for name in backends if isinstance(name, str)
                 and _capacity.is_provider_id(name)}
        if names:
            table[object_id] = frozenset(names)
    return table


@dataclasses.dataclass(frozen=True)
class _Context:
    """Everything the eight steps are allowed to see. Read-only by construction."""

    records: tuple
    held: tuple
    entries: Mapping
    writable: frozenset
    near_full: frozenset
    pressured: frozenset
    under_pressure: bool
    destructive_allowed: bool
    confirmed: Mapping
    clock: object


# --- the shared destructive gate ------------------------------------------------


def _survivors_required(criticality):
    """How many confirmed copies must remain after a removal.

    ``policy.yaml``'s ``min_independent_provider_copies``, read through
    ``replication.replication_requirement`` so that the numbers cannot drift
    from the document that sets them - and floored at one for every class except
    EPHEMERAL, whose zero the policy states explicitly beside ``ttl_expiry:
    true``. Expiry is the one lifecycle event whose whole purpose is that
    nothing remains; everywhere else, removing the last copy anybody has seen is
    not a capacity measure, it is the loss the capacity measure exists to avoid.
    """
    required = _replication.replication_requirement(criticality)
    if criticality == "EPHEMERAL":
        return required
    return max(1, required)


def _delete_proposals(ctx, record, *, step, reason):
    """Proposed removals for one object, or an empty list.

    Every condition below is a gate rather than a contribution, and every one of
    them fails closed. The order is not significant to the result; it is
    significant to the reader, which is why the cheapest refusals are stated
    first.
    """
    if not ctx.destructive_allowed:
        return []
    criticality = record["criticality"]
    if criticality in NEVER_CAPACITY_DELETED:
        return []

    verification = record.get("verification")
    if not isinstance(verification, Mapping):
        return []
    if verification.get("hash_verified") is not True:
        return []

    # Spec S15's evidence is dated evidence. An absent or unparseable
    # ``last_verified_at``, or one dated after the evaluation instant, is not a
    # verification anybody can stand behind.
    verified_at = _capacity._parse_instant(record.get("last_verified_at"))
    if verified_at is None or verified_at > ctx.clock:
        return []

    confirmed = ctx.confirmed.get(record["object_id"])
    if not confirmed:
        return []

    # Survivors are counted from every confirmed copy, but only a backend the
    # index *also* names is a deletion target. The asymmetry is deliberate and
    # is safe in both directions: a copy confirmed on a backend the record has
    # forgotten still counts as a survivor, while a proposal to remove one would
    # be this module acting on a holder nothing in the mesh has registered.
    targets = confirmed & {record["primary_backend"], *record["replica_backends"]}

    required = _survivors_required(criticality)
    remaining = set(confirmed)
    proposals = []
    for backend in sorted(targets):
        survivors = remaining - {backend}
        if len(survivors) < required:
            continue
        remaining = survivors
        proposals.append(Action(
            step=step,
            kind="DELETE",
            object_id=record["object_id"],
            provider_id=backend,
            reason=reason,
            destructive=True,
            requires_authorization=True,
            evidence={
                "criticality": criticality,
                "required_confirmed_copies": required,
                "surviving_confirmed_copies": sorted(survivors),
            },
        ))
    return proposals


# --- Spec S14, in Spec S14's order ---------------------------------------------


def _step_1_expire_ephemeral(ctx):
    """1. expire EPHEMERAL data."""
    out = []
    for record in ctx.records:
        if record["criticality"] != "EPHEMERAL":
            continue
        touched = _capacity._parse_instant(
            record.get("last_accessed_at", record.get("created_at")))
        if touched is None or touched > ctx.clock:
            continue
        if (ctx.clock - touched).total_seconds() < EPHEMERAL_TTL_SECONDS:
            continue
        out.extend(_delete_proposals(ctx, record, step=1,
                                     reason="EPHEMERAL_TTL_ELAPSED"))
    return out


def _step_2_compact_telemetry(ctx):
    """2. compact telemetry and experience records.

    A proposal to run ``compaction.py`` over an object, not a compaction. This
    module never reads an object's bytes.
    """
    if not ctx.under_pressure:
        return []
    out = []
    for record in ctx.records:
        if record.get("object_class") not in TELEMETRY_OBJECT_CLASSES:
            continue
        if record["lifecycle_state"] not in COMPACTABLE_STATES:
            continue
        out.append(Action(
            step=2, kind="COMPACT", object_id=record["object_id"],
            provider_id=record["primary_backend"],
            reason="TELEMETRY_COMPACTION_AVAILABLE",
            destructive=False, requires_authorization=False,
            evidence={"lifecycle_state": record["lifecycle_state"],
                      "object_class": record["object_class"]},
        ))
    return out


def _step_3_evict_reproducible(ctx):
    """3. remove redundant reproducible artifacts.

    "Redundant" means a surviving copy somebody has *confirmed*, not a replica
    the index claims. Both halves are required: the class must be REPRODUCIBLE
    *and* the record must agree it is reproducible, because Spec S8 permits
    eviction precisely because the object can be regenerated.
    """
    if not ctx.under_pressure:
        return []
    out = []
    for record in ctx.records:
        if record["criticality"] != "REPRODUCIBLE":
            continue
        if record.get("reproducible") is not True:
            continue
        out.extend(_delete_proposals(ctx, record, step=3,
                                     reason="REDUNDANT_REPRODUCIBLE_COPY"))
    return out


def _step_4_compress_cold(ctx):
    """4. compress cold evidence."""
    if not ctx.under_pressure:
        return []
    out = []
    for record in ctx.records:
        if record["storage_tier"] != "COLD":
            continue
        if record["lifecycle_state"] not in COMPRESSIBLE_STATES:
            continue
        out.append(Action(
            step=4, kind="COMPRESS", object_id=record["object_id"],
            provider_id=record["primary_backend"],
            reason="COLD_EVIDENCE_UNCOMPRESSED",
            destructive=False, requires_authorization=False,
            evidence={"lifecycle_state": record["lifecycle_state"],
                      "size_bytes": record["size_bytes"]},
        ))
    return out


def _step_5_rebalance_movable(ctx):
    """5. rebalance movable objects.

    No destination is named. Choosing one is ``placement.py``'s decision and
    carrying the move out is ``replication.rebalance_object``'s protocol; naming
    a destination here would be this module making a placement decision it has
    no authority to make. A rebalance also needs somewhere to go, so this step
    is exhausted - not merely unproductive - when no provider is writable.
    """
    if not ctx.under_pressure or not ctx.writable:
        return []
    out = []
    for record in ctx.records:
        if record["storage_tier"] in IMMOVABLE_TIERS:
            continue
        if record["privacy_class"] == "LOCAL_ONLY":
            continue
        if record["primary_backend"] not in ctx.pressured:
            continue
        out.append(Action(
            step=5, kind="REBALANCE", object_id=record["object_id"],
            provider_id=record["primary_backend"],
            reason="PROVIDER_UNDER_PRESSURE",
            destructive=False, requires_authorization=True,
            evidence={"destination_chosen_here": False,
                      "criticality": record["criticality"]},
        ))
    return out


def _step_6_pause_learning_writes(ctx):
    """6. pause non-critical background-learning writes.

    Only while there is still writable capacity to protect. With nothing
    writable there is nothing left to pause, and the answer is further down the
    list.
    """
    if not ctx.under_pressure or not ctx.writable:
        return []
    return [Action(
        step=6, kind="PAUSE_NON_CRITICAL_LEARNING_WRITES", object_id=None,
        provider_id=None, reason="NON_CRITICAL_WRITES_PAUSED",
        destructive=False, requires_authorization=True,
        evidence={"writable_providers": len(ctx.writable)},
    )]


def _step_7_reserve_for_critical(ctx):
    """7. reserve capacity for critical evidence.

    Reached when nothing is writable but a provider is NEAR_FULL rather than
    gone: the emergency reserve ``capacity.usable_headroom_bytes`` withholds
    below the hard limit is exactly the capacity CRITICAL evidence may still
    use, and reserving it is the last thing before degrading.
    """
    if ctx.writable or not ctx.near_full:
        return []
    return [Action(
        step=7, kind="RESERVE_CAPACITY_FOR_CRITICAL", object_id=None,
        provider_id=provider, reason="EMERGENCY_RESERVE_FOR_CRITICAL",
        destructive=False, requires_authorization=True,
        evidence={"emergency_reserve_ratio": _capacity.EMERGENCY_RESERVE_RATIO},
    ) for provider in sorted(ctx.near_full)]


def _step_8_enter_degraded_mode(ctx):
    """8. enter read-only/degraded mode if no safe free capacity remains.

    Spec S14's closing line: the system must degrade instead of crashing. This
    is what degrading looks like as a value - a proposal to stop writing, not an
    exception thrown at whoever called on the worst day.
    """
    if not ctx.entries or ctx.writable or ctx.near_full:
        return []
    return [Action(
        step=8, kind="ENTER_DEGRADED_READ_ONLY", object_id=None,
        provider_id=None, reason="NO_SAFE_FREE_CAPACITY_REMAINS",
        destructive=False, requires_authorization=True,
        evidence={"providers_known": len(ctx.entries)},
    )]


#: Spec S14's eight steps, in Spec S14's order. The tuple *is* the order: there
#: is no priority number, no weight and no sort, so the only way to reorder them
#: is to edit this list, which is the point.
PRESSURE_STEPS = (
    (1, "EXPIRE_EPHEMERAL", _step_1_expire_ephemeral),
    (2, "COMPACT_TELEMETRY_AND_EXPERIENCE", _step_2_compact_telemetry),
    (3, "EVICT_REDUNDANT_REPRODUCIBLE", _step_3_evict_reproducible),
    (4, "COMPRESS_COLD_EVIDENCE", _step_4_compress_cold),
    (5, "REBALANCE_MOVABLE", _step_5_rebalance_movable),
    (6, "PAUSE_NON_CRITICAL_LEARNING_WRITES", _step_6_pause_learning_writes),
    (7, "RESERVE_CAPACITY_FOR_CRITICAL", _step_7_reserve_for_critical),
    (8, "ENTER_DEGRADED_READ_ONLY", _step_8_enter_degraded_mode),
)


# --- the post-condition --------------------------------------------------------


def _permitted(action, criticalities):
    """The guard that still holds when a step is added by somebody else.

    Applied to everything the steps returned, after they have returned it. A
    destructive proposal survives only if it is a well-formed ``Action``, names
    an object this call actually validated, and that object's class is not one
    ``policy.yaml`` forbids capacity-deleting. A proposal about an object nobody
    validated is refused for the same reason a malformed record is held: the
    class of an object nobody read is a class nobody knows.
    """
    if not isinstance(action, Action):
        return False
    if action.kind not in ACTION_KINDS or action.reason not in REASONS:
        return False
    if action.kind not in DESTRUCTIVE_KINDS:
        return True
    if action.object_id not in criticalities:
        return False
    return criticalities[action.object_id] not in NEVER_CAPACITY_DELETED


# --- the entry point -----------------------------------------------------------


def lifecycle_actions(objects, provider_states, *, now=None,
                      metadata_store=None, confirmed_copies=None):
    """Propose the mesh's response to current storage pressure (Spec S14).

    ``objects`` is a sequence of manifest records and ``provider_states`` a
    ``{provider_id: state}`` mapping, where a state is a name from
    ``capacity.PROVIDER_STATES`` or a whole provider record to resolve. Returns
    a list of ``Action`` proposals, ordered, possibly empty, never ``None`` and
    never an exception.

    **This function performs nothing.** It does not delete, write, move,
    compact, compress or connect, and it never calls a method on
    ``metadata_store`` other than the health question that decides whether
    somebody else's destructive action may proceed at all.

    Three keyword arguments are the evidence, and each one defaults to "absent",
    which is the same as "no". ``now`` is the evaluation instant. ``metadata_store``
    is the index whose certainty ``policy.yaml`` requires before any destructive
    lifecycle action (Spec S18). ``confirmed_copies`` is
    ``{object_id: {backend_id}}`` - copies something that can actually look has
    head-verified - because this function cannot look and will not count a claim
    as a copy.

    Without all three, no ``DELETE`` is ever proposed. That is not caution for
    its own sake: an absent fact is never permission.
    """
    try:
        records, held = _records(objects)
        entries = _provider_entries(provider_states)
        confirmed = _confirmed(confirmed_copies)
        clock = _capacity._clock(now)

        writable = frozenset(
            name for name, state in entries.items()
            if state in _capacity.WRITABLE_STATES)
        near_full = frozenset(
            name for name, state in entries.items() if state == "NEAR_FULL")
        pressured = frozenset(
            name for name, state in entries.items()
            if state in ("PRESSURED", "NEAR_FULL"))
        unknown = any(state is None for state in entries.values())

        under_pressure = bool(entries) and (bool(pressured) or not writable)

        # policy.yaml: destructive_action_on_uncertain_evidence: FAIL_CLOSED.
        # Every clause is a fact that must be *present*, never one that must be
        # absent, so a field nobody supplied cannot read as consent.
        destructive_allowed = bool(
            clock is not None
            and entries
            and not unknown
            and _metadata.can_perform_destructive_lifecycle(metadata_store))

        ctx = _Context(
            records=tuple(records), held=tuple(held), entries=entries,
            writable=writable, near_full=near_full, pressured=pressured,
            under_pressure=under_pressure,
            destructive_allowed=destructive_allowed,
            confirmed=confirmed, clock=clock)

        actions = [Action(
            step=0, kind="HOLD_UNCERTAIN_RECORD", object_id=None,
            provider_id=None, reason="MALFORMED_RECORD",
            destructive=False, requires_authorization=False,
            evidence={"record_index": index},
        ) for index in held]

        # The gates. The first step with anything to propose is the only step
        # that proposes: a later step never runs before an earlier one is
        # exhausted, and pressure is part of a step's trigger rather than part
        # of any comparison between steps.
        for _number, _name, step in PRESSURE_STEPS:
            try:
                proposed = list(step(ctx))
            except Exception:  # noqa: BLE001 - degrade, never crash (Spec S14)
                proposed = []
            if proposed:
                actions.extend(proposed)
                break

        criticalities = {record["object_id"]: record["criticality"]
                         for record in records}
        permitted = [action for action in actions
                     if _permitted(action, criticalities)]
        return _bounded(permitted)
    except Exception:  # noqa: BLE001 - see the module docstring: never raises
        return []


def _bounded(actions):
    """Cap the list, and drop anything that grew a way to hold bulk.

    Every field of an ``Action`` is drawn from a closed vocabulary, a validated
    object id, a validated provider id or a small integer, so this bound is
    unreachable by a well-formed proposal and is meant to stay that way. It is
    here so that a field added later with a careless value cannot turn a
    proposal into a payload slot.
    """
    out = []
    for action in actions[:MAX_ACTIONS]:
        try:
            encoded = json.dumps(action.as_dict(), sort_keys=True)
        except Exception:  # noqa: BLE001 - unserialisable is not proposable
            continue
        if len(encoded) <= MAX_ACTION_BYTES:
            out.append(action)
    return out


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "PROPOSAL_ONLY", "PERFORMS_DELETION_HERE", "PERFORMS_NETWORK_IO_HERE",
    "ENCRYPTION_IMPLEMENTED_HERE", "EPHEMERAL_TTL_SECONDS", "MAX_OBJECTS",
    "MAX_PROVIDERS", "MAX_ACTIONS", "MAX_ACTION_BYTES", "ACTION_KINDS",
    "DESTRUCTIVE_KINDS", "REASONS", "NEVER_CAPACITY_DELETED",
    "TELEMETRY_OBJECT_CLASSES", "COMPACTABLE_STATES", "COMPRESSIBLE_STATES",
    "IMMOVABLE_TIERS", "DECISION_VALUE_CHECKS", "DECISION_FIELDS",
    "IGNORED_MANIFEST_FIELDS", "PRESSURE_STEPS", "Action", "lifecycle_actions",
]
