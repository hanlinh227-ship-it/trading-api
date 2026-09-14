from __future__ import annotations

import os
import sys

from . import runner
from . import runtime_v2


def _restart_self_v2() -> None:
    print("Worker V2 code updated; restarting to load new code...", flush=True)
    os.execv(
        sys.executable,
        [sys.executable, "-m", "money_ecosystem.worker.runner_v2", *sys.argv[1:]],
    )


def main() -> int:
    runner.execute_job = runtime_v2.execute_job
    runner.runtime_module = runtime_v2
    runner.RUNNER_BUILD = "worker-reliability-v4+render-gateway-v2"
    runner._restart_self = _restart_self_v2
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
