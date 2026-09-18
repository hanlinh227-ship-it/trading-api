"""Can this worker actually run a model, or is it merely switched on?

    python AI_SKILL_LIBRARY/v4/tools/worker_execution_liveness.py --evidence /tmp/live.json

Every health signal the fabric currently collects describes the *host*: a fresh
heartbeat, free RAM, disk headroom, an unexpired lease, a closed circuit, queue
depth. All of them can be true on a machine whose inference engine cannot
execute a single instruction, and on that machine the worker reports
`online: true, circuit: CLOSED` and keeps its place in every role that names it.

That is not hypothetical. It is the state of this container right now:
`detect_llama_cpp_python()` terminates the interpreter with SIGILL, so the one
worker holding every local weight can serve nothing, while reporting itself
healthy by all six existing measures.

So this asks the one question the others do not: start a *subprocess*, import
the backend, and see whether it comes back. The subprocess matters - a SIGILL
is not an exception and cannot be caught, so a probe that ran in-process would
take the prober down with it and leave no evidence at all. A worker that kills
its probe is exactly the worker this is looking for.

Three outcomes, kept apart on purpose:

  EXECUTION_LIVE     the engine imported and identified itself
  EXECUTION_DEAD     the probe died or errored; the signal or error is recorded
  EXECUTION_UNKNOWN  the probe could not be run, which is not a pass

**This tool decides nothing.** It does not route, evict, demote or change a
worker's state. It reports a fact the existing health fields cannot express, so
that the scheduler's owners can act on it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

EVIDENCE = "CHECKPOINTS/evidence"

#: Run in a subprocess. Anything that kills the interpreter is caught as a
#: signal by the parent instead of ending the run.
PROBE = (
    "from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import "
    "detect_llama_cpp_python;"
    "identity = detect_llama_cpp_python();"
    "print('ENGINE_OK' if identity else 'ENGINE_ABSENT')"
)


def probe_local_engine(root: Path, *, timeout: float = 120.0) -> dict[str, Any]:
    """Ask a throwaway process whether the local inference engine runs."""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", PROBE],
            cwd=str(root), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "state": "EXECUTION_DEAD",
            "reason": f"the engine probe did not return within {timeout:.0f}s",
            "detail": "a probe that hangs is not a worker that serves",
        }
    except OSError as exc:  # pragma: no cover - the probe could not be launched
        return {"state": "EXECUTION_UNKNOWN", "reason": "the probe could not be started",
                "detail": str(exc)}

    stdout = (completed.stdout or "").strip()
    if completed.returncode == 0 and "ENGINE_OK" in stdout:
        return {"state": "EXECUTION_LIVE", "reason": "the engine imported and identified itself"}
    if completed.returncode == 0 and "ENGINE_ABSENT" in stdout:
        return {
            "state": "EXECUTION_DEAD",
            "reason": "no local inference engine is installed",
            "detail": "absent is not broken, but it serves no local model either",
        }
    if completed.returncode < 0:
        signal_number = -completed.returncode
        return {
            "state": "EXECUTION_DEAD",
            "reason": f"the engine probe was killed by signal {signal_number}",
            "signal": signal_number,
            "detail": (
                "SIGILL (4) means the installed binary uses instructions this CPU does not "
                "have - typically a container moved to different hardware. The artifact and "
                "the code are unchanged; the machine under them is not."
                if signal_number == 4 else
                "the probe terminated abnormally rather than returning a result"
            ),
        }
    return {
        "state": "EXECUTION_DEAD",
        "reason": f"the engine probe exited {completed.returncode}",
        "detail": (completed.stderr or "").strip()[-400:] or "no stderr",
    }


def _roles_on_local_workers(root: Path) -> list[dict[str, Any]]:
    """Which roles lose their primary if the local engine cannot run."""
    path = root / EVIDENCE / "ROLE_CAPABILITY_MATRIX.json"
    if not path.is_file():
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    affected = []
    for role in document.get("ROLE_CAPABILITY_MATRIX") or []:
        primary = role.get("primary") or {}
        if primary.get("placement") != "LOCAL":
            continue
        fallbacks = [role.get(k) for k in ("secondary", "fallback", "emergency_fallback")]
        offhost = [f for f in fallbacks
                   if isinstance(f, dict) and f.get("placement") not in (None, "LOCAL")]
        affected.append({
            "role_id": role.get("role_id"),
            "criticality": role.get("criticality"),
            "primary_model": primary.get("model_id"),
            "has_an_off_host_alternative": bool(offhost),
            "off_host_alternative": offhost[0].get("model_id") if offhost else None,
        })
    return affected


def build(root: Path) -> dict[str, Any]:
    engine = probe_local_engine(root)
    live = engine["state"] == "EXECUTION_LIVE"
    affected = _roles_on_local_workers(root)
    stranded = [row for row in affected if not row["has_an_off_host_alternative"]]
    critical_stranded = [row["role_id"] for row in stranded if row["criticality"] == "CRITICAL"]

    report: dict[str, Any] = {
        "tool": "worker_execution_liveness",
        "LOCAL_ENGINE": engine,
        "EXECUTION_LIVE": live,
        "roles_with_a_local_primary": affected,
        "roles_stranded_if_the_local_engine_is_dead": [row["role_id"] for row in stranded],
        "critical_roles_stranded": critical_stranded,
        "health_fields_that_would_still_read_healthy": [
            "online", "stale_lease", "last_seen", "ram_available_mb",
            "disk_free_mb", "circuit", "quota_exhausted",
        ],
        "why_this_is_separate": (
            "every existing worker health field describes the host. None of them asks whether "
            "the engine runs, so a worker that cannot execute still reports online with a "
            "closed circuit. Resource liveness and execution liveness are different facts."
        ),
        "routing_authority": False,
        "admission_authority": False,
        "scheduling_authority": False,
        "changes_nothing": True,
    }
    if not live:
        report["FEDERATION_IMPACT"] = (
            f"{len(affected)} role(s) name a local model as primary and cannot be served by it. "
            f"{len(critical_stranded)} CRITICAL role(s) have no off-host alternative."
            if affected else
            "no role currently names a local model as primary, so nothing is stranded."
        )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero when the local engine cannot execute")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build(root)
    if args.evidence:
        out = Path(args.evidence)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    state = report["LOCAL_ENGINE"]["state"]
    print(f"WORKER_EXECUTION_LIVENESS={state} "
          f"stranded_roles={len(report['roles_stranded_if_the_local_engine_is_dead'])} "
          f"critical_stranded={len(report['critical_roles_stranded'])}")
    return 1 if (args.strict and not report["EXECUTION_LIVE"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
