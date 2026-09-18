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
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

EVIDENCE = "CHECKPOINTS/evidence"

#: The instruction-set extensions that decide whether a prebuilt engine runs at
#: all. A binary compiled for a host with avx512 raises SIGILL on one without
#: it, which is the difference between EXECUTION_LIVE and EXECUTION_DEAD for
#: the same commit and the same artifact.
_CPU_FLAGS = ("avx", "avx2", "avx512f", "avx512bw", "avx512vl", "avx512dq",
              "avx512cd", "avx512_vnni", "f16c", "fma")


def observing_host() -> dict[str, Any]:
    """Who looked, so that two sessions disagreeing is informative.

    An execution-liveness reading is a fact about one machine at one moment,
    not about the repository. Recorded without a host it looks like a property
    of the commit, and two sessions on different hardware will then overwrite
    each other forever, each one correct and each one erasing the other. With
    a host attached both readings stand, and the disagreement becomes what it
    actually is: evidence that the fabric's execution depends on which machine
    a session happens to get.
    """
    flags: list[str] = []
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
        present = set(re.findall(r"\b(" + "|".join(_CPU_FLAGS) + r")\b", cpuinfo))
        flags = sorted(present)
    except OSError:
        flags = []
    body = json.dumps({
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "cpu_flags": flags,
    }, sort_keys=True, separators=(",", ":"))
    return {
        "host_fingerprint": hashlib.sha256(body.encode("utf-8")).hexdigest()[:32],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_flags_present": flags,
        "why_the_flags": (
            "a prebuilt engine raises SIGILL on a CPU lacking the extensions it was compiled "
            "for, so these decide liveness for an unchanged commit and an unchanged artifact"
        ),
    }

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
                "SIGILL (4): the CPU refused an instruction the installed binary issued. The "
                "usual cause is a prebuilt engine meeting a CPU without the extensions it was "
                "compiled for, but check OBSERVED_ON.cpu_flags_present before concluding that - "
                "a host advertising the expected extensions and still taking SIGILL points "
                "elsewhere, to a microarchitecture mismatch or a damaged install. Either way "
                "the artifact and the code are unchanged and the machine under them is not."
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
        "OBSERVED_ON": observing_host(),
        "reading_scope": (
            "this is a fact about the machine named in OBSERVED_ON at the moment it ran, not a "
            "property of the commit. A different host may read the opposite and both are true."
        ),
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


def _merge_readings(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Keep one reading per host instead of letting the last session win.

    Two sessions on different hardware were overwriting each other here, each
    recording a true result and erasing a true result. Keyed by host, both
    survive, and a fabric whose execution depends on which machine answered
    becomes visible in the file rather than in the commit history.
    """
    readings: dict[str, Any] = {}
    if path.is_file():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
        readings = dict(previous.get("READINGS_BY_HOST") or {})
        # A file written before this field existed still holds one real reading.
        if not readings and previous.get("LOCAL_ENGINE"):
            older = previous.get("OBSERVED_ON") or {}
            key = older.get("host_fingerprint", "host_not_recorded")
            readings[key] = {
                "OBSERVED_ON": older or {"note": "this reading predates host attribution"},
                "LOCAL_ENGINE": previous["LOCAL_ENGINE"],
                "EXECUTION_LIVE": previous.get("EXECUTION_LIVE"),
            }

    host = report["OBSERVED_ON"]["host_fingerprint"]
    readings[host] = {
        "OBSERVED_ON": report["OBSERVED_ON"],
        "LOCAL_ENGINE": report["LOCAL_ENGINE"],
        "EXECUTION_LIVE": report["EXECUTION_LIVE"],
    }
    merged = dict(report)
    merged["READINGS_BY_HOST"] = readings
    merged["hosts_observed"] = len(readings)
    live = [k for k, v in readings.items() if v.get("EXECUTION_LIVE")]
    merged["hosts_where_the_engine_runs"] = len(live)
    if len(readings) > 1 and 0 < len(live) < len(readings):
        merged["EXECUTION_IS_HOST_DEPENDENT"] = True
        merged["host_dependence_note"] = (
            "the same commit and the same artifacts execute on some of the hosts observed and "
            "not on others. Neither reading is wrong. This is the SINGLE_PATH_RISK made "
            "concrete: one host holds every local weight, so whether the federation can run "
            "locally depends on which machine answered."
        )
    return merged


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
        report = _merge_readings(out, report)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    state = report["LOCAL_ENGINE"]["state"]
    print(f"WORKER_EXECUTION_LIVENESS={state} "
          f"stranded_roles={len(report['roles_stranded_if_the_local_engine_is_dead'])} "
          f"critical_stranded={len(report['critical_roles_stranded'])}")
    return 1 if (args.strict and not report["EXECUTION_LIVE"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
