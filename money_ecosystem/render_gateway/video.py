from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple


@dataclass(frozen=True)
class ContinuityState:
    identity: Mapping[str, str]
    wardrobe: Mapping[str, str]
    object_geometry: Mapping[str, str]
    environment: str
    camera_direction: str
    lighting_direction: str
    start_position: Mapping[str, str]
    end_position: Mapping[str, str]
    previous_shot_anchors: Tuple[str, ...]


@dataclass(frozen=True)
class MotionContract:
    approved_keyframe: bool
    start_frame_id: str
    end_frame_id: str
    action: str
    duration_seconds: float
    continuity: ContinuityState


def require_flow_grade_video_ready(motion: MotionContract) -> None:
    if not motion.approved_keyframe:
        raise ValueError("FLOW_GRADE video requires an approved keyframe")
    if not motion.start_frame_id.strip():
        raise ValueError("start frame is required")
    if not motion.end_frame_id.strip():
        raise ValueError("end frame is required")
    if not motion.action.strip():
        raise ValueError("motion action is required")
    if motion.duration_seconds <= 0 or motion.duration_seconds > 30:
        raise ValueError("duration_seconds must be within 0..30")
    if not motion.continuity.environment.strip():
        raise ValueError("continuity environment is required")
    if not motion.continuity.camera_direction.strip():
        raise ValueError("continuity camera direction is required")
    if not motion.continuity.lighting_direction.strip():
        raise ValueError("continuity lighting direction is required")
