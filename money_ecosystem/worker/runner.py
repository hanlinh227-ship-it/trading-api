from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from .client import WorkerQueue
from .runtime import execute_job


def run_once(queue: WorkerQueue, workspace_root: Path | str) -> bool:
    job = queue.next_job()
    if job is None:
        return False
    result = execute_job(job, workspace_root)
    queue.write_result(
        job["job_id"],
        result["status"],
        result.get("artifact_manifest", {}),
        result.get("message", ""),
    )
    queue.mark_seen(job["job_id"])
    return True


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _head(repo_root: Path) -> str:
    result = _git(repo_root, "rev-parse", "HEAD")
    if result.returncode != 0:
        raise RuntimeError(f"git rev-parse failed: {result.stdout.strip()}")
    return result.stdout.strip()


def _worker_code_changed(repo_root: Path, before: str, after: str) -> bool:
    if before == after:
        return False
    result = _git(
        repo_root,
        "diff",
        "--name-only",
        before,
        after,
        "--",
        "money_ecosystem/worker",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stdout.strip()}")
    changed_paths = [
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    return any(path.startswith("money_ecosystem/worker/") for path in changed_paths)


def sync_from_remote(repo_root: Path, branch: str) -> bool:
    before = _head(repo_root)
    result = _git(repo_root, "pull", "--rebase", "origin", branch)
    if result.returncode != 0:
        raise RuntimeError(f"git pull --rebase failed: {result.stdout.strip()}")
    after = _head(repo_root)
    return _worker_code_changed(repo_root, before, after)


def _restart_self() -> None:
    print("Worker code updated; restarting to load new code...", flush=True)
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "money_ecosystem.worker.runner",
            *sys.argv[1:],
        ],
    )


def push_results(repo_root: Path, branch: str) -> None:
    result_dir = repo_root / "worker_jobs" / "results"
    if not result_dir.exists():
        return

    _git(repo_root, "add", "worker_jobs/results")
    diff = _git(repo_root, "diff", "--cached", "--quiet")
    if diff.returncode != 0:
        commit = _git(repo_root, "commit", "-m", "worker: publish local result")
        if commit.returncode != 0:
            raise RuntimeError(f"git commit failed: {commit.stdout.strip()}")

    rebase = _git(repo_root, "pull", "--rebase", "origin", branch)
    if rebase.returncode != 0:
        raise RuntimeError(f"git pull --rebase before push failed: {rebase.stdout.strip()}")

    ahead = _git(repo_root, "rev-list", "--count", f"origin/{branch}..HEAD")
    if ahead.returncode != 0:
        raise RuntimeError(f"git rev-list failed: {ahead.stdout.strip()}")
    try:
        ahead_count = int(ahead.stdout.strip() or "0")
    except ValueError as exc:
        raise RuntimeError(f"unexpected git rev-list output: {ahead.stdout.strip()}") from exc

    if ahead_count <= 0:
        return

    push = _git(repo_root, "push", "origin", f"HEAD:{branch}")
    if push.returncode != 0:
        raise RuntimeError(f"git push failed: {push.stdout.strip()}")


def _load_secret(secret_file: Path) -> bytes:
    secret = secret_file.read_text(encoding="utf-8-sig").strip()
    if len(secret) < 32:
        raise ValueError("Worker secret must be at least 32 characters")
    return secret.encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Curious Beyond Windows media worker")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--secret-file", required=True)
    parser.add_argument("--branch", default="ai-money-ecosystem-autopilot-v1")
    parser.add_argument("--poll-seconds", type=int, default=15)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    secret = _load_secret(Path(args.secret_file).resolve())
    queue = WorkerQueue(repo_root, secret)

    print("Curious Beyond Worker ONLINE")
    print(f"Repo: {repo_root}")
    print(f"Branch: {args.branch}")

    while True:
        try:
            if sync_from_remote(repo_root, args.branch):
                _restart_self()
            run_once(queue, repo_root)
            push_results(repo_root, args.branch)
        except Exception as exc:
            print(f"Worker cycle error: {exc}")
        time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
