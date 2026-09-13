from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .allowlist import ensure_safe_path
from .protocol import verify_envelope


class WorkerQueue:
    def __init__(self, repo_root: Path | str, secret: bytes):
        self.repo_root = Path(repo_root).resolve()
        self.secret = secret
        self.state_dir = self.repo_root / ".worker_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.seen_file = self.state_dir / "seen_jobs.json"

    def _load_seen(self) -> set[str]:
        if not self.seen_file.exists():
            return set()
        data = json.loads(self.seen_file.read_text(encoding="utf-8"))
        return {str(item) for item in data}

    def next_job(self) -> dict[str, Any] | None:
        signed_path = self.repo_root / "worker_jobs" / "signed" / "current.json"
        if not signed_path.exists():
            return None
        envelope = json.loads(signed_path.read_text(encoding="utf-8"))
        payload = verify_envelope(envelope, self.secret)
        if payload["job_id"] in self._load_seen():
            return None
        return payload

    def mark_seen(self, job_id: str) -> None:
        seen = self._load_seen()
        seen.add(job_id)
        self.seen_file.write_text(
            json.dumps(sorted(seen), indent=2),
            encoding="utf-8",
        )

    def write_result(
        self,
        job_id: str,
        status: str,
        artifact_manifest: dict[str, Any],
        message: str,
    ) -> Path:
        results_dir = self.repo_root / "worker_jobs" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        target = ensure_safe_path(
            self.repo_root,
            results_dir / f"{job_id}.json",
        )
        body = {
            "job_id": job_id,
            "status": status,
            "message": message,
            "artifact_manifest": artifact_manifest,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        target.write_text(
            json.dumps(body, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target
