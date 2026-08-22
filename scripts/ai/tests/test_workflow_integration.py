#!/usr/bin/env python3
"""AUTO-INTAKE must be the real, unbypassable entry boundary.

These tests parse the ACTUAL workflow definitions and assert a structural
invariant across every workflow in the repository: DeepSeek is never invoked
without the AUTO-INTAKE boundary having run first in the same job.

This is a wiring invariant, deliberately checked against a different artifact
(the workflow YAML) than the module that implements the boundary.
"""

from __future__ import annotations

import pathlib
import re
import unittest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

WORKFLOW_DIR = pathlib.Path(__file__).resolve().parents[3] / ".github" / "workflows"

IMPLEMENTER_RE = re.compile(r"deepseek_implementer\.py")
INTAKE_RE = re.compile(r"auto_intake\.py")
INTAKE_ISSUE_RE = re.compile(r"auto_intake\.py\s+--issue")
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
                    IMPLEMENTER_RE.search(raw),
                    f"{name} cannot be structurally verified and must not "
                    f"invoke deepseek_implementer.py",
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
            if not IMPLEMENTER_RE.search(raw):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
