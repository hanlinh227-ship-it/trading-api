from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MasterEntity:
    entity_id: str
    kind: str
    reference_ids: tuple[str, ...]
    silhouette_traits: tuple[str, ...]
    palette: tuple[str, ...]
    wardrobe: tuple[str, ...]
    forbidden_mutations: tuple[str, ...]
    role_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.entity_id.strip():
            raise ValueError("entity_id is required")
        if not self.kind.strip():
            raise ValueError("kind is required")
        if not self.reference_ids:
            raise ValueError(f"master entity {self.entity_id} requires at least one reference")
        if any(not str(ref).strip() for ref in self.reference_ids):
            raise ValueError("reference_ids cannot contain empty values")


class MasterLockRegistry:
    def __init__(self, entities: Iterable[MasterEntity] = ()) -> None:
        self._entities: dict[str, MasterEntity] = {}
        for entity in entities:
            self.add(entity)

    def add(self, entity: MasterEntity) -> None:
        if entity.entity_id in self._entities:
            raise ValueError(f"duplicate master entity: {entity.entity_id}")
        self._entities[entity.entity_id] = entity

    def get(self, entity_id: str) -> MasterEntity:
        try:
            return self._entities[entity_id]
        except KeyError as exc:
            raise KeyError(f"unknown master entity: {entity_id}") from exc

    def contains(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def all(self) -> tuple[MasterEntity, ...]:
        return tuple(self._entities.values())
