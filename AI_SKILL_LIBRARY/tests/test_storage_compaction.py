"""Task 7a - compaction, and the one thing compaction must never do.

Spec S12 asks the mesh to reduce growth before adding providers, and Spec S13
asks it to deduplicate by content hash. Both are ways of removing rows, which
makes this the second module in the lane that can lose data, and the failure
mode is quieter than the first: a rebalance that deletes the wrong copy is an
incident, while a compaction that silently drops a run is a number that is
simply wrong from then on and that nobody can reconstruct.

So the load-bearing assertion in this file is not that compaction compacts. It
is that it *conserves*: ``sum(run_count)`` over the output equals the number of
records that went in, for every window in the vocabulary, for duplicate rows,
for out-of-order rows, for rows sitting exactly on a window boundary, and for
rows that share every field. Compaction that loses a run is data loss wearing a
different hat.

Three further themes:

**Dedupe is content-addressed, and the content is the whole record.** Two rows
merge when their canonical encodings are byte-identical and never otherwise.
The sweep below walks every field of the experience schema, perturbs exactly
one, and requires two rows out. A dedupe keyed on a name, a timestamp or an id
would pass a happy-path test and quietly merge two different runs.

**The field set is closed and every field is bounded.** An experience record is
where a raw prompt would hide - it is written by the thing that ran the prompt -
so the credential sweep goes through every string field, through the *keys* as
well as the values, and then checks that the needle appears in no ``str``, no
``repr`` and no ``traceback.format_exc()``. The last of those is not
decoration: a chained ``__context__`` leak was found in Task 5 and ``str(exc)``
hid it.

**Nothing here proposes or performs an action.** No file, no connection, no
credential, no deletion. ``dedupe`` and ``aggregate_experience`` return new
lists; the caller with the authority decides what to do with them.
"""

from __future__ import annotations

import json
import pathlib
import re
import traceback
import unittest

from AI_SKILL_LIBRARY.v4.storage import compaction
from AI_SKILL_LIBRARY.v4.storage import manifest as manifest_module

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPERIENCE_SCHEMA_PATH = (
    REPO_ROOT / "AI_SKILL_LIBRARY/v4/schemas/experience_ledger.schema.json")

AUTHORITY_FLAGS = (
    "storage_authority", "routing_authority", "reasoning_authority",
    "model_selection_authority", "admission_authority", "scheduling_authority",
    "merge_authority", "trading_authority",
)

#: Two kilobytes of the shape a real leaked credential has, matching the needle
#: the rest of the lane uses. Long enough that no bounded field can hold it.
SMUGGLED_CREDENTIAL = "sk-" + ("A7bQ" * 512)

TIME = "2026-09-18T12:30:00Z"


def schema_item_properties():
    """The experience row's property names, read from the schema on disk."""
    document = json.loads(EXPERIENCE_SCHEMA_PATH.read_text())
    return set(document["properties"]["experiences"]["items"]["properties"])


def experience(**overrides):
    """A fully-populated, legitimate experience row.

    Every optional field is present on purpose: a row with the optional fields
    omitted cannot exercise the bounds on the optional fields, and those are
    precisely the ones a prompt body would be smuggled through.
    """
    row = {
        "experience_id": "exp-0001",
        "timestamp": TIME,
        "request_class": "coding",
        "role_id": "CODING_BRANCH",
        "skill_ids": ["storage-mesh", "compaction"],
        "model_id": "qwen3-8b",
        "provider_id": "cf-workers-ai",
        "worker_id": "cf-worker-01",
        "latency_ms": 120,
        "success": True,
        "failure_class": None,
        "verifier_passed": True,
        "retry_count": 0,
        "escalation_path": ["tier-1"],
        "fallback_path": ["tier-2"],
        "resource_observation": "cpu-bound",
        "quota_impact": "within-budget",
        "user_feedback_signal": "accepted",
        "evidence_ref": "CHECKPOINTS/evidence/storage_mesh.json",
    }
    row.update(overrides)
    return {name: value for name, value in row.items() if value is not _ABSENT}


_ABSENT = object()


