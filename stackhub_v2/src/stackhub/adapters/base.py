from __future__ import annotations

from typing import Protocol
from stackhub.models import Opportunity


class OpportunitySource(Protocol):
    async def fetch_open(self, limit: int = 50) -> list[Opportunity]: ...
