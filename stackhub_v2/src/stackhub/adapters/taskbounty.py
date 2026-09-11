from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError, Field

from stackhub.config import SourceConfig
from stackhub.models import Opportunity, Reward


class TaskBountyProtocolError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        retry_after_seconds: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.retry_after_seconds = retry_after_seconds


class _FeedItem(BaseModel):
    id: str = Field(min_length=1)
    url: str | None = None
    title: str | None = None
    content_text: str | None = None


class _Feed(BaseModel):
    version: str | None = None
    items: list[_FeedItem]


class _Task(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    bounty_cents: int = Field(ge=0)
    github_repo_url: str | None = None
    github_issue_url: str = Field(min_length=1)
    created_at: str | None = None
    complexity_tag: str | None = None
    language: str | None = None


_EFFORT = {"small": 30, "medium": 60, "large": 120}


def _retry_after_seconds(response: httpx.Response) -> int | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return max(value, 0)


def _raise_http_error(exc: httpx.HTTPStatusError) -> None:
    code = exc.response.status_code
    if code in (401, 403):
        error = "auth_invalid"
    elif code == 429:
        error = "rate_limited"
    else:
        error = f"http_{code}"
    raise TaskBountyProtocolError(
        str(exc),
        status_code=code,
        error_code=error,
        retry_after_seconds=_retry_after_seconds(exc.response) if code == 429 else None,
    ) from exc


def _parse_task_detail(payload: object) -> _Task:
    if isinstance(payload, dict):
        if isinstance(payload.get("task"), dict):
            payload = payload["task"]
        elif isinstance(payload.get("tasks"), list) and len(payload["tasks"]) == 1:
            payload = payload["tasks"][0]
    return _Task.model_validate(payload)


class TaskBountyAdapter:
    """Strictly read-only TaskBounty adapter using the public JSON Feed discovery surface."""

    def __init__(self, config: SourceConfig, *, client: httpx.AsyncClient | None = None, api_key: str | None = None):
        if not config.read_only:
            raise ValueError("TaskBountyAdapter requires read_only source configuration")
        self.config = config
        self.api_key = api_key.strip() if api_key else None
        self._owned_client = client is None
        self.client = client or httpx.AsyncClient(timeout=config.request_timeout_seconds)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/feed+json, application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def fetch_open(self, limit: int = 50) -> list[Opportunity]:
        limit = max(1, min(int(limit), 100))
        headers = self._headers()
        try:
            response = await self.client.get(
                f"{self.config.base_url.rstrip('/')}/bounties.json",
                params={"limit": limit},
                headers=headers,
            )
            response.raise_for_status()
            feed = _Feed.model_validate(response.json())
        except httpx.HTTPStatusError as exc:
            _raise_http_error(exc)
        except ValidationError as exc:
            raise TaskBountyProtocolError(str(exc), error_code="validation_error") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise TaskBountyProtocolError(str(exc), error_code="protocol_error") from exc

        items: list[Opportunity] = []
        for feed_item in feed.items:
            try:
                detail = await self.client.get(
                    f"{self.config.base_url.rstrip('/')}/tasks/{quote(feed_item.id, safe='')}",
                    headers=headers,
                )
                detail.raise_for_status()
                task = _parse_task_detail(detail.json())
            except httpx.HTTPStatusError as exc:
                _raise_http_error(exc)
            except ValidationError as exc:
                raise TaskBountyProtocolError(str(exc), error_code="validation_error") from exc
            except (httpx.HTTPError, ValueError) as exc:
                raise TaskBountyProtocolError(str(exc), error_code="protocol_error") from exc

            solver_amount = (
                Decimal(task.bounty_cents) * Decimal("0.80") / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
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
