"""What the worker fabric can actually hold, and under three named loads.

    python AI_SKILL_LIBRARY/v4/tools/worker_capacity_matrix.py --evidence /tmp/cap.json

A capacity plan is the artifact an optimistic number slips into most easily, so
every figure here carries how it was obtained and the source is never dropped:

  MEASURED   read from this machine by detect_resources(), or from a real run
             that was recorded (a peak RSS, a load latency).
  DECLARED   published by the provider or the platform - a runner's RAM, a free
             plan's daily allowance. True by contract, not by observation here.
  ESTIMATED  derived arithmetic, and the derivation is stated in the row.

An ESTIMATED figure never silently becomes a MEASURED one, and a DECLARED
ceiling is never reported as capacity the fabric has been seen to use.

The three scenarios are load shapes, not predictions:

  MINIMUM_OPERATIONAL  one request at a time. What has to be true for the core
                       to answer at all.
  NORMAL_CONCURRENT    a maker and a checker at once, which is the shape every
                       federation round actually takes.
  PEAK_FEDERATION      every currently eligible executor busy at once.

**This tool decides nothing.** It does not route, admit, promote or schedule.
It reads the same worker contract and the same recorded provider paths the
Free Worker Mesh reads, and prints what they add up to.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources  # noqa: E402

PATHS_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/free_execution_paths.yaml"
REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
EVIDENCE = "CHECKPOINTS/evidence"

#: Provider states in which an executor may be counted as capacity at all.
USABLE_STATES = frozenset({"VERIFIED_AVAILABLE", "VERIFIED_LIMITED"})

#: Headroom the host keeps for the OS and this process. Not capacity.
HOST_RESERVE_MB = 1500


def _load_json(root: Path, name: str) -> Any:
    try:
        return json.loads((root / EVIDENCE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _measured_peaks(root: Path) -> dict[str, int]:
    """Peak RSS per model, from runs that were actually recorded."""
    peaks: dict[str, int] = {}
    for path in sorted((root / EVIDENCE).glob("*.json")):
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        stack: list[Any] = [blob]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                model = node.get("model_id") or (node.get("artifact_identity") or {}).get("model_id")
                peak = node.get("peak_ram_mb") or node.get("peak_rss_mb")
                if model and isinstance(peak, (int, float)) and peak > 0:
                    peaks[str(model)] = max(peaks.get(str(model), 0), int(peak))
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    return peaks


def build(root: Path) -> dict[str, Any]:
    paths_doc = yaml.safe_load((root / PATHS_REL).read_text(encoding="utf-8")) or {}
    providers = paths_doc.get("paths") or []
    snapshot = detect_resources(disk_path=str(root / ".model-cache"))
    peaks = _measured_peaks(root)

    rows: list[dict[str, Any]] = []

    for provider in providers:
        pid = str(provider.get("provider_id"))
        state = str(provider.get("verification_state") or "DISCOVERED")
        usable = state in USABLE_STATES
        local = provider.get("execution_type") == "LOCAL_PROCESS"

        if local:
            ram_mb, ram_src = int(snapshot.ram_total_mb or 0), "MEASURED"
            avail_mb, avail_src = int(snapshot.ram_available_mb or 0), "MEASURED"
            disk_mb, disk_src = int(snapshot.disk_free_mb or 0), "MEASURED"
        else:
            ram_mb, ram_src = int(provider.get("max_ram_mb") or 0), "DECLARED"
            avail_mb, avail_src = ram_mb, "DECLARED"
            disk_mb, disk_src = int(provider.get("max_disk_mb") or 0), "DECLARED"

        # Concurrent slots: how many resident models of the largest size this
        # fabric has actually measured would fit, after host reserve. Stated as
        # arithmetic so the reader can redo it.
        largest_measured = max(peaks.values(), default=0)
        if avail_mb and largest_measured:
            slots = max(0, (avail_mb - HOST_RESERVE_MB) // largest_measured)
            slots_src = "ESTIMATED"
            slots_basis = (f"({avail_mb} MB available - {HOST_RESERVE_MB} MB host reserve) / "
                           f"{largest_measured} MB, the largest MEASURED peak in the fabric")
        elif provider.get("execution_type") == "SERVERLESS_HOSTED_CATALOG":
            # A hosted catalog holds no weights for us. Its limit is quota and
            # wall-clock, not RAM, so a "slot" count would be an invented number.
            slots, slots_src = None, "NOT_APPLICABLE"
            slots_basis = ("resident-model slots are a host concept. This provider holds "
                           "no weights on our behalf; its ceiling is its free quota.")
        else:
            slots, slots_src, slots_basis = None, "UNKNOWN", "no measured model peak to divide by"

        rows.append({
            "worker_id": pid,
            "execution_type": provider.get("execution_type"),
            "cost_class": provider.get("cost_class"),
            "verification_state": state,
            "counts_as_capacity": usable,
            "holds_custom_weights": bool(provider.get("custom_weights")),
            "ram_total_mb": {"value": ram_mb or None, "source": ram_src},
            "ram_available_mb": {"value": avail_mb or None, "source": avail_src},
            "disk_free_mb": {"value": disk_mb or None, "source": disk_src},
            "gpus": {"value": len(snapshot.gpus) if local else 0,
                     "source": "MEASURED" if local else "DECLARED"},
            "max_job_seconds": {"value": provider.get("max_job_seconds"),
                                "source": "DECLARED"} if provider.get("max_job_seconds") else None,
            "cold_start_ms": {"value": provider.get("cold_start_ms"),
                              "source": "DECLARED"} if provider.get("cold_start_ms") else None,
            "quota": {"value": provider.get("quota"), "source": "DECLARED"},
            "keeps_a_model_warm": provider.get("execution_type") in
                                  ("LOCAL_PROCESS", "SERVERLESS_HOSTED_CATALOG"),
            "concurrent_resident_models": {
                "value": slots, "source": slots_src, "basis": slots_basis},
        })

    usable_rows = [r for r in rows if r["counts_as_capacity"]]
    weight_holders = [r for r in usable_rows if r["holds_custom_weights"]]
    host = next((r for r in rows if r["execution_type"] == "LOCAL_PROCESS"), None)

    # Two different questions, and conflating them is how a capacity plan goes
    # wrong. `host_total` asks what this machine can EVER hold and is a property
    # of the machine. `host_avail` asks what is free at this instant and moves
    # while a benchmark is running - this very matrix reads lower during a run.
    host_avail = (host or {}).get("ram_available_mb", {}).get("value") or 0
    host_total = (host or {}).get("ram_total_mb", {}).get("value") or 0
    largest = max(peaks.values(), default=0)
    smallest = min(peaks.values(), default=0)

    scenarios = {
        "MINIMUM_OPERATIONAL": {
            "shape": "one request at a time, nothing else resident",
            "executors_required": 1,
            "ram_required_mb": {"value": largest or None, "source": "MEASURED",
                                "basis": "the largest measured peak RSS in the fabric"},
            "satisfied_by_host_alone": bool(largest and host_total - HOST_RESERVE_MB >= largest),
            "satisfiable_right_now": bool(largest and host_avail - HOST_RESERVE_MB >= largest),
            "evidence": "every Wave 0 baseline run took exactly this shape",
        },
        "NORMAL_CONCURRENT": {
            "shape": "a maker and a checker at once - the shape every federation round takes",
            "executors_required": 2,
            "ram_required_mb": {
                "value": (largest + smallest) or None, "source": "ESTIMATED",
                "basis": (f"largest measured peak {largest} MB + smallest measured peak "
                          f"{smallest} MB. The federation proof ran this pairing "
                          f"sequentially, not concurrently, so the sum is arithmetic "
                          f"and not an observation.")},
            "satisfied_by_host_alone": bool(
                largest and host_total - HOST_RESERVE_MB >= largest + smallest),
            "satisfiable_right_now": bool(
                largest and host_avail - HOST_RESERVE_MB >= largest + smallest),
            "evidence": ("WAVE3_FEDERATION_PROOF ran nine maker/checker rounds. Concurrency "
                         "of the pair is ESTIMATED; the rounds themselves are MEASURED."),
        },
        "PEAK_FEDERATION": {
            "shape": "every currently eligible executor busy at once",
            "executors_required": len(usable_rows),
            "ram_required_mb": {
                "value": None, "source": "NOT_APPLICABLE",
                "basis": ("peak is not a single RAM figure: one executor is this host, one "
                          "is a runner with its own RAM, and one is a hosted catalog bounded "
                          "by quota rather than memory. Adding them would invent a number.")},
            "binding_constraint": (
                "the hosted catalog's daily free quota and the runner's cold start, not RAM"),
            "satisfied_by_host_alone": False,
            "satisfiable_right_now": False,
            "evidence": ("never executed as a single concurrent burst. Recorded as a planned "
                         "shape with no measurement behind it, which is why it carries no "
                         "RAM figure."),
        },
    }

    plan = {
        "weight_holding_executors": [r["worker_id"] for r in weight_holders],
        "hosted_catalog_executors": [r["worker_id"] for r in usable_rows
                                     if r["execution_type"] == "SERVERLESS_HOSTED_CATALOG"],
        "executors_that_keep_a_model_warm": [r["worker_id"] for r in usable_rows
                                             if r["keeps_a_model_warm"]],
        "single_point_of_failure": (
            "one host holds every local weight. If this container dies, exact-model execution "
            "stops and only the hosted catalog answers - under a different model's name."),
        "largest_measured_model_peak_mb": largest or None,
        "measured_model_peaks_mb": dict(sorted(peaks.items())),
        "host_reserve_mb": HOST_RESERVE_MB,
        "host_ram_total_mb": host_total or None,
        "host_ram_available_mb_at_read_time": host_avail or None,
        "reading_is_a_moment": (
            "ram_available_mb is a live reading and drops while work is running. "
            "satisfied_by_host_alone is computed from total RAM, which is a property of "
            "the machine; satisfiable_right_now is computed from available RAM, which is "
            "a property of this instant."),
    }

    return {
        "tool": "worker_capacity_matrix",
        "WORKER_CAPACITY_MATRIX": rows,
        "FLEET_CAPACITY_PLAN": plan,
        "CAPACITY_SCENARIOS": scenarios,
        "source_legend": {
            "MEASURED": "read from this machine or from a recorded run",
            "DECLARED": "published by the provider or platform; true by contract, not observed here",
            "ESTIMATED": "derived arithmetic; the derivation is in the row",
        },
        "routing_authority": False,
        "admission_authority": False,
        "scheduling_authority": False,
        "note": ("Capacity is not permission. A worker appearing here with room is still "
                 "subject to attestation, privacy ceiling, quota and the mesh's own "
                 "eligibility rules before it may be handed anything."),
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build(args.root)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    print(f"WORKER_CAPACITY_MATRIX workers={len(result['WORKER_CAPACITY_MATRIX'])}")
    for row in result["WORKER_CAPACITY_MATRIX"]:
        ram = row["ram_available_mb"]
        slots = row["concurrent_resident_models"]
        print(f"  {row['worker_id']:<30} {row['verification_state']:<20} "
              f"ram={ram['value']}({ram['source']}) slots={slots['value']}({slots['source']})")
    for name, sc in result["CAPACITY_SCENARIOS"].items():
        need = sc["ram_required_mb"]
        print(f"  {name:<22} executors={sc['executors_required']} "
              f"ram={need['value']}({need['source']}) "
              f"host_alone={sc['satisfied_by_host_alone']} "
              f"now={sc['satisfiable_right_now']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
