"""The whole point is that two true statements are allowed to disagree."""

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent / "v4" / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_spec = importlib.util.spec_from_file_location(
    "federation_status_scopes", _TOOLS / "federation_status_scopes.py")
scopes = importlib.util.module_from_spec(_spec)
sys.modules["federation_status_scopes"] = scopes
_spec.loader.exec_module(scopes)

ROOT = _HERE.parent.parent
NOW = datetime(2026, 9, 18, 8, 0, 0, tzinfo=timezone.utc)


def _head():
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


# --- the vocabularies are derived, never restated -----------------------------

def test_vocabulary_tuples_are_derived_from_their_tables():
    # Not `== tuple(...)`: that would pass for a hand-written tuple that happens
    # to agree today. These must be the same object's keys, so a table edit
    # cannot leave a tuple behind.
    assert scopes.BINDING_VALUES == tuple(scopes.BINDINGS)
    assert scopes.FRESHNESS_VALUES == tuple(scopes.FRESHNESS)
    assert scopes.LOCALITY_VALUES == tuple(scopes.LOCALITIES)
    assert scopes.SCOPE_VALUES == tuple(scopes.SCOPES)
    assert scopes.CLASSIFICATION_VALUES == tuple(scopes.CLASSIFICATIONS)
    assert scopes.SCOPED_DOCUMENT_NAMES == tuple(scopes.SCOPED_DOCUMENTS)


def test_every_vocabulary_member_carries_a_written_reason():
    for table in (scopes.BINDINGS, scopes.FRESHNESS, scopes.LOCALITIES,
                  scopes.SCOPES, scopes.CLASSIFICATIONS):
        for name, reason in table.items():
            assert isinstance(reason, str) and len(reason) > 20, name


def test_counting_sets_are_subsets_of_the_vocabulary():
    for name in scopes.ACTIVE_NOW + scopes.CANONICAL_VERIFIED:
        assert name in scopes.CLASSIFICATIONS


# --- an unbound claim can never be canonical ----------------------------------

def test_a_passing_document_with_no_binding_is_historical():
    reading = scopes.scope_document(
        {"federation_status": "PROVEN", "rounds_passed": 22, "rounds_total": 22},
        root=ROOT, host_fingerprint="abc", now=NOW)
    assert reading["binding"] == "UNBOUND"
    assert reading["scope"] == "HISTORICAL"


def test_the_claim_itself_never_influences_the_scope():
    passed = scopes.scope_document({"federation_status": "PROVEN"},
                                   root=ROOT, host_fingerprint="abc", now=NOW)
    failed = scopes.scope_document({"federation_status": "FAILED"},
                                   root=ROOT, host_fingerprint="abc", now=NOW)
    assert passed["scope"] == failed["scope"] == "HISTORICAL"


def test_timestamp_without_sha_is_unbound():
    reading = scopes.scope_document({"proof_timestamp": "2026-09-18T07:00:00Z"},
                                    root=ROOT, host_fingerprint="abc", now=NOW)
    assert reading["binding"] == "UNBOUND"


def test_sha_without_timestamp_is_unbound():
    reading = scopes.scope_document({"source_sha": _head()},
                                    root=ROOT, host_fingerprint="abc", now=NOW)
    assert reading["binding"] == "UNBOUND"


def test_an_invented_sha_is_not_a_revision():
    reading = scopes.scope_document(
        {"source_sha": "0" * 40, "proof_timestamp": "2026-09-18T07:00:00Z"},
        root=ROOT, host_fingerprint="abc", now=NOW)
    assert reading["freshness"] == "STALE_REVISION"
    assert reading["scope"] == "HISTORICAL"


def test_a_sha_with_a_trailing_newline_is_refused():
    # `\Z` and not `$`: Python's `$` also matches before a trailing newline, so
    # a `$`-anchored check would let "<sha>\n" through with the newline still on.
    reading = scopes.scope_document(
        {"source_sha": _head() + "\n", "proof_timestamp": "2026-09-18T07:00:00Z"},
        root=ROOT, host_fingerprint="abc", now=NOW)
    assert reading["binding"] == "UNBOUND"


def test_non_object_documents_fail_closed():
    for document in (None, [], "PROVEN", 22, True):
        reading = scopes.scope_document(document, root=ROOT,
                                        host_fingerprint="abc", now=NOW)
        assert reading["scope"] == "HISTORICAL"


# --- the locality and freshness split -----------------------------------------

def _at_head(host, stamp):
    return {"source_sha": _head(), "proof_timestamp": stamp,
            "OBSERVED_ON": {"host_fingerprint": host}}


