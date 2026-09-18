"""Does every CRITICAL role have two paths that can actually run?

    python AI_SKILL_LIBRARY/v4/tools/critical_role_redundancy_proof.py \\
        --source-sha "$(git rev-parse HEAD)" \\
        --evidence CHECKPOINTS/evidence/CRITICAL_ROLE_REDUNDANCY_PROOF.json

The role matrix answers a different question than the one redundancy needs. It
says which models are *named* for a role, and by that measure REASONING_BRANCH
has eight candidates and looks comfortable. All eight are local weights on one
machine, and on this machine the inference engine dies with SIGILL, so the true
count of things that can serve REASONING_BRANCH right now is zero. Eight names,
no paths. That gap - between being listed and being able to execute - is the
whole subject of this tool.

So a candidate becomes a *path* only by surviving four questions:

  1. is there a worker that actually serves this model, at this revision?
  2. did that worker's execution probe come back alive? EXECUTION_DEAD and
     EXECUTION_UNKNOWN both fail; neither is a pass, and a worker whose probe
     was killed by a signal is dead however green its heartbeat reads.
  3. is it policy-eligible? COOLDOWN, DEGRADED, QUARANTINED, UNAVAILABLE and
     UNKNOWN are not capacity.
  4. was it admitted under the same execution mode the role asks for? A
     capability provider is not the exact model, and saying so out loud is the
     point rather than an inconvenience.

Surviving paths are then grouped by failure domain, because two models on one
box are one path. A role is covered when two *domains* cover it.

**This tool decides nothing and changes nothing.** It routes nothing, admits
nothing, schedules nothing and publishes no readiness of its own: it writes one
evidence file stating what it found, for the existing gate authority to read.

Fail-closed throughout. Missing, malformed, stale-revision or contradictory
evidence produces ``ready=false``. An absent fact is never a pass.

What this cannot prove: it does not call a provider, and it does not probe a
remote host. For a local host it reads the execution probe's own per-host
reading; for a hosted worker it reads a record someone else wrote. So a
``true`` here means "the evidence supplied, bound to this revision, describes
two independent paths" - not "a model answered just now". The record's own
liveness must come from something that actually ran, or this gate is only as
truthful as its inputs. It refuses to be *less* truthful than them.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

# Run as a script as well as imported as a module, like the other tools here.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.tools.worker_execution_liveness import (
    EXECUTION_DEAD, EXECUTION_LIVE, EXECUTION_UNKNOWN, current_source_sha,
    observing_host, utc_now,
)

EVIDENCE = "CHECKPOINTS/evidence"
ROLE_MATRIX_FILE = "ROLE_CAPABILITY_MATRIX.json"
LIVENESS_FILE = "WORKER_EXECUTION_LIVENESS.json"

#: This tool reports a fact. It grants nothing and clears nothing.
AUTHORITY = False

GATE = "CRITICAL_ROLE_REDUNDANCY_READY"

#: Two, not one. One path is a single point of failure wearing the word
#: "redundant"; it is exactly the state this repository is in and the reason
#: the gate exists.
REQUIRED_INDEPENDENT_PATHS = 2

#: The matrix slots that can name a candidate, in preference order.
CANDIDATE_SLOTS = ("primary", "secondary", "fallback", "emergency_fallback")

EXECUTION_MODES = ("EXACT_MODEL", "CAPABILITY_PROVIDER")
PLACEMENTS = ("LOCAL", "HOSTED", "SERVERLESS")
LIVENESS_STATES = (EXECUTION_LIVE, EXECUTION_DEAD, EXECUTION_UNKNOWN)

#: Only ELIGIBLE is capacity. The rest are listed so that a state nobody
#: anticipated is refused rather than silently treated as fine.
POLICY_STATES = ("ELIGIBLE", "COOLDOWN", "DEGRADED", "QUARANTINED",
                 "UNAVAILABLE", "UNKNOWN")
POLICY_ELIGIBLE = "ELIGIBLE"

# --- bounds -----------------------------------------------------------------
# Every anchored pattern here ends in ``\Z`` and never in ``$``. Python's ``$``
# also matches immediately before a final newline, so ``"abc\n"`` passes a
# ``$``-anchored token check and then travels on as a 4-character token through
# a 3-character bound. That is a real bug this repository has already paid for
# in the storage manifest, and repeating it in an evidence producer would let a
# trailing newline ride inside a worker id into a JSON file other gates read.

MAX_TOKEN = 64
MAX_MODEL_ID = 128
MAX_SHA = 64
MAX_TIMESTAMP = 32
MAX_EVIDENCE_REF = 200
#: Every free-text string this tool emits. Reasons are written by this module
#: from bounded templates plus bounded inputs, and the emitted document is
#: walked in the tests to prove no string escapes this.
MAX_TEXT = 600

MAX_WORKERS = 256
MAX_MODELS = 64
MAX_ROLES = 128
MAX_PATHS = 64
MAX_HEALTH_FIELDS = 24
MAX_HEALTH_VALUE = 64

_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/+-]{0,63}\Z")
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9@][A-Za-z0-9_.@/+ -]{0,127}\Z")
_SHA_RE = re.compile(r"^[0-9a-f]{7,64}\Z")
_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]{1,6})?Z\Z")
_EVIDENCE_REF_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,150}[.][A-Za-z0-9]{1,16}\Z")


class RecordRejected(ValueError):
    """A record that cannot be trusted is refused, never repaired."""


def _bounded_string(value: Any, pattern: re.Pattern[str], limit: int, *, field: str) -> str:
    if not isinstance(value, str):
        raise RecordRejected(
            f"{field} must be a string, got {type(value).__name__}")
    if len(value) > limit:
        raise RecordRejected(
            f"{field} is {len(value)} characters, over the {limit}-character bound")
    if not pattern.fullmatch(value):
        raise RecordRejected(
            f"{field} does not match {pattern.pattern}")
    return value


def _enum(allowed: Sequence[str]) -> Callable[..., str]:
    """A closed vocabulary check that never repeats what it was given.

    This was the one refusal in this module that echoed its input: a 5000-
    character ``placement`` reached ``malformed_records[0].reason`` in the
    emitted document - bounded at ``MAX_TEXT``, but still an input this tool
    does not own, written into an evidence file other gates read. A reader
    needs to know what arrived, not to be shown it, so the refusal states a
    type and a length and names the vocabulary that was expected.
    """
    def check(value: Any, *, field: str) -> str:
        if not isinstance(value, str):
            raise RecordRejected(f"{field} must be a string, got {type(value).__name__}")
        if value not in allowed:
            raise RecordRejected(
                f"{field} is a str of length {len(value)} that is not one of "
                f"{list(allowed)}; the value is not repeated here because this "
                "document does not echo inputs it does not own")
        return value
    return check


def _string(pattern: re.Pattern[str], limit: int) -> Callable[..., str]:
    def check(value: Any, *, field: str) -> str:
        return _bounded_string(value, pattern, limit, field=field)
    return check


def _covers(value: Any, *, field: str) -> str:
    """What part of the role a candidate claims, as a bounded token."""
    if value is None:
        return "UNSTATED"
    return _bounded_string(value, _TOKEN_RE, MAX_TOKEN, field=field)


def _check_serves_models(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise RecordRejected(f"{field} must be a list, got {type(value).__name__}")
    if len(value) > MAX_MODELS:
        raise RecordRejected(
            f"{field} lists {len(value)} models, over the {MAX_MODELS} bound")
    return [_bounded_string(item, _MODEL_ID_RE, MAX_MODEL_ID, field=f"{field}[{i}]")
            for i, item in enumerate(value)]


def _check_host_health(value: Any, *, field: str) -> dict[str, str]:
    """Recorded, and deliberately never consulted.

    A worker may carry the health fields the fabric already collects - online,
    circuit, ram_available_mb - so that the evidence shows what *did* look fine
    on a worker that cannot execute. Keeping them in the document and out of
    the qualification logic is the entire claim this tool makes.
    """
    if not isinstance(value, dict):
        raise RecordRejected(f"{field} must be a mapping, got {type(value).__name__}")
    if len(value) > MAX_HEALTH_FIELDS:
        raise RecordRejected(
            f"{field} has {len(value)} entries, over the {MAX_HEALTH_FIELDS} bound")
    out: dict[str, str] = {}
    for key, item in value.items():
        name = _bounded_string(key, _TOKEN_RE, MAX_TOKEN, field=f"{field} key")
        if isinstance(item, bool) or isinstance(item, int):
            item = str(item)
        if not isinstance(item, str):
            raise RecordRejected(
                f"{field}.{name} must be a scalar, got {type(item).__name__}")
        if len(item) > MAX_HEALTH_VALUE:
            raise RecordRejected(
                f"{field}.{name} is over the {MAX_HEALTH_VALUE}-character bound")
        out[name] = item
    return out


#: One validator per permitted field of a worker record. A table rather than a
#: run of ``if`` statements so that the permitted field set can be *derived*
#: from it: ``WORKER_RECORD_FIELDS`` below is this table's keys, so a field
#: that is allowed but validated by nothing cannot exist. This repository has
#: found that exact shape four separate times - a name on an allow-list with no
#: checker behind it, surviving because no fixture happened to populate it -
#: and the tests drive the field list from the data contract in both
#: directions so a field added later cannot repeat it.
FIELD_CHECKS: dict[str, Callable[..., Any]] = {
    "worker_id": _string(_TOKEN_RE, MAX_TOKEN),
    "execution_host": _string(_TOKEN_RE, MAX_TOKEN),
    "failure_domain": _string(_TOKEN_RE, MAX_TOKEN),
    "provider": _string(_TOKEN_RE, MAX_TOKEN),
    "placement": _enum(PLACEMENTS),
    "execution_mode": _enum(EXECUTION_MODES),
    "execution_liveness": _enum(LIVENESS_STATES),
    "policy_state": _enum(POLICY_STATES),
    "source_sha": _string(_SHA_RE, MAX_SHA),
    "proof_timestamp": _string(_TIMESTAMP_RE, MAX_TIMESTAMP),
    "serves_models": _check_serves_models,
    # Recorded, and deliberately never consulted - like ``host_health``. It
    # used to be a coverage basis on its own; see ``_match``.
    "serves_placement": _enum(PLACEMENTS),
    "evidence_ref": _string(_EVIDENCE_REF_RE, MAX_EVIDENCE_REF),
    "host_health": _check_host_health,
}

#: Derived, not declared a second time.
WORKER_RECORD_FIELDS = tuple(FIELD_CHECKS)

#: The pattern-bounded string fields, and their bounds, exposed so that the
#: tests can assert the anchor and the length of every one of them without
#: repeating the list.
FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "worker_id": _TOKEN_RE,
    "execution_host": _TOKEN_RE,
    "failure_domain": _TOKEN_RE,
    "provider": _TOKEN_RE,
    "source_sha": _SHA_RE,
    "proof_timestamp": _TIMESTAMP_RE,
    "evidence_ref": _EVIDENCE_REF_RE,
}
FIELD_MAX_LENGTHS: dict[str, int] = {
    "worker_id": MAX_TOKEN,
    "execution_host": MAX_TOKEN,
    "failure_domain": MAX_TOKEN,
    "provider": MAX_TOKEN,
    "source_sha": MAX_SHA,
    "proof_timestamp": MAX_TIMESTAMP,
    "evidence_ref": MAX_EVIDENCE_REF,
}

#: One value per bounded string field that its own checker accepts. Used by the
#: tests to prove each bound admits something as well as refusing something: a
#: pattern that rejects everything is a different bug from a pattern that
#: bounds nothing, and both have shipped here before.
SAMPLE_VALUES: dict[str, str] = {
    "worker_id": "local-engine-93891604",
    "execution_host": "host:93891604",
    "failure_domain": "host:93891604",
    "provider": "cloudflare",
    "source_sha": "c322abc210f1afd22a256ffbd6226c27aa01af52",
    "proof_timestamp": "2026-09-18T00:00:00Z",
    "evidence_ref": "CHECKPOINTS/evidence/WORKER_EXECUTION_LIVENESS.json",
    "placement": "LOCAL",
    "execution_mode": "EXACT_MODEL",
    "execution_liveness": EXECUTION_LIVE,
    "policy_state": POLICY_ELIGIBLE,
    "serves_placement": "HOSTED",
}

REQUIRED_WORKER_FIELDS = ("worker_id", "execution_host", "placement",
                          "execution_mode", "execution_liveness", "policy_state",
                          "source_sha", "proof_timestamp")


def _text(value: str) -> str:
    """Bound a reason string at the edge where it enters the document."""
    return value if len(value) <= MAX_TEXT else value[:MAX_TEXT - 1] + "…"


def walk_strings(node: Any, trail: str = "") -> Iterator[tuple[str, str]]:
    """Every string in an emitted document, so a test can bound all of them."""
    if isinstance(node, str):
        yield trail, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from walk_strings(value, f"{trail}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk_strings(value, f"{trail}[{index}]")


def normalise_worker(record: Any) -> dict[str, Any]:
    """Whitelist one worker record against the closed, checked field set."""
    if not isinstance(record, dict):
        raise RecordRejected(f"a worker record must be a mapping, got {type(record).__name__}")
    unknown = sorted(set(record) - set(FIELD_CHECKS))
    if unknown:
        raise RecordRejected(
            f"worker record rejects unknown field(s) {unknown}: the field set is "
            f"closed, so a field nobody anticipated is refused rather than stored")
    missing = sorted(set(REQUIRED_WORKER_FIELDS) - set(record))
    if missing:
        raise RecordRejected(f"worker record is missing required field(s) {missing}")
    out: dict[str, Any] = {}
    for field, value in record.items():
        if value is None:
            raise RecordRejected(
                f"{field} is null; an optional field is omitted rather than "
                "emitted as null, because a null here is a fact nobody stated")
        out[field] = FIELD_CHECKS[field](value, field=field)
    out.setdefault("failure_domain", f"host:{out['execution_host']}"[:MAX_TOKEN])
    return out


def workers_from_liveness(
        document: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    """Turn per-host execution readings into worker records.

    The liveness tool keys its readings by host on purpose: a reading is a fact
    about one machine at one moment, and two sessions on different hardware
    must not overwrite each other. That structure is exactly what independence
    needs here, so it is read as written - one worker per host, each carrying
    its own revision - rather than flattened into a single verdict.
    """
    malformed: list[dict[str, str]] = []
    stale: list[dict[str, str]] = []
    if not isinstance(document, dict):
        return [], [{"reason": _text("the liveness evidence is not a JSON object")}], []

    readings = document.get("READINGS_BY_HOST")
    if not isinstance(readings, dict):
        # A file written before per-host attribution existed still holds one
        # real reading; it is read, and then judged like any other.
        readings = {}
        if document.get("LOCAL_ENGINE"):
            observed = document.get("OBSERVED_ON") or {}
            readings[str(observed.get("host_fingerprint") or "host_not_recorded")] = document

    records: list[dict[str, Any]] = []
    for host, reading in sorted(readings.items())[:MAX_WORKERS]:
        if not isinstance(reading, dict):
            malformed.append({"reason": _text(f"reading for host {host!r} is not an object")})
            continue
        engine = reading.get("LOCAL_ENGINE") or {}
        state = reading.get("execution_liveness") or engine.get("state")
        # What this host actually holds, as the reading states it. A reading
        # that does not say is not filled in with a guess: the worker is then
        # emitted with no served models and qualifies for nothing, which is the
        # only honest reading of "an execution probe answered on some machine".
        served = reading.get("serves_models")
        if served is None and isinstance(engine, dict):
            served = engine.get("serves_models")
        candidate = {
            "worker_id": reading.get("worker_id") or f"local-engine-{host}",
            "execution_host": f"host:{host}",
            "failure_domain": f"host:{host}",
            "placement": "LOCAL",
            "execution_mode": "EXACT_MODEL",
            "execution_liveness": state,
            "policy_state": POLICY_ELIGIBLE,
            "serves_placement": "LOCAL",
            "source_sha": reading.get("source_sha"),
            "proof_timestamp": reading.get("proof_timestamp"),
        }
        if served is not None:
            candidate["serves_models"] = served
        if candidate["source_sha"] is None or candidate["proof_timestamp"] is None:
            # A reading that names no revision or no instant cannot be shown to
            # be about the code running now. The one in this repository's
            # evidence says EXECUTION_LIVE, names no host and no revision, and
            # would otherwise resurrect a path on a machine nobody can find.
            # It is not malformed - it was true when it was written - so it is
            # disqualified as stale rather than treated as a broken file.
            stale.append({
                "worker_id": str(candidate["worker_id"])[:MAX_TOKEN],
                "execution_host": str(candidate["execution_host"])[:MAX_TOKEN],
                "reason": _text(
                    f"stale: the reading for host {host!r} names no source_sha or no "
                    "proof_timestamp, so it cannot be shown to be about the revision "
                    "under test, whatever it says about execution"),
            })
            continue
        try:
            records.append(normalise_worker(candidate))
        except RecordRejected as exc:
            malformed.append({"worker_id": str(candidate["worker_id"])[:MAX_TOKEN],
                              "reason": _text(str(exc))})
    return records, malformed, stale


def critical_roles(document: Any) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """The CRITICAL rows of the role matrix and the candidates they name."""
    malformed: list[dict[str, str]] = []
    if not isinstance(document, dict):
        return [], [{"reason": _text("the role matrix is not a JSON object")}]
    rows = document.get("ROLE_CAPABILITY_MATRIX")
    if not isinstance(rows, list):
        return [], [{"reason": _text("the role matrix has no ROLE_CAPABILITY_MATRIX list")}]

    roles: list[dict[str, Any]] = []
    for row in rows[:MAX_ROLES]:
        if not isinstance(row, dict) or row.get("criticality") != "CRITICAL":
            continue
        try:
            role_id = _bounded_string(row.get("role_id"), _TOKEN_RE, MAX_TOKEN,
                                      field="role_id")
        except RecordRejected as exc:
            malformed.append({"reason": _text(str(exc))})
            continue
        candidates = []
        for slot in CANDIDATE_SLOTS:
            value = row.get(slot)
            if not isinstance(value, dict):
                continue
            try:
                candidates.append({
                    "slot": slot,
                    "model_id": _bounded_string(value.get("model_id"), _MODEL_ID_RE,
                                                MAX_MODEL_ID, field=f"{role_id}.{slot}.model_id"),
                    "execution_mode": FIELD_CHECKS["execution_mode"](
                        value.get("execution_mode"), field=f"{role_id}.{slot}.execution_mode"),
                    "placement": FIELD_CHECKS["placement"](
                        value.get("placement"), field=f"{role_id}.{slot}.placement"),
                    # Bounded by a pattern, not by a slice. A field whose only
                    # bound is ``[:MAX_TOKEN]`` is the allowed-but-unchecked
                    # shape this repository has found repeatedly; this one is
                    # never consumed today, which is exactly when such a field
                    # goes unnoticed.
                    "covers": _covers(value.get("covers"),
                                      field=f"{role_id}.{slot}.covers"),
                })
            except RecordRejected as exc:
                malformed.append({"role_id": role_id, "reason": _text(str(exc))})
        roles.append({"role_id": role_id, "candidates": candidates})
    roles.sort(key=lambda role: role["role_id"])
    return roles, malformed


def _disqualify(worker: dict[str, Any], source_sha: str | None) -> str | None:
    """Why this worker is not capacity, or ``None`` when it is."""
    if source_sha is None or worker["source_sha"] != source_sha:
        return _text(
            f"stale: the record names revision {worker['source_sha']}, not the "
            f"revision under test ({source_sha}); evidence from another revision "
            "does not count")
    if worker["execution_liveness"] != EXECUTION_LIVE:
        return _text(
            f"execution_liveness is {worker['execution_liveness']}: a worker that "
            "cannot be shown to execute serves no role and is not a redundant "
            "path, however healthy its heartbeat, lease, memory and circuit read")
    if worker["policy_state"] != POLICY_ELIGIBLE:
        return _text(
            f"policy_state is {worker['policy_state']}: a worker in cooldown, "
            "degraded, quarantined or unknown state is not live capacity")
    if not worker.get("serves_models"):
        return _text(
            "the record names no serves_models: a worker that does not say which "
            "models it holds cannot be shown to serve any candidate, and a "
            "placement label is not a model name. It is reported, and it is not "
            "a path")
    return None


def _match(worker: dict[str, Any], candidate: dict[str, Any]) -> str | None:
    """How this worker covers this candidate, or ``None`` if it does not.

    Naming the model is the only way. There used to be a second basis,
    ``declared_placement``: when a worker listed no ``serves_models`` at all,
    a bare ``serves_placement == candidate.placement`` counted as coverage. A
    worker naming no model therefore covered *every* candidate at that
    placement - and because ``execution_mode`` still read EXACT_MODEL on both
    sides, the exact-model versus capability-provider distinction survived in
    the report and meant nothing in the arithmetic. Worse, the liveness reader
    below synthesised exactly such workers, so any execution-live host covered
    every LOCAL candidate of every critical role whatever weights it held.
    A placement is not a model name and no longer stands in for one.
    """
    serves = worker.get("serves_models") or []
    if not serves:
        return None
    return "explicit_model" if candidate["model_id"] in serves else None


def build(*, role_matrix: Any, liveness: Any = None,
          extra_workers: Sequence[Any] | None = None,
          source_sha: str | None, observed: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute the proof. Reads nothing from disk and writes nothing."""
    blocking: list[str] = []
    #: Reasons that make the gate false on their own, kept apart from the
    #: running commentary. A worker that does not qualify is reported and does
    #: not, by itself, fail the gate - it simply is not a path, and the roles
    #: it fails to cover say so. Missing, malformed, contradictory or
    #: unattributable evidence *is* fatal: an absent fact is never a pass.
    fatal: list[str] = []
    malformed: list[dict[str, str]] = []

    if source_sha is None:
        fatal.append(_text(
            "no source revision was supplied, so no evidence can be shown to be "
            "about the code under test"))
    else:
        try:
            source_sha = _bounded_string(source_sha, _SHA_RE, MAX_SHA, field="source_sha")
        except RecordRejected as exc:
            fatal.append(_text(str(exc)))
            source_sha = None

    roles, role_problems = critical_roles(role_matrix)
    malformed.extend(role_problems)

    workers: list[dict[str, Any]] = []
    stale_readings: list[dict[str, str]] = []
    if liveness is not None:
        found, problems, stale_readings = workers_from_liveness(liveness)
        workers.extend(found)
        malformed.extend(problems)
    for record in list(extra_workers or [])[:MAX_WORKERS]:
        try:
            workers.append(normalise_worker(record))
        except RecordRejected as exc:
            worker_id = record.get("worker_id") if isinstance(record, dict) else None
            malformed.append({"worker_id": str(worker_id)[:MAX_TOKEN] if worker_id else "?",
                              "reason": _text(str(exc))})

    # Contradiction: one host cannot be both alive and dead at one revision.
    by_host: dict[str, set[str]] = {}
    for worker in workers:
        if worker["source_sha"] == source_sha:
            by_host.setdefault(worker["execution_host"], set()).add(worker["execution_liveness"])
    contradictions = sorted(host for host, states in by_host.items() if len(states) > 1)
    for host in contradictions:
        fatal.append(_text(
            f"execution host {host} has contradictory liveness readings "
            f"({sorted(by_host[host])}) at the same revision; contradictory "
            "evidence fails closed rather than picking the convenient one"))

    # A failure domain is a property of the machine, not a label a record may
    # choose per worker. Without this, two workers on one box could each name
    # a different domain and manufacture the exact independence this gate
    # exists to refuse - the cheapest possible way to make it say true.
    domains_by_host: dict[str, set[str]] = {}
    for worker in workers:
        domains_by_host.setdefault(worker["execution_host"], set()).add(worker["failure_domain"])
    for host in sorted(h for h, d in domains_by_host.items() if len(d) > 1):
        fatal.append(_text(
            f"execution host {host} is declared in more than one failure domain "
            f"({sorted(domains_by_host[host])}); one machine is one domain, and two "
            "labels on one box are not two paths"))

    qualified: list[dict[str, Any]] = []
    disqualified: list[dict[str, str]] = list(stale_readings)
    blocking.extend(_text(f"reading {row['worker_id']} is not capacity: {row['reason']}")
                    for row in stale_readings)
    for worker in workers:
        reason = _disqualify(worker, source_sha)
        if reason is None:
            qualified.append(worker)
        else:
            disqualified.append({"worker_id": worker["worker_id"],
                                 "execution_host": worker["execution_host"],
                                 "reason": reason})
            blocking.append(_text(f"worker {worker['worker_id']} is not capacity: {reason}"))

    role_rows: list[dict[str, Any]] = []
    for role in roles:
        paths: list[dict[str, Any]] = []
        rejected: list[dict[str, str]] = []
        for candidate in role["candidates"]:
            covered_by = []
            for worker in qualified:
                basis = _match(worker, candidate)
                if basis is None:
                    continue
                if worker["execution_mode"] != candidate["execution_mode"]:
                    rejected.append({
                        "model_id": candidate["model_id"],
                        "worker_id": worker["worker_id"],
                        "reason": _text(
                            f"execution mode mismatch: the role asks for "
                            f"{candidate['execution_mode']} and {worker['worker_id']} is "
                            f"admitted as {worker['execution_mode']}; a capability "
                            "provider is not the exact model and is not silently "
                            "substituted for one"),
                    })
                    continue
                covered_by.append({
                    "model_id": candidate["model_id"],
                    "slot": candidate["slot"],
                    "execution_mode": candidate["execution_mode"],
                    "candidate_placement": candidate["placement"],
                    "worker_id": worker["worker_id"],
                    "execution_host": worker["execution_host"],
                    "failure_domain": worker["failure_domain"],
                    "provider": worker.get("provider", "unstated"),
                    "match_basis": basis,
                })
            if not covered_by:
                rejected.append({
                    "model_id": candidate["model_id"],
                    "worker_id": "-",
                    "reason": _text(
                        "no qualifying worker serves this candidate at this revision"),
                })
            paths.extend(covered_by)
        paths = paths[:MAX_PATHS]
        domains = sorted({path["failure_domain"] for path in paths})
        covered = len(domains) >= REQUIRED_INDEPENDENT_PATHS
        if not covered:
            blocking.append(_text(
                f"{role['role_id']} has {len(domains)} independent execution path(s), "
                f"fewer than the {REQUIRED_INDEPENDENT_PATHS} required; "
                f"{len(role['candidates'])} candidate(s) are named for it"))
        role_rows.append({
            "role_id": role["role_id"],
            "criticality": "CRITICAL",
            "candidates_named": len(role["candidates"]),
            "qualifying_paths": paths,
            "independent_failure_domains": domains,
            "independent_path_count": len(domains),
            "covered": covered,
            "rejected_candidates": rejected[:MAX_PATHS],
        })

    if not roles:
        fatal.append(_text(
            "the role matrix declares no CRITICAL role, so there is nothing to "
            "prove redundant; an absent fact is not a pass"))
    if malformed:
        fatal.append(_text(
            f"{len(malformed)} record(s) could not be read as stated; malformed "
            "evidence fails closed rather than being skipped"))

    blocking = fatal + blocking
    ready = bool(roles) and not fatal and all(row["covered"] for row in role_rows)

    report: dict[str, Any] = {
        "tool": "critical_role_redundancy_proof",
        "gate": GATE,
        "ready": ready,
        "source_sha": source_sha,
        "proof_timestamp": utc_now(),
        "OBSERVED_ON": observed if observed is not None else observing_host(),
        "reading_scope": _text(
            "the execution readings this proof consumes are facts about the machines "
            "they name at the moments they were taken, not a property of the commit. A "
            "different host may read the opposite and both are true."),
        "required_independent_paths": REQUIRED_INDEPENDENT_PATHS,
        "independence_rule": _text(
            "paths are counted by failure domain, not by model name: two models on one "
            "execution host are one path, and on an execution-dead host they are none."),
        "critical_roles": role_rows,
        "workers_considered": len(workers),
        "qualifying_workers": [worker["worker_id"] for worker in qualified][:MAX_WORKERS],
        "disqualified_workers": disqualified[:MAX_WORKERS],
        "malformed_records": malformed[:MAX_WORKERS],
        "contradictory_hosts": contradictions,
        "fail_closed_reasons": fatal[:MAX_ROLES * 2],
        "blocking_reasons": blocking[:MAX_ROLES * 2],
        "proofs": [
            "execution_liveness_verified_per_worker",
            "failure_domain_independence_verified",
            "execution_mode_distinction_preserved",
            "evidence_bound_to_source_sha",
        ] if ready else [],
        "routing_authority": False,
        "admission_authority": False,
        "scheduling_authority": False,
        "model_selection_authority": False,
        "evidence_authority": False,
        "changes_nothing": True,
    }
    return report


