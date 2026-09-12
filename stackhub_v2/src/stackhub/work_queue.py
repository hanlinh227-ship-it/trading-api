from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Awaitable, Callable


class FallbackLane(StrEnum):
    SERVICE_API = "service_api"
    DIGITAL_ASSET = "digital_asset"
    SOURCE_DISCOVERY = "source_discovery"
    PRODUCT_IMPROVEMENT = "product_improvement"


FallbackHandler = Callable[[], Awaitable[dict[str, object]]]


@dataclass(order=True)
class FallbackWorkItem:
    sort_key: tuple[int, int] = field(init=False, repr=False)
    priority: int
    sequence: int
    name: str = field(compare=False)
    lane: FallbackLane = field(compare=False)
    handler: FallbackHandler = field(compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sort_key", (-self.priority, self.sequence))


class FallbackWorkQueue:
    def __init__(self):
        self._heap: list[FallbackWorkItem] = []
        self._sequence = 0

    def put(
        self,
        name: str,
        lane: FallbackLane,
        priority: int,
        handler: FallbackHandler,
    ) -> None:
        self._sequence += 1
        heapq.heappush(
            self._heap,
            FallbackWorkItem(priority, self._sequence, name, lane, handler),
        )

    def pop(self) -> FallbackWorkItem | None:
        if not self._heap:
            return None
        return heapq.heappop(self._heap)

    def __len__(self) -> int:
        return len(self._heap)
