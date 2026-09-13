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


def test_sync_rebases_and_restarts_only_for_worker_code(monkeypatch, tmp_path):
    heads = iter(["old", "new"])
    monkeypatch.setattr(runner, "_head", lambda repo_root: next(heads))

    class Result:
        def __init__(self, stdout="ok"):
            self.returncode = 0
            self.stdout = stdout

    calls = []
    def fake_git(repo_root, *args):
        calls.append(args)
        if args[:2] == ("diff", "--name-only"):
            return Result("money_ecosystem/worker/runtime.py\n")
        return Result()

    monkeypatch.setattr(runner, "_git", fake_git)
    assert runner.sync_from_remote(tmp_path, "ai-money-ecosystem-autopilot-v1") is True
    assert calls[0] == ("pull", "--rebase", "origin", "ai-money-ecosystem-autopilot-v1")


def test_sync_does_not_restart_for_job_only_commit(monkeypatch, tmp_path):
    heads = iter(["old", "new"])
    monkeypatch.setattr(runner, "_head", lambda repo_root: next(heads))

    class Result:
        returncode = 0
        stdout = "worker_jobs/signed/current.json\n"

    monkeypatch.setattr(runner, "_git", lambda repo_root, *args: Result())
    assert runner.sync_from_remote(tmp_path, "ai-money-ecosystem-autopilot-v1") is False


def test_pending_results_can_be_retried_without_new_job():
    assert callable(runner.push_results)
