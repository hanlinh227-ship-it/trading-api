"""Four different facts that have been sharing one word, and one flag each.

    python AI_SKILL_LIBRARY/v4/tools/federation_status_scopes.py \
        --evidence CHECKPOINTS/evidence/FEDERATION_STATUS_SCOPES.json

A free-worker audit run in a container with no provider credentials reported
``VERIFIED_ACTIVE_WORKERS=0`` and ``24X7_FEDERATION_READY=false``. Both readings
are correct *about that container*, and neither is a statement about the
federation. Read as one, they erase every verification the repository has ever
recorded. Read the other way round, a PASS from four revisions ago is quoted as
though a provider were answering right now.

Both mistakes are the same mistake: a status with no scope attached. So this
tool refuses to emit an unscoped status. Every claim it makes carries three
independent axes, recorded separately because collapsing any two of them is how
the confusion started:

  binding    is the claim tied to a nameable revision at all?
  freshness  is that revision HEAD, an ancestor whose proved surfaces have not
             moved, or something else?
  locality   was the reading taken on this host, another host, or no recorded
             host?

An evidence document that names no ``source_sha`` and no ``proof_timestamp``
can only ever be HISTORICAL here, whatever it claims about itself. That is not
a technicality. ``CHECKPOINTS/evidence/FEDERATION_24X7_PROOF.json`` says
``federation_status: PROVEN, 22/22`` and carries neither field, so nothing in
it can be aged, attributed, or contradicted - it is an ALLOWED claim whose
VALUE nothing bounds, which is the defect class this branch has now found eight
times. Re-running that same tool at HEAD scores 21/22.

**This tool decides nothing and promotes nothing.** It routes no request,
selects no model, admits no worker and clears no gate. GITHUB_BRAIN_V4 remains
the only Brain, ``task_router`` the only routing authority, Model Mesh the only
model-selection authority, and the Free Worker Mesh capacity only. What this
adds is a vocabulary in which "we cannot reach it from here" and "it was never
verified" are different sentences.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worker_execution_liveness import (  # noqa: E402
    EXECUTION_DEAD,
    EXECUTION_LIVE,
    EXECUTION_UNKNOWN,
    SOURCE_SHA_RE,
    current_source_sha,
    observing_host,
    utc_now,
)

EVIDENCE = "CHECKPOINTS/evidence"

#: Reports a fact. Selects nothing, clears nothing, promotes nothing.
AUTHORITY = False
ROUTING_AUTHORITY = False
MODEL_SELECTION_AUTHORITY = False
ADMISSION_AUTHORITY = False
SCHEDULING_AUTHORITY = False

#: How old a reading may be and still describe "now" on this host. A liveness
#: reading is about the moment it was taken; an hour-old one is a claim about an
#: hour ago, and this tool will not launder it into the present.
CURRENT_ENV_MAX_AGE_SECONDS = 3600


# --- the three axes -----------------------------------------------------------
#
# Each axis is a table mapping a value to the written reason it exists, and each
# vocabulary tuple is DERIVED from its table. Task 4 established why: a tuple
# maintained alongside the table it describes is a second statement of the same
# set, and a second statement is a thing to drift.

BINDINGS: dict[str, str] = {
    "BOUND_TO_REVISION": "the document names a source_sha that resolves to a commit here",
    "UNBOUND": "the document names no source_sha, or no proof_timestamp, so nothing "
               "says which revision or which moment it describes",
    "UNRESOLVABLE": "the document names a source_sha that names no commit in this "
                    "repository",
}
BINDING_VALUES = tuple(BINDINGS)

FRESHNESS: dict[str, str] = {
    "CURRENT_REVISION": "bound to HEAD itself, so it describes the code under "
                        "test with nothing in between",
    "ANCESTOR_SURFACES_UNCHANGED": "bound to an ancestor of HEAD with no change to a "
                                   "proved surface since, so it still describes HEAD",
    "STALE_REVISION": "bound to a revision that is not HEAD, or to an ancestor from "
                      "before a proved surface moved",
    "NOT_APPLICABLE": "unbound documents have no freshness; they have no revision to "
                      "be fresh or stale against",
}
FRESHNESS_VALUES = tuple(FRESHNESS)

LOCALITIES: dict[str, str] = {
    "THIS_HOST": "the reading records the fingerprint of the machine reading it now",
    "OTHER_HOST": "the reading records a different machine's fingerprint",
    "NO_HOST_RECORDED": "the reading records no host, so it attributes itself to "
                        "nothing and cannot be checked against this machine",
}
LOCALITY_VALUES = tuple(LOCALITIES)

#: The derived scope. Ordered least to most demanding; a document sits in
#: exactly one, and a higher scope implies every lower one holds.
SCOPES: dict[str, str] = {
    "HISTORICAL": "it happened, and nothing here says it still holds",
    "CANONICAL_VERIFIED": "bound to a revision that still describes HEAD, on whatever "
                          "host; this is what 'the federation has been verified' means",
    "CURRENT_ENV": "canonical, and taken on this machine inside the freshness window; "
                   "this is what 'it works here, now' means",
    "CURRENT_LIVE_PROBE": "produced by a probe this run executed, not read from a file",
}
SCOPE_VALUES = tuple(SCOPES)


# --- the worker/provider vocabulary (section 3 of the directive) --------------

CLASSIFICATIONS: dict[str, str] = {
    "VERIFIED_LIVE_NOW": "something this run executed against it came back",
    "VERIFIED_HISTORICALLY": "a bound, still-describing-HEAD record says it worked; "
                             "no one has asked it anything since",
    "CONFIGURED_NOT_PROBED": "the registries name it and nothing has tried it",
    "CATALOG_ONLY": "it appears in a catalogue of candidates and is configured nowhere",
    "CREDENTIAL_REQUIRED": "reaching it needs a credential this environment does not "
                           "hold; that is a fact about this environment, not about it",
    "LICENSE_GATE_REQUIRED": "reaching it needs a licence acceptance that has not been "
                             "recorded",
    "UNAVAILABLE": "it was reached, or reachably attempted, and cannot serve",
}
CLASSIFICATION_VALUES = tuple(CLASSIFICATIONS)

#: A classification that counts towards CURRENT_ENV_ACTIVE_WORKERS. Exactly one
#: does. VERIFIED_HISTORICALLY deliberately does not: the whole point of the
#: split is that a past pass is not a present path.
ACTIVE_NOW = ("VERIFIED_LIVE_NOW",)

#: ...and towards CANONICAL_VERIFIED_WORKERS. Two do.
CANONICAL_VERIFIED = ("VERIFIED_LIVE_NOW", "VERIFIED_HISTORICALLY")

#: The providers this tool reports on. Named here rather than discovered so that
#: a provider silently disappearing from a registry cannot silently disappear
#: from the report.
TRACKED_PROVIDERS = ("ephemeral-local-0", "github_actions_ubuntu_latest",
                     "cloudflare_workers_ai", "nvidia_nim")

#: Per provider: the evidence file that would show it has ever answered, the
#: field carrying that document's verdict, and the value that counts as a pass.
#: A provider absent from this table has no probe record, which is a different
#: fact from having a failing one and is reported as such.
PROVIDER_EVIDENCE: dict[str, tuple[str, str, Any]] = {
    "ephemeral-local-0": ("WORKER_EXECUTION_LIVENESS.json", "EXECUTION_LIVE", True),
    "cloudflare_workers_ai": ("WORKERS_AI_FREE_TIER_PROBE.json", "status", "PROBED"),
}


def historical_classification(provider_id: str, *, root: Path,
                              host_fingerprint: str,
                              now: datetime) -> tuple[str, dict[str, Any] | None]:
    """Has this provider EVER answered, and does that record still describe HEAD?

    Credential-blind on purpose, and separate from `classify` for the reason
    this whole tool exists: an audit run without a credential correctly reports
    CREDENTIAL_REQUIRED, and if that were the only axis, the report would also
    have said the provider was never verified. It is not the same sentence. So
    the current axis may say CREDENTIAL_REQUIRED while this one says
    VERIFIED_HISTORICALLY, and both stand.
    """
    entry = PROVIDER_EVIDENCE.get(provider_id)
    if entry is None:
        return "CONFIGURED_NOT_PROBED", None
    name, field, passing = entry
    document, problem = _load(root / EVIDENCE / name)
    if problem is not None:
        return "CONFIGURED_NOT_PROBED", {"evidence": name, "reason": problem}
    reading = scope_document(document, root=root,
                             host_fingerprint=host_fingerprint, now=now)
    reading["evidence"] = name
    reading["claim_field"] = field
    reading["claims_pass"] = (isinstance(document, dict)
                              and document.get(field) == passing)
    if not reading["claims_pass"]:
        return "CONFIGURED_NOT_PROBED", reading
    return "VERIFIED_HISTORICALLY", reading


# --- bounded readers ----------------------------------------------------------

MAX_ID = 128
MAX_TEXT = 600
MAX_TIMESTAMP = 32
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/+-]{0,127}\Z")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def _bounded(value: Any, pattern: re.Pattern[str], limit: int) -> str | None:
    """A string that matches, or None. Never a value copied through unread."""
    if not isinstance(value, str) or len(value) > limit:
        return None
    return value if pattern.match(value) else None


def _text(value: Any) -> str:
    return " ".join(str(value).split())[:MAX_TEXT]


def _parse_timestamp(value: Any) -> datetime | None:
    stamp = _bounded(value, _TIMESTAMP_RE, MAX_TIMESTAMP)
    if stamp is None:
        return None
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# --- revision verification ----------------------------------------------------

#: The surfaces whose movement invalidates evidence from before it. Same list
#: the always-on gate uses, named here rather than imported so that this tool's
#: judgement does not silently change when that gate's does.
PROVED_SURFACES = ("AI_SKILL_LIBRARY/", "cloudflare-worker/")


def _git(root: Path, *args: str) -> tuple[int | None, str]:
    try:
        done = subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return done.returncode, done.stdout.strip()


def revision_freshness(source_sha: str, root: Path) -> tuple[str, str]:
    """Which FRESHNESS value this revision earns, and why. Fails closed."""
    rc, resolved = _git(root, "rev-parse", "--verify", "%s^{commit}" % source_sha)
    if rc is None:
        return "STALE_REVISION", ("git could not be run, so no revision could be "
                                  "verified; unverifiable is not verified")
    if rc != 0 or not SOURCE_SHA_RE.match(resolved or ""):
        return "STALE_REVISION", "%s names no commit in this repository" % source_sha

    head_rc, head = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    if head_rc is None or head_rc != 0 or not SOURCE_SHA_RE.match(head or ""):
        return "STALE_REVISION", "HEAD could not be read, so nothing can be compared"
    if resolved == head:
        return "CURRENT_REVISION", "bound to HEAD %s" % head

    anc_rc, _ = _git(root, "merge-base", "--is-ancestor", resolved, head)
    if anc_rc != 0:
        return "STALE_REVISION", ("%s is neither HEAD nor an ancestor of it"
                                  % source_sha)
    diff_rc, _ = _git(root, "diff", "--quiet", resolved, head, "--", *PROVED_SURFACES)
    if diff_rc != 0:
        return "STALE_REVISION", ("%s is an ancestor of HEAD, but %s moved between "
                                  "them" % (source_sha, " or ".join(PROVED_SURFACES)))
    return "ANCESTOR_SURFACES_UNCHANGED", ("%s is an ancestor of HEAD and no proved "
                                           "surface moved since" % source_sha)


# --- scoping a document -------------------------------------------------------


def scope_document(document: Any, *, root: Path, host_fingerprint: str,
                   now: datetime) -> dict[str, Any]:
    """The three axes and the derived scope for one evidence document.

    Deliberately not keyed off what the document claims. A document saying
    PROVEN gets exactly the same scoping as one saying FAILED; the claim is
    reported beside the scope, never used to decide it.
    """
    reading: dict[str, Any] = {
        "binding": "UNBOUND",
        "freshness": "NOT_APPLICABLE",
        "locality": "NO_HOST_RECORDED",
        "scope": "HISTORICAL",
        "source_sha": None,
        "proof_timestamp": None,
        "age_seconds": None,
        "reasons": [],
    }
    if not isinstance(document, dict):
        reading["reasons"].append("not an object; nothing can be read from it")
        return reading

    sha = _bounded(document.get("source_sha"), SOURCE_SHA_RE, 64)
    stamp_raw = document.get("proof_timestamp")
    stamp = _parse_timestamp(stamp_raw)
    reading["source_sha"] = sha
    reading["proof_timestamp"] = _bounded(stamp_raw, _TIMESTAMP_RE, MAX_TIMESTAMP)

    if sha is None or stamp is None:
        reading["reasons"].append(BINDINGS["UNBOUND"])
        return reading

    freshness, why = revision_freshness(sha, root)
    reading["freshness"] = freshness
    reading["reasons"].append(why)
    rc, _ = _git(root, "rev-parse", "--verify", "%s^{commit}" % sha)
    reading["binding"] = "BOUND_TO_REVISION" if rc == 0 else "UNRESOLVABLE"
    if reading["binding"] == "UNRESOLVABLE":
        reading["reasons"].append(BINDINGS["UNRESOLVABLE"])
        return reading

    observed = document.get("OBSERVED_ON")
    recorded_host = None
    if isinstance(observed, dict):
        recorded_host = _bounded(observed.get("host_fingerprint"), _ID_RE, MAX_ID)
    if recorded_host is None:
        reading["locality"] = "NO_HOST_RECORDED"
    elif recorded_host == host_fingerprint:
        reading["locality"] = "THIS_HOST"
    else:
        reading["locality"] = "OTHER_HOST"

    age = (now - stamp).total_seconds()
    reading["age_seconds"] = int(age)

    if freshness in ("CURRENT_REVISION", "ANCESTOR_SURFACES_UNCHANGED"):
        reading["scope"] = "CANONICAL_VERIFIED"
        if (reading["locality"] == "THIS_HOST"
                and 0 <= age <= CURRENT_ENV_MAX_AGE_SECONDS):
            reading["scope"] = "CURRENT_ENV"
        elif reading["locality"] == "THIS_HOST":
            reading["reasons"].append(
                "taken on this host but %ds old, past the %ds window, so it "
                "describes then and not now" % (int(age), CURRENT_ENV_MAX_AGE_SECONDS))
    return reading


# --- credentials, by name only ------------------------------------------------

#: Provider id -> the environment variable names that would let this environment
#: reach it. Only ever tested for emptiness. No value is read, logged, recorded
#: or returned; a credential that reached this tool's output would be a
#: credential in a committed evidence file.
CREDENTIAL_NAMES: dict[str, tuple[str, ...]] = {
    "cloudflare_workers_ai": ("CLOUDFLARE_API_TOKEN", "CF_API_TOKEN"),
    "nvidia_nim": ("NVIDIA_API_KEY", "NGC_API_KEY"),
    "huggingface_inference": ("HF_TOKEN", "HUGGINGFACE_TOKEN"),
    "groq": ("GROQ_API_KEY",),
    "together": ("TOGETHER_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "github_actions_ubuntu_latest": ("GITHUB_TOKEN", "GH_TOKEN"),
}


def credential_present(provider_id: str,
                       environ: dict[str, str] | None = None) -> bool | None:
    """True, False, or None when this tool does not know what it would need.

    None is not False. A provider whose credential requirement is unknown is not
    thereby credential-free, and it is not thereby blocked either; it is
    unclassified, and saying so is the whole job.
    """
    names = CREDENTIAL_NAMES.get(provider_id)
    if names is None:
        return None
    env = os.environ if environ is None else environ
    return any(env.get(name) for name in names)


def classify(provider_id: str, *, probe_result: str | None = None,
             configured: bool = False, catalogued: bool = False,
             licence_gate: bool = False,
             environ: dict[str, str] | None = None) -> tuple[str, str]:
    """One classification and the reason for it. Order matters and is argued.

    A live probe outranks everything because it is the only input that describes
    now. Absent one, a licence gate outranks a credential gate because accepting
    a licence is a decision and obtaining a credential is an errand. A credential
    gate outranks 'configured but unprobed' because it says *why* it was not
    probed. UNAVAILABLE is reserved for a path that was actually reached.
    """
    if probe_result == EXECUTION_LIVE:
        return "VERIFIED_LIVE_NOW", CLASSIFICATIONS["VERIFIED_LIVE_NOW"]
    if probe_result == EXECUTION_DEAD:
        return "UNAVAILABLE", ("probed from here this run and it cannot serve: "
                               + CLASSIFICATIONS["UNAVAILABLE"])
    if licence_gate:
        return "LICENSE_GATE_REQUIRED", CLASSIFICATIONS["LICENSE_GATE_REQUIRED"]
    if credential_present(provider_id, environ) is False:
        return "CREDENTIAL_REQUIRED", CLASSIFICATIONS["CREDENTIAL_REQUIRED"]
    if configured:
        return "CONFIGURED_NOT_PROBED", CLASSIFICATIONS["CONFIGURED_NOT_PROBED"]
    if catalogued:
        return "CATALOG_ONLY", CLASSIFICATIONS["CATALOG_ONLY"]
    return "CONFIGURED_NOT_PROBED", CLASSIFICATIONS["CONFIGURED_NOT_PROBED"]


# --- the documents this tool scopes -------------------------------------------
#
# Each entry names the field carrying the document's own claim and the value
# that counts as a pass. The claim is reported next to the scope and never used
# to compute it - a document does not get to vouch for its own freshness.

SCOPED_DOCUMENTS: dict[str, tuple[str, Any]] = {
    "FEDERATION_24X7_PROOF.json": ("federation_status", "PROVEN"),
    "FREE_WORKER_MESH_PROOF.json": ("mesh_status", "PROVEN"),
    "CRITICAL_ROLE_REDUNDANCY_PROOF.json": ("ready", True),
    "WORKER_EXECUTION_LIVENESS.json": ("EXECUTION_LIVE", True),
    "MEMORY_CONTINUITY_PROOF.json": ("ready", True),
}
SCOPED_DOCUMENT_NAMES = tuple(SCOPED_DOCUMENTS)


def _load(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        return None, "absent"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, _text("unreadable: %s" % type(exc).__name__)


def scope_evidence(root: Path, *, host_fingerprint: str,
                   now: datetime) -> dict[str, dict[str, Any]]:
    """Every tracked document, scoped. Absent and unreadable are not passes."""
    out: dict[str, dict[str, Any]] = {}
    for name, (field, passing) in SCOPED_DOCUMENTS.items():
        document, problem = _load(root / EVIDENCE / name)
        if problem is not None:
            out[name] = {"binding": "UNBOUND", "freshness": "NOT_APPLICABLE",
                         "locality": "NO_HOST_RECORDED", "scope": "HISTORICAL",
                         "source_sha": None, "proof_timestamp": None,
                         "age_seconds": None, "claims_pass": False,
                         "claim_field": field, "reasons": [problem]}
            continue
        reading = scope_document(document, root=root,
                                 host_fingerprint=host_fingerprint, now=now)
        reading["claim_field"] = field
        reading["claims_pass"] = (isinstance(document, dict)
                                  and document.get(field) == passing)
        out[name] = reading
    return out


def _canonical(reading: dict[str, Any]) -> bool:
    """A claim that both passed and still describes HEAD."""
    return bool(reading.get("claims_pass")) and reading.get("scope") in (
        "CANONICAL_VERIFIED", "CURRENT_ENV")


def probe_this_environment(root: Path) -> dict[str, Any]:
    """What this machine can be shown to do, right now, by trying it.

    The local engine is probed in a subprocess by the liveness tool, for the
    reason that tool documents: SIGILL is not an exception, so an in-process
    probe takes the prober down with it and leaves no evidence at all.
    """
    from worker_execution_liveness import probe_local_engine  # noqa: PLC0415

    engine = probe_local_engine(root)
    state = engine.get("state")
    if state not in (EXECUTION_LIVE, EXECUTION_DEAD, EXECUTION_UNKNOWN):
        state = EXECUTION_UNKNOWN
    return {"local_engine": state, "local_engine_detail": _text(engine.get("reason", ""))}


# --- Work's free-worker matrix, as candidate evidence only --------------------


def reconcile_work_matrix(matrix: Any, *, environ: dict[str, str] | None = None,
                          scoped: dict[str, dict[str, Any]] | None = None,
                          probe: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify an external audit's rows without letting it set any flag.

    The matrix arrives from an environment with its own credential state, which
    is the one thing about it that does not travel. So its rows are read for
    *identity* - which provider, which licence gate - and re-classified against
    what is true here. Its own verdict fields are recorded under
    ``reported_by_work`` and are not consulted by the classifier.
    """
    result: dict[str, Any] = {"present": False, "rows": [], "rejected_rows": [],
                              "note": "candidate evidence; sets no flag in this tool"}
    if matrix is None:
        result["reason"] = ("no matrix supplied; every provider below is classified "
                            "from this repository's own evidence alone")
        return result
    rows = matrix.get("workers") if isinstance(matrix, dict) else None
    if not isinstance(rows, list):
        result["reason"] = "matrix carries no 'workers' list; nothing to reconcile"
        return result

    result["present"] = True
    probe = probe or {}
    for record in rows[:256]:
        if not isinstance(record, dict):
            result["rejected_rows"].append({"reason": "row is not an object"})
            continue
        provider_id = _bounded(record.get("provider_id") or record.get("worker_id"),
                               _ID_RE, MAX_ID)
        if provider_id is None:
            result["rejected_rows"].append(
                {"reason": "row names no provider_id or worker_id within bounds"})
            continue
        licence_gate = record.get("license_accepted") is False
        classification, why = classify(
            provider_id,
            probe_result=probe.get(provider_id),
            configured=True,
            licence_gate=licence_gate,
            environ=environ,
        )
        result["rows"].append({
            "provider_id": provider_id,
            "classification": classification,
            "why": why,
            "reported_by_work": _text(record.get("status", "")),
            "provenance": "FREE_WORKER_EXPANSION_MATRIX.json (Work audit)",
        })
    return result


