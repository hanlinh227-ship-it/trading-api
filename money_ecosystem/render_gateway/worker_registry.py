from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class LeaseConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkerCapabilities:
    worker_id: str
    gpu: str
    engines: tuple[str, ...]
    capabilities: tuple[str, ...]
    runner_build: str
    runtime_build: str


@dataclass(frozen=True)
class WorkerHeartbeat:
    capabilities: WorkerCapabilities
    heartbeat_at: datetime


@dataclass(frozen=True)
class Lease:
    job_id: str
    attempt_id: str
    worker_id: str
    acquired_at: datetime
    expires_at: datetime


class WorkerRegistry:
    def __init__(self, *, heartbeat_ttl: timedelta, lease_ttl: timedelta) -> None:
        if heartbeat_ttl.total_seconds() <= 0 or lease_ttl.total_seconds() <= 0:
            raise ValueError("TTL values must be positive")
        self.heartbeat_ttl = heartbeat_ttl
        self.lease_ttl = lease_ttl
        self._heartbeats: dict[str, WorkerHeartbeat] = {}
        self._leases: dict[tuple[str, str], Lease] = {}

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)

    def heartbeat(self, capabilities: WorkerCapabilities, now: datetime) -> WorkerHeartbeat:
        if not capabilities.worker_id.strip():
            raise ValueError("worker_id is required")
        beat = WorkerHeartbeat(capabilities=capabilities, heartbeat_at=self._utc(now))
        self._heartbeats[capabilities.worker_id] = beat
        return beat

    def is_online(self, worker_id: str, now: datetime) -> bool:
        beat = self._heartbeats.get(worker_id)
        if beat is None:
            return False
        return self._utc(now) - beat.heartbeat_at <= self.heartbeat_ttl

    def get_capabilities(self, worker_id: str, now: datetime) -> WorkerCapabilities | None:
        if not self.is_online(worker_id, now):
            return None
        return self._heartbeats[worker_id].capabilities

    def lease_valid(self, lease: Lease, now: datetime) -> bool:
        return self._utc(now) < lease.expires_at

    def acquire_lease(
        self,
        job_id: str,
        attempt_id: str,
        worker_id: str,
        now: datetime,
    ) -> Lease:
        if not self.is_online(worker_id, now):
            raise LeaseConflict(f"worker is offline: {worker_id}")
        key = (str(job_id), str(attempt_id))
        current = self._leases.get(key)
        if current is not None and self.lease_valid(current, now) and current.worker_id != worker_id:
            raise LeaseConflict(
                f"active lease exists for {job_id}/{attempt_id}: {current.worker_id}"
            )
        acquired = self._utc(now)
        lease = Lease(
            job_id=str(job_id),
            attempt_id=str(attempt_id),
            worker_id=str(worker_id),
            acquired_at=acquired,
            expires_at=acquired + self.lease_ttl,
        )
        self._leases[key] = lease
        return lease

    def release_lease(self, job_id: str, attempt_id: str, worker_id: str) -> bool:
        key = (str(job_id), str(attempt_id))
        lease = self._leases.get(key)
        if lease is None or lease.worker_id != worker_id:
            return False
        del self._leases[key]
        return True
