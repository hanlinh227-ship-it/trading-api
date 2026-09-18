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

def test_an_unbound_proof_cannot_set_the_canonical_flag():
    """The defect this tool was built to catch, kept as a live test.

    The committed 24x7 proof used to say PROVEN 22/22 with no revision, no
    moment and no host, and the scoping refused to count it. That document is
    preserved under evidence/historical/, so the case is still exercised
    against the real file rather than a fixture.
    """
    document = json.loads(
        (ROOT / "CHECKPOINTS/evidence/historical/FEDERATION_24X7_PROOF.json")
        .read_text(encoding="utf-8"))
    assert document["federation_status"] == "PROVEN"     # the file says so
    reading = scopes.scope_document(document, root=ROOT,
                                    host_fingerprint="anything", now=NOW)
    assert reading["binding"] == "UNBOUND"               # and nothing binds it
    assert reading["scope"] == "HISTORICAL"


def test_the_live_24x7_flags_follow_the_current_document():
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    reading = report["EVIDENCE_FRESHNESS"]["FEDERATION_24X7_PROOF.json"]
    # CI checks out with the default fetch-depth: 1, so an ancestor the document
    # legitimately names is simply absent from the clone. That is reported as
    # UNRESOLVABLE_HERE rather than UNRESOLVABLE, because "this clone lacks the
    # commit" and "this sha names no commit anywhere" are different claims and
    # the second accuses real evidence of being invented.
    assert reading["binding"] in ("BOUND_TO_REVISION", "UNRESOLVABLE_HERE")
    if reading["binding"] == "UNRESOLVABLE_HERE":
        assert scopes.is_shallow(ROOT)
        assert reading["scope"] == "HISTORICAL"
    assert report["CANONICAL_24X7_FEDERATION_READY"] is False
    assert report["CURRENT_ENV_24X7_READY"] is False


def test_current_env_flag_needs_both_scope_and_a_passing_claim():
    """Being current is not being green, and being green is not being current.

    The 24x7 document is CURRENT_ENV right now - bound to HEAD, taken on this
    machine, inside the window - and still fails, because the live inference
    round cannot run here. The flag is the conjunction and neither half alone.
    """
    report = scopes.build(ROOT, environ={}, skip_probe=True)
    reading = report["EVIDENCE_FRESHNESS"]["FEDERATION_24X7_PROOF.json"]
    assert report["CURRENT_ENV_24X7_READY"] == (
        reading["scope"] == "CURRENT_ENV" and reading["claims_pass"])


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


# --- the two proofs this tool caught asserting PROVEN with nothing behind it ---