def rows(count, **overrides):
    """``count`` rows that differ only in their per-row identifier."""
    return [experience(experience_id=f"exp-{index:04d}", **overrides)
            for index in range(count)]


def string_paths(value, prefix=()):
    """Every path in a record whose leaf is a string."""
    if isinstance(value, str):
        yield prefix
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from string_paths(nested, prefix + (key,))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from string_paths(nested, prefix + (index,))


def set_path(record, path, value):
    copied = json.loads(json.dumps(record))
    cursor = copied
    for step in path[:-1]:
        cursor = cursor[step]
    cursor[path[-1]] = value
    return copied


class AuthorityTests(unittest.TestCase):
    """The mesh is a subordinate subsystem (Spec S2), and so is this module."""

    def test_module_holds_no_authority(self):
        self.assertIs(compaction.AUTHORITY, False)
        self.assertEqual(set(compaction.AUTHORITY_FLAGS), set(AUTHORITY_FLAGS))
        for flag, held in compaction.AUTHORITY_FLAGS.items():
            self.assertIs(held, False, flag)

    def test_module_declares_it_performs_nothing(self):
        self.assertIs(compaction.PERFORMS_DELETION_HERE, False)
        self.assertIs(compaction.PERFORMS_NETWORK_IO_HERE, False)
        self.assertIs(compaction.ENCRYPTION_IMPLEMENTED_HERE, False)

    def test_functions_do_not_mutate_their_input(self):
        original = rows(4)
        snapshot = json.loads(json.dumps(original))
        compaction.dedupe(original)
        compaction.aggregate_experience(original, window="day")
        self.assertEqual(original, snapshot)


class StructuralGuardTests(unittest.TestCase):
    """Every property of the schema is in exactly one table, with a reason.

    This is the remedy the lane converged on after the same hole - a field
    admitted by name and validated by nothing - got past review four times. The
    field list is driven from the schema on disk rather than from a literal, so
    a property added to the contract later lands in no table and fails this test
    the day it is added.
    """

    def test_partition_covers_the_schema_exactly(self):
        partition = (set(compaction.GROUPING_FIELDS)
                     | set(compaction.AGGREGATED_FIELDS)
                     | set(compaction.WINDOW_FIELDS)
                     | set(compaction.REFUSED_FROM_AGGREGATE))
        self.assertEqual(partition, schema_item_properties())

    def test_partition_halves_are_disjoint(self):
        tables = (compaction.GROUPING_FIELDS, compaction.AGGREGATED_FIELDS,
                  compaction.WINDOW_FIELDS, compaction.REFUSED_FROM_AGGREGATE)
        seen = set()
        for table in tables:
            self.assertEqual(seen & set(table), set())
            seen |= set(table)

    def test_every_refused_field_carries_a_written_reason(self):
        for field, reason in compaction.REFUSED_FROM_AGGREGATE.items():
            self.assertIsInstance(reason, str, field)
            self.assertGreater(len(reason), 40, field)

    def test_every_accepted_field_has_a_bounded_checker(self):
        self.assertEqual(set(compaction.EXPERIENCE_VALUE_CHECKS),
                         schema_item_properties())
        self.assertEqual(compaction.EXPERIENCE_FIELDS,
                         tuple(compaction.EXPERIENCE_VALUE_CHECKS))

    def test_shared_checkers_are_the_same_callable_not_a_sixth_copy(self):
        """Bound by identity, the way the lane binds them elsewhere.

        A second, independently-written copy of "what a bounded classifier looks
        like" is a copy that will drift, and the looser of the two is the one an
        attacker gets to use.
        """
        checks = compaction.EXPERIENCE_VALUE_CHECKS
        self.assertIs(checks["request_class"], manifest_module._check_classifier)
        self.assertIs(checks["timestamp"], manifest_module._check_timestamp)
        self.assertIs(checks["evidence_ref"], manifest_module._check_evidence_ref)

    def test_aggregate_output_fields_are_bounded_too(self):
        self.assertEqual(compaction.AGGREGATE_FIELDS,
                         tuple(compaction.AGGREGATE_VALUE_CHECKS))

    def test_mirrored_patterns_match_the_schema_on_disk(self):
        """``\\Z`` rather than ``$``, and otherwise the schema's own pattern.

        Python's ``$`` also matches before a trailing newline, so a mirrored
        pattern using it is looser than the schema it mirrors.
        """
        document = json.loads(EXPERIENCE_SCHEMA_PATH.read_text())
        properties = document["properties"]["experiences"]["items"]["properties"]
        defs = document["$defs"]
        schema_role = properties["role_id"]["pattern"]
        schema_identifier = defs["identifier"]["pattern"]
        self.assertEqual(compaction._ROLE_ID_RE.pattern,
                         schema_role[:-1] + r"\Z")
        self.assertEqual(compaction._IDENTIFIER_RE.pattern,
                         schema_identifier[:-1] + r"\Z")
        self.assertNotIn("$", compaction._ROLE_ID_RE.pattern)
        self.assertNotIn("$", compaction._IDENTIFIER_RE.pattern)


