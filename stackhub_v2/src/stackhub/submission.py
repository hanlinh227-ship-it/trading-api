from __future__ import annotations

from datetime import datetime
from typing import Mapping

from .adapters.base import MutationSourceAdapter, SubmissionReceipt
from .solvers.base import Artifact
from .source_capabilities import assert_source_eligible_for
from .worker_state import WorkerState


class SubmissionManager:
    def __init__(
        self,
        repo,
        adapters: Mapping[str, MutationSourceAdapter],
    ):
        self.repo = repo
        self.adapters = dict(adapters)

    def _existing_submission(self, source: str, opportunity_id: str):
        if hasattr(self.repo, "get_submission"):
            return self.repo.get_submission(source, opportunity_id)
        row = self.repo.conn.execute(
            "SELECT * FROM submissions WHERE source=? AND opportunity_id=? ORDER BY id ASC LIMIT 1",
            (source, opportunity_id),
        ).fetchone()
        return None if row is None else dict(row)

    def _claim(self, source: str, opportunity_id: str):
        if hasattr(self.repo, "get_claim"):
            return self.repo.get_claim(source, opportunity_id)
        row = self.repo.conn.execute(
            "SELECT * FROM claims WHERE source=? AND opportunity_id=?",
            (source, opportunity_id),
        ).fetchone()
        return None if row is None else dict(row)

    async def submit_verified(
        self,
        source: str,
        opportunity_id: str,
        artifact: Artifact,
        observed_at: datetime,
    ) -> SubmissionReceipt:
        existing = self._existing_submission(source, opportunity_id)
        if existing is not None:
            return SubmissionReceipt(
                source=source,
                opportunity_id=opportunity_id,
                reference=str(existing["reference"]),
                submission_id=existing.get("submission_id"),
                status=existing.get("status"),
            )

        claim = self._claim(source, opportunity_id)
        if claim is None or str(claim["state"]) != WorkerState.VERIFIED.value:
            raise ValueError("submission requires VERIFIED claim")

        adapter = self.adapters[source]
        assert_source_eligible_for("submit", adapter.capabilities)
        receipt = await adapter.submit(opportunity_id, artifact.reference)
        self.repo.record_submission(
            source,
            opportunity_id,
            receipt.reference,
            receipt.submission_id,
            observed_at,
        )
        self.repo.transition_claim(
            source,
            opportunity_id,
            WorkerState.SUBMITTED,
            observed_at,
        )
        return receipt
