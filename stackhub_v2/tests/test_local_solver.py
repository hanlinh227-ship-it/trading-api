from stackhub.local_solver import build_prompt, safe_artifact_path


def test_local_solver_prompt_contains_task_constraints(tmp_path):
    payload = {
        "opportunity": {
            "source": "taskforce",
            "id": "tf-1",
            "category": "development",
            "requirements": ["Return a concise technical answer", "Do not invent evidence"],
            "acceptance_criteria": ["Answer is directly usable"],
        },
        "workspace_reference": "application-123",
    }
    prompt = build_prompt(payload)
    assert "Return a concise technical answer" in prompt
    assert "Do not invent evidence" in prompt
    assert "Answer is directly usable" in prompt
    assert "Do not claim actions" in prompt


def test_safe_artifact_path_is_confined_to_root(tmp_path):
    path = safe_artifact_path(tmp_path, "taskforce", "../bad/id")
    assert path.parent.parent == tmp_path
    assert path.name.endswith(".txt")
    assert ".." not in path.name
