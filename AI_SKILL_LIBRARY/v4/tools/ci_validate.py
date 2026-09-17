"""Single validation entrypoint for GITHUB_BRAIN_V4 (local and CI).

Runs every validator exactly once, in a fixed order, and reports one summary:
  legacy validators -> V4 validators -> Universal Fabric + Model Mesh + Open Model Universe + Legion safety validators ->
  Skill Gateway snapshot compile/validate -> Model Mesh snapshot compile/validate ->
  Active Candidate Index compile/validate -> release + retrieval-index freshness ->
  consolidation invariants -> unit tests (optional)

Production Model Mesh compilation defaults to the canonical promoted active registry.
An explicit --model-candidates path remains available for quarantine/candidate tests.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ACTIVE_REGISTRY = "AI_SKILL_LIBRARY/v4/model_mesh/active.json"
DEFAULT_ACTIVE_INDEX = "AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-active-candidate-index.json"
DEFAULT_CAPABILITY_LEDGER = "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json"

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
    "AI_SKILL_LIBRARY/v4/tools/validate_universal_fabric.py",
    "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh.py",
    "AI_SKILL_LIBRARY/v4/tools/validate_open_model_universe.py",
    "AI_SKILL_LIBRARY/v4/tools/validate_legion.py",
    "AI_SKILL_LIBRARY/v4/tools/validate_brain_expansion.py",
)


def _run(cmd: list[str], root: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _compile_skill_snapshot(py: str, root: Path, source_sha: str, snapshot: str, *, label: str = "") -> list[str]:
    failures: list[str] = []
    prefix = f"{label} " if label else ""
    code, out = _run([py, "AI_SKILL_LIBRARY/v4/tools/compile_skill_gateway.py", "--source-sha", source_sha, "--output", snapshot], root)
    print(f"{'PASS' if code == 0 else 'FAIL'} {prefix}compile_skill_gateway: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"{prefix}compile_skill_gateway: {out}")
        return failures
    code, out = _run([py, "AI_SKILL_LIBRARY/v4/tools/validate_skill_gateway_snapshot.py", snapshot], root)
    print(f"{'PASS' if code == 0 else 'FAIL'} {prefix}validate_skill_gateway_snapshot: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"{prefix}validate_skill_gateway_snapshot: {out}")
    return failures


def _compile_model_snapshot(
    py: str,
    root: Path,
    source_sha: str,
    model_snapshot: str,
    *,
    model_candidates: str | None = None,
    active_registry: str = DEFAULT_ACTIVE_REGISTRY,
    active_index: str = DEFAULT_ACTIVE_INDEX,
    label: str = "",
) -> list[str]:
    failures: list[str] = []
    prefix = f"{label} " if label else ""

    code, out = _run(
        [py, "AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_policy.py", "--root", str(root)],
        root,
    )
    print(f"{'PASS' if code == 0 else 'FAIL'} {prefix}compile_model_mesh_policy: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"{prefix}compile_model_mesh_policy: {out}")
        return failures

    cmd = [
        py,
        "AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_snapshot.py",
        "--root",
        str(root),
        "--source-sha",
        source_sha,
        "--output",
        model_snapshot,
    ]
    if model_candidates:
        cmd.extend(["--candidates", model_candidates])
    else:
        cmd.extend(["--active-registry", active_registry])
    code, out = _run(cmd, root)
    print(f"{'PASS' if code == 0 else 'FAIL'} {prefix}compile_model_mesh_snapshot: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"{prefix}compile_model_mesh_snapshot: {out}")
        return failures

    code, out = _run(
        [py, "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_snapshot.py", model_snapshot, "--root", str(root), "--source-sha", source_sha],
        root,
    )
    print(f"{'PASS' if code == 0 else 'FAIL'} {prefix}validate_model_mesh_snapshot: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"{prefix}validate_model_mesh_snapshot: {out}")
        return failures

    code, out = _run(
        [
            py,
            "AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_active_index.py",
            "--root",
            str(root),
            "--source-sha",
            source_sha,
            "--snapshot",
            model_snapshot,
            "--ledger",
            DEFAULT_CAPABILITY_LEDGER,
            "--output",
            active_index,
        ],
        root,
    )
    print(f"{'PASS' if code == 0 else 'FAIL'} {prefix}compile_model_mesh_active_index: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"{prefix}compile_model_mesh_active_index: {out}")
        return failures

    code, out = _run(
        [
            py,
            "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_active_index.py",
            active_index,
            "--root",
            str(root),
            "--snapshot",
            model_snapshot,
            "--source-sha",
            source_sha,
        ],
        root,
    )
    print(f"{'PASS' if code == 0 else 'FAIL'} {prefix}validate_model_mesh_active_index: {out.splitlines()[-1] if out else ''}")
    if code != 0:
        failures.append(f"{prefix}validate_model_mesh_active_index: {out}")
    return failures


def run_validators(
    root: Path,
    *,
    source_sha: str,
    include_tests: bool = True,
    snapshot_output: str | None = None,
    model_snapshot_output: str | None = None,
    model_candidates: str | None = None,
    active_registry: str = DEFAULT_ACTIVE_REGISTRY,
) -> list[str]:
    root = Path(root).resolve()
    failures: list[str] = []
    py = sys.executable
    rooted = {
        "validate_universal_fabric.py",
        "validate_model_mesh.py",
        "validate_open_model_universe.py",
        "validate_legion.py",
    }
    for rel in VALIDATORS:
        cmd = [py, rel]
        if Path(rel).name in rooted:
            cmd.extend(["--root", str(root)])
        code, out = _run(cmd, root)
        tail = out.splitlines()[-1] if out else ""
        print(f"{'PASS' if code == 0 else 'FAIL'} {rel}: {tail}")
        if code != 0:
            failures.append(f"{rel}: {tail}")

    snapshot = snapshot_output or "AI_SKILL_LIBRARY/v4/runtime/generated/skill-gateway-snapshot.json"
    model_snapshot = model_snapshot_output or "AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json"
    failures.extend(_compile_skill_snapshot(py, root, source_sha, snapshot))
    failures.extend(_compile_model_snapshot(py, root, source_sha, model_snapshot, model_candidates=model_candidates, active_registry=active_registry))

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

        failures.extend(_compile_skill_snapshot(py, root, source_sha, snapshot, label="finalize_exact_sha"))
        failures.extend(
            _compile_model_snapshot(
                py,
                root,
                source_sha,
                model_snapshot,
                model_candidates=model_candidates,
                active_registry=active_registry,
                label="finalize_exact_sha",
            )
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True, help="exact git SHA the snapshots are compiled for")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--snapshot-output", default=None)
    parser.add_argument("--model-snapshot-output", default=None)
    parser.add_argument("--model-candidates", default=None, help="optional verified quarantine candidate report; overrides active registry")
    parser.add_argument("--active-registry", default=DEFAULT_ACTIVE_REGISTRY, help="canonical promoted FREE_ONLY model registry")
    args = parser.parse_args()
    failures = run_validators(
        Path(args.root),
        source_sha=args.source_sha,
        include_tests=not args.skip_tests,
        snapshot_output=args.snapshot_output,
        model_snapshot_output=args.model_snapshot_output,
        model_candidates=args.model_candidates,
        active_registry=args.active_registry,
    )
    for item in failures:
        print(f"[ERROR] {item}")
    print(f"CI_VALIDATE={'PASS' if not failures else 'FAIL'} failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
