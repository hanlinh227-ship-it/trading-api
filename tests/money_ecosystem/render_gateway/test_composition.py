import pytest

from money_ecosystem.render_gateway.composition import CompositionBlueprint, Region


def test_blueprint_requires_anchor_and_non_overlapping_identity_regions():
    bp = CompositionBlueprint(
        anchor_id="layout-1",
        anchor_kind="layout_sketch",
        regions=(
            Region("character.max", 0.02, 0.25, 0.36, 0.95),
            Region("character.dad_max", 0.58, 0.18, 0.92, 0.78),
        ),
    )
    bp.validate()
    assert bp.region_for("character.max").x1 < bp.region_for("character.dad_max").x0


def test_blueprint_rejects_missing_anchor():
    with pytest.raises(ValueError, match="anchor"):
        CompositionBlueprint("", "layout_sketch", (Region("character.max", 0, 0, 1, 1),)).validate()


def test_region_coordinates_are_normalized():
    with pytest.raises(ValueError, match="normalized"):
        CompositionBlueprint("layout", "layout_sketch", (Region("character.max", -0.1, 0, 1, 1),)).validate()
