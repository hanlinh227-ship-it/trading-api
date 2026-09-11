from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import httpx
from pydantic import BaseModel, ValidationError, Field

from stackhub.config import SourceConfig
from stackhub.models import Opportunity, Reward


class TaskBountyProtocolError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, error_code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class _Task(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    bounty_cents: int = Field(ge=0)
    github_repo_url: str | None = None
    github_issue_url: str = Field(min_length=1)
    created_at: str | None = None
    complexity_tag: str | None = None
    language: str | None = None


class _Envelope(BaseModel):
    tasks: list[_Task]


_EFFORT = {"small": 30, "medium": 60, "large": 120}


class TaskBountyAdapter:
    """Strictly read-only adapter for TaskBounty's public task listing endpoint."""

    def __init__(self, config: SourceConfig, *, client: httpx.AsyncClient | None = None, api_key: str | None = None):
        if not config.read_only:
            raise ValueError("TaskBountyAdapter requires read_only source configuration")
        self.config = config
        self._owned_client = client is None
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = client or httpx.AsyncClient(timeout=config.request_timeout_seconds, headers=headers)

    async def fetch_open(self, limit: int = 50) -> list[Opportunity]:
        limit = max(1, min(int(limit), 100))
        try:
            response = await self.client.get(f"{self.config.base_url.rstrip('/')}/tasks", params={"state": "open", "limit": limit})
            response.raise_for_status()
            envelope = _Envelope.model_validate(response.json())
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            error = "rate_limited" if code == 429 else f"http_{code}"
            raise TaskBountyProtocolError(str(exc), status_code=code, error_code=error) from exc
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise TaskBountyProtocolError(str(exc), error_code="protocol_error") from exc

        items: list[Opportunity] = []
        for task in envelope.tasks:
            solver_amount = (Decimal(task.bounty_cents) * Decimal("0.80") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lang = task.language or "unspecified"
            repo = task.github_repo_url or "unspecified"
            items.append(
                Opportunity(
                    id=task.id,
                    source="taskbounty",
                    url=task.github_issue_url,
                    category="coding",
                    reward=Reward(amount=solver_amount, asset="USD", network=None),
                    deadline=None,
                    requirements=(f"Fix the funded GitHub issue in {repo}", f"Language: {lang}"),
                    acceptance_criteria=("Pass TaskBounty end-to-end verification",),
                    competition_model="best_submission",
                    agent_allowed=True,
                    estimated_effort_minutes=_EFFORT.get((task.complexity_tag or "").lower(), 60),
                )
            )
        return items

    async def aclose(self) -> None:
        if self._owned_client:
            await self.client.aclose()
