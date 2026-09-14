from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Protocol

from .contract import AssetRef


_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


class AssetIntegrityError(ValueError):
    pass


def _safe_component(value: str) -> str:
    cleaned = _SAFE_COMPONENT.sub("_", str(value).strip()).strip("._")
    if not cleaned:
        raise ValueError("empty path component")
    return cleaned


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_logical_path(project_id: str, job_id: str, role: str) -> str:
    return (
        "CuriousBeyond_RenderGateway/projects/"
        f"{_safe_component(project_id)}/jobs/{_safe_component(job_id)}/{_safe_component(role)}"
    )


@dataclass(frozen=True)
class StoredArtifact:
    drive_file_id: str
    logical_role: str
    mime_type: str
    byte_size: int
    sha256: str
    source_name: str
    parent_id: str


class AssetStore(Protocol):
    def fetch(self, asset: AssetRef, dest: Path) -> Path: ...

    def put(
        self,
        path: Path,
        logical_role: str,
        parent_id: str,
        *,
        mime_type: str,
    ) -> StoredArtifact: ...
