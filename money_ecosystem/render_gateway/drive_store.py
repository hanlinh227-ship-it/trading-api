from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Callable

from .asset_store import AssetIntegrityError, StoredArtifact, sha256_file
from .contract import AssetRef


Downloader = Callable[[str], bytes]
Uploader = Callable[[Path, str, str, str], dict[str, Any]]


class DriveAssetStore:
    """Drive-backed binary store with integrity checks.

    Production may inject a pre-authenticated Google Drive service or explicit
    downloader/uploader callables. Credentials are deliberately outside the
    render job payload.
    """

    def __init__(
        self,
        *,
        drive_service: Any | None = None,
        downloader: Downloader | None = None,
        uploader: Uploader | None = None,
        artifact_parent_id: str | None = None,
    ) -> None:
        self._drive_service = drive_service
        self._downloader = downloader
        self._uploader = uploader
        self.artifact_parent_id = str(artifact_parent_id or "").strip()
        if drive_service is None and (downloader is None or uploader is None):
            raise ValueError("DriveAssetStore requires drive_service or downloader+uploader")

    def _download_bytes(self, file_id: str) -> bytes:
        if self._downloader is not None:
            return self._downloader(file_id)
        try:
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError as exc:  # pragma: no cover - production dependency gate
            raise RuntimeError("google-api-python-client is required for Drive downloads") from exc

        request = self._drive_service.files().get_media(fileId=file_id)
        buffer = BytesIO()
        transfer = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = transfer.next_chunk()
        return buffer.getvalue()

    def fetch(self, asset: AssetRef, dest: Path) -> Path:
        target = Path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self._download_bytes(asset.drive_file_id)
        target.write_bytes(payload)

        actual_size = target.stat().st_size
        if actual_size != asset.byte_size:
            target.unlink(missing_ok=True)
            raise AssetIntegrityError(
                f"Drive byte-size mismatch for {asset.asset_id}: expected {asset.byte_size}, got {actual_size}"
            )

        actual_sha = sha256_file(target)
        if actual_sha.lower() != asset.sha256.lower():
            target.unlink(missing_ok=True)
            raise AssetIntegrityError(
                f"Drive SHA256 mismatch for {asset.asset_id}: expected {asset.sha256}, got {actual_sha}"
            )
        return target

    def _upload(self, path: Path, logical_role: str, parent_id: str, mime_type: str) -> dict[str, Any]:
        if self._uploader is not None:
            return self._uploader(path, logical_role, parent_id, mime_type)
        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:  # pragma: no cover - production dependency gate
            raise RuntimeError("google-api-python-client is required for Drive uploads") from exc

        body = {"name": path.name, "parents": [parent_id], "description": f"logical_role={logical_role}"}
        media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
        return (
            self._drive_service.files()
            .create(body=body, media_body=media, fields="id,mimeType,size")
            .execute()
        )

    def put(
        self,
        path: Path,
        logical_role: str,
        parent_id: str,
        *,
        mime_type: str,
    ) -> StoredArtifact:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        before_sha = sha256_file(source)
        before_size = source.stat().st_size
        metadata = self._upload(source, logical_role, parent_id, mime_type)
        drive_file_id = str(metadata.get("id", "")).strip()
        if not drive_file_id:
            raise RuntimeError("Drive upload did not return file id")
        after_sha = sha256_file(source)
        if after_sha != before_sha or source.stat().st_size != before_size:
            raise AssetIntegrityError("local artifact changed during Drive upload")
        remote_size = metadata.get("size")
        if remote_size not in (None, "") and int(remote_size) != before_size:
            raise AssetIntegrityError(
                f"Drive upload size mismatch: local {before_size}, remote {remote_size}"
            )
        return StoredArtifact(
            drive_file_id=drive_file_id,
            logical_role=str(logical_role),
            mime_type=str(metadata.get("mimeType") or mime_type),
            byte_size=before_size,
            sha256=before_sha,
            source_name=source.name,
            parent_id=str(parent_id),
        )
