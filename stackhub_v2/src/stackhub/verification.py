from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence
import re
import subprocess


_SECRET_PATTERNS = (
    re.compile(r"tb_live_[A-Za-z0-9_-]{12,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(seed phrase|mnemonic)\b\s*[:=]"),
)


@dataclass(frozen=True)
class VerificationEvidence:
    test_command: tuple[str, ...]
    exit_code: int
    stdout_tail: str
    stderr_tail: str
    diff_path: str
    passed: bool


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _tail(value: str, limit: int = 8192) -> str:
    return value[-limit:]


def verify_workspace(
    path: Path,
    test_command: Sequence[str],
    *,
    solver_root: Path,
    diff_path: Path,
    timeout_seconds: int = 900,
) -> VerificationEvidence:
    path = Path(path)
    solver_root = Path(solver_root)
    diff_path = Path(diff_path)

    if not test_command:
        raise ValueError("test command is required")
    if not _contained(path, solver_root) or not _contained(diff_path, solver_root):
        raise ValueError("solver workspace must remain inside solver_root")
    if not path.is_dir():
        raise ValueError("solver workspace does not exist")

    try:
        diff_text = diff_path.read_text(encoding="utf-8")
    except OSError:
        diff_text = ""

    secret_free = bool(diff_text.strip()) and not any(pattern.search(diff_text) for pattern in _SECRET_PATTERNS)

    try:
        result = subprocess.run(
            list(test_command),
            cwd=path,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
            shell=False,
        )
        exit_code = int(result.returncode)
        stdout = result.stdout or ""
        stderr = result.stderr or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else "timeout"

    passed = exit_code == 0 and secret_free
    return VerificationEvidence(
        test_command=tuple(test_command),
        exit_code=exit_code,
        stdout_tail=_tail(stdout),
        stderr_tail=_tail(stderr),
        diff_path=str(diff_path),
        passed=passed,
    )
