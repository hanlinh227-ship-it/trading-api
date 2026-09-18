"""Offline fail-closed tests for the Always-On durable job contract (Task 1).

No network. No new dependencies. Validates the JSON Schema and policy.yaml
without touching Cloudflare worker files, Storage Mesh, Survival Plane,
checkpoint.json, shared_state.yaml, universal_fabric.yaml, release pointers,
or existing Always-On retry/reconciler files.
"""

import json
import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCHEMA_PATH = os.path.join(REPO_ROOT, "AI_SKILL_LIBRARY", "v4", "always_on", "job.schema.json")
POLICY_PATH = os.path.join(REPO_ROOT, "AI_SKILL_LIBRARY", "v4", "always_on", "policy.yaml")

REQUIRED_FIELDS = [
    "job_id",
    "request_id",
    "project_id",
    "role_id",
    "capability",
    "privacy_class",
    "priority",
    "idempotency_key",
    "attempt",
    "max_attempts",
    "created_at",
    "available_at",
    "deadline_at",
    "lease_owner",
    "lease_expires_at",
    "source_revision",
    "evidence_refs",
    "authority",
]

PRIVACY_CLASSES = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY"]


def _load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_policy_text():
    with open(POLICY_PATH, "r", encoding="utf-8") as handle:
        return handle.read()


def _policy_scalar(text, key):
    match = re.search(r"(?m)^" + re.escape(key) + r"\s*:\s*(\S+)\s*$", text)
    if not match:
        return None
    return match.group(1)


def _valid_job():
    return {
        "job_id": "job-1",
        "request_id": "req-1",
        "project_id": "proj-1",
        "role_id": "role-1",
        "capability": "cap-1",
        "privacy_class": "INTERNAL",
        "priority": 10,
        "idempotency_key": "idem-1",
        "attempt": 0,
        "max_attempts": 3,
        "created_at": "2024-01-01T00:00:00Z",
        "available_at": "2024-01-01T00:00:00Z",
        "deadline_at": "2024-01-02T00:00:00Z",
        "lease_owner": "worker-1",
        "lease_expires_at": "2024-01-01T00:05:00Z",
        "source_revision": "rev-1",
        "evidence_refs": ["evidence://ref-1"],
        "authority": False,
    }


def _validate(schema, job):
    """Minimal fail-closed validator for the subset of JSON Schema used here."""
    if not isinstance(job, dict):
        return ["job must be an object"]
    errors = []
    for field in schema.get("required", []):
        if field not in job:
            errors.append("missing required field: " + field)
    if schema.get("additionalProperties") is False:
        for key in job:
            if key not in schema.get("properties", {}):
                errors.append("unexpected field: " + key)
    for key, spec in schema.get("properties", {}).items():
        if key not in job:
            continue
        value = job[key]
        expected = spec.get("type")
        if expected == "string":
            if not isinstance(value, str):
                errors.append(key + " must be a string")
                continue
            if "minLength" in spec and len(value) < spec["minLength"]:
                errors.append(key + " too short")
            if "maxLength" in spec and len(value) > spec["maxLength"]:
                errors.append(key + " too long")
            if "enum" in spec and value not in spec["enum"]:
                errors.append(key + " not in enum")
        elif expected == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(key + " must be an integer")
                continue
            if "minimum" in spec and value < spec["minimum"]:
                errors.append(key + " below minimum")
            if "maximum" in spec and value > spec["maximum"]:
                errors.append(key + " above maximum")
        elif expected == "boolean":
            if not isinstance(value, bool):
                errors.append(key + " must be a boolean")
                continue
            if "const" in spec and value is not spec["const"]:
                errors.append(key + " must equal const")
        elif expected == "array":
            if not isinstance(value, list):
                errors.append(key + " must be an array")
                continue
            if "minItems" in spec and len(value) < spec["minItems"]:
                errors.append(key + " too few items")
            if "maxItems" in spec and len(value) > spec["maxItems"]:
                errors.append(key + " too many items")
            item_spec = spec.get("items", {})
            for item in value:
                if item_spec.get("type") == "string":
                    if not isinstance(item, str):
                        errors.append(key + " item must be a string")
                    elif "minLength" in item_spec and len(item) < item_spec["minLength"]:
                        errors.append(key + " item too short")
                    elif "maxLength" in item_spec and len(item) > item_spec["maxLength"]:
                        errors.append(key + " item too long")
    return errors


