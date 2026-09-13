from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from config import DEFAULT_CONFIG, SYMBOLS
from g9.lane_runner import execute_adaptive_lane


def _source_sha() -> str:
    return (
        os.getenv("GITHUB_SHA")
        or os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("DEPLOYMENT_SOURCE_SHA")
        or os.getenv("SOURCE_SHA")
        or "unknown"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one bounded adaptive G9 research lane")
    parser.add_argument("--symbol", required=True, choices=SYMBOLS)
    parser.add_argument("--start", default=DEFAULT_CONFIG.start)
    parser.add_argument("--end", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--candidate-budget", type=int, default=4)
    parser.add_argument("--source-sha", default=_source_sha())
    parser.add_argument("--max-adaptive-trials", type=int, default=200)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = execute_adaptive_lane(
        args.symbol,
        args.start,
        args.end,
        Path(args.state_dir),
        Path(args.results_dir),
        candidate_budget=args.candidate_budget,
        source_sha=args.source_sha,
        max_adaptive_trials=args.max_adaptive_trials,
    )
    print("G9_LANE_JSON=" + json.dumps(payload, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
