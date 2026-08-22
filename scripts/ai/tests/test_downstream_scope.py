#!/usr/bin/env python3
"""Behavioural tests for the downstream post-validation scope recheck.

These drive the REAL `deepseek_implementer` functions against a REAL temporary
git repository. Nothing here asserts that a source string exists: each test
performs an actual mutation and checks whether the guard actually catches it.

Runs under `python3 -m unittest` and under pytest.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "deepseek_implementer.py"

_spec = importlib.util.spec_from_file_location("deepseek_impl_under_test", MODULE_PATH)
dsi = importlib.util.module_from_spec(_spec)
sys.modules["deepseek_impl_under_test"] = dsi
_spec.loader.exec_module(dsi)

GIT = shutil.which("git")


def git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@t.t", *args],
        cwd=str(repo), text=True, capture_output=True, check=False,
    )


@unittest.skipIf(GIT is None, "git unavailable")
class DownstreamScopeBase(unittest.TestCase):
    """A real repo with one in-scope and one out-of-scope tracked file."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self._tmp.name)
        self._root = dsi.ROOT
        dsi.ROOT = self.repo
        self.addCleanup(self._restore)

        git(self.repo, "init", "-q", "-b", "main")
        self.write("scripts/ai/in_scope.py", "# in scope\n")
        self.write("cloudflare-worker/src/index.js", "// out of scope\n")
        git(self.repo, "add", "-A")
        commit = git(self.repo, "commit", "-q", "-m", "base")
        self.assertEqual(commit.returncode, 0, commit.stderr)

        self.task = {
            "task_id": "SCOPE-TEST",
            "allowed_paths": ["scripts/ai/**"],
            "forbidden_paths": [],
            "validation_commands": [],
        }

    def _restore(self):
        dsi.ROOT = self._root
        self._tmp.cleanup()

    def write(self, rel: str, content: str) -> pathlib.Path:
        target = self.repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def run_validation(self, shell_command: str):
        """Run a command through the REAL validation runner."""
        task = dict(self.task, validation_commands=[shell_command])
        return dsi.run_validations(task)


class TestPostValidationMutationDetected(DownstreamScopeBase):
    """BLOCKER 3: prove out-of-scope mutations made DURING validation are caught."""

    def test_pre_check_passes_then_validator_mutation_is_caught(self):
        before = dsi.capture_untracked_files()
        self.write("scripts/ai/in_scope.py", "# implementation edit\n")

        # Pre-validation check passes: only in-scope files changed.
        dsi.ensure_result_scope(self.task, before)

        # A validator now mutates a TRACKED file outside allowed_paths.
        ok, _ = self.run_validation("echo mutated >> cloudflare-worker/src/index.js")
        self.assertTrue(ok)

        # Post-validation recheck must catch it.
        with self.assertRaises(SystemExit) as ctx:
            dsi.ensure_result_scope(self.task, before)
        self.assertEqual(ctx.exception.code, 2)

    def test_validator_created_out_of_scope_file_is_caught(self):
        before = dsi.capture_untracked_files()
        self.write("scripts/ai/in_scope.py", "# implementation edit\n")
        dsi.ensure_result_scope(self.task, before)

        ok, _ = self.run_validation("mkdir -p cloudflare-worker/src && echo x > cloudflare-worker/src/injected.js")
        self.assertTrue(ok)

        with self.assertRaises(SystemExit):
            dsi.ensure_result_scope(self.task, before)

    def test_arbitrary_untracked_dotfile_is_still_caught(self):
        """Proves we did NOT broadly exempt dotfiles or untracked files."""
        before = dsi.capture_untracked_files()
        self.write("scripts/ai/in_scope.py", "# edit\n")
        for artifact in [".envrc", ".secret_stash", "tmp_evil.txt", ".config/evil.cfg"]:
            with self.subTest(artifact=artifact):
                path = self.write(artifact, "x\n")
                with self.assertRaises(SystemExit):
                    dsi.ensure_result_scope(self.task, before)
                path.unlink()

    def test_in_scope_only_change_passes(self):
        before = dsi.capture_untracked_files()
        self.write("scripts/ai/in_scope.py", "# edit\n")
        self.write("scripts/ai/new_helper.py", "# new in-scope file\n")
        resulting = dsi.ensure_result_scope(self.task, before)
        self.assertIn("scripts/ai/in_scope.py", resulting)
        self.assertIn("scripts/ai/new_helper.py", resulting)


