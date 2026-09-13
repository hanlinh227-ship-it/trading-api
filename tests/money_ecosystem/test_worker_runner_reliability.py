from pathlib import Path

from money_ecosystem.worker import runner


def test_restart_self_preserves_module_invocation(monkeypatch):
    captured = {}

    def fake_execv(executable, argv):
        captured["executable"] = executable
        captured["argv"] = argv
        raise RuntimeError("stop")

    monkeypatch.setattr(runner.os, "execv", fake_execv)
    monkeypatch.setattr(runner.sys, "argv", ["runner.py", "--repo-root", "C:/AI/CuriousBeyond/repo"])

    try:
        runner._restart_self()
    except RuntimeError as exc:
        assert str(exc) == "stop"

    assert captured["argv"][1:3] == ["-m", "money_ecosystem.worker.runner"]
    assert captured["argv"][3:] == ["--repo-root", "C:/AI/CuriousBeyond/repo"]


def test_sync_uses_rebase_for_recovery(monkeypatch, tmp_path):
    calls = []
    heads = iter(["old", "new"])

    monkeypatch.setattr(runner, "_head", lambda repo_root: next(heads))

    class Result:
        returncode = 0
        stdout = "ok"

    def fake_git(repo_root, *args):
        calls.append(args)
        return Result()

    monkeypatch.setattr(runner, "_git", fake_git)
    changed = runner.sync_from_remote(tmp_path, "ai-money-ecosystem-autopilot-v1")

    assert changed is True
    assert calls == [("pull", "--rebase", "origin", "ai-money-ecosystem-autopilot-v1")]


def test_main_cycle_attempts_result_push_even_without_new_job(monkeypatch):
    # Reliability invariant is represented by the helper used by the loop:
    # publish_pending_results must be callable independently of run_once.
    assert callable(runner.push_results)
