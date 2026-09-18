"""Redundancy is a property of independent execution, not of a list of names.

The matrix can name eight candidate models for a CRITICAL role and still be
one failure away from having none, because all eight run on the same box and
that box cannot execute an instruction. These tests hold the proof to the only
reading of "redundant" that survives contact with this container: two paths
that can actually run, in two failure domains, at the revision under test.

The two fixtures the plan names are here explicitly - an execution-dead local
worker with perfect health fields, and two hosted workers on genuinely
independent provider paths - because they are the two directions the gate must
be able to answer. A gate that can only say false is not measuring anything.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools import critical_role_redundancy_proof as proof

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
OTHER_SHA = "b" * 40


def _role(role_id, criticality="CRITICAL", **slots):
    role = {"role_id": role_id, "criticality": criticality, "status": "AVAILABLE_PRIMARY"}
    role.update(slots)
    return role


def _slot(model_id, *, mode="EXACT_MODEL", placement="LOCAL"):
    return {"model_id": model_id, "covers": "WHOLE_ROLE",
            "execution_mode": mode, "placement": placement}


def _matrix(*roles):
    return {"tool": "role_capability_matrix", "ROLE_CAPABILITY_MATRIX": list(roles)}


def _worker(worker_id, **overrides):
    record = {
        "worker_id": worker_id,
        "execution_host": worker_id,
        "placement": "HOSTED",
        "execution_mode": "EXACT_MODEL",
        "execution_liveness": "EXECUTION_LIVE",
        "policy_state": "ELIGIBLE",
        "source_sha": SHA,
        "proof_timestamp": "2026-09-18T00:00:00Z",
        "serves_models": ["model-a"],
    }
    record.update(overrides)
    return record


ONE_CRITICAL = _matrix(_role("REASONING_BRANCH", primary=_slot("model-a")))


def _build(matrix=None, workers=(), liveness=None, source_sha=SHA):
    return proof.build(role_matrix=matrix if matrix is not None else ONE_CRITICAL,
                       liveness=liveness, extra_workers=list(workers),
                       source_sha=source_sha)


class ContractGuardTests(unittest.TestCase):
    """Every allowed field is bounded, because the table *is* the allow-list.

    This repository has found the same bug four times: a field named in an
    allow-list and validated by nothing, which survives because no hand-written
    fixture happens to populate it. The structure here removes the gap rather
    than testing around it - a worker record's permitted field set is derived
    from the checker table, so a field with no checker is not a field that can
    be accepted. These tests drive the field list from the data contract and
    assert the two agree in both directions.
    """

    #: The data contract, written out here rather than imported, so that a
    #: field added to the tool without being considered fails this test.
    CONTRACT = {
        "worker_id", "execution_host", "failure_domain", "provider", "placement",
        "execution_mode", "execution_liveness", "policy_state", "source_sha",
        "proof_timestamp", "serves_models", "serves_placement", "evidence_ref",
        "host_health",
    }

    def test_the_allowed_field_set_is_exactly_the_contract(self):
        self.assertEqual(set(proof.WORKER_RECORD_FIELDS), self.CONTRACT)

    def test_the_allowed_field_set_is_derived_from_the_checker_table(self):
        """Not two lists that must be kept in step: one table, read twice."""
        self.assertEqual(set(proof.WORKER_RECORD_FIELDS), set(proof.FIELD_CHECKS))

    def test_every_field_the_contract_names_has_a_checker(self):
        unchecked = sorted(self.CONTRACT - set(proof.FIELD_CHECKS))
        self.assertEqual(unchecked, [])

    def test_every_pattern_is_anchored_with_backslash_Z_not_dollar(self):
        """``$`` also matches before a final newline; ``\\Z`` does not."""
        offenders = [name for name, pattern in proof.FIELD_PATTERNS.items()
                     if not pattern.pattern.endswith(r"\Z") or "$" in pattern.pattern]
        self.assertEqual(offenders, [])

    def test_every_bounded_string_field_refuses_a_trailing_newline(self):
        for field in sorted(proof.FIELD_PATTERNS):
            with self.subTest(field=field):
                value = proof.SAMPLE_VALUES[field] + "\n"
                with self.assertRaises(proof.RecordRejected):
                    proof.FIELD_CHECKS[field](value, field=field)

    def test_every_bounded_string_field_refuses_an_over_long_value(self):
        for field, limit in sorted(proof.FIELD_MAX_LENGTHS.items()):
            with self.subTest(field=field):
                with self.assertRaises(proof.RecordRejected):
                    proof.FIELD_CHECKS[field]("a" * (limit + 1), field=field)

    def test_each_sample_value_is_accepted_by_its_own_checker(self):
        """A bound nothing can pass is a different bug from a bound nothing bounds."""
        for field, value in sorted(proof.SAMPLE_VALUES.items()):
            with self.subTest(field=field):
                proof.FIELD_CHECKS[field](value, field=field)

    def test_a_field_nobody_anticipated_is_refused_rather_than_stored(self):
        with self.assertRaises(proof.RecordRejected):
            proof.normalise_worker(_worker("w1", surprise="value"))

    def test_a_missing_required_field_is_refused(self):
        for field in sorted(proof.REQUIRED_WORKER_FIELDS):
            record = _worker("w1")
            record.pop(field, None)
            with self.subTest(field=field):
                with self.assertRaises(proof.RecordRejected):
                    proof.normalise_worker(record)

    def test_an_array_longer_than_its_bound_is_refused(self):
        record = _worker("w1", serves_models=[f"m-{i}" for i in range(proof.MAX_MODELS + 1)])
        with self.assertRaises(proof.RecordRejected):
            proof.normalise_worker(record)

    def test_every_string_the_report_emits_is_bounded(self):
        report = _build(workers=[_worker("w1")])
        oversize = [trail for trail, value in proof.walk_strings(report)
                    if len(value) > proof.MAX_TEXT]
        self.assertEqual(oversize, [])


class ExecutionDeadWorkerTests(unittest.TestCase):
    """The fixture that started this: every health field green, nothing runs."""

    HEALTHY = {"online": "true", "circuit": "CLOSED", "stale_lease": "false",
               "ram_available_mb": "64000", "disk_free_mb": "900000",
               "last_seen": "2026-09-18T00:00:00Z", "quota_exhausted": "false"}

    def _dead(self):
        return _worker("local-box", execution_liveness="EXECUTION_DEAD",
                       placement="LOCAL", host_health=dict(self.HEALTHY))

    def test_an_execution_dead_worker_satisfies_no_critical_role(self):
        report = _build(workers=[self._dead()])
        role = report["critical_roles"][0]
        self.assertEqual(role["qualifying_paths"], [])
        self.assertEqual(role["independent_path_count"], 0)
        self.assertIs(role["covered"], False)
        self.assertIs(report["ready"], False)

    def test_perfect_health_fields_do_not_rescue_it(self):
        report = _build(workers=[self._dead()])
        self.assertIs(report["ready"], False)
        self.assertTrue(any("EXECUTION_DEAD" in reason
                            for reason in report["blocking_reasons"]))

    def test_the_report_says_which_worker_was_disqualified_and_why(self):
        report = _build(workers=[self._dead()])
        disqualified = report["disqualified_workers"]
        self.assertEqual([row["worker_id"] for row in disqualified], ["local-box"])
        self.assertIn("EXECUTION_DEAD", disqualified[0]["reason"])

    def test_two_models_on_one_execution_dead_host_are_not_two_paths(self):
        matrix = _matrix(_role("REASONING_BRANCH",
                               primary=_slot("model-a"), secondary=_slot("model-b")))
        dead = self._dead()
        dead["serves_models"] = ["model-a", "model-b"]
        report = _build(matrix, workers=[dead])
        self.assertEqual(report["critical_roles"][0]["independent_path_count"], 0)
        self.assertIs(report["ready"], False)

    def test_an_unknown_liveness_is_not_a_pass(self):
        report = _build(workers=[_worker("w1", execution_liveness="EXECUTION_UNKNOWN")])
        self.assertIs(report["ready"], False)


class IndependentPathTests(unittest.TestCase):
    """Two paths only when two things can fail separately."""

    def _pair(self, **overrides):
        second = {"execution_host": "groq-1", "provider": "groq"}
        second.update(overrides)
        return [_worker("cf-1", execution_host="cf-1", provider="cloudflare"),
                _worker("groq-1", **second)]

    def test_two_live_hosted_workers_on_independent_providers_pass(self):
        report = _build(workers=self._pair())
        role = report["critical_roles"][0]
        self.assertEqual(role["independent_path_count"], 2)
        self.assertIs(role["covered"], True)
        self.assertIs(report["ready"], True)
        self.assertTrue(report["proofs"])

    def test_every_critical_role_must_be_covered_not_merely_one(self):
        matrix = _matrix(_role("REASONING_BRANCH", primary=_slot("model-a")),
                         _role("CODING_BRANCH", primary=_slot("model-z")))
        report = _build(matrix, workers=self._pair())
        self.assertIs(report["ready"], False)
        covered = {row["role_id"]: row["covered"] for row in report["critical_roles"]}
        self.assertEqual(covered, {"REASONING_BRANCH": True, "CODING_BRANCH": False})

    def test_two_workers_in_one_failure_domain_are_one_path(self):
        workers = self._pair(failure_domain="shared-region")
        workers[0]["failure_domain"] = "shared-region"
        report = _build(workers=workers)
        self.assertEqual(report["critical_roles"][0]["independent_path_count"], 1)
        self.assertIs(report["ready"], False)

    def test_two_workers_on_one_execution_host_are_one_path(self):
        workers = self._pair(execution_host="cf-1", provider="cloudflare")
        report = _build(workers=workers)
        self.assertEqual(report["critical_roles"][0]["independent_path_count"], 1)
        self.assertIs(report["ready"], False)

    def test_a_second_path_in_cooldown_does_not_count(self):
        for state in ("COOLDOWN", "DEGRADED", "QUARANTINED", "UNAVAILABLE", "UNKNOWN"):
            with self.subTest(policy_state=state):
                report = _build(workers=self._pair(policy_state=state))
                self.assertIs(report["ready"], False)
                self.assertEqual(report["critical_roles"][0]["independent_path_count"], 1)

    def test_a_second_path_that_cannot_execute_does_not_count(self):
        report = _build(workers=self._pair(execution_liveness="EXECUTION_DEAD"))
        self.assertIs(report["ready"], False)

    def test_a_worker_that_serves_another_model_does_not_cover_this_role(self):
        report = _build(workers=self._pair(serves_models=["some-other-model"]))
        self.assertIs(report["ready"], False)
        self.assertEqual(report["critical_roles"][0]["independent_path_count"], 1)

    def test_the_covering_paths_are_listed_with_their_failure_domains(self):
        report = _build(workers=self._pair())
        paths = report["critical_roles"][0]["qualifying_paths"]
        self.assertEqual(sorted(p["worker_id"] for p in paths), ["cf-1", "groq-1"])
        self.assertEqual(sorted(p["failure_domain"] for p in paths),
                         ["host:cf-1", "host:groq-1"])


class ExactModelVersusCapabilityProviderTests(unittest.TestCase):
    """A provider that covers the capability is not the model, and says so."""

    def test_a_capability_provider_does_not_silently_serve_an_exact_model_role(self):
        workers = [_worker("cf-1", execution_mode="CAPABILITY_PROVIDER"),
                   _worker("groq-1", execution_host="groq-1")]
        report = _build(workers=workers)
        self.assertIs(report["ready"], False)
        role = report["critical_roles"][0]
        self.assertTrue(any("execution mode" in row["reason"]
                            for row in role["rejected_candidates"]))

    def test_a_capability_provider_role_is_covered_by_capability_providers(self):
        matrix = _matrix(_role("RETRIEVAL_BRANCH",
                               primary=_slot("@cf/baai/bge-m3",
                                             mode="CAPABILITY_PROVIDER",
                                             placement="SERVERLESS")))
        workers = [_worker("cf-1", execution_mode="CAPABILITY_PROVIDER",
                           serves_models=["@cf/baai/bge-m3"]),
                   _worker("vo-1", execution_host="vo-1", provider="voyage",
                           execution_mode="CAPABILITY_PROVIDER",
                           serves_models=["@cf/baai/bge-m3"])]
        report = _build(matrix, workers=workers)
        self.assertIs(report["ready"], True)
        modes = {p["execution_mode"] for p in report["critical_roles"][0]["qualifying_paths"]}
        self.assertEqual(modes, {"CAPABILITY_PROVIDER"})

    def test_each_path_records_the_mode_it_was_admitted_under(self):
        report = _build(workers=[_worker("cf-1"), _worker("groq-1", execution_host="groq-1")])
        for path in report["critical_roles"][0]["qualifying_paths"]:
            self.assertEqual(path["execution_mode"], "EXACT_MODEL")


class FailClosedTests(unittest.TestCase):
    """An absent fact is never a pass."""

    def test_a_worker_bound_to_another_revision_is_stale_and_does_not_count(self):
        workers = [_worker("cf-1"), _worker("groq-1", execution_host="groq-1",
                                            source_sha=OTHER_SHA)]
        report = _build(workers=workers)
        self.assertIs(report["ready"], False)
        self.assertTrue(any("stale" in row["reason"]
                            for row in report["disqualified_workers"]))

    def test_no_workers_at_all_is_false_rather_than_vacuously_true(self):
        report = _build(workers=[])
        self.assertIs(report["ready"], False)

    def test_a_matrix_with_no_critical_roles_is_false_rather_than_vacuously_true(self):
        report = _build(_matrix(_role("VISION_BRANCH", criticality="NORMAL",
                                      primary=_slot("model-a"))),
                        workers=[_worker("cf-1")])
        self.assertIs(report["ready"], False)
        self.assertTrue(any("no CRITICAL role" in reason
                            for reason in report["blocking_reasons"]))

    def test_a_missing_source_sha_is_refused(self):
        report = _build(workers=[_worker("cf-1")], source_sha=None)
        self.assertIs(report["ready"], False)

    def test_contradictory_liveness_for_one_host_fails_closed(self):
        workers = [_worker("cf-1"), _worker("cf-1b", execution_host="cf-1",
                                            execution_liveness="EXECUTION_DEAD")]
        report = _build(workers=workers)
        self.assertIs(report["ready"], False)
        self.assertTrue(any("contradict" in reason for reason in report["blocking_reasons"]))

    def test_one_host_cannot_be_relabelled_into_two_failure_domains(self):
        """The cheapest way to fake independence, refused structurally."""
        workers = [_worker("cf-1", execution_host="cf-1", failure_domain="domain-a"),
                   _worker("cf-2", execution_host="cf-1", failure_domain="domain-b")]
        report = _build(workers=workers)
        self.assertIs(report["ready"], False)
        self.assertTrue(any("failure domain" in reason
                            for reason in report["fail_closed_reasons"]))

    def test_a_malformed_worker_record_blocks_rather_than_being_skipped(self):
        report = _build(workers=[_worker("cf-1"), {"worker_id": "broken"}])
        self.assertIs(report["ready"], False)
        self.assertTrue(report["malformed_records"])

    def test_a_missing_evidence_file_is_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = proof.main(["--role-matrix", str(Path(tmp) / "nope.json"),
                               "--source-sha", SHA, "--strict"])
        self.assertEqual(code, 1)

    def test_malformed_json_on_disk_is_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "matrix.json"
            bad.write_text("{not json", encoding="utf-8")
            out = Path(tmp) / "evidence.json"
            code = proof.main(["--role-matrix", str(bad), "--source-sha", SHA,
                               "--evidence", str(out), "--strict"])
            self.assertEqual(code, 1)
            self.assertIs(json.loads(out.read_text(encoding="utf-8"))["ready"], False)

    def test_proofs_are_empty_unless_the_gate_is_actually_ready(self):
        report = _build(workers=[_worker("cf-1")])
        self.assertIs(report["ready"], False)
        self.assertEqual(report["proofs"], [])


class LivenessEvidenceTests(unittest.TestCase):
    """Reading the per-host structure the liveness tool writes, as written."""

    def _liveness(self, readings):
        return {"tool": "worker_execution_liveness", "READINGS_BY_HOST": readings}

    #: A reading must say which weights the host holds. One that does not is
    #: not a path - see ForgedLivenessFileTests - so a fixture that omits this
    #: would measure the refusal rather than the behaviour it names.
    def _reading(self, fingerprint, state, sha=SHA,
                 serves_models=("model-a", "model-b", "model-c")):
        reading = {
            "OBSERVED_ON": {"host_fingerprint": fingerprint},
            "LOCAL_ENGINE": {"state": state},
            "EXECUTION_LIVE": state == "EXECUTION_LIVE",
            "worker_id": f"local-engine-{fingerprint}",
            "execution_liveness": state,
            "proof_timestamp": "2026-09-18T00:00:00Z",
        }
        if serves_models is not None:
            reading["serves_models"] = list(serves_models)
        if sha is not None:
            reading["source_sha"] = sha
        return reading

    def test_a_dead_host_reading_yields_no_path(self):
        liveness = self._liveness({"h1": self._reading("h1", "EXECUTION_DEAD")})
        report = _build(liveness=liveness)
        self.assertIs(report["ready"], False)
        self.assertEqual(report["critical_roles"][0]["independent_path_count"], 0)

    def test_a_reading_without_a_revision_is_stale_even_when_it_says_live(self):
        """The legacy reading in this repository's evidence says EXECUTION_LIVE
        and names no host and no revision. It must not resurrect a path."""
        liveness = self._liveness({
            "host_not_recorded": self._reading("host_not_recorded", "EXECUTION_LIVE",
                                               sha=None),
            "h1": self._reading("h1", "EXECUTION_DEAD"),
        })
        report = _build(liveness=liveness)
        self.assertIs(report["ready"], False)
        self.assertTrue(any("stale" in row["reason"]
                            for row in report["disqualified_workers"]))

    def test_two_live_local_hosts_are_two_independent_paths(self):
        liveness = self._liveness({"h1": self._reading("h1", "EXECUTION_LIVE"),
                                   "h2": self._reading("h2", "EXECUTION_LIVE")})
        report = _build(liveness=liveness)
        self.assertIs(report["ready"], True)
        self.assertEqual(report["critical_roles"][0]["independent_path_count"], 2)

    def test_one_live_local_host_holding_every_weight_is_one_path(self):
        liveness = self._liveness({"h1": self._reading("h1", "EXECUTION_LIVE")})
        matrix = _matrix(_role("REASONING_BRANCH", primary=_slot("model-a"),
                               secondary=_slot("model-b"), fallback=_slot("model-c")))
        report = _build(matrix, liveness=liveness)
        self.assertEqual(report["critical_roles"][0]["independent_path_count"], 1)
        self.assertIs(report["ready"], False)


class RealMatrixTests(unittest.TestCase):
    """Against the matrix actually in this repository."""

    def setUp(self):
        path = ROOT / "CHECKPOINTS" / "evidence" / "ROLE_CAPABILITY_MATRIX.json"
        self.matrix = json.loads(path.read_text(encoding="utf-8"))

    def test_it_lists_every_critical_role_the_matrix_declares(self):
        report = _build(self.matrix)
        declared = [row["role_id"] for row in self.matrix["ROLE_CAPABILITY_MATRIX"]
                    if row.get("criticality") == "CRITICAL"]
        self.assertEqual([row["role_id"] for row in report["critical_roles"]],
                         sorted(declared))

    def test_a_single_live_local_host_still_fails_the_real_matrix(self):
        """Eight candidates on one machine is one path, however many names it has."""
        liveness = {"READINGS_BY_HOST": {"h1": {
            "OBSERVED_ON": {"host_fingerprint": "h1"},
            "LOCAL_ENGINE": {"state": "EXECUTION_LIVE"},
            "EXECUTION_LIVE": True,
            "worker_id": "local-engine-h1",
            "execution_liveness": "EXECUTION_LIVE",
            "source_sha": SHA,
            "proof_timestamp": "2026-09-18T00:00:00Z",
        }}}
        report = _build(self.matrix, liveness=liveness)
        self.assertIs(report["ready"], False)
        for role in report["critical_roles"]:
            with self.subTest(role=role["role_id"]):
                self.assertLessEqual(role["independent_path_count"], 1)


class AuthorityTests(unittest.TestCase):
    """It reports a fact. It decides nothing."""

    def test_the_module_claims_no_authority(self):
        self.assertIs(proof.AUTHORITY, False)

    def test_every_authority_flag_in_the_report_is_false(self):
        report = _build(workers=[_worker("cf-1")])
        for key in ("routing_authority", "admission_authority", "scheduling_authority",
                    "model_selection_authority", "evidence_authority"):
            with self.subTest(flag=key):
                self.assertIs(report[key], False)
        self.assertIs(report["changes_nothing"], True)

    def test_the_gate_name_is_the_one_the_aggregator_reads(self):
        report = _build(workers=[_worker("cf-1")])
        self.assertEqual(report["gate"], "CRITICAL_ROLE_REDUNDANCY_READY")

    def test_the_evidence_names_the_revision_it_proves(self):
        report = _build(workers=[_worker("cf-1")])
        self.assertEqual(report["source_sha"], SHA)
        self.assertRegex(report["proof_timestamp"],
                         r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")

    def test_the_reading_names_the_host_that_produced_it(self):
        report = _build(workers=[_worker("cf-1")])
        self.assertIn("host_fingerprint", report["OBSERVED_ON"])
        self.assertIn("not a property of the commit", report["reading_scope"])


class CommandLineTests(unittest.TestCase):
    """The file it writes, and the exit code it returns."""

    def _run(self, workers, extra=()):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "matrix.json").write_text(json.dumps(ONE_CRITICAL), encoding="utf-8")
            (tmp / "workers.json").write_text(json.dumps({"workers": workers}),
                                              encoding="utf-8")
            out = tmp / "CRITICAL_ROLE_REDUNDANCY_PROOF.json"
            code = proof.main(["--role-matrix", str(tmp / "matrix.json"),
                               "--workers", str(tmp / "workers.json"),
                               "--source-sha", SHA, "--evidence", str(out), *extra])
            return code, json.loads(out.read_text(encoding="utf-8"))

    def test_a_redundant_fixture_writes_ready_true_and_exits_zero(self):
        code, document = self._run([_worker("cf-1"), _worker("groq-1",
                                                             execution_host="groq-1")])
        self.assertEqual(code, 0)
        self.assertIs(document["ready"], True)
        self.assertEqual(document["gate"], "CRITICAL_ROLE_REDUNDANCY_READY")
        self.assertEqual(document["source_sha"], SHA)

    def test_strict_mode_exits_non_zero_when_the_gate_is_false(self):
        code, document = self._run([_worker("cf-1")], extra=["--strict"])
        self.assertEqual(code, 1)
        self.assertIs(document["ready"], False)

    def test_it_writes_only_the_evidence_file_it_was_asked_for(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "matrix.json").write_text(json.dumps(ONE_CRITICAL), encoding="utf-8")
            out = tmp / "sub" / "evidence.json"
            proof.main(["--role-matrix", str(tmp / "matrix.json"),
                        "--source-sha", SHA, "--evidence", str(out)])
            written = sorted(p.relative_to(tmp).as_posix()
                             for p in tmp.rglob("*") if p.is_file())
        self.assertEqual(written, ["matrix.json", "sub/evidence.json"])

    def test_the_machine_readable_line_is_emitted(self):
        import contextlib
        import io
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            proof.main(["--role-matrix", "/nonexistent.json", "--source-sha", SHA])
        self.assertTrue(re.search(r"^CRITICAL_ROLE_REDUNDANCY_READY=false",
                                  buffer.getvalue(), re.MULTILINE))


class ServedModelsAreRequiredTests(unittest.TestCase):
    """A worker that names no model covered every candidate at its placement.

    `_match` fell back to `serves_placement == candidate.placement` and called
    the result `declared_placement`. A worker naming NO MODEL therefore covered
    EVERY candidate at that placement, while `execution_mode` still read
    EXACT_MODEL on both sides - so the exact-model versus capability-provider
    distinction was preserved in name and void in effect. Naming what you serve
    is now the only way to serve anything.
    """

    def test_a_worker_that_names_no_model_covers_no_candidate(self):
        anonymous = _worker("anon-1", placement="LOCAL", serves_placement="LOCAL")
        anonymous.pop("serves_models")
        matrix = _matrix(_role("REASONING_BRANCH",
                               primary=_slot("model-a", placement="LOCAL")))
        report = proof.build(role_matrix=matrix, extra_workers=[anonymous],
                             source_sha=SHA)
        self.assertIs(report["ready"], False)
        self.assertEqual(report["critical_roles"][0]["independent_path_count"], 0)

    def test_an_empty_served_model_list_covers_no_candidate(self):
        report = _build(workers=[_worker("anon-1", serves_models=[])])
        self.assertIs(report["ready"], False)
        self.assertEqual(report["critical_roles"][0]["independent_path_count"], 0)

    def test_a_worker_naming_no_model_is_reported_as_not_capacity(self):
        anonymous = _worker("anon-1")
        anonymous.pop("serves_models")
        report = _build(workers=[anonymous])
        reasons = " ".join(row["reason"] for row in report["disqualified_workers"])
        self.assertIn("serves_models", reasons)

    def test_no_path_is_ever_matched_on_placement_alone(self):
        """`declared_placement` was the only basis that needed no model name."""
        anonymous = _worker("anon-1", placement="LOCAL", serves_placement="LOCAL")
        anonymous.pop("serves_models")
        report = proof.build(
            role_matrix=_matrix(_role("REASONING_BRANCH",
                                      primary=_slot("model-a", placement="LOCAL"))),
            extra_workers=[anonymous, _worker("anon-2", execution_host="anon-2",
                                              placement="LOCAL",
                                              serves_placement="LOCAL",
                                              serves_models=[])],
            source_sha=SHA)
        self.assertNotIn("declared_placement", json.dumps(report))
        self.assertIs(report["ready"], False)

    def test_naming_the_model_still_covers_it(self):
        """The bound must admit something as well as refuse something."""
        report = _build(workers=[_worker("cf-1"),
                                 _worker("groq-1", execution_host="groq-1")])
        self.assertIs(report["ready"], True)
        bases = {path["match_basis"]
                 for path in report["critical_roles"][0]["qualifying_paths"]}
        self.assertEqual(bases, {"explicit_model"})


class ForgedLivenessFileTests(unittest.TestCase):
    """The reproduction: two invented hosts, the real matrix, ready=true.

    Editing only WORKER_EXECUTION_LIVENESS.json to add two made-up host
    fingerprints - EXECUTION_LIVE, the correct sha, a well-formed timestamp -
    against the unmodified real ROLE_CAPABILITY_MATRIX.json certified all three
    CRITICAL roles without naming a single model, because the synthesised
    workers carried `serves_placement: LOCAL` and no served-model list. A
    liveness reading that does not say which weights the host holds must now
    qualify for nothing at all.
    """

    def setUp(self):
        path = ROOT / "CHECKPOINTS" / "evidence" / "ROLE_CAPABILITY_MATRIX.json"
        self.matrix = json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _forged(fingerprint, models=None):
        reading = {
            "OBSERVED_ON": {"host_fingerprint": fingerprint},
            "LOCAL_ENGINE": {"state": "EXECUTION_LIVE"},
            "EXECUTION_LIVE": True,
            "worker_id": f"local-engine-{fingerprint}",
            "execution_liveness": "EXECUTION_LIVE",
            "source_sha": SHA,
            "proof_timestamp": "2026-09-18T00:00:00Z",
        }
        if models is not None:
            reading["serves_models"] = list(models)
        return reading

    def test_two_invented_live_hosts_certify_nothing(self):
        liveness = {"tool": "worker_execution_liveness", "READINGS_BY_HOST": {
            "deadbeef01": self._forged("deadbeef01"),
            "deadbeef02": self._forged("deadbeef02"),
        }}
        report = proof.build(role_matrix=self.matrix, liveness=liveness,
                             source_sha=SHA)
        self.assertIs(report["ready"], False)
        for role in report["critical_roles"]:
            with self.subTest(role=role["role_id"]):
                self.assertEqual(role["independent_path_count"], 0)
                self.assertEqual(role["qualifying_paths"], [])

    def test_a_reading_that_names_its_weights_can_still_be_a_path(self):
        """Fail-closed, not fail-always: a host that says what it holds counts."""
        model = self.matrix["ROLE_CAPABILITY_MATRIX"][0]["primary"]["model_id"]
        role_id = self.matrix["ROLE_CAPABILITY_MATRIX"][0]["role_id"]
        liveness = {"READINGS_BY_HOST": {
            "h1": self._forged("h1", [model]),
            "h2": self._forged("h2", [model]),
        }}
        report = proof.build(role_matrix=self.matrix, liveness=liveness,
                             source_sha=SHA)
        rows = {row["role_id"]: row for row in report["critical_roles"]}
        self.assertEqual(rows[role_id]["independent_path_count"], 2)


class RefusalsDoNotEchoTheirInputTests(unittest.TestCase):
    """The one refusal that repeated what it was given, into an evidence file.

    `_enum` wrote `f"{field}={value!r} is not one of ..."`, so a 5000-character
    `placement` reached `malformed_records[0].reason` in the emitted document -
    truncated at 600, but still an echo of an input this tool does not own.
    A type and a length say everything a reader needs.
    """

    def test_an_enum_refusal_does_not_repeat_the_value(self):
        payload = "Q" * 5000
        with self.assertRaises(proof.RecordRejected) as caught:
            proof.FIELD_CHECKS["placement"](payload, field="placement")
        message = str(caught.exception)
        self.assertNotIn("Q" * 20, message)
        self.assertIn("5000", message)
        self.assertIn("str", message)

    def test_an_oversized_enum_value_does_not_reach_the_document(self):
        report = _build(workers=[_worker("w1", placement="Q" * 5000)])
        self.assertNotIn("Q" * 20, json.dumps(report))
        self.assertIs(report["ready"], False)

    def test_no_refusal_message_in_the_document_echoes_its_input(self):
        report = _build(workers=[_worker("w1", policy_state="Z" * 300),
                                 _worker("w2", execution_mode="Y" * 300)])
        document = json.dumps(report)
        self.assertNotIn("Z" * 20, document)
        self.assertNotIn("Y" * 20, document)


class CoversIsBoundedTests(unittest.TestCase):
    """A field bounded only by a slice is the shape this repository keeps finding."""

    def test_a_covers_value_that_is_not_a_token_is_refused(self):
        matrix = _matrix(_role("REASONING_BRANCH",
                               primary={"model_id": "model-a", "covers": "x" * 500,
                                        "execution_mode": "EXACT_MODEL",
                                        "placement": "LOCAL"}))
        report = _build(matrix, workers=[_worker("cf-1")])
        self.assertIs(report["ready"], False)
        self.assertNotIn("x" * 20, json.dumps(report))

    def test_a_covers_value_with_a_trailing_newline_is_refused(self):
        matrix = _matrix(_role("REASONING_BRANCH",
                               primary={"model_id": "model-a", "covers": "WHOLE_ROLE\n",
                                        "execution_mode": "EXACT_MODEL",
                                        "placement": "LOCAL"}))
        report = _build(matrix, workers=[_worker("cf-1")])
        self.assertIs(report["ready"], False)

    def test_the_covers_values_the_real_matrix_uses_are_accepted(self):
        path = ROOT / "CHECKPOINTS" / "evidence" / "ROLE_CAPABILITY_MATRIX.json"
        matrix = json.loads(path.read_text(encoding="utf-8"))
        roles, malformed = proof.critical_roles(matrix)
        self.assertEqual(malformed, [])
        self.assertTrue(roles)



if __name__ == "__main__":
    unittest.main()
