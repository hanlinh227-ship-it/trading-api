#!/usr/bin/env python3
"""Behavioural tests for the downstream post-validation scope recheck.

These drive the REAL `deepseek_implementer` functions against a REAL temporary
git repository. Nothing here asserts that a source string exists: each test
performs an actual mutation and checks whether the guard actually catches it.

Runs under `python3 -m unittest` and under pytest.
"""

from __future__ import annotations

import importlib.util
import os
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


class TestControlPlaneImmutability(DownstreamScopeBase):
    """BLOCKER 2, behavioural: a PR edit of orchestration code must not become
    the executable used by repair.

    Models the real workflow: origin/main is archived into a pinned directory,
    the worktree is then switched to a PR branch that rewrites the orchestration
    scripts, and the pinned copy is invoked with AI_REPO_ROOT pointing at the
    tampered worktree.
    """

    MARKER = "PWNED_BY_PR_CHECKOUT"

    def _pin_control_plane(self) -> pathlib.Path:
        pinned = pathlib.Path(self._tmp.name).parent / (self.repo.name + "-cp")
        pinned.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, pinned, True)
        archive = subprocess.run(
            ["git", "archive", "HEAD", "scripts/ai"],
            cwd=str(self.repo), capture_output=True, check=False,
        )
        self.assertEqual(archive.returncode, 0, archive.stderr)
        extract = subprocess.run(
            ["tar", "-x", "-C", str(pinned)], input=archive.stdout, check=False,
            capture_output=True,
        )
        self.assertEqual(extract.returncode, 0, extract.stderr)
        return pinned

    def setUp(self):
        super().setUp()
        # A benign orchestration script tracked on "main".
        self.write("scripts/ai/orchestrator.py", "print('BENIGN_CONTROL_PLANE')\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "orchestration on main")

    def test_pinned_executable_is_unaffected_by_pr_tampering(self):
        pinned = self._pin_control_plane()

        # The PR checkout rewrites the orchestration script in the worktree.
        self.write("scripts/ai/orchestrator.py", f"print('{self.MARKER}')\n")

        worktree_run = subprocess.run(
            [sys.executable, str(self.repo / "scripts/ai/orchestrator.py")],
            text=True, capture_output=True, check=False,
        )
        pinned_run = subprocess.run(
            [sys.executable, str(pinned / "scripts/ai/orchestrator.py")],
            text=True, capture_output=True, check=False,
        )

        # The tampering is real...
        self.assertIn(self.MARKER, worktree_run.stdout)
        # ...but the pinned control plane still runs the trusted code.
        self.assertNotIn(self.MARKER, pinned_run.stdout)
        self.assertIn("BENIGN_CONTROL_PLANE", pinned_run.stdout)

    def test_pinned_intake_ignores_a_tampered_worktree_copy(self):
        """A PR that neuters auto_intake.py cannot disable the boundary."""
        intake_src = (MODULE_PATH.parent / "auto_intake.py").read_text(encoding="utf-8")
        self.write("scripts/ai/auto_intake.py", intake_src)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "intake on main")
        pinned = self._pin_control_plane()

        # PR replaces the boundary with an always-accept stub.
        self.write(
            "scripts/ai/auto_intake.py",
            "import sys\nprint('BOUNDARY_DISABLED')\nsys.exit(0)\n",
        )

        task = self.repo / "task.json"
        task.write_text("{}", encoding="utf-8")
        env = dict(os.environ, AI_REPO_ROOT=str(self.repo))
        proc = subprocess.run(
            [sys.executable, str(pinned / "scripts/ai/auto_intake.py"),
             "--validate-task-file", str(task), "--expect-head", "a" * 40],
            text=True, capture_output=True, check=False, env=env,
        )

        self.assertNotIn("BOUNDARY_DISABLED", proc.stdout)
        self.assertNotEqual(proc.returncode, 0, "pinned boundary must still reject")
        self.assertIn("AUTO_INTAKE_BLOCK", proc.stderr)

    def test_ai_repo_root_redirects_the_target_not_the_executable(self):
        env = dict(os.environ, AI_REPO_ROOT=str(self.repo))
        proc = subprocess.run(
            [sys.executable, "-c",
             "import importlib.util,os,pathlib,sys;"
             "spec=importlib.util.spec_from_file_location('m', sys.argv[1]);"
             "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
             "print(m.ROOT)",
             str(MODULE_PATH.parent / "auto_intake.py")],
            text=True, capture_output=True, check=False, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), str(self.repo.resolve()))


class TestCredentialFreeValidation(DownstreamScopeBase):
    """BLOCKER 3, defence in depth: validators run with no credentials."""

    LEAKY = [
        "DEEPSEEK_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "ACTIONS_RUNTIME_TOKEN",
        "SOME_CUSTOM_SECRET", "MY_PRIVATE_KEY", "SERVICE_PASSWORD",
    ]

    def test_credentials_are_absent_from_the_validation_environment(self):
        for name in self.LEAKY:
            os.environ[name] = "leaked-value"
            self.addCleanup(os.environ.pop, name, None)
        scrubbed = dsi.credential_free_env()
        for name in self.LEAKY:
            with self.subTest(var=name):
                self.assertNotIn(name, scrubbed)

    def test_benign_environment_is_preserved(self):
        scrubbed = dsi.credential_free_env()
        for name in ("PATH", "HOME"):
            if name in os.environ:
                with self.subTest(var=name):
                    self.assertIn(name, scrubbed)

    def test_plugin_injection_env_vars_are_scrubbed(self):
        """Env equivalents of the blocked pytest plugin/config options."""
        for name in ("PYTEST_PLUGINS", "PYTEST_ADDOPTS", "PYTHONPATH",
                     "PYTHONSTARTUP", "PYTHONHOME", "PYTHONWARNINGS"):
            os.environ[name] = "evil"
            self.addCleanup(os.environ.pop, name, None)
        scrubbed = dsi.credential_free_env()
        for name in ("PYTEST_PLUGINS", "PYTEST_ADDOPTS", "PYTHONPATH",
                     "PYTHONSTARTUP", "PYTHONHOME", "PYTHONWARNINGS"):
            with self.subTest(var=name):
                self.assertNotIn(name, scrubbed)

    def test_pytest_addopts_cannot_reach_a_validator(self):
        """End-to-end through the real validation runner."""
        os.environ["PYTEST_ADDOPTS"] = "-p evil_plugin"
        self.addCleanup(os.environ.pop, "PYTEST_ADDOPTS", None)
        task = dict(
            self.task,
            validation_commands=['echo "ADDOPTS:${PYTEST_ADDOPTS:-ABSENT}"'],
        )
        ok, logs = dsi.run_validations(task)
        self.assertTrue(ok, logs)
        self.assertIn("ADDOPTS:ABSENT", logs)
        self.assertNotIn("evil_plugin", logs)

    def test_a_validator_cannot_read_credentials_at_runtime(self):
        """End-to-end through the real validation runner."""
        os.environ["DEEPSEEK_API_KEY"] = "sk-must-not-be-visible-000000"
        self.addCleanup(os.environ.pop, "DEEPSEEK_API_KEY", None)
        task = dict(
            self.task,
            validation_commands=['echo "SEEN:${DEEPSEEK_API_KEY:-ABSENT}"'],
        )
        ok, logs = dsi.run_validations(task)
        self.assertTrue(ok, logs)
        self.assertIn("SEEN:ABSENT", logs)
        self.assertNotIn("sk-must-not-be-visible", logs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