def _tool(name):
    spec = importlib.util.spec_from_file_location(name, _TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_the_24x7_proof_now_binds_itself():
    result = _tool("federation_24x7_proof").build(ROOT, skip_live=True)
    assert scopes.SOURCE_SHA_RE.match(result["source_sha"] or "")
    assert scopes._parse_timestamp(result["proof_timestamp"]) is not None
    assert result["OBSERVED_ON"]["host_fingerprint"]


def test_the_free_worker_proof_now_binds_itself():
    result = _tool("free_worker_mesh_proof").build(ROOT, live=False)
    assert scopes.SOURCE_SHA_RE.match(result["source_sha"] or "")
    assert scopes._parse_timestamp(result["proof_timestamp"]) is not None


def test_a_skipped_live_round_leaves_the_denominator_alone():
    # The round used to be dropped rather than failed, which shrank BOTH sides
    # of the fraction and returned PROVEN 9/9 on a host that cannot execute one
    # instruction of the engine.
    result = _tool("free_worker_mesh_proof").build(ROOT, live=False)
    assert result["mesh_status"] == "FAILED"
    assert result["rounds_run"] == 10
    assert "J" in result["failed_rounds"]


def test_a_skipped_round_never_passes_in_either_proof():
    for module, kwargs, field in (
            ("federation_24x7_proof", {"skip_live": True}, "federation_status"),
            ("free_worker_mesh_proof", {"live": False}, "mesh_status")):
        result = _tool(module).build(ROOT, **kwargs)
        assert result[field] == "FAILED", module


def test_a_bound_proof_is_scoped_current_env_when_it_is_one():
    # End to end: the freshly built 24x7 proof, scoped by the tool that refused
    # the old unbound one, lands in CURRENT_ENV rather than HISTORICAL.
    result = _tool("federation_24x7_proof").build(ROOT, skip_live=True)
    host = result["OBSERVED_ON"]["host_fingerprint"]
    reading = scopes.scope_document(result, root=ROOT, host_fingerprint=host,
                                    now=datetime.now(timezone.utc))
    assert reading["binding"] == "BOUND_TO_REVISION"
    assert reading["locality"] == "THIS_HOST"
    assert reading["scope"] == "CURRENT_ENV"


# --- a live round that could not run vs one that was merely not run -----------

def test_live_round_vocabulary_is_derived():
    assert scopes.LIVE_ROUND_STATUS_VALUES == tuple(scopes.LIVE_ROUND_STATUSES)
    for name in scopes.GATE_TOLERATED_LIVE_STATUSES:
        assert name in scopes.LIVE_ROUND_STATUSES


def test_a_flag_cannot_produce_the_external_verdict():
    # The whole guard: if passing --skip-live were enough to yield
    # REAL_RUNTIME_REQUIRED, every closure gate honouring that verdict could be
    # cleared by an argument. Only a probed-dead engine may produce it, and
    # SKIPPED_BY_FLAG is deliberately not gate-tolerated.
    assert "SKIPPED_BY_FLAG" not in scopes.GATE_TOLERATED_LIVE_STATUSES


def test_a_round_that_ran_and_failed_is_not_external():
    verdict = scopes.classify_live_round(ROOT, ran=True, passed=False)
    assert verdict["live_round_status"] == "ROUND_FAILED"
    assert scopes.blocking_class([], verdict) == "ROUND_FAILED"


def test_a_round_that_ran_and_passed_blocks_nothing():
    verdict = scopes.classify_live_round(ROOT, ran=True, passed=True)
    assert verdict["live_round_status"] == "PASSED"
    assert scopes.blocking_class([], verdict) == "NONE"


def test_a_failed_state_round_outranks_an_absent_runtime():
    # An external blocker must never mask a real one.
    external = {"live_round_status": "REAL_RUNTIME_REQUIRED"}
    assert scopes.blocking_class(["C"], external) == "ROUND_FAILED"


def test_an_unprobeable_engine_is_not_an_external_blocker():
    for state in ("SKIPPED_BY_FLAG",):
        assert scopes.blocking_class([], {"live_round_status": state}) == "ROUND_FAILED"


def test_the_gate_predicate_needs_both_halves():
    from importlib import import_module
    gate = _tool("wave3_closure_gate")
    ok, verdict = gate._proven_or_external({"mesh_status": "PROVEN"}, "mesh_status")
    assert (ok, verdict) == (True, "PROVEN")
    ok, verdict = gate._proven_or_external(
        {"mesh_status": "FAILED", "blocking_class": "REAL_RUNTIME_REQUIRED",
         "state_rounds_failed": []}, "mesh_status")
    assert (ok, verdict) == (True, "REAL_RUNTIME_REQUIRED")
    # ...and a real round failure is still a failure, whatever else is true.
    ok, verdict = gate._proven_or_external(
        {"mesh_status": "FAILED", "blocking_class": "REAL_RUNTIME_REQUIRED",
         "state_rounds_failed": ["C"]}, "mesh_status")
    assert (ok, verdict) == (False, "NOT_PROVEN")
    ok, verdict = gate._proven_or_external({"mesh_status": "FAILED"}, "mesh_status")
    assert (ok, verdict) == (False, "NOT_PROVEN")


def test_the_regenerated_proofs_carry_the_classification():
    for name, field in (("FEDERATION_24X7_PROOF.json", "federation_status"),
                        ("FREE_WORKER_MESH_PROOF.json", "mesh_status")):
        document = json.loads(
            (ROOT / "CHECKPOINTS/evidence" / name).read_text(encoding="utf-8"))
        assert document["live_round_status"] in scopes.LIVE_ROUND_STATUSES
        assert document["blocking_class"] in (
            "NONE", "REAL_RUNTIME_REQUIRED", "ROUND_FAILED")
        assert document["state_rounds_failed"] == []


def test_the_preserved_history_is_labelled_historical_and_unbound():
    # A credential-less environment reading 21/22 must not erase the fact that
    # 22/22 was once recorded - and that record must not be quotable as current.
    for name in ("FEDERATION_24X7_PROOF.json", "FREE_WORKER_MESH_PROOF.json"):
        path = ROOT / "CHECKPOINTS/evidence/historical" / name
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["scope"] == "HISTORICAL"
        assert document["binding"] == "UNBOUND"
        reading = scopes.scope_document(document, root=ROOT,
                                        host_fingerprint="anything", now=NOW)
        assert reading["scope"] == "HISTORICAL"


# --- the phase6 exemption, tested where phase6 itself cannot run --------------

def _phase6():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "phase6_closure_gate", _TOOLS / "phase6_closure_gate.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["phase6_closure_gate"] = module
    spec.loader.exec_module(module)
    return module


def test_phase6_exemption_needs_a_probed_engine_and_a_clean_state_run():
    gate = _phase6()
    assert gate.LIVE_ROUND == "V"
    # Both halves, and neither alone.
    assert gate.is_externally_blocked(
        {"blocking_class": "REAL_RUNTIME_REQUIRED", "state_rounds_failed": []}) is True
    assert gate.is_externally_blocked(
        {"blocking_class": "REAL_RUNTIME_REQUIRED", "state_rounds_failed": ["C"]}) is False
    assert gate.is_externally_blocked(
        {"blocking_class": "ROUND_FAILED", "state_rounds_failed": []}) is False


def test_phase6_exemption_is_not_reachable_by_a_flag():
    gate = _phase6()
    # SKIPPED_BY_FLAG is what a --skip-live on a HEALTHY engine produces. If it
    # cleared this gate, the gate would be clearable by an argument.
    assert gate.is_externally_blocked(
        {"blocking_class": "SKIPPED_BY_FLAG", "state_rounds_failed": []}) is False


def test_phase6_exemption_fails_closed_on_junk():
    gate = _phase6()
    for proof in (None, [], "REAL_RUNTIME_REQUIRED", 0, {}, {"blocking_class": None}):
        assert gate.is_externally_blocked(proof) is False


def test_the_committed_24x7_proof_is_judged_by_what_it_records():
    """The rule, not a fixed expectation of which host last ran the proof.

    This asserted the committed proof earns the exemption, which was true while
    every reading came from a host whose engine is dead. A GitHub-hosted runner
    executes, so the live round now RUNS there - and when it runs and fails,
    `blocking_class` is ROUND_FAILED and the exemption must not apply. Pinning
    the old value would have meant asserting that a real round failure is an
    external blocker, which is the one thing the exemption exists to prevent.
    """
    gate = _phase6()
    document = json.loads(
        (ROOT / "CHECKPOINTS/evidence/FEDERATION_24X7_PROOF.json")
        .read_text(encoding="utf-8"))
    expected = (document.get("blocking_class") == "REAL_RUNTIME_REQUIRED"
                and not document.get("state_rounds_failed"))
    assert gate.is_externally_blocked(document) is bool(expected)
    if document.get("live_round_status") == "ROUND_FAILED":
        assert gate.is_externally_blocked(document) is False


def test_a_round_that_ran_and_failed_never_earns_the_exemption():
    """The invariant that must hold whatever host produced the document."""
    gate = _phase6()
    assert gate.is_externally_blocked(
        {"blocking_class": "ROUND_FAILED", "state_rounds_failed": []}) is False



def test_a_shallow_clone_is_not_an_invented_revision():
    """One label over two facts, caught by CI's shallow checkout.

    A sha this clone does not contain and a sha that names no commit anywhere
    were both reported UNRESOLVABLE. The first is a property of the checkout;
    the second is evidence naming nothing. Both still fail closed to
    HISTORICAL - the difference is in what the reading says, not what it allows.
    """
    assert "UNRESOLVABLE_HERE" in scopes.BINDINGS
    assert scopes.BINDING_VALUES == tuple(scopes.BINDINGS)
    # A full clone: an invented sha is still an invention, not a shallow miss.
    if not scopes.is_shallow(ROOT):
        reading = scopes.scope_document(
            {"source_sha": "0" * 40, "proof_timestamp": "2026-09-18T07:00:00Z"},
            root=ROOT, host_fingerprint="abc", now=NOW)
        assert reading["scope"] == "HISTORICAL"