class TestAlwaysOnJobContract(unittest.TestCase):
    def setUp(self):
        self.schema = _load_schema()
        self.policy_text = _load_policy_text()

    def test_schema_requires_exact_durable_fields(self):
        self.assertEqual(sorted(self.schema.get("required", [])), sorted(REQUIRED_FIELDS))
        self.assertFalse(self.schema.get("additionalProperties", True))

    def test_valid_job_passes(self):
        self.assertEqual(_validate(self.schema, _valid_job()), [])

    def test_missing_authority_fails_closed(self):
        job = _valid_job()
        del job["authority"]
        self.assertTrue(_validate(self.schema, job))

    def test_authority_true_fails_closed(self):
        job = _valid_job()
        job["authority"] = True
        self.assertTrue(_validate(self.schema, job))

    def test_authority_const_is_false(self):
        self.assertIs(self.schema["properties"]["authority"].get("const"), False)

    def test_missing_required_durable_fields_fail_closed(self):
        for field in REQUIRED_FIELDS:
            job = _valid_job()
            del job[field]
            self.assertTrue(_validate(self.schema, job), "missing " + field + " must fail")

    def test_invalid_privacy_class_fails_closed(self):
        job = _valid_job()
        job["privacy_class"] = "SECRET"
        self.assertTrue(_validate(self.schema, job))

    def test_privacy_class_enum_is_canonical(self):
        self.assertEqual(
            self.schema["properties"]["privacy_class"].get("enum"),
            PRIVACY_CLASSES,
        )

    def test_invalid_attempt_bounds_fail_closed(self):
        job = _valid_job()
        job["attempt"] = -1
        self.assertTrue(_validate(self.schema, job))
        job = _valid_job()
        job["max_attempts"] = 0
        self.assertTrue(_validate(self.schema, job))
        job = _valid_job()
        job["attempt"] = "0"
        self.assertTrue(_validate(self.schema, job))
        job = _valid_job()
        job["max_attempts"] = True
        self.assertTrue(_validate(self.schema, job))

    def test_malformed_evidence_refs_fail_closed(self):
        job = _valid_job()
        job["evidence_refs"] = "evidence://ref-1"
        self.assertTrue(_validate(self.schema, job))
        job = _valid_job()
        job["evidence_refs"] = [""]
        self.assertTrue(_validate(self.schema, job))
        job = _valid_job()
        job["evidence_refs"] = [123]
        self.assertTrue(_validate(self.schema, job))

    def test_policy_authority_flags_are_false(self):
        for key in (
            "routing_authority",
            "scheduling_authority",
            "trading_authority",
            "model_selection_authority",
            "merge_authority",
            "deployment_authority",
        ):
            self.assertEqual(_policy_scalar(self.policy_text, key), "false", key)

    def test_policy_paid_execution_fallback_disabled(self):
        self.assertIn("paid_execution_fallback:", self.policy_text)
        self.assertIn("enabled: false", self.policy_text)

    def test_policy_background_processing_bounded_event_driven(self):
        self.assertIn("mode: event_driven", self.policy_text)
        self.assertIn("bounded: true", self.policy_text)
        self.assertIn("busy_polling: false", self.policy_text)

    def test_policy_duplicate_delivery_side_effect_safe(self):
        self.assertIn("side_effect_safe: true", self.policy_text)
        self.assertIn("idempotency_key_required: true", self.policy_text)

    def test_policy_sole_authority_notes_present(self):
        self.assertIn("GITHUB_BRAIN_V4 remains the sole Brain", self.policy_text)
        self.assertIn("task_router remains the sole routing authority", self.policy_text)
        self.assertIn("Model Mesh remains the model/provider selector", self.policy_text)


if __name__ == "__main__":
    unittest.main()
