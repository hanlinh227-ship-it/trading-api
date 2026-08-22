#!/usr/bin/env python3
"""AUTO-INTAKE must be the real, unbypassable entry boundary.

These tests parse the ACTUAL workflow definitions and assert a structural
invariant across every workflow in the repository: DeepSeek is never invoked
without the AUTO-INTAKE boundary having run first in the same job.

This is a wiring invariant, deliberately checked against a different artifact
(the workflow YAML) than the module that implements the boundary.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

WORKFLOW_DIR = pathlib.Path(__file__).resolve().parents[3] / ".github" / "workflows"

def _invocation(script: str) -> re.Pattern[str]:
    """Match an actual `python3 <path>/<script>.py` execution.

    A bare filename mention (e.g. a `test -f` existence guard) is NOT an
    invocation and must not satisfy the boundary invariant.
    """
    return re.compile(
        r"python3(?:[ \t]*\\\n[ \t]*|[ \t]+)+[\"']?[^\s\"']*"
        + re.escape(script) + r"\.py"
    )


IMPLEMENTER_RE = _invocation("deepseek_implementer")
INTAKE_RE = _invocation("auto_intake")
INTAKE_ISSUE_RE = re.compile(r"auto_intake\.py\s+--issue")
MENTION_IMPLEMENTER_RE = re.compile(r"deepseek_implementer\.py")
INTAKE_FILE_RE = re.compile(r"auto_intake\.py\s+\\?\s*\n?\s*--validate-task-file")
INLINE_CONTRACT_RE = re.compile(r"AI_TASK_JSON_BEGIN")


def step_scripts(job: dict) -> list[tuple[str, str]]:
    out = []
    for step in job.get("steps") or []:
        if isinstance(step, dict) and isinstance(step.get("run"), str):
            out.append((step.get("name") or "", step["run"]))
    return out


@unittest.skipIf(yaml is None, "pyyaml unavailable")
class TestAutoIntakeIsTheEntryBoundary(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WORKFLOW_DIR.is_dir(), f"missing {WORKFLOW_DIR}")
        self.workflows = {}
        self.unparseable = {}
        for path in sorted(WORKFLOW_DIR.glob("*.yml")):
            raw = path.read_text(encoding="utf-8")
            try:
                doc = yaml.safe_load(raw)
            except yaml.YAMLError:
                # Pre-existing malformed workflows unrelated to the AI loop are
                # still checked textually for a bypass below.
                self.unparseable[path.name] = raw
                continue
            if isinstance(doc, dict) and doc.get("jobs"):
                self.workflows[path.name] = (doc, raw)

    def test_unparseable_workflows_do_not_invoke_the_implementer(self):
        for name, raw in self.unparseable.items():
            with self.subTest(wf=name):
                self.assertIsNone(
                    MENTION_IMPLEMENTER_RE.search(raw),
                    f"{name} cannot be structurally verified and must not "
                    f"reference deepseek_implementer.py at all",
                )

    def test_ai_loop_issue_path_enters_through_auto_intake(self):
        doc, _ = self.workflows["ai-loop.yml"]
        steps = step_scripts(doc["jobs"]["dispatch"])
        self.assertTrue(
            any(INTAKE_ISSUE_RE.search(run) for _, run in steps),
            "dispatch job must invoke auto_intake.py --issue",
        )

    def test_entry_jobs_do_not_parse_issue_json_inline(self):
        """The old inline parsers were the bypass; they must all be gone."""
        for wf, job in [("ai-loop.yml", "dispatch"), ("ai-loop-wake.yml", "wake-dispatch")]:
            doc, _ = self.workflows[wf]
            for name, run in step_scripts(doc["jobs"][job]):
                with self.subTest(wf=wf, step=name):
                    self.assertIsNone(
                        INLINE_CONTRACT_RE.search(run),
                        f"{wf}:{name!r} parses the task contract outside AUTO-INTAKE",
                    )

    def test_wake_path_enters_through_auto_intake(self):
        doc, _ = self.workflows["ai-loop-wake.yml"]
        steps = step_scripts(doc["jobs"]["wake-dispatch"])
        self.assertTrue(any(INTAKE_ISSUE_RE.search(run) for _, run in steps))

    def test_every_implementer_invocation_is_preceded_by_the_boundary(self):
        """Repository-wide non-bypass invariant, including future workflows."""
        found_any = False
        for filename, (doc, _) in self.workflows.items():
            for job_name, job in (doc.get("jobs") or {}).items():
                seen_boundary = False
                for step_name, run in step_scripts(job):
                    if INTAKE_RE.search(run):
                        seen_boundary = True
                    if IMPLEMENTER_RE.search(run):
                        found_any = True
                        with self.subTest(wf=filename, job=job_name, step=step_name):
                            self.assertTrue(
                                seen_boundary,
                                f"{filename}:{job_name}:{step_name!r} runs "
                                f"deepseek_implementer.py without a preceding "
                                f"auto_intake.py boundary step",
                            )
        self.assertTrue(found_any, "no implementer invocation found to check")

    def test_repair_path_revalidates_through_the_boundary(self):
        _, raw = self.workflows["ai-loop.yml"]
        monitor_start = raw.index("  monitor:")
        monitor = raw[monitor_start:]
        self.assertIn("--validate-task-file", monitor)
        self.assertIn("--expect-head", monitor)

    def test_manual_dispatch_path_revalidates_through_the_boundary(self):
        doc, _ = self.workflows["ai-task.yml"]
        steps = step_scripts(doc["jobs"]["implement"])
        boundary = [run for _, run in steps if INTAKE_RE.search(run)]
        self.assertTrue(boundary, "ai-task.yml must re-validate through AUTO-INTAKE")
        self.assertIn("--validate-task-file", "\n".join(boundary))

    def test_implementer_consumes_the_intake_produced_task_file(self):
        doc, _ = self.workflows["ai-loop.yml"]
        steps = doc["jobs"]["dispatch"]["steps"]
        impl = [s for s in steps if isinstance(s.get("run"), str)
                and IMPLEMENTER_RE.search(s["run"])]
        self.assertEqual(len(impl), 1)
        env = impl[0].get("env") or {}
        self.assertIn(
            "steps.intake.outputs.task_file", "".join(str(v) for v in env.values()),
            "implementer must consume the AUTO-INTAKE task file output",
        )

    def test_write_lock_and_secret_gates_are_still_enforced(self):
        """BLOCKER 5: pre-existing gates must not be dropped by the rewiring."""
        doc, _ = self.workflows["ai-loop.yml"]
        joined = "\n".join(run for _, run in step_scripts(doc["jobs"]["dispatch"]))
        self.assertIn("WRITE_LOCK.md", joined)
        self.assertIn("OWNER:[[:space:]]*DEEPSEEK", joined)
        self.assertIn("MISSING_DEEPSEEK_SECRET", joined)
        self.assertIn("DUPLICATE_IMPLEMENTATION_PR", joined)

    def test_no_auto_merge_or_deploy_in_the_ai_loop(self):
        for filename in ("ai-loop.yml", "ai-task.yml"):
            doc, _ = self.workflows[filename]
            for job_name, job in doc["jobs"].items():
                joined = "\n".join(run for _, run in step_scripts(job))
                with self.subTest(wf=filename, job=job_name):
                    self.assertNotIn("gh pr merge", joined)
                    self.assertNotIn("wrangler deploy", joined)


def split_jobs(raw: str) -> list[tuple[str, str]]:
    """Split a workflow's raw text into (job_name, job_text) without PyYAML."""
    lines = raw.splitlines(keepends=True)
    starts: list[tuple[int, str]] = []
    in_jobs = False
    for idx, line in enumerate(lines):
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if re.match(r"^\S", line):  # dedent back to top level ends jobs:
            in_jobs = False
            continue
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m:
            starts.append((idx, m.group(1)))
    jobs = []
    for i, (idx, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(lines)
        jobs.append((name, "".join(lines[idx:end])))
    return jobs


class TestEntryBoundaryWithoutPyYAML(unittest.TestCase):
    """The core non-bypass invariant, enforced with no third-party dependency.

    This must never silently skip: it is the property that keeps issue-supplied
    task contracts from reaching DeepSeek unvalidated.
    """

    def test_every_implementer_call_has_a_prior_boundary_call_in_its_job(self):
        checked = 0
        for path in sorted(WORKFLOW_DIR.glob("*.yml")):
            raw = path.read_text(encoding="utf-8")
            if not MENTION_IMPLEMENTER_RE.search(raw):
                continue
            for job_name, job_text in split_jobs(raw):
                impl = [m.start() for m in IMPLEMENTER_RE.finditer(job_text)]
                if not impl:
                    continue
                boundary = [m.start() for m in INTAKE_RE.finditer(job_text)]
                for offset in impl:
                    checked += 1
                    with self.subTest(wf=path.name, job=job_name):
                        self.assertTrue(
                            any(b < offset for b in boundary),
                            f"{path.name}:{job_name} invokes deepseek_implementer.py "
                            f"with no preceding auto_intake.py boundary",
                        )
        self.assertGreater(checked, 0, "no implementer invocation found to check")

    ENTRY_JOBS = {
        "ai-loop.yml": "dispatch",
        "ai-loop-wake.yml": "wake-dispatch",
        "ai-task.yml": "implement",
    }

    def test_no_entry_job_parses_the_task_contract_inline(self):
        """Entry jobs must take the contract from AUTO-INTAKE, never parse it.

        The `monitor` repair job may rebuild a task from the linked issue, but
        it must then re-enter the boundary via --validate-task-file before the
        implementer runs; that ordering is covered by the invariant above.
        """
        for wf, job in self.ENTRY_JOBS.items():
            raw = (WORKFLOW_DIR / wf).read_text(encoding="utf-8")
            jobs = dict(split_jobs(raw))
            self.assertIn(job, jobs, f"{wf}: entry job {job} not found")
            with self.subTest(wf=wf, job=job):
                self.assertIsNone(
                    INLINE_CONTRACT_RE.search(jobs[job]),
                    f"{wf}:{job} still parses AI_TASK_JSON outside AUTO-INTAKE",
                )

    def test_inline_rebuilt_task_is_revalidated_before_the_implementer(self):
        """Any job that DOES parse the contract inline must re-enter the
        boundary with --validate-task-file before invoking DeepSeek."""
        for path in sorted(WORKFLOW_DIR.glob("*.yml")):
            raw = path.read_text(encoding="utf-8")
            for job_name, job_text in split_jobs(raw):
                if not INLINE_CONTRACT_RE.search(job_text):
                    continue
                if not IMPLEMENTER_RE.search(job_text):
                    continue
                with self.subTest(wf=path.name, job=job_name):
                    impl = IMPLEMENTER_RE.search(job_text).start()
                    guard = job_text.find("--validate-task-file")
                    self.assertNotEqual(guard, -1,
                                        f"{path.name}:{job_name} rebuilds a task inline "
                                        f"without re-validating it")
                    self.assertLess(guard, impl)

    def test_ai_loop_entry_points_call_auto_intake_with_issue(self):
        for wf in ("ai-loop.yml", "ai-loop-wake.yml"):
            raw = (WORKFLOW_DIR / wf).read_text(encoding="utf-8")
            with self.subTest(wf=wf):
                self.assertIsNotNone(INTAKE_ISSUE_RE.search(raw))


class TestTaskFileReachesPythonConsumer(unittest.TestCase):
    """BLOCKER 1: a shell-local TASK_FILE is invisible to `os.environ`."""

    CONSUMER_RE = re.compile(r"""TASK_ID="\$\(python3 -c '([^']+)'([^)]*)\)""")

    def _consumers(self):
        for path in sorted(WORKFLOW_DIR.glob("*.yml")):
            raw = path.read_text(encoding="utf-8")
            for m in self.CONSUMER_RE.finditer(raw):
                yield path.name, m.group(1), m.group(2)

    def test_no_consumer_reads_task_file_from_os_environ(self):
        found = 0
        for wf, code, _tail in self._consumers():
            found += 1
            with self.subTest(wf=wf):
                self.assertNotIn(
                    'os.environ["TASK_FILE"]', code,
                    f"{wf}: TASK_FILE is shell-local; os.environ would KeyError",
                )
        self.assertGreater(found, 0, "no task-file consumer found to check")

    def test_every_consumer_receives_the_path_as_an_argument(self):
        for wf, code, tail in self._consumers():
            with self.subTest(wf=wf):
                self.assertIn("sys.argv[1]", code)
                self.assertIn('"$TASK_FILE"', tail,
                              f"{wf}: consumer does not pass $TASK_FILE as argv")

    def test_consumer_snippet_actually_works(self):
        """Execute the real snippet the way the workflow does."""
        consumers = list(self._consumers())
        self.assertTrue(consumers)
        with tempfile.TemporaryDirectory() as tmp:
            task = pathlib.Path(tmp) / "task.json"
            task.write_text(json.dumps({"task_id": "ARGV-OK"}), encoding="utf-8")
            for wf, code, _tail in consumers:
                with self.subTest(wf=wf):
                    proc = subprocess.run(
                        [sys.executable, "-c", code, str(task)],
                        text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout.strip(), "ARGV-OK")

    def test_env_style_snippet_would_have_failed(self):
        """Proves the old form was genuinely broken, not a style nit."""
        broken = 'import json,os; print(json.load(open(os.environ["TASK_FILE"]))["task_id"])'
        env = {k: v for k, v in os.environ.items() if k != "TASK_FILE"}
        proc = subprocess.run(
            [sys.executable, "-c", broken], text=True, capture_output=True,
            check=False, env=env,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("KeyError", proc.stderr)


class TestRepairUsesImmutableControlPlane(unittest.TestCase):
    """BLOCKER 2: the PR worktree must not supply the control-plane executable."""

    def _monitor_text(self) -> str:
        raw = (WORKFLOW_DIR / "ai-loop.yml").read_text(encoding="utf-8")
        jobs = dict(split_jobs(raw))
        self.assertIn("monitor", jobs)
        return jobs["monitor"]

    def test_control_plane_is_pinned_from_origin_main(self):
        monitor = self._monitor_text()
        self.assertIn("git archive", monitor)
        self.assertIn("origin/main", monitor)
        self.assertIn("ai-control-plane", monitor)

    def test_repair_checks_out_pr_then_runs_pinned_executables(self):
        monitor = self._monitor_text()
        checkout = monitor.index('git checkout -B "$BRANCH"')
        for script in ("auto_intake", "deepseek_implementer"):
            with self.subTest(script=script):
                match = _invocation(script).search(monitor, checkout)
                self.assertIsNotNone(
                    match, f"no {script} invocation after the PR checkout")
                invoked = monitor[match.start():match.end()]
                self.assertIn(
                    "$CONTROL_PLANE", invoked,
                    f"{script} is executed from the untrusted PR worktree",
                )

    def test_no_worktree_relative_control_plane_invocation_after_checkout(self):
        monitor = self._monitor_text()
        checkout = monitor.index('git checkout -B "$BRANCH"')
        after = monitor[checkout:]
        for script in ("auto_intake", "deepseek_implementer"):
            for m in _invocation(script).finditer(after):
                with self.subTest(script=script, call=m.group(0)[:60]):
                    self.assertNotIn(
                        "python3 scripts/ai/", m.group(0),
                        "repair must never run scripts/ai/* from the PR checkout",
                    )

    def test_pinned_executable_operates_on_the_workspace(self):
        monitor = self._monitor_text()
        for script in ("auto_intake", "deepseek_implementer"):
            m = _invocation(script).search(monitor, monitor.index("git checkout -B"))
            with self.subTest(script=script):
                prefix = monitor[max(0, m.start() - 120):m.start()]
                self.assertIn("AI_REPO_ROOT", prefix + m.group(0))

    def test_control_plane_is_write_protected_and_cleaned_up(self):
        monitor = self._monitor_text()
        self.assertIn("chmod -R a-w", monitor)
        raw = (WORKFLOW_DIR / "ai-loop.yml").read_text(encoding="utf-8")
        self.assertIn("rm -rf \"${RUNNER_TEMP:-/tmp}/ai-control-plane\"", raw)


class TestWriterPathsEnforceTheLock(unittest.TestCase):
    """Every job that writes source and pushes must honour the exclusive-writer
    lock, and must read it from a ref the PR cannot influence."""

    WRITER_JOBS = [
        ("ai-loop.yml", "dispatch"),
        ("ai-loop.yml", "monitor"),
        ("ai-loop-wake.yml", "wake-dispatch"),
        ("ai-task.yml", "implement"),
    ]

    def _job(self, wf: str, job: str) -> str:
        raw = (WORKFLOW_DIR / wf).read_text(encoding="utf-8")
        jobs = dict(split_jobs(raw))
        self.assertIn(job, jobs, f"{wf}: job {job} not found")
        return jobs[job]

    def test_every_pushing_job_checks_the_write_lock(self):
        checked = 0
        for wf, job in self.WRITER_JOBS:
            body = self._job(wf, job)
            if "git push" not in body:
                continue
            checked += 1
            with self.subTest(wf=wf, job=job):
                self.assertIn("WRITE_LOCK.md", body,
                              f"{wf}:{job} pushes source without a WRITE_LOCK check")
                self.assertIn("OWNER:[[:space:]]*DEEPSEEK", body)
        self.assertGreater(checked, 0)

    def test_repair_job_reads_the_lock_from_pinned_main(self):
        """The repair loop checks out a PR branch, so the lock must come from
        the pinned main ref, never from the PR worktree."""
        body = self._job("ai-loop.yml", "monitor")
        self.assertIn('$MAIN_SHA:docs/ai-coengineer/WRITE_LOCK.md', body)
        lock_at = body.index("WRITE_LOCK.md")
        checkout_at = body.index('git checkout -B "$BRANCH"')
        self.assertLess(lock_at, checkout_at,
                        "lock must be verified before any PR checkout")

    def test_every_pushing_job_requires_the_deepseek_secret(self):
        for wf, job in self.WRITER_JOBS:
            body = self._job(wf, job)
            if "git push" not in body:
                continue
            with self.subTest(wf=wf, job=job):
                self.assertIn("DEEPSEEK", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
