import pytest

from money_ecosystem.render_gateway.master_lock import MasterEntity, MasterLockRegistry


def test_registry_keeps_distinct_character_identity_records():
    registry = MasterLockRegistry()
    registry.add(MasterEntity(
        entity_id="character.max",
        kind="character",
        reference_ids=("max-front", "max-side"),
        silhouette_traits=("small red monkey child",),
        palette=("red", "yellow", "denim-blue"),
        wardrobe=("yellow T-shirt", "denim shorts", "blue-white shoes"),
        forbidden_mutations=("adult suit", "duplicate tail"),
        role_constraints=("child passenger",),
    ))
    registry.add(MasterEntity(
        entity_id="character.dad_max",
        kind="character",
        reference_ids=("dad-front",),
        silhouette_traits=("adult red monkey",),
        palette=("red", "navy", "white", "black"),
        wardrobe=("navy suit", "white shirt", "black tie"),
        forbidden_mutations=("yellow child T-shirt",),
        role_constraints=("driver",),
    ))
    assert registry.get("character.max").reference_ids != registry.get("character.dad_max").reference_ids


def test_duplicate_entity_id_is_rejected():
    entity = MasterEntity("character.max", "character", ("max",), (), (), (), (), ())
    registry = MasterLockRegistry([entity])
    with pytest.raises(ValueError, match="duplicate"):
        registry.add(entity)
