"""Land measured capability evidence in the canonical mesh ledger.

    python AI_SKILL_LIBRARY/v4/tools/compile_capability_ledger.py --check
    python AI_SKILL_LIBRARY/v4/tools/compile_capability_ledger.py --write

`local_runtime_wave0.py` measures a model and *prints* a ledger row; it never
writes one, because a benchmark harness that could edit the registry it is
benchmarking for is one bug away from promoting its own model. The rows have
been sitting in `CHECKPOINTS/evidence/WAVE0_CAPABILITY_*.json` ever since, and
`model_mesh/capability_evidence.json` has stayed empty - which is why the
compiled active index reports `verified=0` and routing has no measured evidence
to consume.

This is the other half of that deliberate split: it collects the rows that real
runs already produced and writes them to the canonical ledger. It measures
nothing and it invents nothing. Every row must survive four checks against the
Open Model Universe registry, and a row that fails any of them is refused rather
than dropped, so a silent partial ledger is not a possible outcome:

* the model must be a registry row at all;
* the digest in the row's `evidence_id` must equal that row's own
  `artifact_identity.sha256`, so a measurement cannot be inherited by different
  bytes;
* the score must equal the score the registry records for that digest, so the
  ledger and the governance plane cannot drift into two different numbers;
* the run must have been `measured: true` with a real benchmark id, version and
  suite hash. A refused run contributes nothing, which is why BitNet and
  Ministral are absent: their artifacts are intact and the runtime cannot load
  them, so there is no measurement to land.

A documentation URL is not a measurement and cannot enter here: the only source
is a recorded local benchmark run, and `provenance.reference` names the file the
row actually came from. That reference used to be hardcoded to one model's
evidence file for every row, which made a row untraceable to the run behind it;
it is now per-row and checked.

`--check` recompiles and compares without writing, so CI fails if the ledger and
the evidence it claims to summarise ever diverge. `--write` is what makes the
change, and it is only half the act: `capability_evidence.json` is sealed by the
active release manifest, so the ledger must be re-sealed by a release cut. That
is intended. Landing capability evidence in the Brain's mesh ledger is a
governed act and looks like one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

from AI_SKILL_LIBRARY.v4.tools.capability_evidence import load_capability_ledger  # noqa: E402

EVIDENCE_GLOB = "CHECKPOINTS/evidence/WAVE0_CAPABILITY_*.json"
LEDGER_REL = "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json"
REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"


class LedgerRefused(RuntimeError):
    """A row that cannot be backed. Refused, never quietly skipped."""


def _registry_index(root: Path) -> dict[str, dict[str, Any]]:
    document = yaml.safe_load((root / REGISTRY_REL).read_text(encoding="utf-8")) or {}
    return {
        str(model.get("model_id")): model
        for model in (document.get("models") or [])
        if isinstance(model, dict)
    }


def _digest_of(record: dict[str, Any]) -> str:
    return str((record.get("artifact_identity") or {}).get("sha256") or "").lower()


def collect_rows(root: Path) -> list[dict[str, Any]]:
    """Every measured row the evidence files hold, checked against the registry."""
    registry = _registry_index(root)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for path in sorted(root.glob(EVIDENCE_GLOB)):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise LedgerRefused(f"{path.name}: unreadable ({exc})") from exc
        if not isinstance(document, dict):
            raise LedgerRefused(f"{path.name}: evidence root is not an object")

        row = document.get("ledger_record")
        if document.get("measured") is not True or not isinstance(row, dict):
            # A refused run has nothing to land. Not an error: it is the honest
            # state of a model the runtime could not load.
            continue

        row = dict(row)
        model_id = str(row.get("model_id") or "")
        record = registry.get(model_id)
        if record is None:
            raise LedgerRefused(
                f"{path.name}: {model_id!r} is not a registry row; a measurement of a "
                "model nothing admitted belongs nowhere near the mesh ledger"
            )

        declared = _digest_of(record)
        measured_digest = str(
            (document.get("artifact_identity") or {}).get("artifact_sha256") or ""
        ).lower()
        if not measured_digest or measured_digest != declared:
            raise LedgerRefused(
                f"{path.name}: measured {measured_digest[:12] or '<none>'} but the registry "
                f"row declares {declared[:12] or '<none>'}; a score measured on one set of "
                "weights can never be inherited by another"
            )
        if str(row.get("evidence_id") or "").split("-")[1:2] != [measured_digest[:12]]:
            raise LedgerRefused(
                f"{path.name}: evidence_id {row.get('evidence_id')!r} does not name the "
                f"digest it was measured on"
            )

        governance = (record.get("capability_evidence") or {}).get(str(row.get("capability")))
        if not isinstance(governance, dict):
            raise LedgerRefused(
                f"{path.name}: the registry records no {row.get('capability')!r} evidence for "
                f"{model_id}, so the ledger would be the only place this score exists"
            )
        if float(governance.get("score") or -1.0) != float(row.get("score") or -2.0):
            raise LedgerRefused(
                f"{path.name}: ledger score {row.get('score')} disagrees with the registry's "
                f"{governance.get('score')} for the same digest"
            )
        if str(governance.get("artifact_sha256") or "").lower() != declared:
            raise LedgerRefused(
                f"{path.name}: the registry's own capability evidence is not bound to that "
                "row's artifact digest"
            )

        for field in ("benchmark_id", "benchmark_version", "measured_at", "source_sha"):
            if not str(row.get(field) or "").strip():
                raise LedgerRefused(f"{path.name}: {field} is empty; the row is not traceable")

        evidence_id = str(row.get("evidence_id"))
        if evidence_id in seen:
            raise LedgerRefused(f"{path.name}: duplicate evidence_id {evidence_id!r}")
        seen.add(evidence_id)

        # The reference must name the file this row actually came from. It was
        # hardcoded to a single model's evidence file for every row, which made
        # each one untraceable to the run behind it.
        row["provenance"] = {
            **(row.get("provenance") or {}),
            "reference": str(path.relative_to(root)),
        }
        rows.append(row)

    rows.sort(key=lambda item: (str(item["provider_id"]), str(item["model_id"]), str(item["capability"])))
    return rows


def build(root: Path) -> dict[str, Any]:
    return {
        "version": 1,
        # Restated because the schema pins them: a capability ledger reports
        # what was measured; it never decides where a request goes.
        "routing_authority": False,
        "reasoning_authority": False,
        "records": collect_rows(root),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true",
                        help="write the ledger; without it the run only reports")
    parser.add_argument("--check", action="store_true",
                        help="fail if the ledger on disk differs from the evidence")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    ledger_path = root / LEDGER_REL
    try:
        compiled = build(root)
    except LedgerRefused as exc:
        print(f"CAPABILITY_LEDGER_COMPILE=REFUSED {exc}")
        return 1

    rendered = json.dumps(compiled, indent=2, sort_keys=True) + "\n"

    if args.write:
        ledger_path.write_text(rendered, encoding="utf-8")
        # Validate what was written, through the canonical loader rather than a
        # local re-check, so the ledger is held to the same schema its consumers
        # apply to it.
        try:
            load_capability_ledger(root, Path(LEDGER_REL))
        except ValueError as exc:
            print(f"CAPABILITY_LEDGER_COMPILE=INVALID {exc}")
            return 1

    if args.check:
        try:
            on_disk = ledger_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"CAPABILITY_LEDGER_CHECK=FAIL unreadable ledger: {exc}")
            return 1
        if on_disk != rendered:
            print("CAPABILITY_LEDGER_CHECK=FAIL the ledger does not match the evidence it "
                  "summarises; re-run with --write and cut a release")
            return 1
        print(f"CAPABILITY_LEDGER_CHECK=PASS records={len(compiled['records'])}")
        return 0

    models = sorted({str(row["model_id"]) for row in compiled["records"]})
    print(f"CAPABILITY_LEDGER_COMPILE=PASS records={len(compiled['records'])} "
          f"models={len(models)} written={bool(args.write)}")
    for row in compiled["records"]:
        print(f"  {row['provider_id']}:{row['model_id']} {row['capability']}="
              f"{row['score']} ({row['benchmark_id']}@{row['benchmark_version']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
