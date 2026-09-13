from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from config import DEFAULT_CONFIG, SYMBOLS
from g8.loop import run_generation


def _source_sha() -> str:
    return (
        os.getenv("GITHUB_SHA")
        or os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("DEPLOYMENT_SOURCE_SHA")
        or os.getenv("SOURCE_SHA")
        or "unknown"
    )


def _symbols(raw: str) -> list[str]:
    parsed = [part.strip().upper() for part in str(raw).split(",") if part.strip()]
    if not parsed:
        raise ValueError("at least one symbol is required")
    unknown = [symbol for symbol in parsed if symbol not in SYMBOLS]
    if unknown:
        raise ValueError("unsupported symbols: " + ",".join(unknown))
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded G8 Continuous BrainLoop research generation")
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--start", default=DEFAULT_CONFIG.start)
    parser.add_argument("--end", required=True)
    parser.add_argument("--state-dir", default=".g8-state")
    parser.add_argument("--results-dir", default="g8-results")
    parser.add_argument("--candidate-budget", type=int, default=4)
    parser.add_argument("--source-sha", default=_source_sha())
    parser.add_argument("--max-adaptive-trials", type=int, default=200)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_generation(
        _symbols(args.symbols),
        args.start,
        args.end,
        Path(args.state_dir),
        Path(args.results_dir),
        candidate_budget=args.candidate_budget,
        source_sha=args.source_sha,
        max_adaptive_trials=args.max_adaptive_trials,
    )
    print("G8_GENERATION_JSON=" + json.dumps(result.to_dict(), sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
