from pathlib import Path

import pytest

from money_ecosystem.render_gateway.video import ContinuityState, MotionContract, require_flow_grade_video_ready


def _continuity():
    return ContinuityState(
        identity={"character.max": "locked"},
        wardrobe={"character.max": "yellow-shirt-denim-shorts"},
        object_geometry={"bus": "yellow-blue-cream-fixed"},
        environment="BG1",
        camera_direction="front three-quarter",
        lighting_direction="soft daylight",
        start_position={"character.max": "sidewalk"},
        end_position={"character.max": "sidewalk-wave"},
        previous_shot_anchors=("bus-shape",),
    )


def test_flow_grade_video_requires_approved_keyframe():
    motion = MotionContract(
        approved_keyframe=False,
        start_frame_id="start",
        end_frame_id="end",
        action="Max waves while bus approaches slowly",
        duration_seconds=6.0,
        continuity=_continuity(),
    )
    with pytest.raises(ValueError, match="approved keyframe"):
        require_flow_grade_video_ready(motion)


def test_motion_contract_preserves_continuity_state():
    motion = MotionContract(True, "start", "end", "wave", 6.0, _continuity())
    require_flow_grade_video_ready(motion)
    assert motion.continuity.environment == "BG1"
    assert motion.continuity.object_geometry["bus"] == "yellow-blue-cream-fixed"
