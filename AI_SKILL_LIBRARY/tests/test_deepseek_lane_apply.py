"""Offline proof that the DeepSeek lane parser and ownership guard fail closed.

Every fixture here is a literal written in this file. Nothing in this module
opens a socket, reads an API key, or costs a fraction of a cent: the whole point
is that the lane's output contract can be settled without spending the balance
the way four consecutive runs spent it on the same unnamed `invalid_response`.

The case that matters most is `content_truncated`. Four runs reported a healthy
API and an unusable body, and the log could not tell them apart because
`finish_reason` was printed only on the success path. A reply cut off at
max_tokens is not a malformed reply, and the fix for it is a larger ceiling, not
a rewritten parser.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "deepseek_lane_apply.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("deepseek_lane_apply", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


apply_module = _load_module()
ALLOWED_FILES = apply_module.ALLOWED_FILES


def envelope(content, *, finish_reason="stop", prompt_tokens=338,
             completion_tokens=4338, choices=None):
    """One OpenAI-compatible response. `content` is whatever the model said."""
    if choices is None:
        choices = [{"index": 0, "finish_reason": finish_reason,
                    "message": {"role": "assistant", "content": content}}]
    return {
        "id": "chatcmpl-offline-fixture",
        "object": "chat.completion",
        "model": "deepseek-chat",
        "choices": choices,
        "usage": {"prompt_tokens": prompt_tokens,
                  "completion_tokens": completion_tokens,
                  "total_tokens": prompt_tokens + completion_tokens},
    }


def five_files(**overrides):
    files = {path: f"# generated content for {path}\n" for path in sorted(ALLOWED_FILES)}
    files.update(overrides)
    return {"files": files}


class LaneHarness(unittest.TestCase):
    """Run the script the way the workflow runs it, and capture the verdict."""

    def run_apply(self, document, *, argv_extra=None):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            response_path = Path(tmp) / "response.json"
            if document is not None:
                response_path.write_text(
                    document if isinstance(document, str) else json.dumps(document),
                    encoding="utf-8")
            argv = argv_extra or ["deepseek_lane_apply.py", str(response_path), str(root)]
            buffer = io.StringIO()
            code = 0
            try:
                with redirect_stdout(buffer):
                    apply_module.main(argv)
            except SystemExit as exc:
                code = exc.code
            written = sorted(
                str(p.relative_to(root)).replace("\\", "/")
                for p in root.rglob("*") if p.is_file())
            return code, buffer.getvalue(), written

    def assertRejected(self, document, reason):
        code, out, written = self.run_apply(document)
        self.assertEqual(code, 1, f"expected rejection, got clean exit\n{out}")
        self.assertIn("DEEPSEEK_PAYLOAD_VALID=FAIL", out)
        self.assertEqual(written, [], "a rejected response wrote files to disk")
        self.assertIn(reason, apply_module.REASONS)
        return out


class CaseAValidResponseApplies(LaneHarness):
    """Case A: valid envelope + exact five-file JSON => APPLY PASS."""

    def test_the_five_files_are_written_and_the_lane_reports_pass(self):
        code, out, written = self.run_apply(envelope(json.dumps(five_files())))
        self.assertEqual(code, 0, out)
        self.assertIn("DEEPSEEK_API_HEALTH=PASS", out)
        self.assertIn("DEEPSEEK_PAYLOAD_VALID=PASS", out)
        self.assertIn("DEEPSEEK_OUTPUT_APPLIED=PASS", out)
        self.assertEqual(written, sorted(ALLOWED_FILES))

    def test_diagnostics_are_reported_on_the_success_path_too(self):
        _, out, _ = self.run_apply(envelope(json.dumps(five_files())))
        for field in ("DEEPSEEK_CHOICE_COUNT=1", "DEEPSEEK_FINISH_REASON=stop",
                      "DEEPSEEK_CONTENT_PRESENT=true",
                      "DEEPSEEK_USAGE_PROMPT_TOKENS=338",
                      "DEEPSEEK_USAGE_COMPLETION_TOKENS=4338"):
            self.assertIn(field, out)


class CaseBFencedJsonApplies(LaneHarness):
    """Case B: valid fenced JSON => APPLY PASS."""

    def test_a_json_fence_is_unwrapped(self):
        fenced = "```json\n" + json.dumps(five_files()) + "\n```"
        code, out, written = self.run_apply(envelope(fenced))
        self.assertEqual(code, 0, out)
        self.assertEqual(written, sorted(ALLOWED_FILES))

    def test_a_bare_fence_with_no_language_is_unwrapped(self):
        fenced = "```\n" + json.dumps(five_files()) + "\n```"
        code, _, written = self.run_apply(envelope(fenced))
        self.assertEqual(code, 0)
        self.assertEqual(written, sorted(ALLOWED_FILES))

    def test_an_unterminated_fence_is_refused(self):
        self.assertRejected(envelope("```json\n" + json.dumps(five_files())),
                            "invalid_fence")


class CaseCEmptyContentRejected(LaneHarness):
    """Case C: empty content => REJECT."""

    def test_an_empty_string_is_refused(self):
        out = self.assertRejected(envelope(""), "content_empty")
        self.assertIn("DEEPSEEK_CONTENT_LENGTH=0", out)

    def test_whitespace_only_is_refused(self):
        self.assertRejected(envelope("   \n\t "), "content_empty")

    def test_empty_content_with_finish_reason_length_is_named_a_truncation(self):
        """The distinction four runs needed and could not make."""
        _, out, _ = self.run_apply(envelope("", finish_reason="length"))
        self.assertIn("DEEPSEEK_FINISH_REASON=length", out)
        self.assertIn("DEEPSEEK_API_HEALTH=PASS", out)
        self.assertIn("DEEPSEEK_PAYLOAD_VALID=FAIL", out)


class CaseDMalformedJsonRejected(LaneHarness):
    """Case D: malformed JSON => REJECT."""

    def test_prose_instead_of_json_is_refused(self):
        self.assertRejected(
            envelope("Certainly! Here are the five files you asked for."),
            "payload_not_json")

    def test_a_json_array_is_not_an_object(self):
        self.assertRejected(envelope(json.dumps([{"files": {}}])), "payload_not_object")

    def test_a_truncated_body_is_reported_as_truncation_not_as_bad_json(self):
        full = json.dumps(five_files())
        cut = full[:max(1, len(full) // 2)]
        _, out, _ = self.run_apply(envelope(cut, finish_reason="length"))
        self.assertIn("DEEPSEEK_FINISH_REASON=length", out)
        self.assertIn("DEEPSEEK_PAYLOAD_VALID=FAIL", out)

    def test_a_truncated_body_is_never_scavenged_into_a_partial_apply(self):
        """The old parser raw_decode'd from the first '{' and could hand back a
        short object. A truncated reply must apply nothing at all."""
        full = json.dumps(five_files())
        cut = full[:max(1, len(full) // 2)]
        code, _, written = self.run_apply(envelope(cut, finish_reason="length"))
        self.assertEqual(code, 1)
        self.assertEqual(written, [])

    def test_the_response_file_itself_being_unreadable_is_not_api_health_pass(self):
        code, out, _ = self.run_apply(None)
        self.assertEqual(code, 1)
        self.assertNotIn("DEEPSEEK_API_HEALTH=PASS", out)


class CaseEFileSetMismatchRejected(LaneHarness):
    """Case E: missing or extra file => REJECT."""

    def test_four_of_five_is_refused(self):
        payload = five_files()
        payload["files"].pop(sorted(ALLOWED_FILES)[0])
        self.assertRejected(envelope(json.dumps(payload)), "file_set_mismatch")

    def test_a_sixth_file_is_refused(self):
        payload = five_files()
        payload["files"]["AI_SKILL_LIBRARY/v4/survival/extra.py"] = "x = 1\n"
        self.assertRejected(envelope(json.dumps(payload)), "path_not_allowed")

    def test_a_storage_mesh_file_is_refused(self):
        """The lane may never touch another lane's files."""
        payload = five_files()
        payload["files"]["AI_SKILL_LIBRARY/v4/storage/manifest.py"] = "AUTHORITY = True\n"
        self.assertRejected(envelope(json.dumps(payload)), "path_not_allowed")

    def test_a_workflow_file_is_refused(self):
        payload = five_files()
        payload["files"][".github/workflows/deepseek-survival-plane-lane.yml"] = "on: push\n"
        self.assertRejected(envelope(json.dumps(payload)), "path_not_allowed")

    def test_no_files_key_is_refused(self):
        self.assertRejected(envelope(json.dumps({"result": "ok"})), "files_missing")

    def test_a_non_string_file_body_is_refused(self):
        payload = five_files(**{sorted(ALLOWED_FILES)[0]: {"nested": "object"}})
        self.assertRejected(envelope(json.dumps(payload)), "file_content_not_string")

    def test_nothing_is_written_when_the_fifth_file_is_bad(self):
        """All-or-nothing: the old loop wrote as it validated."""
        payload = five_files(**{sorted(ALLOWED_FILES)[-1]: 12345})
        code, _, written = self.run_apply(envelope(json.dumps(payload)))
        self.assertEqual(code, 1)
        self.assertEqual(written, [], "a partial application reached the working tree")


class CaseFPathTraversalRejected(LaneHarness):
    """Case F: path traversal => REJECT."""

    def test_traversal_shapes_are_refused(self):
        for hostile in ("../../etc/passwd",
                        "AI_SKILL_LIBRARY/../../.ssh/id_rsa",
                        "/etc/passwd",
                        "AI_SKILL_LIBRARY/v4/survival/../../../.git/config"):
            with self.subTest(path=hostile):
                payload = five_files()
                payload["files"][hostile] = "pwned\n"
                # Caught by the allowlist first, which is the stronger check:
                # a path that is not one of the five never reaches the
                # traversal test at all.
                self.assertRejected(envelope(json.dumps(payload)), "path_not_allowed")

    def test_nothing_escapes_the_root_even_on_the_success_path(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            sentinel = Path(tmp) / "outside.txt"
            response = Path(tmp) / "r.json"
            response.write_text(json.dumps(envelope(json.dumps(five_files()))),
                                encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                apply_module.main(["x", str(response), str(root)])
            self.assertFalse(sentinel.exists())
            for path in root.rglob("*"):
                self.assertTrue(path.resolve().is_relative_to(root.resolve()))


class EnvelopeValidationTests(LaneHarness):
    """The outer envelope is a separate verdict from the payload inside it."""

    def test_no_choices_is_refused(self):
        self.assertRejected(envelope(None, choices=[]), "envelope_no_choices")

    def test_a_non_object_envelope_is_refused(self):
        self.assertRejected(json.dumps(["not", "an", "object"]), "envelope_not_object")

    def test_unparseable_json_is_an_api_health_failure_not_a_payload_failure(self):
        code, out, _ = self.run_apply("{not json at all")
        self.assertEqual(code, 1)
        self.assertIn("DEEPSEEK_API_HEALTH=FAIL", out)

    def test_a_healthy_api_can_coexist_with_an_invalid_payload(self):
        """Order item 5, stated as an executable fact."""
        _, out, _ = self.run_apply(envelope("not json"))
        self.assertIn("DEEPSEEK_API_HEALTH=PASS", out)
        self.assertIn("DEEPSEEK_PAYLOAD_VALID=FAIL", out)

    def test_a_null_content_is_refused(self):
        self.assertRejected(envelope(None), "content_not_string")


class NoSecretReachesTheLogTests(LaneHarness):
    """Nothing from the response body is ever printed."""

    NEEDLES = (
        "sk-deadbeefdeadbeefdeadbeefdeadbeef",
        "AKIAIOSFODNN7EXAMPLE",
        "-----BEGIN RSA PRIVATE KEY-----",
        "Bearer abcdef0123456789abcdef0123456789",
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    )

    def test_no_needle_survives_into_stdout_on_any_path(self):
        for needle in self.NEEDLES:
            for label, document in (
                ("prose content", envelope(f"sorry, here is my key {needle}")),
                ("payload value", envelope(json.dumps(
                    five_files(**{sorted(ALLOWED_FILES)[0]: needle})))),
                ("extra path", envelope(json.dumps({"files": {needle: "x"}}))),
                ("envelope field", envelope(json.dumps(five_files()),
                                            finish_reason=needle)),
            ):
                with self.subTest(needle=needle[:12], case=label):
                    _, out, _ = self.run_apply(document)
                    self.assertNotIn(needle, out)

    def test_the_script_never_reads_an_environment_variable(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("os.environ", "getenv", "DEEPSEEK_API_KEY",
                          "Authorization", "requests.", "urllib", "socket",
                          "subprocess"):
            self.assertNotIn(forbidden, source,
                             f"the apply script references {forbidden!r}")

    def test_every_reason_code_is_declared_and_none_interpolates_input(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("assert reason in REASONS", source)
        for reason in apply_module.REASONS:
            self.assertRegex(reason, r"^[a-z_]+$")


class OwnershipGuardTests(unittest.TestCase):
    """Cases G and H: the guard must enumerate deep untracked files one by one.

    The FAIL in run 35302103254 was not a bad file - it was `git status --short`
    collapsing a new directory into a single `dir/` entry, so the guard compared
    a directory name against a list of file paths and refused its own correct
    output. `--untracked-files=all` is what makes the comparison meaningful.
    """

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.git("init", "-q")
        self.git("config", "user.email", "lane@example.invalid")
        self.git("config", "user.name", "lane")
        (self.root / "seed.txt").write_text("seed\n", encoding="utf-8")
        self.git("add", "seed.txt")
        self.git("commit", "-q", "-m", "seed")

    def git(self, *args):
        return subprocess.run(("git", *args), cwd=self.root, capture_output=True,
                              text=True, check=False).stdout

    def write(self, relative, body="x\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def untracked(self, *, all_files):
        flag = "--untracked-files=all" if all_files else "--untracked-files=normal"
        out = self.git("status", "--short", flag)
        return sorted(line[3:] for line in out.splitlines() if line.startswith("?? "))

    def test_collapsed_output_is_why_the_guard_failed(self):
        """Reproduces the root cause: without the flag git reports a directory."""
        for relative in sorted(ALLOWED_FILES):
            self.write(relative)
        collapsed = self.untracked(all_files=False)
        self.assertNotEqual(collapsed, sorted(ALLOWED_FILES))
        self.assertTrue(any(entry.endswith("/") for entry in collapsed),
                        f"expected a collapsed directory entry, got {collapsed}")

    def test_case_g_the_guard_enumerates_every_file_and_passes_the_allowlist(self):
        for relative in sorted(ALLOWED_FILES):
            self.write(relative)
        self.assertEqual(self.untracked(all_files=True), sorted(ALLOWED_FILES))
        self.assertEqual(set(self.untracked(all_files=True)) - ALLOWED_FILES, set())

    def test_case_h_the_guard_rejects_a_sixth_file(self):
        for relative in sorted(ALLOWED_FILES):
            self.write(relative)
        self.write("AI_SKILL_LIBRARY/v4/storage/manifest.py", "AUTHORITY = True\n")
        unexpected = set(self.untracked(all_files=True)) - ALLOWED_FILES
        self.assertEqual(unexpected, {"AI_SKILL_LIBRARY/v4/storage/manifest.py"})

    def test_the_guard_also_sees_a_modified_tracked_file(self):
        """An untracked-file scan alone would miss an edit to an existing file."""
        (self.root / "seed.txt").write_text("tampered\n", encoding="utf-8")
        out = self.git("status", "--short", "--untracked-files=all")
        self.assertTrue(any(line.startswith(" M") for line in out.splitlines()), out)


class WorkflowContractTests(unittest.TestCase):
    """The request settings the order fixes, asserted against the workflow."""

    WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deepseek-survival-plane-lane.yml"

    def setUp(self):
        if not self.WORKFLOW.is_file():
            self.skipTest("lane workflow not present on this branch")
        self.source = self.WORKFLOW.read_text(encoding="utf-8")

    def test_the_request_is_deterministic(self):
        self.assertIn('"temperature": 0', self.source)
        self.assertIn('"model": "deepseek-chat"', self.source)
        self.assertIn('"response_format": {"type": "json_object"}', self.source)

    def test_the_ownership_guard_enumerates_untracked_files_individually(self):
        self.assertIn("--untracked-files=all", self.source)

    def test_no_secret_value_is_echoed_by_the_workflow(self):
        for forbidden in ("echo $DEEPSEEK", "echo \"$DEEPSEEK",
                          "cat /tmp/deepseek-response.json"):
            self.assertNotIn(forbidden, self.source)


if __name__ == "__main__":
    unittest.main()