class DedupeTests(unittest.TestCase):
    """Spec S13: SHA-256 content dedupe, and nothing cleverer than that."""

    def test_identical_rows_collapse_to_one_with_a_count(self):
        out = compaction.dedupe([experience(), experience(), experience()])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["duplicate_count"], 3)

    def test_distinct_rows_are_never_merged(self):
        out = compaction.dedupe(rows(5))
        self.assertEqual(len(out), 5)
        self.assertTrue(all(row["duplicate_count"] == 1 for row in out))

    def test_dedupe_is_content_addressed_and_carries_the_digest(self):
        out = compaction.dedupe([experience()])
        digest = out[0]["content_sha256"]
        self.assertRegex(digest, r"\A[0-9a-f]{64}\Z")
        again = compaction.dedupe([experience()])
        self.assertEqual(again[0]["content_sha256"], digest)

    def test_a_single_differing_field_prevents_a_merge(self):
        """Including the timestamp, which a name- or time-keyed dedupe would
        happily collapse."""
        base = experience()
        perturbations = {
            "experience_id": "exp-9999",
            "timestamp": "2026-09-18T12:30:01Z",
            "request_class": "review",
            "role_id": "REVIEW_BRANCH",
            "skill_ids": ["storage-mesh"],
            "model_id": "qwen3-4b",
            "provider_id": "hf-inference",
            "worker_id": "cf-worker-02",
            "latency_ms": 121,
            "success": False,
            "failure_class": "timeout.upstream",
            "verifier_passed": False,
            "retry_count": 1,
            "escalation_path": ["tier-3"],
            "fallback_path": ["tier-4"],
            "resource_observation": "io-bound",
            "quota_impact": "near-budget",
            "user_feedback_signal": "rejected",
            "evidence_ref": "CHECKPOINTS/evidence/storage_other.json",
        }
        self.assertEqual(set(perturbations), schema_item_properties())
        for field, value in perturbations.items():
            with self.subTest(field=field):
                other = dict(base)
                other[field] = value
                self.assertEqual(len(compaction.dedupe([base, other])), 2)

    def test_first_seen_order_is_preserved(self):
        original = rows(4)
        out = compaction.dedupe(original + original)
        self.assertEqual([row["experience_id"] for row in out],
                         [row["experience_id"] for row in original])

    def test_an_unknown_field_is_refused_rather_than_stored(self):
        with self.assertRaises(compaction.CompactionInputError):
            compaction.dedupe([experience(prompt="write me a poem")])

    def test_a_caller_may_not_assert_the_digest(self):
        """``content_sha256`` is computed here or it is not present.

        A row arriving with its own digest is a claim by the thing being
        checked, and a check that consults its subject for the answer is not a
        check.
        """
        with self.assertRaises(compaction.CompactionInputError):
            compaction.dedupe([experience(content_sha256="0" * 64)])

    def test_dedupe_refuses_more_rows_than_the_schema_allows(self):
        with self.assertRaises(compaction.CompactionInputError):
            compaction.dedupe(rows(compaction.MAX_INPUT_RECORDS + 1))

    def test_a_malformed_row_fails_closed_rather_than_being_skipped(self):
        with self.assertRaises(compaction.CompactionInputError):
            compaction.dedupe([experience(), experience(timestamp="not-a-date")])


