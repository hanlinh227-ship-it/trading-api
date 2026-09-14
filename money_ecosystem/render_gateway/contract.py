from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from types import MappingProxyType
from typing import Any, Mapping, Tuple


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_RESOLUTION_RE = re.compile(r"^[1-9][0-9]*x[1-9][0-9]*$")
_ALLOWED_JOB_TYPES = {"IMAGE_RENDER", "VIDEO_RENDER", "FINAL_RENDER"}


class QualityTier(str, Enum):
    FLOW_GRADE = "FLOW_GRADE"
    HIGH = "HIGH"
    DRAFT_LOCAL = "DRAFT_LOCAL"


class CostPolicy(str, Enum):
    USE_EXISTING_ENTITLEMENTS = "USE_EXISTING_ENTITLEMENTS"
    ASK_BEFORE_PAID = "ASK_BEFORE_PAID"
    LOCAL_ONLY = "LOCAL_ONLY"


class ReturnMode(str, Enum):
    CHAT_ATTACHMENT_PREFERRED = "CHAT_ATTACHMENT_PREFERRED"
    DRIVE_CARD = "DRIVE_CARD"
    LOCAL_PATH_DIAGNOSTIC = "LOCAL_PATH_DIAGNOSTIC"


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


@dataclass(frozen=True)
class AssetRef:
    asset_id: str
    drive_file_id: str
    logical_role: str
    mime_type: str
    byte_size: int
    sha256: str
    source: str
    rights_note: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AssetRef":
        sha = _required_text(payload, "sha256").lower()
        if not _SHA256_RE.fullmatch(sha):
            raise ValueError("asset sha256 must be exactly 64 hexadecimal characters")
        size = int(payload.get("byte_size", -1))
        if size < 0:
            raise ValueError("asset byte_size must be >= 0")
        return cls(
            asset_id=_required_text(payload, "asset_id"),
            drive_file_id=_required_text(payload, "drive_file_id"),
            logical_role=_required_text(payload, "logical_role"),
            mime_type=_required_text(payload, "mime_type"),
            byte_size=size,
            sha256=sha,
            source=_required_text(payload, "source"),
            rights_note=str(payload.get("rights_note", "")).strip(),
        )


@dataclass(frozen=True)
class SceneContract:
    required_entities: Tuple[str, ...]
    data: Mapping[str, Any]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SceneContract":
        if not isinstance(payload, Mapping) or not payload:
            raise ValueError("scene_contract is required")
        required = payload.get("required_entities", ())
        if not isinstance(required, (list, tuple)) or not all(isinstance(x, str) and x.strip() for x in required):
            raise ValueError("scene_contract.required_entities must be a list of non-empty strings")
        frozen = MappingProxyType(dict(payload))
        return cls(tuple(x.strip() for x in required), frozen)


@dataclass(frozen=True)
class RenderJob:
    job_id: str
    attempt_id: str
    project_id: str
    job_type: str
    quality_tier: QualityTier
    cost_policy: CostPolicy
    aspect_ratio: str
    output_resolution: str
    prompt: str
    negative_constraints: Tuple[str, ...]
    assets: Tuple[AssetRef, ...]
    scene_contract: SceneContract
    max_attempts: int
    return_mode: ReturnMode

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RenderJob":
        if not isinstance(payload, Mapping):
            raise ValueError("render job payload must be an object")

        job_type = _required_text(payload, "job_type")
        if job_type not in _ALLOWED_JOB_TYPES:
            raise ValueError(f"job_type is unsupported: {job_type}")

        try:
            quality_tier = QualityTier(_required_text(payload, "quality_tier"))
        except ValueError as exc:
            raise ValueError("quality_tier is invalid") from exc
        try:
            cost_policy = CostPolicy(_required_text(payload, "cost_policy"))
        except ValueError as exc:
            raise ValueError("cost_policy is invalid") from exc
        try:
            return_mode = ReturnMode(_required_text(payload, "return_mode"))
        except ValueError as exc:
            raise ValueError("return_mode is invalid") from exc

        resolution = _required_text(payload, "output_resolution")
        if not _RESOLUTION_RE.fullmatch(resolution):
            raise ValueError("output_resolution must use WIDTHxHEIGHT")

        prompt = _required_text(payload, "prompt")
        aspect_ratio = _required_text(payload, "aspect_ratio")

        attempts = int(payload.get("max_attempts", 3))
        if attempts < 1 or attempts > 5:
            raise ValueError("max_attempts must be 1..5")

        raw_assets = payload.get("assets", ())
        if not isinstance(raw_assets, (list, tuple)):
            raise ValueError("assets must be a list")
        assets = tuple(AssetRef.from_dict(item) for item in raw_assets)

        negatives = payload.get("negative_constraints", ())
        if not isinstance(negatives, (list, tuple)) or not all(isinstance(x, str) for x in negatives):
            raise ValueError("negative_constraints must be a list of strings")

        scene_contract = SceneContract.from_dict(payload.get("scene_contract", {}))

        return cls(
            job_id=_required_text(payload, "job_id"),
            attempt_id=_required_text(payload, "attempt_id"),
            project_id=_required_text(payload, "project_id"),
            job_type=job_type,
            quality_tier=quality_tier,
            cost_policy=cost_policy,
            aspect_ratio=aspect_ratio,
            output_resolution=resolution,
            prompt=prompt,
            negative_constraints=tuple(x.strip() for x in negatives),
            assets=assets,
            scene_contract=scene_contract,
            max_attempts=attempts,
            return_mode=return_mode,
        )
