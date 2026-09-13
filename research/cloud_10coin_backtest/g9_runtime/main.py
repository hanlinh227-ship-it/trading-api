from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import threading
from typing import Mapping

from .app import create_http_server, seconds_until_next_minute
from .provider_binance import BinancePublicMinuteProvider
from .provider_bybit import BybitPublicMinuteProvider
from .provider_chain import FailoverMinuteProvider
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


def _default_provider(symbols: tuple[str, ...], env: Mapping[str, str]):
    order = tuple(
        part.strip().lower()
        for part in env.get("G9_PROVIDER_ORDER", "bybit,binance").split(",")
        if part.strip()
    )
    if not order or len(set(order)) != len(order):
        raise ValueError("G9_PROVIDER_ORDER must contain unique provider names")
    factories = {
        "bybit": lambda: BybitPublicMinuteProvider(symbols=symbols),
        "binance": lambda: BinancePublicMinuteProvider(symbols=symbols),
    }
    providers = []
    for name in order:
        factory = factories.get(name)
        if factory is None:
            raise ValueError(f"unsupported G9 minute provider: {name}")
        label = "BYBIT_PUBLIC_LINEAR" if name == "bybit" else "BINANCE_PUBLIC_USD_M"
        providers.append((label, factory()))
    return FailoverMinuteProvider(providers)


def build_runtime(env: Mapping[str, str], *, provider=None) -> G9Runtime:
    symbols = _symbols_from_env(env.get("G9_SYMBOLS"))
    data_dir = Path(env.get("G9_DATA_DIR", "/tmp/g9-data"))
    source_sha = (
        env.get("DEPLOYMENT_SOURCE_SHA")
        or env.get("RAILWAY_GIT_COMMIT_SHA")
        or "unknown"
    )
    host = env.get("HOST", "0.0.0.0")
    port = int(env.get("PORT", "8080"))
    ready_max_age = float(env.get("G9_READY_MAX_AGE_SECONDS", "90"))

    sink = JsonSnapshotSink(data_dir)
    lease = FileLease(data_dir / "minute.lock")
    provider = provider or _default_provider(symbols, env)
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
