from pathlib import Path

import pytest

from stackhub.verification import verify_workspace


def test_verify_workspace_requires_nonempty_diff(tmp_path: Path):
    root = tmp_path / "solver-root"
    work = root / "task"
    work.mkdir(parents=True)
    (work / "fix.patch").write_text("", encoding="utf-8")

    evidence = verify_workspace(
        work,
        ["python", "-c", "print('ok')"],
        solver_root=root,
        diff_path=work / "fix.patch",
        timeout_seconds=10,
    )
    assert evidence.passed is False
    assert evidence.exit_code == 0


def test_verify_workspace_passes_with_successful_test_and_diff(tmp_path: Path):
    root = tmp_path / "solver-root"
    work = root / "task"
    work.mkdir(parents=True)
    patch = work / "fix.patch"
    patch.write_text("diff --git a/a.py b/a.py\n+print('fixed')\n", encoding="utf-8")

    evidence = verify_workspace(
        work,
        ["python", "-c", "print('tests pass')"],
        solver_root=root,
        diff_path=patch,
        timeout_seconds=10,
    )
    assert evidence.passed is True
    assert "tests pass" in evidence.stdout_tail


def test_verify_workspace_rejects_path_escape(tmp_path: Path):
    root = tmp_path / "solver-root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    patch = outside / "fix.patch"
    patch.write_text("diff --git a/a b/a\n+x\n", encoding="utf-8")

    with pytest.raises(ValueError):
        verify_workspace(
            outside,
            ["python", "-c", "print('x')"],
            solver_root=root,
            diff_path=patch,
            timeout_seconds=10,
        )


def test_verify_workspace_rejects_secret_like_diff(tmp_path: Path):
    root = tmp_path / "solver-root"
    work = root / "task"
    work.mkdir(parents=True)
    patch = work / "fix.patch"
    patch.write_text("+TASKBOUNTY_API_KEY=tb_live_REALLOOKINGTOKEN123\n", encoding="utf-8")

    evidence = verify_workspace(
        work,
        ["python", "-c", "print('ok')"],
        solver_root=root,
        diff_path=patch,
        timeout_seconds=10,
    )
    assert evidence.passed is False
