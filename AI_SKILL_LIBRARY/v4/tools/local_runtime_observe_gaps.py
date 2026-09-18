"""OBSERVE step: report gaps in the runtime/model plane. Changes nothing.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_observe_gaps.py --evidence /tmp/gaps.json

Reads the canonical registry and the committed evidence and reports what is
incomplete, each gap pointing at the existing tool that would close it. It
cannot edit, run, approve or advance anything - deciding what should change and
making the change are different jobs, and keeping them apart is what makes
self-development controlled rather than self-approving.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.gap_observer import observe  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="observe runtime/model gaps")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = observe(args.root)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    # Gaps are the normal state of a system still being built, not an error.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
