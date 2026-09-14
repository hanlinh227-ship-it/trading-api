import pytest

from money_ecosystem.render_gateway.master_lock import MasterEntity, MasterLockRegistry
from money_ecosystem.render_gateway.scene_contract import ExactSceneContract, validate_scene_against_masters


def _registry():
    return MasterLockRegistry([
        MasterEntity("character.max", "character", ("max-ref",), (), (), ("yellow T-shirt",), ("adult suit",), ("child",)),
        MasterEntity("character.dad_max", "character", ("dad-ref",), (), (), ("navy suit", "white shirt", "black tie"), ("yellow T-shirt",), ("driver",)),
        MasterEntity("vehicle.yellow_bus", "vehicle", ("bus-ref",), (), ("yellow", "light-blue", "cream"), (), ("red bus",), ("school bus",)),
        MasterEntity("background.bg01_bus_stop", "background", ("bg1-ref",), (), ("pastel",), (), (), ("bus stop",)),
    ])


def _scene(bindings=None, anchor_ids=("layout-1",)):
    return ExactSceneContract(
        visible_entity_count=3,
        required_entities=("character.max", "character.dad_max", "vehicle.yellow_bus"),
        forbidden_entities=(),
        background_id="background.bg01_bus_stop",
        camera="low three-quarter front",
        framing="medium wide",
        actions={"character.max": "wave", "character.dad_max": "drive", "vehicle.yellow_bus": "approach"},
        spatial_placement={"character.max": "sidewalk left", "character.dad_max": "driver seat", "vehicle.yellow_bus": "road right"},
        wardrobe_state={"character.max": "yellow T-shirt", "character.dad_max": "navy suit"},
        object_state={"vehicle.yellow_bus": "yellow/light-blue/cream fixed geometry"},
        style_lock="3D preschool soft rounded pastel",
        lighting_lock="clean child-friendly daylight",
        no_text_logo_watermark=True,
        entity_reference_bindings=bindings or {"character.max": ("max-ref",), "character.dad_max": ("dad-ref",), "vehicle.yellow_bus": ("bus-ref",)},
        composition_anchor_ids=anchor_ids,
    )


def test_exact_scene_with_distinct_bindings_passes():
    validate_scene_against_masters(_scene(), _registry())


def test_two_characters_cannot_share_wrong_reference_binding():
    bindings = {"character.max": ("max-ref",), "character.dad_max": ("max-ref",), "vehicle.yellow_bus": ("bus-ref",)}
    with pytest.raises(ValueError, match="reference binding"):
        validate_scene_against_masters(_scene(bindings), _registry())


def test_complex_scene_requires_composition_anchor():
    with pytest.raises(ValueError, match="composition anchor"):
        validate_scene_against_masters(_scene(anchor_ids=()), _registry())
