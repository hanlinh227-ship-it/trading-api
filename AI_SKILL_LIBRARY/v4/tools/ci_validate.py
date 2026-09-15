"""Single validation entrypoint for GITHUB_BRAIN_V4 (local and CI).

Runs every validator exactly once, in a fixed order, and reports one summary:
  legacy validators -> V4 validators -> Skill Gateway snapshot compile/validate ->
  Model Mesh contract + snapshot compile/validate -> release + retrieval-index
  freshness -> consolidation invariants -> unit tests (optional)

Usage:
  python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)" [--skip-tests]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

VALIDATORS = (
    "AI_SKILL_LIBRARY/validate_registry.py",
    "AI_SKILL_LIBRARY/validate_brain.py",
    "AI_SKILL_LIBRARY/validate_router.py",
    "AI_SKILL_LIBRARY/validate_authority.py",
    "AI_SKILL_LIBRARY/validate_runtime.py",
    "AI_SKILL_LIBRARY/validate_v3.py",
    "AI_SKILL_LIBRARY/validate_v4.py",
    "AI_SKILL_LIBRARY/validate_skill_registry.py",
    "AI_SKILL_LIBRARY/validate_skill_gateway.py",
    "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh.py",
)


def _run(cmd: list[str], root: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _empty_quarantine_candidates(path: Path) -> None:
    payload = {
        "state": "quarantine",
        "routing_authority": False,
        "stable_mutation": False,
        "candidates": [],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_validators(
    root: Path,
    *,
    source_sha: str,
    include_tests: bool = True,
    snapshot_output: str | None = None,
    model_snapshot_output: str | None = None,
    model_candidates: str | None = None,
) -> list[str]:
    root = Path(root).resolve()
    failures: list[str] = []
    py = sys.executable
    for rel in VALIDATORS:
        code, out = _run([py, rel, "--root", str(root)] if rel.endswith("validate_model_mesh.py") else [py, rel], root)
        tail = out.splitlines()[-1] if out else ""
        print(f"{'PASS' if code == 0 else 'FAIL'} {rel}: {tail}")
        if code != 0:
            failures.append(f"{rel}: {tail}")

    snapshot = snapshot_output or "AI_SKILL_LIBRARY/v4/runtime/generated/skill-gateway-snapshot.json"
    code, out = _run([py, "AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py", "--source-sha", source_sha, "--output", snapshot], root)
    print(f"{'PASS' if code == 0 else 'FAIL'} compile_skill_gateway: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"compile_skill_gateway: {out}")
    else:
        code, out = _run([py, "AI_SKILL_LIBRARY/v4/tools/validate_skill_gateway_snapshot.py", snapshot], root)
        print(f"{'PASS' if code == 0 else 'FAIL'} validate_skill_gateway_snapshot: {out.splitlines()[-1] if out else ''}")
        if code != 0:
            failures.append(f"validate_skill_gateway_snapshot: {out}")

    model_snapshot = model_snapshot_output or "AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json"
    with tempfile.TemporaryDirectory(prefix="brain-model-mesh-") as temp_dir:
        if model_candidates:
            candidates_path = Path(model_candidates)
            if not candidates_path.is_absolute():
                candidates_path = root / candidates_path
        else:
            candidates_path = Path(temp_dir) / "empty-quarantine-candidates.json"
            _empty_quarantine_candidates(candidates_path)
        code, out = _run(
            [
                py,
                "AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_snapshot.py",
                "--root",
                str(root),
                "--source-sha",
                source_sha,
                "--candidates",
                str(candidates_path),
                "--output",
                model_snapshot,
            ],
            root,
        )
        print(f"{'PASS' if code == 0 else 'FAIL'} compile_model_mesh_snapshot: {out.splitlines()[-1] if out else ''}")
        if code != 0:
            failures.append(f"compile_model_mesh_snapshot: {out}")
        else:
            code, out = _run(
                [
                    py,
                    "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_snapshot.py",
                    model_snapshot,
                    "--root",
                    str(root),
                    "--source-sha",
                    source_sha,
                ],
                root,
            )
            print(f"{'PASS' if code == 0 else 'FAIL'} validate_model_mesh_snapshot: {out.splitlines()[-1] if out else ''}")
            if code != 0:
                failures.append(f"validate_model_mesh_snapshot: {out}")

    code, out = _run([py, "AI_SKILL_LIBRARY/v4/tools/release.py", "check", "--root", str(root)], root)
    print(f"{'PASS' if code == 0 else 'FAIL'} release check: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"release check: {out}")
    code, out = _run([py, "AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py", "--check", "--root", str(root)], root)
    print(f"{'PASS' if code == 0 else 'FAIL'} retrieval index check: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"retrieval index: {out}")
    code, out = _run([py, "AI_SKILL_LIBRARY/v4/tools/validate_consolidation.py", str(root)], root)
    print(f"{'PASS' if code == 0 else 'FAIL'} validate_consolidation: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"validate_consolidation: {out}")
    if include_tests:
        for start in ("AI_SKILL_LIBRARY/tests", "tests"):
            code, out = _run([py, "-m", "unittest", "discover", "-s", start, "-p", "test_*.py"], root)
            tail = [line for line in out.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
            print(f"{'PASS' if code == 0 else 'FAIL'} unittest {start}: {' | '.join(tail)}")
            if code != 0:
                failures.append(f"unittest {start}: {out[-2000:]}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True, help="exact git SHA the snapshots are compiled for")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--snapshot-output", default=None)
    parser.add_argument("--model-snapshot-output", default=None)
    parser.add_argument("--model-candidates", default=None, help="optional verified candidate report; omitted means a safe empty Stable pool")
    args = parser.parse_args()
    failures = run_validators(
        Path(args.root),
        source_sha=args.source_sha,
        include_tests=not args.skip_tests,
        snapshot_output=args.snapshot_output,
        model_snapshot_output=args.model_snapshot_output,
        model_candidates=args.model_candidates,
    )
    for item in failures:
        print(f"[ERROR] {item}")
    print(f"CI_VALIDATE={'PASS' if not failures else 'FAIL'} failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