def _load(path: Path | None, *, label: str) -> tuple[Any, list[dict[str, str]]]:
    if path is None:
        return None, []
    if not path.is_file():
        return None, [{"reason": _text(f"{label} is missing at {path.name}")}]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, json.JSONDecodeError) as exc:
        return None, [{"reason": _text(f"{label} could not be read: {exc}")}]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--role-matrix", dest="role_matrix")
    parser.add_argument("--liveness")
    parser.add_argument("--workers", action="append", default=[],
                        help="JSON file holding {\"workers\": [...]} records")
    parser.add_argument("--source-sha", dest="source_sha")
    parser.add_argument("--evidence")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero when the gate is not ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    matrix_path = Path(args.role_matrix) if args.role_matrix else root / EVIDENCE / ROLE_MATRIX_FILE
    liveness_path = Path(args.liveness) if args.liveness else root / EVIDENCE / LIVENESS_FILE
    source_sha = args.source_sha or current_source_sha(root)

    matrix, problems = _load(matrix_path, label="the role matrix")
    liveness, liveness_problems = _load(liveness_path, label="the liveness evidence")
    problems.extend(liveness_problems)

    extra: list[Any] = []
    for name in args.workers:
        document, worker_problems = _load(Path(name), label="a worker record file")
        problems.extend(worker_problems)
        if isinstance(document, dict) and isinstance(document.get("workers"), list):
            extra.extend(document["workers"])
        elif isinstance(document, list):
            extra.extend(document)
        elif document is not None:
            problems.append({"reason": _text(f"{name} holds no list of worker records")})

    report = build(role_matrix=matrix, liveness=liveness, extra_workers=extra,
                   source_sha=source_sha)
    if problems:
        report["malformed_records"] = (report["malformed_records"] + problems)[:MAX_WORKERS]
        report["blocking_reasons"] = (report["blocking_reasons"] + [
            _text(f"{len(problems)} input file(s) were missing or unreadable; "
                  "missing evidence fails closed")])[:MAX_ROLES * 2]
        report["ready"] = False
        report["proofs"] = []

    if args.evidence:
        out = Path(args.evidence)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    covered = sum(1 for row in report["critical_roles"] if row["covered"])
    print(f"{GATE}={'true' if report['ready'] else 'false'} "
          f"critical_roles={len(report['critical_roles'])} covered={covered}")
    return 1 if (args.strict and not report["ready"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
