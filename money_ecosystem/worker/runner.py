from __future__ import annotations

import argparse
import subprocess
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


def sync_from_remote(repo_root: Path, branch: str) -> None:
    result = _git(repo_root, "pull", "--ff-only", "origin", branch)
    if result.returncode != 0:
        raise RuntimeError(f"git pull failed: {result.stdout.strip()}")


def push_results(repo_root: Path, branch: str) -> None:
    result_dir = repo_root / "worker_jobs" / "results"
    if not result_dir.exists():
        return
    _git(repo_root, "add", "worker_jobs/results")
    diff = _git(repo_root, "diff", "--cached", "--quiet")
    if diff.returncode == 0:
        return
    commit = _git(repo_root, "commit", "-m", "worker: publish local result")
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stdout.strip()}")
    push = _git(repo_root, "push", "origin", f"HEAD:{branch}")
    if push.returncode != 0:
        raise RuntimeError(f"git push failed: {push.stdout.strip()}")


def _load_secret(secret_file: Path) -> bytes:
    # Windows PowerShell 5 may create UTF-8 files with a BOM. utf-8-sig
    # consumes that marker so the local HMAC key matches the GitHub secret.
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
            sync_from_remote(repo_root, args.branch)
            if run_once(queue, repo_root):
                push_results(repo_root, args.branch)
        except Exception as exc:
            print(f"Worker cycle error: {exc}")
        time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
