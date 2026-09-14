from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import BinaryIO

from .client import WorkerQueue
from . import runtime as runtime_module
from .runtime import execute_job

RUNNER_BUILD = "worker-reliability-v4"


def run_once(queue: WorkerQueue, workspace_root: Path | str) -> bool:
    job = queue.next_job()
    if job is None:
        return False
    result = execute_job(job, workspace_root)
    manifest = dict(result.get("artifact_manifest", {}))
    manifest["_worker"] = {
        "runner_build": RUNNER_BUILD,
        "runtime_build": getattr(runtime_module, "RUNTIME_BUILD", "legacy"),
        "pid": os.getpid(),
    }
    queue.write_result(
        job["job_id"],
        result["status"],
        manifest,
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


def _code_changed_since_loaded(repo_root: Path, loaded_head: str) -> bool:
    current_head = _head(repo_root)
    return _worker_code_changed(repo_root, loaded_head, current_head)


def _commit_pending_results(repo_root: Path) -> None:
    result_dir = repo_root / "worker_jobs" / "results"
    if not result_dir.exists():
        return
    add = _git(repo_root, "add", "worker_jobs/results")
    if add.returncode != 0:
        raise RuntimeError(f"git add results failed: {add.stdout.strip()}")
    diff = _git(repo_root, "diff", "--cached", "--quiet")
    if diff.returncode == 0:
        return
    commit = _git(repo_root, "commit", "-m", "worker: publish local result")
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stdout.strip()}")


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


def push_results(repo_root: Path, branch: str) -> bool:
    result_dir = repo_root / "worker_jobs" / "results"
    if not result_dir.exists():
        return False

    _commit_pending_results(repo_root)
    before = _head(repo_root)
    rebase = _git(repo_root, "pull", "--rebase", "origin", branch)
    if rebase.returncode != 0:
        raise RuntimeError(f"git pull --rebase before push failed: {rebase.stdout.strip()}")
    after = _head(repo_root)
    code_changed = _worker_code_changed(repo_root, before, after)

    ahead = _git(repo_root, "rev-list", "--count", f"origin/{branch}..HEAD")
    if ahead.returncode != 0:
        raise RuntimeError(f"git rev-list failed: {ahead.stdout.strip()}")
    try:
        ahead_count = int(ahead.stdout.strip() or "0")
    except ValueError as exc:
        raise RuntimeError(f"unexpected git rev-list output: {ahead.stdout.strip()}") from exc

    if ahead_count > 0:
        push = _git(repo_root, "push", "origin", f"HEAD:{branch}")
        if push.returncode != 0:
            raise RuntimeError(f"git push failed: {push.stdout.strip()}")

    return code_changed


def _try_acquire_instance_lock(repo_root: Path) -> BinaryIO | None:
    state_dir = repo_root / ".worker_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "active_worker.lock"
    handle = path.open("a+b")
    if path.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError):
        handle.close()
        return None
    return handle


def _release_instance_lock(handle: BinaryIO) -> None:
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


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

    instance_lock = _try_acquire_instance_lock(repo_root)
    while instance_lock is None:
        print("Another Curious Beyond Worker is active; waiting for the local worker lock...", flush=True)
        time.sleep(5)
        instance_lock = _try_acquire_instance_lock(repo_root)

    queue = WorkerQueue(repo_root, secret)
    loaded_head = _head(repo_root)

    print("Curious Beyond Worker ONLINE")
    print(f"Repo: {repo_root}")
    print(f"Branch: {args.branch}")
    print(f"Runner build: {RUNNER_BUILD}")
    print(f"Runtime build: {getattr(runtime_module, 'RUNTIME_BUILD', 'legacy')}")

    try:
        while True:
            try:
                # Detect code that reached disk through any path, including a rebase
                # performed by an older runner while publishing a result.
                if _code_changed_since_loaded(repo_root, loaded_head):
                    _restart_self()
                _commit_pending_results(repo_root)
                if sync_from_remote(repo_root, args.branch):
                    _restart_self()
                if _code_changed_since_loaded(repo_root, loaded_head):
                    _restart_self()
                run_once(queue, repo_root)
                if push_results(repo_root, args.branch):
                    _restart_self()
                if _code_changed_since_loaded(repo_root, loaded_head):
                    _restart_self()
            except Exception as exc:
                print(f"Worker cycle error: {exc}", flush=True)
            time.sleep(max(5, args.poll_seconds))
    finally:
        _release_instance_lock(instance_lock)


if __name__ == "__main__":
    raise SystemExit(main())