class AggregateCountTests(unittest.TestCase):
    """``sum(run_count)`` is invariant. This is the whole point of the module."""

    def test_compaction_reduces_rows_but_preserves_counts(self):
        source = rows(100)
        out = compaction.aggregate_experience(source, window="day")
        self.assertLess(len(out), len(source))
        self.assertEqual(sum(row["run_count"] for row in out), 100)

    def test_identical_duplicate_rows_are_still_two_runs(self):
        out = compaction.aggregate_experience(
            [experience(), experience()], window="day")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["run_count"], 2)

    def test_counts_are_preserved_for_every_window_in_the_vocabulary(self):
        source = (rows(7, timestamp="2026-09-18T00:00:00Z")
                  + rows(5, timestamp="2026-09-18T23:59:59Z")
                  + rows(3, timestamp="2026-09-21T06:00:00Z"))
        for window in compaction.WINDOWS:
            with self.subTest(window=window):
                out = compaction.aggregate_experience(source, window=window)
                self.assertEqual(sum(row["run_count"] for row in out),
                                 len(source))

    def test_adjacent_windows_are_not_merged(self):
        source = (rows(2, timestamp="2026-09-18T23:00:00Z")
                  + rows(2, timestamp="2026-09-19T00:00:00Z"))
        out = compaction.aggregate_experience(source, window="day")
        self.assertEqual(len(out), 2)
        self.assertEqual(sum(row["run_count"] for row in out), 4)

    def test_a_boundary_timestamp_belongs_to_the_window_it_opens(self):
        """Start-inclusive, end-exclusive. Stated once, tested directly, because
        the alternative is a run counted twice or not at all."""
        out = compaction.aggregate_experience(
            rows(1, timestamp="2026-09-19T00:00:00Z"), window="day")
        self.assertEqual(out[0]["period_start"], "2026-09-19T00:00:00Z")
        self.assertEqual(out[0]["period_end"], "2026-09-20T00:00:00Z")

    def test_out_of_order_input_gives_the_same_answer_as_sorted_input(self):
        source = (rows(3, timestamp="2026-09-19T01:00:00Z")
                  + rows(2, timestamp="2026-09-18T01:00:00Z")
                  + rows(4, timestamp="2026-09-19T02:00:00Z"))
        shuffled = [source[i] for i in (5, 0, 8, 2, 7, 1, 4, 3, 6)]
        self.assertEqual(compaction.aggregate_experience(source, window="day"),
                         compaction.aggregate_experience(shuffled, window="day"))

    def test_offset_timestamps_are_normalised_before_windowing(self):
        source = [experience(experience_id="exp-a",
                             timestamp="2026-09-19T01:00:00+02:00"),
                  experience(experience_id="exp-b",
                             timestamp="2026-09-18T23:00:00Z")]
        out = compaction.aggregate_experience(source, window="day")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["run_count"], 2)

    def test_output_is_deterministically_ordered(self):
        source = rows(3, timestamp="2026-09-19T01:00:00Z") + rows(
            2, timestamp="2026-09-18T01:00:00Z")
        first = compaction.aggregate_experience(source, window="day")
        second = compaction.aggregate_experience(list(reversed(source)),
                                                 window="day")
        self.assertEqual([row["period_start"] for row in first],
                         [row["period_start"] for row in second])


