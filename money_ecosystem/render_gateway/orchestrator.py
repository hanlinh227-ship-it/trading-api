from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
import re

from .artifacts import ReturnManifest, package_and_upload
from .contract import RenderJob
from .router import QualityTargetUnavailable, RouteDecision, route
from .state import JobState, transition


@dataclass(frozen=True)
class RenderResult:
    state: JobState
    message: str
    state_history: tuple[JobState, ...]
    route_decision: RouteDecision | None = None
    return_manifest: ReturnManifest | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "message": self.message,
            "state_history": [state.value for state in self.state_history],
            "route": None if self.route_decision is None else {
                "selected_provider_id": self.route_decision.selected_provider_id,
                "requires_user_approval": self.route_decision.requires_user_approval,
                "reason": self.route_decision.reason,
                "rejected": [
                    {"provider_id": item.provider_id, "reason": item.reason}
                    for item in self.route_decision.rejected
                ],
            },
            "return_manifest": None if self.return_manifest is None else self.return_manifest.to_dict(),
        }


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "asset"


def classify_failure(exc: Exception) -> JobState:
    text = str(exc).upper()
    if "BLOCKED_AUTH" in text or "AUTHENTICAT" in text or "AUTHORIZATION" in text:
        return JobState.BLOCKED_AUTH
    if "QUOTA" in text:
        return JobState.PROVIDER_QUOTA
    if "WORKER_OFFLINE" in text or "OFFLINE" in text:
        return JobState.WORKER_OFFLINE
    if "ASSET" in text or "SHA256" in text or "CHECKSUM" in text:
        return JobState.BLOCKED_ASSET
    if "RETURN" in text or "UPLOAD" in text or "DRIVE" in text:
        return JobState.RETURN_FAILED
    return JobState.RENDER_FAILED


class RenderOrchestrator:
    def __init__(
        self,
        *,
        providers: Iterable[Any],
        asset_store: Any,
        qa_evaluator: Callable[[RenderJob, list[Path]], Any],
        workspace_root: Path | str,
        chat_attachment_available: bool = False,
        max_poll_cycles: int = 120,
    ) -> None:
        self.providers = list(providers)
        self.asset_store = asset_store
        self.qa_evaluator = qa_evaluator
        self.workspace_root = Path(workspace_root).resolve()
        self.chat_attachment_available = chat_attachment_available
        self.max_poll_cycles = max(1, int(max_poll_cycles))

    def _terminal(
        self,
        history: list[JobState],
        state: JobState,
        message: str,
        decision: RouteDecision | None = None,
    ) -> RenderResult:
        history.append(state)
        return RenderResult(state, message, tuple(history), decision, None)

    def _stage_input_assets(self, job: RenderJob) -> None:
        if not job.assets:
            return
        if self.asset_store is None or not hasattr(self.asset_store, "fetch"):
            raise RuntimeError("BLOCKED_ASSET: no asset store fetch capability")
        target_root = self.workspace_root / ".render_gateway" / job.project_id / job.job_id / job.attempt_id / "inputs"
        target_root.mkdir(parents=True, exist_ok=True)
        for asset in job.assets:
            suffix = Path(asset.asset_id).suffix or Path(asset.mime_type.split("/")[-1]).suffix
            target = target_root / f"{_safe_name(asset.asset_id)}{suffix if suffix else ''}"
            self.asset_store.fetch(asset, target)

    def run(self, job: RenderJob) -> RenderResult:
        history = [JobState.RECEIVED]
        decision: RouteDecision | None = None
        try:
            self._stage_input_assets(job)
            history.append(transition(history[-1], JobState.ASSETS_STAGED))
            history.append(transition(history[-1], JobState.VALIDATED))

            try:
                decision = route(job, self.providers)
            except QualityTargetUnavailable as exc:
                statuses = [provider.preflight() for provider in self.providers]
                if statuses and all(status.authorization == "BLOCKED_AUTH" for status in statuses):
                    return self._terminal(history, JobState.BLOCKED_AUTH, str(exc))
                return self._terminal(history, JobState.QUALITY_TARGET_UNAVAILABLE, str(exc))

            history.append(transition(history[-1], JobState.ROUTED))
            if decision.requires_user_approval:
                return self._terminal(
                    history,
                    JobState.BLOCKED_AUTH,
                    "Provider requires explicit paid-render approval before execution",
                    decision,
                )

            provider = next(
                provider for provider in self.providers
                if provider.capabilities().provider_id == decision.selected_provider_id
            )
            staged = provider.stage_assets(job)
            history.append(transition(history[-1], JobState.QUEUED))
            provider_job = provider.submit(staged)
            history.append(transition(history[-1], JobState.RENDERING))

            poll = None
            for _ in range(self.max_poll_cycles):
                poll = provider.poll(provider_job.provider_job_id)
                state = str(poll.state).upper()
                if state in {"COMPLETE", "SUCCESS", "SUCCEEDED"}:
                    break
                if state in {"FAILED", "ERROR", "BLOCKED_AUTH", "PROVIDER_QUOTA"}:
                    raise RuntimeError(f"provider render failed: {state}: {poll.message}")
            else:
                raise RuntimeError("provider render timed out before completion")

            files = [Path(path) for path in provider.collect(provider_job.provider_job_id)]
            if not files or not all(path.is_file() for path in files):
                raise RuntimeError("provider returned no valid render artifacts")

            history.append(transition(history[-1], JobState.QA))
            qa_report = self.qa_evaluator(job, files)
            if isinstance(qa_report, dict):
                qa_status = str(qa_report.get("terminal_status") or qa_report.get("status") or "UNKNOWN").upper()
            else:
                qa_status = str(getattr(qa_report, "terminal_status", "UNKNOWN")).upper()
            if qa_status not in {"VERIFIED", "ACCEPTED", "PASS", "PASSED"}:
                return self._terminal(
                    history,
                    JobState.QA_REJECTED,
                    f"QA did not verify artifact: {qa_status}",
                    decision,
                )

            history.append(transition(history[-1], JobState.PACKAGING))
            if self.asset_store is None:
                return self._terminal(history, JobState.RETURN_FAILED, "No Drive artifact store configured", decision)
            history.append(transition(history[-1], JobState.RETURNING))
            return_manifest = package_and_upload(
                job,
                files,
                qa_report,
                self.asset_store,
                chat_attachment_available=self.chat_attachment_available,
            )
            history.append(transition(history[-1], JobState.COMPLETE))
            return RenderResult(
                JobState.COMPLETE,
                "Render completed, QA verified, artifact return metadata created",
                tuple(history),
                decision,
                return_manifest,
            )
        except Exception as exc:
            failure = classify_failure(exc)
            return self._terminal(history, failure, str(exc), decision)
