from pathlib import Path

from PIL import Image

from money_ecosystem.render_gateway.contract import QualityTier
from money_ecosystem.render_gateway.qa import QAStatus, evaluate_scene
from money_ecosystem.render_gateway.scene_contract import ExactSceneContract


def _scene():
    return ExactSceneContract(
        visible_entity_count=3,
        required_entities=("character.max", "character.dad_max", "vehicle.yellow_bus"),
        forbidden_entities=(),
        background_id="background.bg01_bus_stop",
        camera="low three-quarter front",
        framing="medium wide",
        actions={"character.max": "wave", "character.dad_max": "drive", "vehicle.yellow_bus": "approach"},
        spatial_placement={"character.max": "sidewalk", "character.dad_max": "driver seat", "vehicle.yellow_bus": "road"},
        wardrobe_state={"character.max": "yellow T-shirt", "character.dad_max": "navy suit"},
        object_state={"vehicle.yellow_bus": "fixed geometry"},
        style_lock="3D preschool",
        lighting_lock="daylight",
        no_text_logo_watermark=True,
        entity_reference_bindings={"character.max": ("max",), "character.dad_max": ("dad",), "vehicle.yellow_bus": ("bus",)},
        composition_anchor_ids=("layout",),
    )


def _image(tmp_path: Path):
    path = tmp_path / "scene.png"
    Image.new("RGB", (1024, 576), "white").save(path)
    return path


def _pass(source="vision_checker"):
    return {"status": "PASS", "score": 0.99, "evidence_source": source, "reason": "verified"}


def test_bad_composition_cannot_pass_flow_grade(tmp_path: Path):
    evidence = {
        "expected_dimensions": (1024, 576),
        "structural": {"entity_count": _pass()},
        "identity": {"character.max": _pass(), "character.dad_max": _pass(), "vehicle.yellow_bus": _pass()},
        "semantic": {
            "background": {"status": "FAIL", "score": 0.0, "evidence_source": "vision_checker", "reason": "white background, BG1 absent"},
            "actions": _pass(),
            "camera": _pass(),
        },
        "finish": {"quality": _pass("image_metrics")},
    }
    report = evaluate_scene(_scene(), _image(tmp_path), evidence, quality_tier=QualityTier.FLOW_GRADE)
    assert report.status in {QAStatus.RETRY, QAStatus.REJECTED}
    assert report.status is not QAStatus.VERIFIED


def test_unverified_mandatory_semantics_require_human_review(tmp_path: Path):
    evidence = {
        "expected_dimensions": (1024, 576),
        "structural": {"entity_count": _pass()},
        "identity": {"character.max": _pass(), "character.dad_max": _pass(), "vehicle.yellow_bus": _pass()},
        "semantic": {
            "background": {"status": "UNVERIFIED", "score": None, "evidence_source": "none", "reason": "no semantic checker"},
            "actions": _pass(),
            "camera": _pass(),
        },
        "finish": {"quality": _pass("image_metrics")},
    }
    report = evaluate_scene(_scene(), _image(tmp_path), evidence, quality_tier=QualityTier.FLOW_GRADE)
    assert report.status is QAStatus.HUMAN_REVIEW


def test_all_mandatory_evidence_passes_as_verified(tmp_path: Path):
    evidence = {
        "expected_dimensions": (1024, 576),
        "structural": {"entity_count": _pass(), "no_extra_subjects": _pass()},
        "identity": {"character.max": _pass(), "character.dad_max": _pass(), "vehicle.yellow_bus": _pass()},
        "semantic": {"background": _pass(), "actions": _pass(), "camera": _pass()},
        "finish": {"quality": _pass("image_metrics")},
    }
    report = evaluate_scene(_scene(), _image(tmp_path), evidence, quality_tier=QualityTier.FLOW_GRADE)
    assert report.status is QAStatus.VERIFIED
