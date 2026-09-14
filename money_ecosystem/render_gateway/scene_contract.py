from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .master_lock import MasterLockRegistry


@dataclass(frozen=True)
class ExactSceneContract:
    visible_entity_count: int
    required_entities: tuple[str, ...]
    forbidden_entities: tuple[str, ...]
    background_id: str
    camera: str
    framing: str
    actions: Mapping[str, str]
    spatial_placement: Mapping[str, str]
    wardrobe_state: Mapping[str, str]
    object_state: Mapping[str, str]
    style_lock: str
    lighting_lock: str
    no_text_logo_watermark: bool
    entity_reference_bindings: Mapping[str, tuple[str, ...]]
    composition_anchor_ids: tuple[str, ...]


def validate_scene_against_masters(scene: ExactSceneContract, registry: MasterLockRegistry) -> None:
    if scene.visible_entity_count <= 0:
        raise ValueError("visible_entity_count must be positive")
    if scene.visible_entity_count != len(scene.required_entities):
        raise ValueError("visible_entity_count must equal exact required entity count")
    if len(set(scene.required_entities)) != len(scene.required_entities):
        raise ValueError("required_entities cannot contain duplicates")
    if set(scene.required_entities) & set(scene.forbidden_entities):
        raise ValueError("entity cannot be both required and forbidden")
    if not scene.background_id.strip():
        raise ValueError("background_id is required")
    if not registry.contains(scene.background_id):
        raise ValueError(f"unknown background master: {scene.background_id}")
    if registry.get(scene.background_id).kind != "background":
        raise ValueError("background_id must reference a background master")
    if not scene.camera.strip() or not scene.framing.strip():
        raise ValueError("camera and framing are required")
    if not scene.style_lock.strip() or not scene.lighting_lock.strip():
        raise ValueError("style_lock and lighting_lock are required")
    if not scene.no_text_logo_watermark:
        raise ValueError("scene must explicitly prohibit text/logo/watermark")
    if len(scene.required_entities) > 1 and not scene.composition_anchor_ids:
        raise ValueError("complex scene requires at least one composition anchor")

    for entity_id in scene.required_entities:
        if not registry.contains(entity_id):
            raise ValueError(f"unknown required master entity: {entity_id}")
        master = registry.get(entity_id)
        bindings = tuple(scene.entity_reference_bindings.get(entity_id, ()))
        if not bindings:
            raise ValueError(f"missing reference binding for {entity_id}")
        if any(binding not in master.reference_ids for binding in bindings):
            raise ValueError(f"invalid reference binding for {entity_id}")
        if entity_id not in scene.actions:
            raise ValueError(f"missing action for {entity_id}")
        if entity_id not in scene.spatial_placement:
            raise ValueError(f"missing spatial placement for {entity_id}")

        if master.kind == "character" and entity_id not in scene.wardrobe_state:
            raise ValueError(f"missing wardrobe state for {entity_id}")
        if master.kind in {"vehicle", "object"} and entity_id not in scene.object_state:
            raise ValueError(f"missing object state for {entity_id}")

    bound_refs: dict[str, str] = {}
    for entity_id in scene.required_entities:
        for ref in scene.entity_reference_bindings.get(entity_id, ()):
            previous = bound_refs.get(ref)
            if previous is not None and previous != entity_id:
                raise ValueError(
                    f"ambiguous reference binding: {ref} is shared by {previous} and {entity_id}"
                )
            bound_refs[ref] = entity_id