class TestValidatorArtifactContainment(DownstreamScopeBase):
    """BLOCKER 4: known validator caches must not cause a false scope failure."""

    ARTIFACTS = [
        ".pytest_cache/v/cache/lastfailed",
        ".pytest_cache/CACHEDIR.TAG",
        "__pycache__/mod.cpython-312.pyc",
        "scripts/ai/__pycache__/auto_intake.cpython-312.pyc",
        ".mypy_cache/3.12/x.json",
        ".ruff_cache/content",
        "cloudflare-worker/__pycache__/x.pyc",
    ]

    def test_validator_artifacts_do_not_fail_scope(self):
        before = dsi.capture_untracked_files()
        self.write("scripts/ai/in_scope.py", "# edit\n")
        for artifact in self.ARTIFACTS:
            self.write(artifact, "cache\n")
        resulting = dsi.ensure_result_scope(self.task, before)
        for artifact in self.ARTIFACTS:
            self.assertNotIn(artifact, resulting)

    def test_real_pytest_run_does_not_fail_scope(self):
        """End-to-end: an actual pytest invocation creating .pytest_cache."""
        before = dsi.capture_untracked_files()
        self.write("scripts/ai/in_scope.py", "# edit\n")
        # Cache contents as they exist BEFORE pytest writes its self-ignoring
        # .gitignore, i.e. while git still reports them as untracked.
        self.write(".pytest_cache/v/cache/nodeids", "[]\n")
        self.write(".pytest_cache/v/cache/lastfailed", "{}\n")
        self.write(".pytest_cache/CACHEDIR.TAG", "Signature\n")
        untracked = dsi.capture_untracked_files()
        self.assertTrue(
            any(u.startswith(".pytest_cache/") for u in untracked),
            "test would be vacuous if git already ignored the cache",
        )
        dsi.ensure_result_scope(self.task, before)

    def test_artifact_exemption_does_not_cover_tracked_files(self):
        """A TRACKED file is never exempt, even with an artifact-like name."""
        self.write("cloudflare-worker/__pycache__/tracked.pyc", "tracked\n")
        git(self.repo, "add", "-Af")
        git(self.repo, "commit", "-q", "-m", "track artifact-named file")

        before = dsi.capture_untracked_files()
        self.write("cloudflare-worker/__pycache__/tracked.pyc", "MUTATED\n")
        with self.assertRaises(SystemExit):
            dsi.ensure_result_scope(self.task, before)

    def test_artifact_classifier_is_narrow(self):
        for artifact in [
            ".pytest_cache/x", "__pycache__/x", "a/b/__pycache__/c",
            ".mypy_cache/x", ".ruff_cache/x", "mod.pyc", "a/b/mod.pyo",
        ]:
            with self.subTest(artifact=artifact):
                self.assertTrue(dsi.is_validator_artifact(artifact))
        for real in [
            ".env", ".envrc", ".git/config", "scripts/ai/evil.py", "tmp.txt",
            ".pytest_cacheX/x", "pytest_cache/x", "notes.pycx", ".secret",
        ]:
            with self.subTest(real=real):
                self.assertFalse(dsi.is_validator_artifact(real))


class TestSecretGuardStillActive(DownstreamScopeBase):
    def test_secret_in_resulting_diff_is_blocked(self):
        before = dsi.capture_untracked_files()
        self.write("scripts/ai/in_scope.py", "KEY = 'sk-abcdefghijklmnopqrstuvwxyz012345'\n")
        with self.assertRaises(SystemExit):
            dsi.ensure_result_scope(self.task, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
