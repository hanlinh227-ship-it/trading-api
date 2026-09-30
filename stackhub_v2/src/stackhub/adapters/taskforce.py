from __future__ import annotations

from datetime import datetime, timezone
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


def _deadline_is_expired(value: object, *, now: datetime | None = None) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, datetime):
        deadline = value
    else:
        raw = str(value).strip()
        if not raw:
            return False
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            deadline = datetime.fromisoformat(raw)
        except ValueError:
            return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return deadline.astimezone(timezone.utc) <= current.astimezone(timezone.utc)


def _explicitly_false(value: object) -> bool:
    if isinstance(value, bool):
        return value is False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, str):
        return value.strip().lower() in {"false", "0", "no", "closed", "disabled"}
    return False


def _applications_are_open(row: dict[str, object]) -> bool:
    # The browse endpoint can briefly keep tasks labelled ACTIVE after their
    # application window has closed. Prefer explicit availability fields when
    # present so the worker does not hammer /apply with deterministic HTTP 400s.
    for key in ("acceptingApplications", "applicationsOpen", "isAcceptingApplications"):
        if key in row and _explicitly_false(row.get(key)):
            return False

    slots_available = row.get("slotsAvailable")
    if slots_available is not None:
        try:
            if int(slots_available) <= 0:
                return False
        except (TypeError, ValueError):
            pass

    current_workers = row.get("currentWorkers")
    max_workers = row.get("maxWorkers")
    if current_workers is not None and max_workers is not None:
        try:
            maximum = int(max_workers)
            current = int(current_workers)
            if maximum > 0 and current >= maximum:
                return False
        except (TypeError, ValueError):
            pass

    return True


def _safe_error_details(response: httpx.Response) -> tuple[str | None, str | None]:
    try:
        payload = response.json()
    except Exception:
        return None, None
    if not isinstance(payload, dict):
        return None, None
    code = str(payload.get("code") or "").strip() or None
    message = str(payload.get("error") or payload.get("message") or "").strip() or None
    if message:
        message = message[:300]
    if code:
        code = code[:100]
    return code, message


def _normalized_error_code(status: int, platform_code: str | None, platform_message: str | None) -> str:
    if platform_code:
        return platform_code
    text = " ".join((platform_message or "").lower().split())
    if "already applied" in text:
        return "already_applied"
    if "cannot apply to your own task" in text or "own task" in text:
        return "cannot_apply_to_own_task"
    if "not verified" in text:
        return "agent_not_verified"
    if "maximum workers" in text or "max workers" in text or "reached maximum" in text:
        return "task_full"
    if "not accepting applications" in text:
        return "task_not_accepting_applications"
    if "task not found" in text:
        return "task_not_found"
    if status == 429:
        return "rate_limited"
    if status in (401, 403):
        return "auth_invalid"
    return f"http_{status}"


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
            status = exc.response.status_code
            platform_code, platform_message = _safe_error_details(exc.response)
            error_code = _normalized_error_code(status, platform_code, platform_message)
            message = f"TaskForce request failed with HTTP {status}"
            if platform_message:
                message += f": {platform_message}"
            raise TaskForceProtocolError(
                message,
                status_code=status,
                error_code=error_code,
                retry_after_seconds=_retry_after_seconds(exc.response) if status == 429 else None,
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
            if _deadline_is_expired(row.get("deadline")):
                continue
            if not _applications_are_open(row):
                continue
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
        try:
            payload, _ = await self._json("POST", f"/api/agent/tasks/{opportunity_id}/apply", json={"message": message[:1000]})
        except TaskForceProtocolError as exc:
            if exc.error_code == "already_applied":
                return AwardRequestReceipt(self.source_name, opportunity_id, f"existing:{opportunity_id}", "PENDING")
            raise
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
