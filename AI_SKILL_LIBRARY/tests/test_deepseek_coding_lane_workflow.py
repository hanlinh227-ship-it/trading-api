from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deepseek-survival-plane-lane.yml"


def test_lane_is_owner_only_branch_scoped_and_not_issue_triggered():
    text = WORKFLOW.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    triggers = data.get("on", data.get(True))
    assert triggers["push"]["branches"] == ["work/deepseek-survival-plane-442"]
    assert "issues" not in triggers
    assert "issue_comment" not in triggers
    assert "pull_request_target" not in triggers
    assert "github.actor == 'hanlinh227-ship-it'" in text


def test_lane_caps_one_call_and_six_thousand_output_tokens():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("/v1/chat/completions") == 1
    assert '"max_tokens": 6000' in text
    assert "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}" in text


def test_lane_declares_nonauthoritative_boundary_and_focused_tests():
    text = WORKFLOW.read_text(encoding="utf-8")
    for boundary in (
        "routing_authority=false",
        "reasoning_authority=false",
        "scheduling_authority=false",
        "merge_authority=false",
        "deployment_authority=false",
        "trading_authority=false",
    ):
        assert boundary in text
    assert "test_survival_policy.py" in text
    assert "test_survival_secrets.py" in text
