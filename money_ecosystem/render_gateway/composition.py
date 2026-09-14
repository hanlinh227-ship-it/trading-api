from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    entity_id: str
    x0: float
    y0: float
    x1: float
    y1: float

    def validate(self) -> None:
        values = (self.x0, self.y0, self.x1, self.y1)
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError("region coordinates must be normalized to 0..1")
        if not self.entity_id.strip():
            raise ValueError("region entity_id is required")
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("region bounds must have positive area")


@dataclass(frozen=True)
class CompositionBlueprint:
    anchor_id: str
    anchor_kind: str
    regions: tuple[Region, ...]

    def validate(self) -> None:
        if not self.anchor_id.strip():
            raise ValueError("composition anchor is required")
        if self.anchor_kind not in {
            "layout_sketch",
            "depth_map",
            "pose_control",
            "background_master",
            "provider_native_reference",
        }:
            raise ValueError("unsupported composition anchor kind")
        if not self.regions:
            raise ValueError("composition blueprint requires at least one region")
        seen: set[str] = set()
        for region in self.regions:
            region.validate()
            if region.entity_id in seen:
                raise ValueError(f"duplicate composition region: {region.entity_id}")
            seen.add(region.entity_id)

    def region_for(self, entity_id: str) -> Region:
        self.validate()
        for region in self.regions:
            if region.entity_id == entity_id:
                return region
        raise KeyError(f"missing region for entity: {entity_id}")
