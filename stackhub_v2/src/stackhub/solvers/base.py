from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..models import Opportunity


@dataclass(frozen=True)
class Artifact:
    reference: str
    kind: str = "generic"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SolverResult:
    artifact: Artifact
    evidence: dict[str, object] = field(default_factory=dict)


class Solver(Protocol):
    async def solve(
        self,
        opportunity: Opportunity,
        workspace_reference: str,
    ) -> SolverResult: ...
