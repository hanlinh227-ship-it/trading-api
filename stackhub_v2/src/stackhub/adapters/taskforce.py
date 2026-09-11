from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import httpx

from stackhub.adapters.base import AdapterError, AwardRequestReceipt, AwardStatus, SubmissionReceipt
from stackhub.config import SourceConfig
from stackhub.models import Opportunity, Reward
from stackhub.solvers.base import Artifact


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

    def __init__(self, config: SourceConfig, *, api_key: str | None, client: httpx.AsyncClient | None = None):
        self.config = config
        self.capabilities = config.capabilities
        self.api_key = api_key.strip() if api_key else None
        self._owned_client = client is None
        self.client = client or httpx.AsyncClient(timeout=config.request_timeout_seconds, follow_redirects=True)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise TaskForceProtocolError("TaskForce API key required", error_code="auth_required")
        return {"Accept": "application/json", "X-API-Key": self.api_key}

    async def _json(self, method: str, path: str, **kwargs):
        try:
            response = await self.client.request(method, f"{self.config.base_url.rstrip('/')}{path}", headers={**self._headers(), **kwargs.pop("headers", {})}, **kwargs)
            response.raise_for_status()
            return response.json(), response
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            raise TaskForceProtocolError(
                f"TaskForce request failed with HTTP {code}", status_code=code,
                error_code="rate_limited" if code == 429 else ("auth_invalid" if code in (401, 403) else f"http_{code}"),
                retry_after_seconds=_retry_after_seconds(exc.response) if code == 429 else None,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise TaskForceProtocolError("TaskForce protocol error", error_code="protocol_error") from exc

    async def discover(self, limit: int = 50) -> list[Opportunity]:
        limit = max(1, min(int(limit), 100))
        payload, _ = await self._json("GET", "/api/agent/tasks", params={"status": "ACTIVE", "limit": limit})
        rows = payload.get("tasks", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise TaskForceProtocolError("TaskForce response validation failed", error_code="validation_error")
        items: list[Opportunity] = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                raise TaskForceProtocolError("TaskForce response validation failed", error_code="validation_error")
            try:
                amount = Decimal(str(row.get("totalBudget", row.get("budget", row.get("reward", 0)))))
            except Exception as exc:
                raise TaskForceProtocolError("TaskForce reward validation failed", error_code="validation_error") from exc
            task_id = str(row["id"])
            requirements = list(_tuple_text(row.get("requirements")))
            if row.get("description"):
                requirements.append(str(row["description"]))
            if row.get("skillsRequired"):
                requirements.extend(_tuple_text(row.get("skillsRequired")))
            items.append(Opportunity(
                id=task_id, source=self.source_name,
                url=str(row.get("url") or f"https://www.task-force.app/tasks/{task_id}"),
                category=str(row.get("category") or "other").strip().lower(),
                reward=Reward(amount=amount, asset="USDC", network=str(row.get("network") or "Solana")),
                deadline=row.get("deadline"), requirements=tuple(requirements),
                acceptance_criteria=_tuple_text(row.get("acceptanceCriteria")),
                competition_model="application", agent_allowed=True,
                estimated_effort_minutes=row.get("estimatedEffortMinutes"),
            ))
        return items

    fetch_open = discover

    async def request_award(self, opportunity_id: str, message: str) -> AwardRequestReceipt:
        payload, _ = await self._json("POST", f"/api/agent/tasks/{opportunity_id}/apply", json={"message": message[:1000]})
        application = payload.get("application", {}) if isinstance(payload, dict) else {}
        ref = str(application.get("id") or "").strip()
        status = str(application.get("status") or "PENDING").upper()
        if not ref:
            raise TaskForceProtocolError("TaskForce application response missing id", error_code="validation_error")
        return AwardRequestReceipt(self.source_name, opportunity_id, ref, status)

    async def poll_award(self, opportunity_id: str, external_reference: str) -> AwardStatus:
        payload, _ = await self._json("GET", "/api/agent/notifications", params={"unreadOnly": "true", "limit": 100})
        notifications = payload.get("notifications", []) if isinstance(payload, dict) else []
        if not isinstance(notifications, list):
            raise TaskForceProtocolError("TaskForce notifications validation failed", error_code="validation_error")
        matched = []
        result = AwardStatus(self.source_name, opportunity_id, "PENDING", external_reference)
        for note in notifications:
            if not isinstance(note, dict):
                continue
            link = str(note.get("link") or "")
            if opportunity_id not in link and opportunity_id not in str(note.get("message") or ""):
                continue
            note_type = str(note.get("type") or "").upper()
            if note.get("id"):
                matched.append(str(note["id"]))
            if note_type == "APPLICATION_ACCEPTED":
                result = AwardStatus(self.source_name, opportunity_id, "ACCEPTED", external_reference)
            elif note_type == "APPLICATION_REJECTED":
                result = AwardStatus(self.source_name, opportunity_id, "REJECTED", external_reference)
        if matched:
            await self._json("POST", "/api/agent/notifications/read", json={"notificationIds": matched})
        return result

    async def submit(self, opportunity_id: str, artifact_reference: str) -> SubmissionReceipt:
        path = Path(artifact_reference)
        feedback = path.read_text(encoding="utf-8") if path.is_file() else artifact_reference
        if not feedback.strip():
            raise TaskForceProtocolError("empty artifact", error_code="validation_error")
        payload, _ = await self._json("POST", f"/api/agent/tasks/{opportunity_id}/submit", json={"feedback": feedback[:20000]})
        submission = payload.get("submission", payload) if isinstance(payload, dict) else {}
        submission_id = str(submission.get("id") or "").strip() or None
        return SubmissionReceipt(self.source_name, opportunity_id, artifact_reference, submission_id, str(submission.get("status") or "SUBMITTED"))

    async def earnings(self) -> dict[str, object]:
        payload, _ = await self._json("GET", "/api/agent/earnings")
        return payload if isinstance(payload, dict) else {}

    async def aclose(self) -> None:
        if self._owned_client:
            await self.client.aclose()
