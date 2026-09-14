from pathlib import Path

from PIL import Image

from money_ecosystem.render_gateway.control_plane import attempt_path, result_path, signed_path
from money_ecosystem.render_gateway.contract import QualityTier
from money_ecosystem.render_gateway.qa import QAStatus, evaluate_scene
from money_ecosystem.render_gateway.scene_contract import ExactSceneContract


def _scene():
    return ExactSceneContract(
        visible_entity_count=2,
        required_entities=("character.max", "vehicle.bus"),
        forbidden_entities=("character.dad_max",),
        background_id="background.bg1",
        camera="front three-quarter",
        framing="medium wide",
        actions={"character.max": "wave", "vehicle.bus": "approach slowly"},
        spatial_placement={"character.max": "left sidewalk", "vehicle.bus": "right road"},
        wardrobe_state={"character.max": "yellow shirt denim shorts"},
        object_state={"vehicle.bus": "yellow-blue-cream fixed geometry"},
        style_lock="3D preschool",
        lighting_lock="soft daylight",
        no_text_logo_watermark=True,
        entity_reference_bindings={"character.max": ("ref.max",), "vehicle.bus": ("ref.bus",)},
        composition_anchor_ids=("anchor.scene1",),
    )


def _evidence(background_status="PASS"):
    return {
        "expected_dimensions": (160, 90),
        "structural": {
            "entity_count": {"status": "PASS", "score": 1.0, "evidence_source": "detector", "reason": "2 visible"},
            "no_extra_subjects": {"status": "PASS", "score": 1.0, "evidence_source": "detector", "reason": "none extra"},
        },
        "identity": {
            "character.max": {"status": "PASS", "score": 0.95, "evidence_source": "identity_checker", "reason": "match"},
            "vehicle.bus": {"status": "PASS", "score": 0.96, "evidence_source": "object_checker", "reason": "match"},
        },
        "semantic": {
            "background": {"status": background_status, "score": 0.95 if background_status == "PASS" else 0.0, "evidence_source": "semantic_checker", "reason": "BG1" if background_status == "PASS" else "white background"},
            "actions": {"status": "PASS", "score": 0.9, "evidence_source": "semantic_checker", "reason": "correct"},
            "camera": {"status": "PASS", "score": 0.9, "evidence_source": "semantic_checker", "reason": "correct"},
        },
        "finish": {"quality": {"status": "PASS", "score": 0.9, "evidence_source": "finish_checker", "reason": "clean"}},
    }


def test_control_plane_paths_are_attempt_scoped():
    assert attempt_path("max-bus", "job-1", "a1").endswith("/request.json")
    assert signed_path("max-bus", "job-1", "a1").endswith("/signed.json")
    assert result_path("max-bus", "job-1", "a1").endswith("/result.json")


def test_good_composition_passes_flow_grade_qa(tmp_path: Path):
    image = tmp_path / "good.png"
    Image.new("RGB", (160, 90), (120, 180, 220)).save(image)
    report = evaluate_scene(_scene(), image, _evidence(), quality_tier=QualityTier.FLOW_GRADE)
    assert report.status is QAStatus.VERIFIED


def test_bad_composition_is_rejected_for_retry(tmp_path: Path):
    image = tmp_path / "bad.png"
    Image.new("RGB", (160, 90), (255, 255, 255)).save(image)
    report = evaluate_scene(_scene(), image, _evidence(background_status="FAIL"), quality_tier=QualityTier.FLOW_GRADE)
    assert report.status is QAStatus.RETRY
