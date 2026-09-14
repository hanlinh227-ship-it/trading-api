from __future__ import annotations

from dataclasses import asdict, dataclass
import mimetypes
from pathlib import Path
from typing import Any, Iterable

from .contract import RenderJob, ReturnMode


@dataclass(frozen=True)
class ReturnArtifact:
    drive_file_id: str
    logical_role: str
    mime_type: str
    byte_size: int
    sha256: str
    source_name: str
    parent_id: str
    qa_summary: dict[str, Any]


@dataclass(frozen=True)
class ReturnManifest:
    job_id: str
    attempt_id: str
    project_id: str
    return_mode: ReturnMode
    artifacts: tuple[ReturnArtifact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "attempt_id": self.attempt_id,
            "project_id": self.project_id,
            "return_mode": self.return_mode.value,
            "artifacts": [asdict(item) for item in self.artifacts],
        }


def select_return_mode(
    requested: ReturnMode,
    *,
    chat_attachment_available: bool,
    drive_available: bool = True,
) -> ReturnMode:
    if requested is ReturnMode.CHAT_ATTACHMENT_PREFERRED:
        if chat_attachment_available:
            return ReturnMode.CHAT_ATTACHMENT_PREFERRED
        if drive_available:
            return ReturnMode.DRIVE_CARD
        return ReturnMode.LOCAL_PATH_DIAGNOSTIC
    if requested is ReturnMode.DRIVE_CARD:
        return ReturnMode.DRIVE_CARD if drive_available else ReturnMode.LOCAL_PATH_DIAGNOSTIC
    return ReturnMode.LOCAL_PATH_DIAGNOSTIC


def _logical_role(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "final_image"
    if suffix in {".mp4", ".mov", ".webm"}:
        return "final_video"
    if suffix == ".zip":
        return "package_zip"
    if path.name.lower().endswith("manifest.json"):
        return "manifest"
    return "artifact"


def _mime_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def package_and_upload(
    job: RenderJob,
    files: Iterable[Path],
    qa_report: Any,
    asset_store: Any,
    *,
    chat_attachment_available: bool = False,
    parent_id: str | None = None,
) -> ReturnManifest:
    destination = parent_id or str(getattr(asset_store, "artifact_parent_id", "")).strip()
    if not destination:
        raise ValueError("artifact Drive parent id is required")

    if isinstance(qa_report, dict):
        qa_summary = dict(qa_report)
    elif hasattr(qa_report, "to_dict"):
        qa_summary = dict(qa_report.to_dict())
    else:
        qa_summary = {"status": str(getattr(qa_report, "terminal_status", "UNKNOWN"))}

    artifacts: list[ReturnArtifact] = []
    for raw_path in files:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        role = _logical_role(path)
        stored = asset_store.put(path, role, destination, mime_type=_mime_type(path))
        if not stored.drive_file_id or len(stored.sha256) != 64:
            raise ValueError("Drive artifact metadata is incomplete")
        artifacts.append(
            ReturnArtifact(
                drive_file_id=stored.drive_file_id,
                logical_role=stored.logical_role,
                mime_type=stored.mime_type,
                byte_size=stored.byte_size,
                sha256=stored.sha256,
                source_name=stored.source_name,
                parent_id=stored.parent_id,
                qa_summary=dict(qa_summary),
            )
        )

    if not artifacts:
        raise ValueError("at least one artifact is required")

    return ReturnManifest(
        job_id=job.job_id,
        attempt_id=job.attempt_id,
        project_id=job.project_id,
        return_mode=select_return_mode(
            job.return_mode,
            chat_attachment_available=chat_attachment_available,
            drive_available=True,
        ),
        artifacts=tuple(artifacts),
    )