class AggregateGroupingTests(unittest.TestCase):
    """Nothing is merged across a field this module does not aggregate."""

    def test_a_single_differing_grouping_field_prevents_a_merge(self):
        base = experience()
        perturbations = {
            "request_class": "review",
            "role_id": "REVIEW_BRANCH",
            "skill_ids": ["storage-mesh"],
            "model_id": "qwen3-4b",
            "provider_id": "hf-inference",
            "worker_id": "cf-worker-02",
            "escalation_path": ["tier-3"],
            "fallback_path": ["tier-4"],
            "resource_observation": "io-bound",
            "quota_impact": "near-budget",
            "user_feedback_signal": "rejected",
        }
        self.assertEqual(set(perturbations), set(compaction.GROUPING_FIELDS))
        for field, value in perturbations.items():
            with self.subTest(field=field):
                other = dict(base)
                other[field] = value
                out = compaction.aggregate_experience([base, other],
                                                      window="day")
                self.assertEqual(len(out), 2)
                self.assertEqual(sum(row["run_count"] for row in out), 2)

    def test_aggregated_fields_do_merge_and_become_statistics(self):
        source = [experience(experience_id="exp-a", success=True,
                             latency_ms=100, verifier_passed=True),
                  experience(experience_id="exp-b", success=False,
                             latency_ms=300, verifier_passed=False,
                             failure_class="timeout.upstream")]
        out = compaction.aggregate_experience(source, window="day")
        self.assertEqual(len(out), 1)
        row = out[0]
        self.assertEqual(row["run_count"], 2)
        self.assertEqual(row["success_count"], 1)
        self.assertEqual(row["success_rate"], 0.5)
        self.assertEqual(row["verifier_pass_rate"], 0.5)
        self.assertEqual(row["failure_histogram"], {"timeout.upstream": 1})
        self.assertEqual(row["latency_p50"], 100)
        self.assertEqual(row["latency_p95"], 300)

    def test_a_per_row_identifier_never_survives_aggregation(self):
        out = compaction.aggregate_experience(rows(3), window="day")
        encoded = json.dumps(out)
        self.assertNotIn("experience_id", encoded)
        self.assertNotIn("exp-0000", encoded)

    def test_unknown_verifier_results_are_counted_not_guessed(self):
        source = [experience(experience_id="exp-a", verifier_passed="unknown"),
                  experience(experience_id="exp-b", verifier_passed=True)]
        row = compaction.aggregate_experience(source, window="day")[0]
        self.assertEqual(row["verifier_unknown_count"], 1)
        self.assertEqual(row["verifier_sample_count"], 1)
        self.assertEqual(row["verifier_pass_rate"], 1.0)

    def test_no_verifier_sample_gives_no_rate_rather_than_a_zero(self):
        row = compaction.aggregate_experience(
            [experience(verifier_passed="unknown")], window="day")[0]
        self.assertIsNone(row["verifier_pass_rate"])

    def test_the_aggregate_row_declares_no_authority(self):
        row = compaction.aggregate_experience(rows(2), window="day")[0]
        self.assertIs(row["authority"], False)
        self.assertEqual(row["lifecycle_state"], "AGGREGATED")

    def test_an_unknown_window_is_refused(self):
        with self.assertRaises(compaction.CompactionInputError):
            compaction.aggregate_experience(rows(2), window="fortnight")

    def test_aggregate_refuses_a_malformed_row_rather_than_dropping_it(self):
        with self.assertRaises(compaction.CompactionInputError):
            compaction.aggregate_experience(
                [experience(), experience(latency_ms=-1)], window="day")

    def test_every_output_row_satisfies_the_output_table(self):
        source = (rows(3, timestamp="2026-09-18T01:00:00Z")
                  + rows(2, timestamp="2026-09-19T01:00:00Z"))
        for row in compaction.aggregate_experience(source, window="day"):
            compaction.validate_aggregate_record(row)


