from types import SimpleNamespace
from money_ecosystem.worker import runner


def _cp(code=0, out=""):
    return SimpleNamespace(returncode=code, stdout=out)


def test_sync_reports_repository_change(monkeypatch, tmp_path):
    calls = iter([_cp(0, "old\n"), _cp(0, "Already up to date.\n"), _cp(0, "new\n")])
    monkeypatch.setattr(runner, "_git", lambda *args, **kwargs: next(calls))
    assert runner.sync_from_remote(tmp_path, "branch") is True


def test_sync_reports_no_change(monkeypatch, tmp_path):
    calls = iter([_cp(0, "same\n"), _cp(0, "Already up to date.\n"), _cp(0, "same\n")])
    monkeypatch.setattr(runner, "_git", lambda *args, **kwargs: next(calls))
    assert runner.sync_from_remote(tmp_path, "branch") is False
