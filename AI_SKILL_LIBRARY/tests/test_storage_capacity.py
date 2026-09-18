"""Task 3a - the Capacity Broker's single question: what state is this provider in?

Task 1 checked in the provider registry and the JSON Schema that bounds a row.
Task 2 built the typed manifest. Neither of them answers the question the
placement engine has to ask first: *given this row, may a byte be written to
this backend right now, and how much room is left below the limits?*

``provider_state`` answers it with one of the seven names Spec S10 fixes, and
the tests here are about three properties.

1. **The thresholds are the spec's, and they are inclusive at the bottom.**
   Spec S10 sets SOFT_LIMIT 80%, HARD_LIMIT 92%, EMERGENCY_RESERVE 5%. 79% is
   HEALTHY, 80% is PRESSURED, 92% is NEAR_FULL. The comparisons are integer
   arithmetic rather than float division, because a boundary that moves with
   the last bit of a double is not a boundary.

2. **Derivation may only narrow, never widen.** The declared ``health`` is
   evidence, and evidence is the ceiling: a row that says NEAR_FULL is
   NEAR_FULL whatever its quota reads, and a row that says HEALTHY becomes
   PRESSURED when its quota says so. There is no path by which a call to this
   module makes a provider look *better* than the registry says it is.

3. **Everything unknown is QUARANTINED.** Spec S11 fixes
   ``UNKNOWN_COST_STATE=QUARANTINE``, and this module reads that literally and
   widely: an absent field, an enum value nobody defined, an unprobed health
   claim, a free tier that expired last month, a spillover risk nobody ruled
   out, a quota nobody can compute - each of them lands on QUARANTINED. Not one
   of them is an optimistic pass. There is deliberately no ``UNKNOWN`` state:
   "we have not looked" and "we looked and it is bad" produce the same refusal,
   which is the only way the first of those two cannot be spent.

The module opens no file, no socket and no provider account, and holds no
authority; the tests assert that rather than trusting the docstring.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from AI_SKILL_LIBRARY.v4.storage import capacity

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "AI_SKILL_LIBRARY/v4/storage/policy.yaml"
PROVIDER_SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_provider.schema.json"

POLICY = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
PROVIDER_SCHEMA = json.loads(PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8"))
PROVIDER_VALIDATOR = Draft202012Validator(PROVIDER_SCHEMA)

AUTHORITY_FLAGS = (
    "storage_authority", "routing_authority", "reasoning_authority",
    "model_selection_authority", "admission_authority", "scheduling_authority",
    "merge_authority", "trading_authority",
)

#: Marker for "this field is not present at all", which is a different input
#: from "this field is null" and has to be tested separately.
ABSENT = object()

PAST = "2020-01-01T00:00:00Z"
NOW = "2026-09-18T00:00:00Z"
FUTURE = "2030-01-01T00:00:00Z"


def external_provider(**overrides):
    """A fully admitted external row: verified recurring free, probed, writable.

    Every fail-closed test below is this row with exactly one thing taken away,
    so the row itself is validated against the shipped schema - otherwise the
    tests could drift into asserting things about a document the contract would
    never have accepted.
    """
    row = {
        "provider_id": "cloudflare_r2",
        "adapter_type": "s3_compatible",
        "external": True,
        "free_status": "VERIFIED_RECURRING_FREE",
        "free_status_evidence": {
            "evidence_class": "runtime_account_evidence",
            "verified_at": NOW,
            "evidence_ref": "evidence/storage/r2_probe.json",
        },
        "free_expiry_at": None,
        "quota_total": 100,
        "quota_used": 0,
        "quota_reserved": 0,
        "hard_stop_verified": True,
        "paid_spillover_possible": False,
        "privacy_classes_allowed": ["PUBLIC"],
        "encryption_required_classes": ["CONFIDENTIAL"],
        "health": "HEALTHY",
        "autonomous_write_allowed": True,
        "read_enabled": True,
        "write_enabled": True,
        "bulk_object_backend_allowed": True,
        "tiers_allowed": ["HOT", "WARM", "COLD"],
        "preferred_tiers": ["HOT"],
        "acceptable_use_class": "object-storage",
        "last_probe_at": NOW,
        "authority": False,
        "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
    }
    row.update(overrides)
    return {key: value for key, value in row.items() if value is not ABSENT}


def local_provider(**overrides):
    """Owned storage. It has no free tier to verify because nobody bills it."""
    row = {
        "provider_id": "local_owned_store",
        "adapter_type": "local_filesystem",
        "external": False,
        "free_status": "NOT_APPLICABLE",
        "free_status_evidence": {"evidence_class": "not_applicable"},
        # storage_provider.schema.json forbids an owned local row from
        # declaring any quota: there is no provider-granted allowance to read,
        # so the honest value is null and the broker treats it as unknowable.
        "quota_total": None,
        "quota_used": None,
        "quota_reserved": None,
        "hard_stop_verified": True,
        "paid_spillover_possible": False,
        "privacy_classes_allowed": ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY"],
        "encryption_required_classes": [],
        "health": "HEALTHY",
        "autonomous_write_allowed": True,
        "read_enabled": True,
        "write_enabled": True,
        "bulk_object_backend_allowed": True,
        "tiers_allowed": ["HOT", "WARM", "COLD"],
        "preferred_tiers": ["HOT"],
        "acceptable_use_class": "owned-storage",
        "last_probe_at": NOW,
        "authority": False,
        "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
    }
    row.update(overrides)
    return {key: value for key, value in row.items() if value is not ABSENT}


def schema_errors(row):
    return [f"{list(e.absolute_path)}: {e.message}"
            for e in PROVIDER_VALIDATOR.iter_errors(row)]


class FixtureIntegrityTests(unittest.TestCase):
    """The fixtures must be documents the shipped contract would accept."""

    def test_the_admitted_external_fixture_validates_against_the_schema(self):
        self.assertEqual(schema_errors(external_provider()), [])

    def test_the_owned_storage_fixture_validates_against_the_schema(self):
        self.assertEqual(schema_errors(local_provider()), [])


class ThresholdTests(unittest.TestCase):
    """Spec S10: SOFT_LIMIT 80%, HARD_LIMIT 92%, inclusive at the bottom."""

    def state(self, used, **overrides):
        return capacity.provider_state(
            external_provider(quota_used=used, **overrides), now=NOW)

    def test_below_the_soft_limit_is_healthy(self):
        self.assertEqual(self.state(79), "HEALTHY")

    def test_the_soft_limit_is_inclusive_and_pressures(self):
        self.assertEqual(self.state(80), "PRESSURED")

    def test_the_hard_limit_is_inclusive_and_is_near_full(self):
        self.assertEqual(self.state(92), "NEAR_FULL")

    def test_the_band_between_the_limits_is_pressured_throughout(self):
        for used in range(80, 92):
            with self.subTest(used=used):
                self.assertEqual(self.state(used), "PRESSURED")

    def test_a_completely_full_provider_is_near_full(self):
        self.assertEqual(self.state(100), "NEAR_FULL")

    def test_boundaries_do_not_depend_on_float_division(self):
        # 23/25 is exactly 0.92 and 4/5 is exactly 0.80; a naive float
        # comparison gets these right by luck and 46/50 wrong by rounding.
        self.assertEqual(
            capacity.provider_state(
                external_provider(quota_total=25, quota_used=23), now=NOW),
            "NEAR_FULL")
        self.assertEqual(
            capacity.provider_state(
                external_provider(quota_total=5, quota_used=4), now=NOW),
            "PRESSURED")
        self.assertEqual(
            capacity.provider_state(
                external_provider(quota_total=10 ** 12, quota_used=(10 ** 12) * 79 // 100),
                now=NOW),
            "HEALTHY")

    def test_reserved_quota_counts_against_the_limits(self):
        # Spec S10 tracks quota_reserved separately; reserved bytes are spoken
        # for, so a provider at 50% used and 40% reserved is at 90%.
        self.assertEqual(self.state(50, quota_reserved=40), "PRESSURED")
        self.assertEqual(self.state(50, quota_reserved=42), "NEAR_FULL")

    def test_thresholds_match_policy_yaml(self):
        # The constants are mirrored for a stable import-time value, exactly as
        # the package enums are. This is the guard against the mirror drifting.
        self.assertEqual(capacity.SOFT_LIMIT_RATIO,
                         POLICY["capacity"]["soft_limit_ratio"])
        self.assertEqual(capacity.HARD_LIMIT_RATIO,
                         POLICY["capacity"]["hard_limit_ratio"])
        self.assertEqual(capacity.EMERGENCY_RESERVE_RATIO,
                         POLICY["capacity"]["emergency_reserve_ratio"])


class DerivationOnlyNarrowsTests(unittest.TestCase):
    """The declared health is the ceiling. Nothing here upgrades a provider."""

    def test_a_declared_near_full_row_stays_near_full_on_an_empty_quota(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(health="NEAR_FULL", quota_used=0), now=NOW),
            "NEAR_FULL")

    def test_a_declared_read_only_row_stays_read_only(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(health="READ_ONLY", quota_used=0), now=NOW),
            "READ_ONLY")

    def test_a_declared_offline_row_stays_offline(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(health="OFFLINE", quota_used=0), now=NOW),
            "OFFLINE")

    def test_free_survives_below_the_soft_limit(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(health="FREE", quota_used=1), now=NOW),
            "FREE")

    def test_free_is_narrowed_by_the_quota_like_any_other_claim(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(health="FREE", quota_used=85), now=NOW),
            "PRESSURED")

    def test_write_disabled_is_read_only_whatever_the_quota_says(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(write_enabled=False, quota_used=0), now=NOW),
            "READ_ONLY")

    def test_neither_read_nor_write_is_offline(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(write_enabled=False, read_enabled=False),
                now=NOW),
            "OFFLINE")


class ZeroCostQuarantineTests(unittest.TestCase):
    """Spec S11. Unknown cost state is QUARANTINE, never an optimistic pass."""

    def test_an_unverified_free_status_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status="UNVERIFIED"), now=NOW),
            "QUARANTINED")

    def test_documented_only_is_quarantined_because_a_pricing_page_is_not_evidence(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status="DOCUMENTED_ONLY"), now=NOW),
            "QUARANTINED")

    def test_a_paid_only_provider_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status="PAID_ONLY"), now=NOW),
            "QUARANTINED")

    def test_an_expired_free_status_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status="FREE_EXPIRED"), now=NOW),
            "QUARANTINED")

    def test_an_absent_free_status_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status=ABSENT), now=NOW),
            "QUARANTINED")

    def test_documentation_evidence_cannot_carry_a_verified_status(self):
        # The schema forbids this pairing; a runtime snapshot reaching the
        # broker by another path must be refused here too.
        row = external_provider(free_status_evidence={
            "evidence_class": "provider_documentation"})
        self.assertNotEqual(schema_errors(row), [])
        self.assertEqual(capacity.provider_state(row, now=NOW), "QUARANTINED")

    def test_a_free_tier_that_has_already_expired_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status="VERIFIED_FREE",
                                  free_expiry_at=PAST), now=NOW),
            "QUARANTINED")

    def test_a_free_tier_expiring_exactly_now_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status="VERIFIED_FREE",
                                  free_expiry_at=NOW), now=NOW),
            "QUARANTINED")

    def test_a_dated_free_tier_still_in_the_future_is_admitted(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status="VERIFIED_FREE",
                                  free_expiry_at=FUTURE), now=NOW),
            "HEALTHY")

    def test_an_unknown_expiry_without_recurring_free_is_quarantined(self):
        # Spec S11 FREE_EXPIRY_UNKNOWN=NO_AUTONOMOUS_WRITE unless the provider
        # is known recurring-free. VERIFIED_FREE plus a null expiry is exactly
        # "free today, no idea about tomorrow".
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status="VERIFIED_FREE",
                                  free_expiry_at=None), now=NOW),
            "QUARANTINED")

    def test_an_absent_expiry_field_is_quarantined_the_same_way(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_status="VERIFIED_FREE",
                                  free_expiry_at=ABSENT), now=NOW),
            "QUARANTINED")

    def test_a_malformed_expiry_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(free_expiry_at="whenever"), now=NOW),
            "QUARANTINED")

    def test_possible_paid_spillover_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(paid_spillover_possible=True), now=NOW),
            "QUARANTINED")

    def test_unknown_paid_spillover_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(paid_spillover_possible="unknown"), now=NOW),
            "QUARANTINED")

    def test_an_unverified_hard_stop_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(hard_stop_verified=False), now=NOW),
            "QUARANTINED")

    def test_owned_storage_needs_no_free_tier(self):
        # Nobody bills a local disk. NOT_APPLICABLE is a real answer, not a gap.
        self.assertEqual(capacity.provider_state(local_provider(), now=NOW),
                         "HEALTHY")

    def test_owned_storage_cannot_borrow_the_local_exemption_while_external(self):
        self.assertEqual(
            capacity.provider_state(
                local_provider(external=True), now=NOW),
            "QUARANTINED")


class FailClosedTests(unittest.TestCase):
    """An omission, an unknown value or a nonsense input is QUARANTINED."""

    def test_a_missing_externality_flag_is_treated_as_external(self):
        # The one assumption that fails closed: if nobody said the backend is
        # ours, it is someone else's, and someone else's needs a verified free
        # tier. The row below would otherwise pass every other gate.
        self.assertEqual(
            capacity.provider_state(
                local_provider(external=ABSENT), now=NOW),
            "QUARANTINED")

    def test_a_missing_health_claim_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(external_provider(health=ABSENT), now=NOW),
            "QUARANTINED")

    def test_an_unknown_health_value_is_quarantined(self):
        for health in ("GREAT", "healthy", "", None, 1, ["HEALTHY"]):
            with self.subTest(health=health):
                self.assertEqual(
                    capacity.provider_state(
                        external_provider(health=health), now=NOW),
                    "QUARANTINED")

    def test_an_unprobed_health_claim_is_quarantined(self):
        # Matching mesh_validator: a health value with no probe behind it is a
        # claim, not evidence.
        self.assertEqual(
            capacity.provider_state(
                external_provider(last_probe_at=None), now=NOW),
            "QUARANTINED")
        self.assertEqual(
            capacity.provider_state(
                external_provider(last_probe_at=ABSENT), now=NOW),
            "QUARANTINED")
        self.assertEqual(
            capacity.provider_state(
                external_provider(last_probe_at="yesterday"), now=NOW),
            "QUARANTINED")

    def test_a_non_mapping_is_quarantined(self):
        for row in (None, "", [], 7, object(), ["provider_id"]):
            with self.subTest(row=repr(row)):
                self.assertEqual(capacity.provider_state(row, now=NOW),
                                 "QUARANTINED")

    def test_a_row_carrying_a_field_the_contract_does_not_define_is_quarantined(self):
        # The provider schema is additionalProperties:false, so an extra key
        # means the row never validated. This is also the credential gate: an
        # unbounded string can only enter through a field nobody declared, and
        # a row carrying one is refused before anything reads it.
        for extra in ("api_key", "token", "bearer", "private_key", "notes"):
            with self.subTest(extra=extra):
                row = external_provider(**{extra: "x" * 4096})
                self.assertNotEqual(schema_errors(row), [])
                self.assertEqual(capacity.provider_state(row, now=NOW),
                                 "QUARANTINED")

    def test_a_nested_object_carrying_an_undeclared_field_is_quarantined(self):
        # The second place an undeclared - and therefore unbounded - string
        # tries to enter, once the top level refuses one.
        for overrides in (
                {"object_size_limits": {"max_object_bytes": 1, "api_key": "x" * 900}},
                {"rate_limits": {"requests_per_minute": 1, "token": "x" * 900}},
                {"free_status_evidence": {
                    "evidence_class": "runtime_account_evidence",
                    "verified_at": NOW,
                    "evidence_ref": "evidence/storage/r2_probe.json",
                    "secret": "x" * 900}},
                {"authority_flags": {"storage_authority": False, "api_key": "x"}}):
            with self.subTest(field=sorted(overrides)[0]):
                row = external_provider(**overrides)
                self.assertNotEqual(schema_errors(row), [])
                self.assertEqual(capacity.provider_state(row, now=NOW),
                                 "QUARANTINED")

    def test_an_unbounded_free_form_string_is_quarantined(self):
        # These are the provider record's only free-form fields. A class_token
        # is at most 40 lower-case characters and explicitly not a long hex
        # run, which is the shape of a raw key. An allowed unbounded string is
        # how a credential gets into a record with no field wide enough to
        # hold one, so the bound is enforced rather than assumed.
        for overrides in (
                {"retention_policy_class": "x" * 900},
                {"retention_policy_class": "a" * 64},
                {"retention_policy_class": ""},
                {"retention_policy_class": 7},
                {"quota_reset_semantics": "x" * 900},
                {"lifecycle_support": ["x" * 900]},
                {"lifecycle_support": "expiry"},
                {"free_status_evidence": {
                    "evidence_class": "runtime_account_evidence",
                    "verified_at": NOW,
                    "evidence_ref": "evidence/storage/r2_probe.json",
                    "observed_by": "x" * 900}}):
            with self.subTest(overrides=sorted(overrides)[0]):
                self.assertEqual(
                    capacity.provider_state(
                        external_provider(**overrides), now=NOW),
                    "QUARANTINED")

    def test_a_bounded_free_form_string_is_still_admitted(self):
        # The nearest legitimate row must still pass, or the bound above is
        # just a refusal of everything.
        self.assertEqual(
            capacity.provider_state(
                external_provider(retention_policy_class="bounded",
                                  quota_reset_semantics="monthly",
                                  lifecycle_support=["expiry", "compaction"]),
                now=NOW),
            "HEALTHY")

    def test_an_unbounded_evidence_reference_is_quarantined(self):
        for ref in ("evidence/" + "a" * 64 + ".dat", "x" * 400, "", 7,
                    "evidence/" + "A" * 300 + ".json"):
            with self.subTest(ref=repr(ref)[:40]):
                self.assertEqual(
                    capacity.provider_state(
                        external_provider(free_status_evidence={
                            "evidence_class": "runtime_account_evidence",
                            "verified_at": NOW, "evidence_ref": ref}), now=NOW),
                    "QUARANTINED")

    def test_an_external_provider_with_an_unknowable_quota_is_quarantined(self):
        for overrides in ({"quota_total": None}, {"quota_used": None},
                          {"quota_total": ABSENT}, {"quota_used": ABSENT}):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    capacity.provider_state(
                        external_provider(**overrides), now=NOW),
                    "QUARANTINED")

    def test_a_quota_that_is_not_a_whole_number_of_bytes_is_quarantined(self):
        for overrides in ({"quota_total": "100"}, {"quota_used": 1.5},
                          {"quota_total": -1}, {"quota_used": -1},
                          {"quota_reserved": -1}, {"quota_reserved": "0"},
                          {"quota_total": 0}):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    capacity.provider_state(
                        external_provider(**overrides), now=NOW),
                    "QUARANTINED")

    def test_a_boolean_is_not_a_quota(self):
        # bool is a subclass of int in Python, so True would otherwise read as
        # one byte used and sail through every numeric check.
        self.assertEqual(
            capacity.provider_state(
                external_provider(quota_used=True), now=NOW),
            "QUARANTINED")
        self.assertEqual(
            capacity.provider_state(
                external_provider(quota_total=True), now=NOW),
            "QUARANTINED")

    def test_a_quota_that_exceeds_itself_is_quarantined(self):
        self.assertEqual(
            capacity.provider_state(
                external_provider(quota_used=101), now=NOW),
            "QUARANTINED")
        self.assertEqual(
            capacity.provider_state(
                external_provider(quota_used=60, quota_reserved=60), now=NOW),
            "QUARANTINED")

    def test_autonomous_write_without_write_enabled_is_not_writable(self):
        self.assertNotIn(
            capacity.provider_state(
                external_provider(write_enabled=False), now=NOW),
            capacity.WRITABLE_STATES)

    def test_the_plans_illustrative_row_is_quarantined_not_healthy(self):
        # The plan sketches provider_state({"quota_used": 79, "quota_total":
        # 100, "health": "HEALTHY", "write_enabled": True}) == "HEALTHY". That
        # row names no externality, no free status, no spillover answer and no
        # probe, and admitting it would be precisely the optimistic pass the
        # zero-cost guard exists to prevent. The threshold it illustrates is
        # asserted above on a complete row; the sketch itself must fail closed.
        self.assertEqual(
            capacity.provider_state({
                "quota_used": 79, "quota_total": 100,
                "health": "HEALTHY", "write_enabled": True}, now=NOW),
            "QUARANTINED")


class HeadroomTests(unittest.TestCase):
    """Spec S10/S14: the hard limit bounds writes and 5% is held for CRITICAL."""

    def test_usable_headroom_stops_at_the_hard_limit_less_the_reserve(self):
        # 100 total: ceiling 92, reserve 5, so an ordinary object sees 87.
        self.assertEqual(
            capacity.usable_headroom_bytes(external_provider(), now=NOW), 87)

    def test_a_critical_object_may_draw_on_the_emergency_reserve(self):
        self.assertEqual(
            capacity.usable_headroom_bytes(
                external_provider(), reserve_exempt=True, now=NOW), 92)

    def test_headroom_never_goes_negative(self):
        self.assertEqual(
            capacity.usable_headroom_bytes(
                external_provider(quota_used=90), now=NOW), 0)

    def test_reserved_quota_is_subtracted_from_headroom(self):
        self.assertEqual(
            capacity.usable_headroom_bytes(
                external_provider(quota_used=10, quota_reserved=20), now=NOW),
            57)

    def test_a_quarantined_provider_has_no_headroom(self):
        self.assertEqual(
            capacity.usable_headroom_bytes(
                external_provider(free_status="UNVERIFIED"), now=NOW), 0)

    def test_a_near_full_provider_has_no_headroom(self):
        self.assertEqual(
            capacity.usable_headroom_bytes(
                external_provider(health="NEAR_FULL"), now=NOW), 0)

    def test_admits_write_fits_an_object_inside_the_reserved_ceiling(self):
        self.assertTrue(capacity.admits_write(external_provider(), 87, now=NOW))
        self.assertFalse(capacity.admits_write(external_provider(), 88, now=NOW))

    def test_admits_write_lets_critical_evidence_into_the_reserve(self):
        row = external_provider(quota_used=85)
        self.assertFalse(capacity.admits_write(row, 5, now=NOW))
        self.assertTrue(
            capacity.admits_write(row, 5, reserve_exempt=True, now=NOW))

    def test_admits_write_refuses_a_size_that_is_not_a_byte_count(self):
        for size in (None, "10", -1, 1.5, True, ABSENT):
            with self.subTest(size=repr(size)):
                self.assertFalse(
                    capacity.admits_write(external_provider(), size, now=NOW))

    def test_admits_a_zero_byte_object(self):
        self.assertTrue(capacity.admits_write(external_provider(), 0, now=NOW))

    def test_admits_write_refuses_a_provider_that_is_not_writable(self):
        for overrides in ({"health": "READ_ONLY"}, {"health": "OFFLINE"},
                          {"health": "NEAR_FULL"}, {"health": "QUARANTINED"},
                          {"write_enabled": False},
                          {"autonomous_write_allowed": False}):
            with self.subTest(overrides=overrides):
                self.assertFalse(
                    capacity.admits_write(
                        external_provider(**overrides), 1, now=NOW))

    def test_owned_storage_with_an_unknowable_quota_is_still_writable(self):
        # mesh_validator draws the same line: an unknown quota is a *cost* risk
        # only where somebody could send a bill. The local cache Spec S6 relies
        # on would otherwise have no admissible home anywhere in the mesh.
        row = local_provider(quota_total=None, quota_used=None)
        self.assertEqual(capacity.provider_state(row, now=NOW), "HEALTHY")
        self.assertTrue(capacity.admits_write(row, 1, now=NOW))


class AuthorityAndPurityTests(unittest.TestCase):
    """Spec S2: this is a subordinate broker with no authority and no side effects."""

    def test_the_module_declares_no_authority(self):
        self.assertIs(capacity.AUTHORITY, False)
        for flag in AUTHORITY_FLAGS:
            with self.subTest(flag=flag):
                self.assertIs(capacity.AUTHORITY_FLAGS[flag], False)

    def test_github_remains_canonical(self):
        self.assertEqual(capacity.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")

    def test_the_module_opens_nothing(self):
        source = (ROOT / "AI_SKILL_LIBRARY/v4/storage/capacity.py").read_text(
            encoding="utf-8")
        code = "\n".join(line for line in source.splitlines()
                         if not line.lstrip().startswith("#"))
        # Matched as code fragments rather than bare words: "requests" alone
        # also matches the schema's own ``requests_per_minute`` field name, and
        # a purity test that fires on a field name is a test nobody keeps.
        for forbidden in ("open(", "import requests", "requests.", "urllib",
                          "httpx", "import socket", "socket.", "subprocess",
                          "boto3", "write_text", "read_text", "os.environ",
                          "getenv(", "eval(", "exec("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)

    def test_the_state_vocabulary_is_the_specs_and_nothing_more(self):
        self.assertEqual(
            capacity.PROVIDER_STATES,
            ("FREE", "HEALTHY", "PRESSURED", "NEAR_FULL", "READ_ONLY",
             "QUARANTINED", "OFFLINE"))
        self.assertEqual(set(capacity.PROVIDER_STATES),
                         set(POLICY["provider_health_states"]))
        self.assertEqual(set(capacity.WRITABLE_STATES),
                         set(POLICY["writable_provider_health_states"]))

    def test_the_known_provider_fields_match_the_schema(self):
        self.assertEqual(set(capacity.PROVIDER_FIELDS),
                         set(PROVIDER_SCHEMA["properties"]))

    def test_the_broker_never_mutates_the_row_it_is_given(self):
        row = external_provider()
        before = json.dumps(row, sort_keys=True)
        capacity.provider_state(row, now=NOW)
        capacity.usable_headroom_bytes(row, now=NOW)
        capacity.admits_write(row, 1, now=NOW)
        self.assertEqual(json.dumps(row, sort_keys=True), before)

    def test_the_answer_does_not_depend_on_key_insertion_order(self):
        row = external_provider(quota_used=81)
        shuffled = dict(reversed(list(row.items())))
        self.assertEqual(capacity.provider_state(row, now=NOW),
                         capacity.provider_state(shuffled, now=NOW))

    def test_repeated_calls_agree(self):
        row = external_provider(quota_used=85)
        answers = {capacity.provider_state(row, now=NOW) for _ in range(25)}
        self.assertEqual(answers, {"PRESSURED"})


class ShippedRegistryTests(unittest.TestCase):
    """The honest state of the mesh today: nothing has been probed."""

    def test_every_shipped_registry_row_is_quarantined(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator
        for row in mesh_validator.load_providers():
            with self.subTest(provider=row.get("provider_id")):
                self.assertEqual(capacity.provider_state(row, now=NOW),
                                 "QUARANTINED")


if __name__ == "__main__":
    unittest.main()