def test_head_on_this_host_inside_the_window_is_current_env():
    stamp = (NOW - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reading = scopes.scope_document(_at_head("thishost", stamp), root=ROOT,
                                    host_fingerprint="thishost", now=NOW)
    assert reading["freshness"] == "CURRENT_REVISION"
    assert reading["locality"] == "THIS_HOST"
    assert reading["scope"] == "CURRENT_ENV"


def test_head_on_another_host_is_canonical_but_not_current_env():
    stamp = (NOW - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reading = scopes.scope_document(_at_head("elsewhere", stamp), root=ROOT,
                                    host_fingerprint="thishost", now=NOW)
    assert reading["locality"] == "OTHER_HOST"
    assert reading["scope"] == "CANONICAL_VERIFIED"


def test_head_on_this_host_past_the_window_drops_to_canonical():
    old = NOW - timedelta(seconds=scopes.CURRENT_ENV_MAX_AGE_SECONDS + 60)
    reading = scopes.scope_document(
        _at_head("thishost", old.strftime("%Y-%m-%dT%H:%M:%SZ")),
        root=ROOT, host_fingerprint="thishost", now=NOW)
    assert reading["scope"] == "CANONICAL_VERIFIED"
    assert any("past the" in r for r in reading["reasons"])


def test_a_reading_from_the_future_is_not_current():
    ahead = NOW + timedelta(hours=2)
    reading = scopes.scope_document(
        _at_head("thishost", ahead.strftime("%Y-%m-%dT%H:%M:%SZ")),
        root=ROOT, host_fingerprint="thishost", now=NOW)
    assert reading["scope"] == "CANONICAL_VERIFIED"


def test_no_recorded_host_is_never_current_env():
    stamp = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    reading = scopes.scope_document(
        {"source_sha": _head(), "proof_timestamp": stamp},
        root=ROOT, host_fingerprint="thishost", now=NOW)
    assert reading["locality"] == "NO_HOST_RECORDED"
    assert reading["scope"] == "CANONICAL_VERIFIED"


# --- credentials: presence only, never a value --------------------------------

def test_credential_presence_is_a_boolean_or_none_never_a_value():
    secret = "sk-not-a-real-token-0123456789"
    env = {"CLOUDFLARE_API_TOKEN": secret}
    assert scopes.credential_present("cloudflare_workers_ai", env) is True
    assert scopes.credential_present("nvidia_nim", env) is False
    assert scopes.credential_present("a_provider_nobody_declared", env) is None


def test_unknown_credential_requirement_is_not_treated_as_absent():
    # None is not False. An unclassified provider must not be reported as
    # blocked on a credential nobody has named.
    classification, _ = scopes.classify("a_provider_nobody_declared",
                                        configured=True, environ={})
    assert classification != "CREDENTIAL_REQUIRED"


def test_no_credential_value_reaches_the_report():
    secret = "sk-not-a-real-token-0123456789"
    report = scopes.build(ROOT, environ={"CLOUDFLARE_API_TOKEN": secret,
                                         "NVIDIA_API_KEY": secret},
                          skip_probe=True)
    assert secret not in json.dumps(report)


# --- the reconciliation this tool exists for ----------------------------------

def test_a_missing_credential_is_not_unavailable():
    classification, _ = scopes.classify("cloudflare_workers_ai",
                                        configured=True, environ={})
    assert classification == "CREDENTIAL_REQUIRED"
    assert classification != "UNAVAILABLE"


def test_a_missing_credential_does_not_erase_a_past_verification():
    # The exact failure mode the Work audit would otherwise have caused:
    # no credential in this container, therefore "never verified".
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    row = next(r for r in report["CURRENT_PROVIDER_LIVENESS"]
               if r["provider_id"] == "cloudflare_workers_ai")
    assert row["current_classification"] == "CREDENTIAL_REQUIRED"
    assert row["historical_classification"] == "VERIFIED_HISTORICALLY"


def test_a_past_verification_does_not_make_a_provider_live_now():
    # ...and the mistake in the other direction.
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    row = next(r for r in report["CURRENT_PROVIDER_LIVENESS"]
               if r["provider_id"] == "cloudflare_workers_ai")
    assert row["current_classification"] != "VERIFIED_LIVE_NOW"
    assert report["CURRENT_ENV_ACTIVE_WORKERS"] == 0


def test_classify_never_returns_verified_historically():
    for provider_id in scopes.TRACKED_PROVIDERS:
        for probe in (None, scopes.EXECUTION_LIVE, scopes.EXECUTION_DEAD,
                      scopes.EXECUTION_UNKNOWN):
            classification, _ = scopes.classify(provider_id, probe_result=probe,
                                                configured=True, environ={})
            assert classification != "VERIFIED_HISTORICALLY"


def test_historical_classification_ignores_credentials():
    a = scopes.historical_classification(
        "cloudflare_workers_ai", root=ROOT, host_fingerprint="x", now=NOW)
    os.environ.pop("CLOUDFLARE_API_TOKEN", None)
    b = scopes.historical_classification(
        "cloudflare_workers_ai", root=ROOT, host_fingerprint="x", now=NOW)
    assert a[0] == b[0] == "VERIFIED_HISTORICALLY"


def test_an_unbound_historical_pass_does_not_count_as_canonical():
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    row = next(r for r in report["CURRENT_PROVIDER_LIVENESS"]
               if r["provider_id"] == "cloudflare_workers_ai")
    assert row["historical_classification"] == "VERIFIED_HISTORICALLY"
    assert row["counts_as_canonical"] is False


# --- the flags -----------------------------------------------------------------

def test_the_unbound_24x7_proof_cannot_set_the_canonical_flag():
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    reading = report["EVIDENCE_FRESHNESS"]["FEDERATION_24X7_PROOF.json"]
    assert reading["claims_pass"] is True        # the file says PROVEN
    assert reading["scope"] == "HISTORICAL"      # and nothing binds that
    assert report["CANONICAL_24X7_FEDERATION_READY"] is False
    assert report["CURRENT_ENV_24X7_READY"] is False


def test_current_env_flag_is_never_set_by_a_non_current_env_document():
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    for name, reading in report["EVIDENCE_FRESHNESS"].items():
        if reading["scope"] != "CURRENT_ENV":
            continue
        assert report["CURRENT_ENV_24X7_READY"] or name != "FEDERATION_24X7_PROOF.json"


def test_absent_evidence_is_not_a_pass():
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    reading = report["EVIDENCE_FRESHNESS"]["MEMORY_CONTINUITY_PROOF.json"]
    assert reading["claims_pass"] is False
    assert reading["scope"] == "HISTORICAL"


def test_every_tracked_provider_appears_in_the_report():
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    named = {r["provider_id"] for r in report["CURRENT_PROVIDER_LIVENESS"]}
    assert named == set(scopes.TRACKED_PROVIDERS)


def test_the_report_claims_no_authority():
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    for field in ("authority", "routing_authority", "model_selection_authority",
                  "admission_authority", "scheduling_authority"):
        assert report[field] is False
    assert report["changes_nothing"] is True


def test_the_report_binds_itself():
    # A tool that refuses unbound evidence and then emits unbound evidence would
    # be the same defect wearing a different hat.
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    assert scopes.SOURCE_SHA_RE.match(report["source_sha"] or "")
    assert scopes._parse_timestamp(report["proof_timestamp"]) is not None


def test_skip_probe_does_not_produce_a_pass():
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    row = next(r for r in report["CURRENT_PROVIDER_LIVENESS"]
               if r["provider_id"] == "ephemeral-local-0")
    assert row["current_classification"] != "VERIFIED_LIVE_NOW"


# --- the Work matrix is candidate evidence, never authority --------------------

def test_no_matrix_is_not_an_error():
    result = scopes.reconcile_work_matrix(None)
    assert result["present"] is False and result["rows"] == []


def test_a_matrix_verdict_never_becomes_a_classification():
    matrix = {"workers": [{"provider_id": "cloudflare_workers_ai",
                           "status": "VERIFIED_ACTIVE"}]}
    result = scopes.reconcile_work_matrix(matrix, environ={})
    row = result["rows"][0]
    assert row["reported_by_work"] == "VERIFIED_ACTIVE"
    assert row["classification"] == "CREDENTIAL_REQUIRED"


def test_matrix_rows_without_an_id_are_rejected_not_guessed():
    matrix = {"workers": [{"status": "VERIFIED_ACTIVE"}, "not an object",
                          {"provider_id": "x" * 400}]}
    result = scopes.reconcile_work_matrix(matrix, environ={})
    assert result["rows"] == []
    assert len(result["rejected_rows"]) == 3


def test_a_malformed_matrix_is_reported_not_raised():
    for matrix in ({}, {"workers": "all of them"}, [], "workers"):
        result = scopes.reconcile_work_matrix(matrix, environ={})
        assert result["present"] is False


def test_a_licence_gate_outranks_a_credential_gate():
    matrix = {"workers": [{"provider_id": "cloudflare_workers_ai",
                           "license_accepted": False}]}
    result = scopes.reconcile_work_matrix(matrix, environ={})
    assert result["rows"][0]["classification"] == "LICENSE_GATE_REQUIRED"


def test_matrix_rows_are_bounded():
    matrix = {"workers": [{"provider_id": "p%d" % i} for i in range(400)]}
    result = scopes.reconcile_work_matrix(matrix, environ={})
    assert len(result["rows"]) <= 256


def test_main_runs_and_writes_bound_evidence(tmp_path):
    out = tmp_path / "scopes.json"
    assert scopes.main(["--evidence", str(out), "--skip-probe"]) == 0
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["tool"] == "federation_status_scopes"
    assert document["changes_nothing"] is True
