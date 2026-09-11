from __future__ import annotations

from decimal import Decimal

import httpx

from stackhub.adapters.base import AdapterError
from stackhub.config import SourceConfig
from stackhub.models import Opportunity, Reward


class TaskForceProtocolError(AdapterError):
    pass


def _retry_after_seconds(response: httpx.Response) -> int | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return None


def _tuple_text(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = value.strip()
        return (value,) if value else ()
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value),)


class TaskForceAdapter:
    source_name = "taskforce"

    def __init__(
        self,
        config: SourceConfig,
        *,
        api_key: str | None,
        client: httpx.AsyncClient | None = None,
    ):
        self.config = config
        self.capabilities = config.capabilities
        self.api_key = api_key.strip() if api_key else None
        self._owned_client = client is None
        self.client = client or httpx.AsyncClient(timeout=config.request_timeout_seconds)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise TaskForceProtocolError("TaskForce API key required", error_code="auth_required")
        return {
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }

    async def discover(self, limit: int = 50) -> list[Opportunity]:
        limit = max(1, min(int(limit), 100))
        try:
            response = await self.client.get(
                f"{self.config.base_url.rstrip('/')}/api/agent/tasks",
                params={"status": "ACTIVE", "limit": limit},
                headers=self._headers(),
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            raise TaskForceProtocolError(
                f"TaskForce request failed with HTTP {code}",
                status_code=code,
                error_code="rate_limited" if code == 429 else ("auth_invalid" if code in (401, 403) else f"http_{code}"),
                retry_after_seconds=_retry_after_seconds(exc.response) if code == 429 else None,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise TaskForceProtocolError("TaskForce protocol error", error_code="protocol_error") from exc

        rows = payload.get("tasks", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise TaskForceProtocolError("TaskForce response validation failed", error_code="validation_error")

        items: list[Opportunity] = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                raise TaskForceProtocolError("TaskForce response validation failed", error_code="validation_error")
            raw_reward = row.get("totalBudget", row.get("budget", row.get("reward", 0)))
            try:
                amount = Decimal(str(raw_reward))
            except Exception as exc:
                raise TaskForceProtocolError("TaskForce reward validation failed", error_code="validation_error") from exc
            task_id = str(row["id"])
            items.append(
                Opportunity(
                    id=task_id,
                    source=self.source_name,
                    url=str(row.get("url") or f"https://task-force.app/tasks/{task_id}"),
                    category=str(row.get("category") or "other").strip().lower(),
                    reward=Reward(amount=amount, asset="USDC", network=str(row.get("network") or "Solana")),
                    deadline=row.get("deadline"),
                    requirements=_tuple_text(row.get("requirements")),
                    acceptance_criteria=_tuple_text(row.get("acceptanceCriteria")),
                    competition_model="application",
                    agent_allowed=True,
                    estimated_effort_minutes=row.get("estimatedEffortMinutes"),
                )
            )
        return items

    fetch_open = discover

    async def aclose(self) -> None:
        if self._owned_client:
            await self.client.aclose()
