import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "deepseek_lane_apply.py"
ALLOWED = {
    "AI_SKILL_LIBRARY/v4/survival/policy.yaml",
    "AI_SKILL_LIBRARY/v4/survival/policy_adapter.py",
    "AI_SKILL_LIBRARY/v4/survival/secrets.py",
    "AI_SKILL_LIBRARY/tests/test_survival_policy.py",
    "AI_SKILL_LIBRARY/tests/test_survival_secrets.py",
}


def run_apply(tmp_path: Path, files: dict[str, str]):
    response = {
        "choices": [{"message": {"content": json.dumps({"files": files})}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    response_path = tmp_path / "response.json"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(response_path), str(tmp_path / "repo")],
        text=True,
        capture_output=True,
    )


def test_applies_only_the_survival_policy_and_secret_contract_files(tmp_path):
    files = {path: f"content for {path}\n" for path in ALLOWED}
    result = run_apply(tmp_path, files)
    assert result.returncode == 0, result.stderr
    for path, content in files.items():
        assert (tmp_path / "repo" / path).read_text(encoding="utf-8") == content
    assert "DEEPSEEK_USAGE_PROMPT_TOKENS=10" in result.stdout
    assert "DEEPSEEK_USAGE_COMPLETION_TOKENS=20" in result.stdout


def test_rejects_any_file_outside_the_exact_allowlist(tmp_path):
    files = {path: "ok\n" for path in ALLOWED}
    files["AI_SKILL_LIBRARY/checkpoint.json"] = "forbidden\n"
    result = run_apply(tmp_path, files)
    assert result.returncode != 0
    assert "DEEPSEEK_OUTPUT_REJECTED=path_not_allowed" in result.stderr
    assert not (tmp_path / "repo" / "AI_SKILL_LIBRARY" / "checkpoint.json").exists()


def test_rejects_missing_required_files(tmp_path):
    result = run_apply(tmp_path, {"AI_SKILL_LIBRARY/v4/survival/policy.yaml": "x\n"})
    assert result.returncode != 0
    assert "DEEPSEEK_OUTPUT_REJECTED=file_set_mismatch" in result.stderr

