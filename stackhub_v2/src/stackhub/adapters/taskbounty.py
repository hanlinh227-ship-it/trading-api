from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field, ValidationError

from stackhub.adapters.base import AdapterError, ClaimReceipt, SubmissionReceipt
from stackhub.config import SourceConfig
from stackhub.models import Opportunity, Reward


class TaskBountyProtocolError(AdapterError):
    pass


class TaskAccess(BaseModel):
    task_id: str = Field(min_length=1)
    clone_url: str = Field(min_length=1)
    expires_at: str | None = None


class SubmissionResult(BaseModel):
    id: str | None = None
    task_id: str = Field(min_length=1)
    status: str | None = None
    external_link: str = Field(min_length=1)


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
    elif code == 409:
        error = "conflict"
    elif code == 429:
        error = "rate_limited"
    else:
        error = f"http_{code}"
    raise TaskBountyProtocolError(
        f"TaskBounty request failed with HTTP {code}",
        status_code=code,
        error_code=error,
        retry_after_seconds=_retry_after_seconds(exc.response) if code == 429 else None,
    ) from exc


def _parse_task_list(payload: object) -> list[_Task]:
    if not isinstance(payload, dict):
        raise TaskBountyProtocolError(
            "TaskBounty response validation failed",
            error_code="validation_error",
        )

    rows = payload.get("data")
    if rows is None:
        rows = payload.get("tasks")
    if not isinstance(rows, list):
        raise TaskBountyProtocolError(
            "TaskBounty response validation failed",
            error_code="validation_error",
        )

    try:
        return [_Task.model_validate(item) for item in rows]
    except ValidationError as exc:
        raise TaskBountyProtocolError(
            "TaskBounty response validation failed",
            error_code="validation_error",
        ) from exc


class TaskBountyAdapter:
    """TaskBounty source adapter using the current REST task lifecycle."""

    source_name = "taskbounty"

    def __init__(
        self,
        config: SourceConfig,
        *,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
    ):
        self.config = config
        self.capabilities = config.capabilities
        self.api_key = api_key.strip() if api_key else None
        self._owned_client = client is None
        self.client = client or httpx.AsyncClient(timeout=config.request_timeout_seconds, follow_redirects=True)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _mutation_headers(self) -> dict[str, str]:
        if self.config.read_only:
            raise TaskBountyProtocolError(
                "TaskBounty mutation disabled",
                error_code="mutation_disabled",
            )
        if not self.api_key:
            raise TaskBountyProtocolError(
                "TaskBounty API key required",
                error_code="auth_required",
            )
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        return headers

    async def fetch_open(self, limit: int = 50) -> list[Opportunity]:
        limit = max(1, min(int(limit), 100))
        headers = self._headers()
        try:
            response = await self.client.get(
                f"{self.config.base_url.rstrip('/')}/tasks",
                params={"state": "open", "limit": limit},
                headers=headers,
            )
            response.raise_for_status()
            tasks = _parse_task_list(response.json())
        except httpx.HTTPStatusError as exc:
            _raise_http_error(exc)
        except TaskBountyProtocolError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise TaskBountyProtocolError(
                "TaskBounty protocol error",
                error_code="protocol_error",
            ) from exc

        items: list[Opportunity] = []
        for task in tasks:
            solver_amount = (
                Decimal(task.bounty_cents) * Decimal("0.80") / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lang = task.language or "unspecified"
            repo = task.github_repo_url or "unspecified"
            items.append(
                Opportunity(
                    id=task.id,
                    source=self.source_name,
                    url=task.github_issue_url,
                    category="coding",
                    reward=Reward(amount=solver_amount, asset="USD", network=None),
                    deadline=None,
                    requirements=(
                        f"Fix the funded GitHub issue in {repo}",
                        f"Issue: {task.github_issue_url}",
                        f"Language: {lang}",
                    ),
                    acceptance_criteria=(
                        "Add or update regression coverage where appropriate",
                        "Run the repository test suite relevant to the change",
                        "Open an upstream GitHub pull request containing the tested fix",
                        "Pass TaskBounty end-to-end verification",
                    ),
                    competition_model="best_submission",
                    agent_allowed=True,
                    estimated_effort_minutes=_EFFORT.get(
                        (task.complexity_tag or "").lower(),
                        60,
                    ),
                )
            )
        return items

    async def discover(self, limit: int = 50) -> list[Opportunity]:
        return await self.fetch_open(limit=limit)

    async def access_task(self, task_id: str) -> TaskAccess:
        headers = self._mutation_headers()
        safe_id = quote(task_id, safe="")
        try:
            response = await self.client.post(
                f"{self.config.base_url.rstrip('/')}/tasks/{safe_id}/access",
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
            return TaskAccess(
                task_id=task_id,
                clone_url=payload["clone_url"],
                expires_at=payload.get("expires_at"),
            )
        except httpx.HTTPStatusError as exc:
            _raise_http_error(exc)
        except (KeyError, ValidationError, ValueError) as exc:
            raise TaskBountyProtocolError(
                "TaskBounty access response invalid",
                error_code="validation_error",
            ) from exc
        except httpx.HTTPError as exc:
            raise TaskBountyProtocolError(
                "TaskBounty protocol error",
                error_code="protocol_error",
            ) from exc

    async def claim(self, opportunity_id: str) -> ClaimReceipt:
        access = await self.access_task(opportunity_id)
        return ClaimReceipt(
            source=self.source_name,
            opportunity_id=opportunity_id,
            workspace_reference=access.clone_url,
            expires_at=access.expires_at,
        )

    async def submit_pr(self, task_id: str, external_link: str) -> SubmissionResult:
        headers = self._mutation_headers()
        try:
            response = await self.client.post(
                f"{self.config.base_url.rstrip('/')}/submissions",
                headers=headers,
                json={"task_id": task_id, "external_link": external_link},
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("submission"), dict):
                payload = payload["submission"]
            if not isinstance(payload, dict):
                raise ValueError("submission response must be an object")
            return SubmissionResult(
                id=payload.get("id"),
                task_id=str(payload.get("task_id") or task_id),
                status=payload.get("status"),
                external_link=str(payload.get("external_link") or external_link),
            )
        except httpx.HTTPStatusError as exc:
            _raise_http_error(exc)
        except (ValidationError, ValueError) as exc:
            raise TaskBountyProtocolError(
                "TaskBounty submission response invalid",
                error_code="validation_error",
            ) from exc
        except httpx.HTTPError as exc:
            raise TaskBountyProtocolError(
                "TaskBounty protocol error",
                error_code="protocol_error",
            ) from exc

    async def submit(
        self,
        opportunity_id: str,
        artifact_reference: str,
    ) -> SubmissionReceipt:
        result = await self.submit_pr(opportunity_id, artifact_reference)
        return SubmissionReceipt(
            source=self.source_name,
            opportunity_id=opportunity_id,
            reference=result.external_link,
            submission_id=result.id,
            status=result.status,
        )

    async def aclose(self) -> None:
        if self._owned_client:
            await self.client.aclose()