# --- the report ---------------------------------------------------------------


def build(root: Path, *, work_matrix: Any = None,
          environ: dict[str, str] | None = None,
          skip_probe: bool = False) -> dict[str, Any]:
    observed = observing_host()
    host_fingerprint = observed.get("host_fingerprint", "host_not_recorded")
    now = datetime.now(timezone.utc)
    source_sha = current_source_sha(root)

    scoped = scope_evidence(root, host_fingerprint=host_fingerprint, now=now)
    probe = ({} if skip_probe
             else {"ephemeral-local-0": probe_this_environment(root)["local_engine"]})

    providers: list[dict[str, Any]] = []
    for provider_id in TRACKED_PROVIDERS:
        historical, record = historical_classification(
            provider_id, root=root, host_fingerprint=host_fingerprint, now=now)
        current, why = classify(
            provider_id,
            probe_result=probe.get(provider_id),
            configured=True,
            environ=environ,
        )
        providers.append({
            "provider_id": provider_id,
            # Two axes, never one. `current` answers "can this environment reach
            # it right now"; `historical` answers "has it ever answered anything,
            # and does that record still describe HEAD". A false on the first is
            # not a false on the second and this shape makes that unsayable.
            "current_classification": current,
            "current_why": why,
            "historical_classification": historical,
            "historical_evidence": record,
            "counts_as_canonical": bool(
                historical in CANONICAL_VERIFIED and record is not None
                and record.get("scope") in ("CANONICAL_VERIFIED", "CURRENT_ENV")),
        })

    current_env_active = sum(1 for row in providers
                             if row["current_classification"] in ACTIVE_NOW)
    canonical_workers = sum(1 for row in providers if row["counts_as_canonical"])

    last_verified = [r["proof_timestamp"] for r in scoped.values()
                     if _canonical(r) and r["proof_timestamp"]]

    report: dict[str, Any] = {
        "tool": "federation_status_scopes",
        "source_sha": source_sha,
        "proof_timestamp": utc_now(),
        "OBSERVED_ON": observed,
        "scope_vocabulary": SCOPES,
        "classification_vocabulary": CLASSIFICATIONS,

        # Scoped flags. Deliberately not collapsible: each answers a different
        # question and they are allowed to disagree.
        "CURRENT_ENV_24X7_READY": bool(
            scoped["FEDERATION_24X7_PROOF.json"]["scope"] == "CURRENT_ENV"
            and scoped["FEDERATION_24X7_PROOF.json"]["claims_pass"]),
        "CANONICAL_24X7_FEDERATION_READY": _canonical(
            scoped["FEDERATION_24X7_PROOF.json"]),
        "CURRENT_ENV_ACTIVE_WORKERS": current_env_active,
        "CANONICAL_VERIFIED_WORKERS": canonical_workers,
        "CURRENT_PROVIDER_LIVENESS": providers,
        "LAST_VERIFIED_AT": max(last_verified) if last_verified else None,
        "EVIDENCE_FRESHNESS": scoped,

        "work_audit_reconciliation": reconcile_work_matrix(
            work_matrix, environ=environ, scoped=scoped, probe=probe),

        "authority": AUTHORITY,
        "routing_authority": ROUTING_AUTHORITY,
        "model_selection_authority": MODEL_SELECTION_AUTHORITY,
        "admission_authority": ADMISSION_AUTHORITY,
        "scheduling_authority": SCHEDULING_AUTHORITY,
        "changes_nothing": True,
    }
    return report


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--work-matrix", type=Path, default=None,
                        help="FREE_WORKER_EXPANSION_MATRIX.json from the Work audit; "
                             "read as candidate evidence, never as authority")
    parser.add_argument("--skip-probe", action="store_true",
                        help="do not probe the local engine; it is then UNKNOWN, "
                             "which is not a pass")
    args = parser.parse_args(list(argv) if argv is not None else None)

    matrix = None
    if args.work_matrix is not None:
        matrix, problem = _load(args.work_matrix)
        if problem is not None:
            print("WORK_MATRIX=%s" % problem, file=sys.stderr)

    report = build(args.root, work_matrix=matrix, skip_probe=args.skip_probe)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    for flag in ("CURRENT_ENV_24X7_READY", "CANONICAL_24X7_FEDERATION_READY",
                 "CURRENT_ENV_ACTIVE_WORKERS", "CANONICAL_VERIFIED_WORKERS",
                 "LAST_VERIFIED_AT"):
        print("%s=%s" % (flag, report[flag]))
    for name, reading in report["EVIDENCE_FRESHNESS"].items():
        print("  %-42s %-18s claims_pass=%s" % (name, reading["scope"],
                                                reading["claims_pass"]))
    for row in report["CURRENT_PROVIDER_LIVENESS"]:
        print("  %-30s now=%-22s ever=%-22s canonical=%s"
              % (row["provider_id"], row["current_classification"],
                 row["historical_classification"], row["counts_as_canonical"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --- why a live round did not pass, established by measurement ----------------

#: The closed set of verdicts on a proof's live inference round. The distinction
#: that matters to a closure gate is between "this host cannot run it" and
#: "it ran and was wrong", and the two must not be reachable by the same input.
LIVE_ROUND_STATUSES: dict[str, str] = {
    "PASSED": "the round ran here and passed",
    "REAL_RUNTIME_REQUIRED": "the round could not run here because the inference "
                             "engine on this machine cannot execute, established by "
                             "probing it and not by anyone passing a flag",
    "SKIPPED_BY_FLAG": "the round was skipped while the engine was capable of "
                       "running it; a choice not to measure is not a finding",
    "ROUND_FAILED": "the round ran and did not pass",
}
LIVE_ROUND_STATUS_VALUES = tuple(LIVE_ROUND_STATUSES)

#: Only this one lets a closure gate proceed without a live pass, and only while
#: it is reported explicitly alongside. SKIPPED_BY_FLAG is deliberately absent:
#: if a flag could produce the same verdict as a measurement, the verdict would
#: be an ALLOWED value that nothing bounds, which is the defect this repository
#: has now corrected nine times.
GATE_TOLERATED_LIVE_STATUSES = ("PASSED", "REAL_RUNTIME_REQUIRED")


def classify_live_round(root: Path, *, ran: bool, passed: bool) -> dict[str, Any]:
    """PASSED, ROUND_FAILED, or - only on a measured dead engine - REAL_RUNTIME_REQUIRED.

    `ran` and `passed` describe what the proof did. Whether a non-run counts as
    an external requirement or as an unmeasured gap is decided here by probing
    the engine in a subprocess, because SIGILL is not an exception and an
    in-process probe would take the prober down with it.
    """
    if ran and passed:
        return {"live_round_status": "PASSED",
                "why": LIVE_ROUND_STATUSES["PASSED"],
                "engine_state": None}
    if ran and not passed:
        return {"live_round_status": "ROUND_FAILED",
                "why": LIVE_ROUND_STATUSES["ROUND_FAILED"],
                "engine_state": None}

    from worker_execution_liveness import probe_local_engine  # noqa: PLC0415

    engine = probe_local_engine(root)
    state = engine.get("state")
    if state == EXECUTION_DEAD:
        return {"live_round_status": "REAL_RUNTIME_REQUIRED",
                "why": LIVE_ROUND_STATUSES["REAL_RUNTIME_REQUIRED"],
                "engine_state": state,
                "engine_detail": _text(engine.get("reason", "")),
                "operator_action": ("run this proof on a host whose inference engine "
                                    "executes, or install an engine build this CPU "
                                    "supports; no edit to this repository can supply "
                                    "the missing measurement")}
    # An engine that is live, or that could not be probed, does not excuse an
    # unmeasured round. UNKNOWN is not a pass and is not an external blocker.
    return {"live_round_status": "SKIPPED_BY_FLAG",
            "why": LIVE_ROUND_STATUSES["SKIPPED_BY_FLAG"],
            "engine_state": state}


def blocking_class(state_rounds_failed: Sequence[str],
                   live: dict[str, Any]) -> str:
    """What is stopping this proof: a real round, an absent runtime, or nothing."""
    if state_rounds_failed:
        return "ROUND_FAILED"
    status = live.get("live_round_status")
    if status == "PASSED":
        return "NONE"
    if status == "REAL_RUNTIME_REQUIRED":
        return "REAL_RUNTIME_REQUIRED"
    return "ROUND_FAILED"
