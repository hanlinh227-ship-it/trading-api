from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import threading
from typing import Mapping

from .app import create_http_server, seconds_until_next_minute
from .provider_binance import BinancePublicMinuteProvider
from .provider_gateway import GatewayMinuteProvider
from .storage import FileLease, JsonSnapshotSink
from .worker import MinuteWorker


DEFAULT_SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "SOLUSDT",
    "TRXUSDT",
    "DOGEUSDT",
    "LINKUSDT",
    "ADAUSDT",
    "XLMUSDT",
)
DEFAULT_GATEWAY_URL = "https://crypto-research-gateway-prod-production.up.railway.app"


@dataclass
class G9Runtime:
    symbols: tuple[str, ...]
    sink: JsonSnapshotSink
    worker: MinuteWorker
    server: object

    def __post_init__(self) -> None:
        self._stop = threading.Event()
        self._scheduler_thread: threading.Thread | None = None

    def tick_once(self, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        return self.worker.run_tick(now)

    def _scheduler_loop(self) -> None:
        while not self._stop.is_set():
            self.tick_once(datetime.now(timezone.utc))
            delay = seconds_until_next_minute(datetime.now(timezone.utc))
            self._stop.wait(delay)

    def run(self) -> None:
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="g9-minute-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        try:
            self.server.serve_forever(poll_interval=0.5)
        finally:
            self._stop.set()
            if self._scheduler_thread is not None:
                self._scheduler_thread.join(timeout=2)
            self.server.server_close()


def _symbols_from_env(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_SYMBOLS
    symbols = tuple(part.strip().upper() for part in value.split(",") if part.strip())
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("G9_SYMBOLS must contain unique non-empty symbols")
    return symbols


def _provider_from_env(env: Mapping[str, str], *, symbols: tuple[str, ...], source_sha: str):
    mode = str(env.get("G9_PROVIDER_MODE", "gateway")).strip().lower()
    if mode == "gateway":
        return GatewayMinuteProvider(
            symbols=symbols,
            source_sha=source_sha,
            base_url=env.get("G9_RESEARCH_GATEWAY_URL", DEFAULT_GATEWAY_URL),
            timeout_seconds=float(env.get("G9_PROVIDER_TIMEOUT_SECONDS", "8")),
        )
    if mode == "binance_direct":
        return BinancePublicMinuteProvider(symbols=symbols, source_sha=source_sha)
    raise ValueError("G9_PROVIDER_MODE must be gateway or binance_direct")


def build_runtime(env: Mapping[str, str], *, provider=None) -> G9Runtime:
    symbols = _symbols_from_env(env.get("G9_SYMBOLS"))
    data_dir = Path(env.get("G9_DATA_DIR", "/tmp/g9-data"))
    source_sha = (
        env.get("DEPLOYMENT_SOURCE_SHA")
        or env.get("RAILWAY_GIT_COMMIT_SHA")
        or "UNKNOWN"
    )
    host = env.get("HOST", "0.0.0.0")
    port = int(env.get("PORT", "8080"))
    ready_max_age = float(env.get("G9_READY_MAX_AGE_SECONDS", "90"))

    sink = JsonSnapshotSink(data_dir)
    lease = FileLease(data_dir / "minute.lock")
    provider = provider or _provider_from_env(env, symbols=symbols, source_sha=source_sha)
    worker = MinuteWorker(
        provider=provider,
        sink=sink,
        source_sha=source_sha,
        lease=lease,
        max_failures=int(env.get("G9_MAX_FAILURES", "3")),
        backoff_seconds=int(env.get("G9_BACKOFF_SECONDS", "60")),
    )
    server = create_http_server(
        worker=worker,
        sink=sink,
        host=host,
        port=port,
        ready_max_age_seconds=ready_max_age,
    )
    return G9Runtime(symbols=symbols, sink=sink, worker=worker, server=server)


def main() -> None:
    runtime = build_runtime(os.environ)
    runtime.run()


if __name__ == "__main__":
    main()
