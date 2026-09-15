import copy
import unittest

from AI_SKILL_LIBRARY.v4.tools.opencode_worker import (
    build_opencode_job,
    translate_brain_permissions,
    validate_opencode_result,
)


class OpenCodeWorkerTests(unittest.TestCase):
    def _task(self, mode="patch"):
        return {
            "task_id": "task-1",
            "mode": mode,
            "permission_ceiling": "bounded_write" if mode == "patch" else "read_only",
            "allowed_paths": ["src/**", "tests/**"],
            "denied_actions": ["git_push", "external_directory", "financial_execution"],
            "timeout_seconds": 300,
            "output_schema": "legion_worker_result_v1",
            "risk_class": "B",
            "data_class": "PUBLIC",
        }

    def test_plan_and_review_deny_edits(self):
        for mode in ("plan", "review"):
            perms = translate_brain_permissions(self._task(mode))
            self.assertEqual(perms["edit"], "deny")
            self.assertEqual(perms["bash"], "deny")

    def test_explore_and_research_are_read_only(self):
        for mode in ("explore", "research"):
            perms = translate_brain_permissions(self._task(mode))
            self.assertEqual(perms["edit"], "deny")
            self.assertEqual(perms["bash"], "deny")
            self.assertEqual(perms["read"], "allow")

    def test_patch_allows_bounded_edit_but_never_git_push(self):
        perms = translate_brain_permissions(self._task("patch"))
        self.assertEqual(perms["edit"], "allow")
        self.assertEqual(perms["git_push"], "deny")
        self.assertEqual(perms["external_directory"], "deny")
        self.assertEqual(perms["financial_execution"], "deny")

    def test_test_mode_allows_test_execution_without_write(self):
        perms = translate_brain_permissions(self._task("test"))
        self.assertEqual(perms["edit"], "deny")
        self.assertEqual(perms["bash"], "allow")
        self.assertEqual(perms["git_push"], "deny")

    def test_brain_deny_cannot_be_upgraded(self):
        task = self._task("patch")
        task["permission_overrides"] = {
            "git_push": "allow",
            "external_directory": "allow",
            "financial_execution": "allow",
        }
        perms = translate_brain_permissions(task)
        self.assertEqual(perms["git_push"], "deny")
        self.assertEqual(perms["external_directory"], "deny")
        self.assertEqual(perms["financial_execution"], "deny")

    def test_job_is_typed_and_pins_source(self):
        job = build_opencode_job(
            self._task("patch"),
            {
                "repository": "owner/repo",
                "source_sha": "a" * 40,
                "branch": "legion-task-task-1",
                "workspace": "/workspace/task-1",
            },
        )
        self.assertEqual(job["task_id"], "task-1")
        self.assertEqual(job["source_sha"], "a" * 40)
        self.assertEqual(job["mode"], "patch")
        self.assertEqual(job["output_schema"], "legion_worker_result_v1")
        self.assertFalse(job["routing_authority"])
        self.assertFalse(job["reasoning_authority"])
        self.assertFalse(job["auto_mode_can_override_denies"])

    def test_result_rejects_wrong_source_path_and_permission_expansion(self):
        task = self._task("patch")
        result = {
            "task_id": "task-1",
            "source_sha": "a" * 40,
            "changed_paths": ["src/a.py", "secrets/.env"],
            "requested_permissions": {"git_push": "allow"},
            "status": "completed",
            "artifacts": [],
            "tests": [],
            "credentials_present": False,
        }
        task["source_sha"] = "a" * 40
        errors = validate_opencode_result(result, task)
        self.assertTrue(any("path" in e.lower() for e in errors))
        self.assertTrue(any("permission" in e.lower() for e in errors))

    def test_result_rejects_credentials_and_sha_mismatch(self):
        task = self._task("review")
        task["source_sha"] = "a" * 40
        result = {
            "task_id": "task-1",
            "source_sha": "b" * 40,
            "changed_paths": [],
            "requested_permissions": {},
            "status": "completed",
            "artifacts": [],
            "tests": [],
            "credentials_present": True,
        }
        errors = validate_opencode_result(result, task)
        self.assertTrue(any("source_sha" in e for e in errors))
        self.assertTrue(any("credential" in e.lower() for e in errors))


if __name__ == "__main__":
    unittest.main()