class PrivacyTests(unittest.TestCase):
    """An experience row is exactly where a raw prompt would hide."""

    def test_every_string_field_refuses_the_credential_needle(self):
        base = experience()
        for path in string_paths(base):
            with self.subTest(path=".".join(str(step) for step in path)):
                smuggled = set_path(base, path, SMUGGLED_CREDENTIAL)
                for call in (lambda: compaction.dedupe([smuggled]),
                             lambda: compaction.aggregate_experience(
                                 [smuggled], window="day")):
                    with self.assertRaises(compaction.CompactionInputError):
                        call()

    def test_every_string_field_refuses_a_two_kilobyte_benign_blob(self):
        """It is not the credential shape doing the work - it is the bound."""
        base = experience()
        for path in string_paths(base):
            with self.subTest(path=".".join(str(step) for step in path)):
                smuggled = set_path(base, path, "a" * 2048)
                with self.assertRaises(compaction.CompactionInputError):
                    compaction.dedupe([smuggled])

    def test_a_credential_shaped_key_is_refused_and_never_echoed(self):
        smuggled = experience()
        smuggled[SMUGGLED_CREDENTIAL] = "x"
        with self.assertRaises(compaction.CompactionInputError) as caught:
            compaction.dedupe([smuggled])
        self.assertNotIn(SMUGGLED_CREDENTIAL, str(caught.exception))
        self.assertNotIn(SMUGGLED_CREDENTIAL, repr(caught.exception))

    def test_the_needle_appears_in_no_traceback_anywhere(self):
        """Including the chained ``__context__``.

        A chained-context leak was found in Task 5 and ``str(exc)`` hid it: the
        sanitised message said nothing while ``traceback.format_exc()`` printed
        the original validator's message, value and all.
        """
        carriers = []
        base = experience()
        for path in string_paths(base):
            carriers.append(set_path(base, path, SMUGGLED_CREDENTIAL))
        keyed = experience()
        keyed[SMUGGLED_CREDENTIAL] = SMUGGLED_CREDENTIAL
        carriers.append(keyed)
        carriers.append({SMUGGLED_CREDENTIAL: SMUGGLED_CREDENTIAL})
        carriers.append(experience(skill_ids=[SMUGGLED_CREDENTIAL]))

        for index, carrier in enumerate(carriers):
            for name, call in (
                    ("dedupe", lambda c=carrier: compaction.dedupe([c])),
                    ("aggregate", lambda c=carrier:
                     compaction.aggregate_experience([c], window="day"))):
                with self.subTest(carrier=index, call=name):
                    try:
                        call()
                    except BaseException as exc:  # noqa: BLE001 - that is the subject
                        rendered = traceback.format_exc()
                        self.assertNotIn(SMUGGLED_CREDENTIAL, rendered)
                        self.assertNotIn(SMUGGLED_CREDENTIAL, str(exc))
                        self.assertNotIn(SMUGGLED_CREDENTIAL, repr(exc))
                        self.assertIsNone(exc.__cause__)
                        self.assertTrue(exc.__context__ is None
                                        or exc.__suppress_context__)
                    else:
                        self.fail("a carrier was admitted")

    def test_no_output_row_can_carry_an_unbounded_string(self):
        source = rows(4)
        for row in (compaction.dedupe(source)
                    + compaction.aggregate_experience(source, window="day")):
            for path in string_paths(row):
                cursor = row
                for step in path:
                    cursor = cursor[step]
                self.assertLessEqual(len(cursor), compaction.MAX_STRING_LENGTH)

    def test_the_module_refers_to_no_forbidden_content(self):
        """The forbidden-content list in policy.yaml, as a field-name check."""
        forbidden = ("prompt", "chain_of_thought", "reasoning", "raw_text",
                     "message", "completion", "api_key", "token")
        for name in forbidden:
            self.assertNotIn(name, compaction.EXPERIENCE_FIELDS, name)
            self.assertNotIn(name, compaction.AGGREGATE_FIELDS, name)


class HostileInputTests(unittest.TestCase):
    """Degrade, never crash with something other than the declared error."""

    HOSTILE = (
        None, 0, "", b"", b"bytes-are-a-sequence", object(), [None], [[]],
        [{"experience_id": object()}], {"a": 1}, [experience(), None],
        [{}], [[experience()]], iter([experience()]),
    )

    def test_hostile_input_raises_only_the_declared_error(self):
        for index, hostile in enumerate(self.HOSTILE):
            for name, call in (
                    ("dedupe", lambda h=hostile: compaction.dedupe(h)),
                    ("aggregate", lambda h=hostile:
                     compaction.aggregate_experience(h, window="day"))):
                with self.subTest(case=index, call=name):
                    try:
                        call()
                    except compaction.CompactionInputError:
                        pass
                    except BaseException as exc:  # noqa: BLE001
                        self.fail(f"{type(exc).__name__}: {exc}")

    def test_bytes_are_not_accepted_as_a_sequence_of_records(self):
        """``bytes`` IS a ``collections.abc.Sequence``; that bug was found in
        Task 3 and is checked for by name here."""
        with self.assertRaises(compaction.CompactionInputError):
            compaction.dedupe(b"not-records")


if __name__ == "__main__":
    unittest.main()
