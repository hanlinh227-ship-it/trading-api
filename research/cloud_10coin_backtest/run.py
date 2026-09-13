from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DEFAULT_CONFIG, SYMBOLS
from data.cache import load_history
from engine.metrics import summarize_outcomes
from features.state import build_features
from optimize.search import CoinResearchResult, search_coin, search_coin_g2
from optimize.search_g3 import search_coin_g3
from optimize.search_g4 import search_coin_g4
from optimize.search_g5 import search_coin_g5
from optimize.search_g6 import search_coin_g6
from reporting import build_manifest, write_report


def parse_symbols(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return list(SYMBOLS)
    symbols = [x.strip().upper() for x in raw.split(",") if x.strip()]
    unknown = [x for x in symbols if x not in SYMBOLS]
    if unknown:
        raise ValueError(f"unsupported symbols: {','.join(unknown)}")
    if not symbols:
        raise ValueError("at least one symbol is required")
    return symbols


def build_final_summary(rows: list[dict]) -> dict:
    total = len(rows)
    pass_count = sum(row.get("status") == "PASS" for row in rows)
    return {"pass_count": pass_count, "total": total, "all_pass": total > 0 and pass_count == total}


def _default_end() -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()


def _source_sha() -> str:
    return os.getenv("GITHUB_SHA") or os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("DEPLOYMENT_SOURCE_SHA") or os.getenv("SOURCE_SHA") or "unknown"


def _empty_result(symbol: str, status: str, bottleneck: str) -> CoinResearchResult:
    zero = summarize_outcomes([])
    return CoinResearchResult(symbol, status, None, zero, zero, zero, zero, [bottleneck], [], [])


def _smoke_label(result: CoinResearchResult) -> CoinResearchResult:
    if result.evaluation.completed_trades >= DEFAULT_CONFIG.min_completed_trades:
        return result
    result.status = "NOT_EVALUATED"
    if "smoke-sample-below-hard-gate" not in result.bottlenecks:
        result.bottlenecks.insert(0, "smoke-sample-below-hard-gate")
    return result


def run_batch(symbols: list[str], start: str, end: str, smoke: bool = False, results_dir: Path | None = None, generation: str = "g2") -> tuple[list[CoinResearchResult], dict]:
    cfg = replace(DEFAULT_CONFIG, start=start, end=end, results_dir=results_dir or DEFAULT_CONFIG.results_dir)
    audits: dict[str, dict] = {}
    results: list[CoinResearchResult] = []
    if generation == "g6":
        search_fn = search_coin_g6
    elif generation == "g5":
        search_fn = search_coin_g5
    elif generation == "g4":
        search_fn = search_coin_g4
    elif generation == "g3":
        search_fn = search_coin_g3
    elif generation == "g2":
        search_fn = search_coin_g2
    else:
        search_fn = search_coin

    for symbol in symbols:
        print(f"COIN_START symbol={symbol} generation={generation} start={start} end={end}", flush=True)
        try:
            bars, audit_meta = load_history(symbol, "5m", start, end, cfg.cache_dir)
            audits[symbol] = audit_meta
            audit = audit_meta.get("audit", {})
            if not audit.get("ok", False):
                result = _empty_result(symbol, "DATA_FAIL", "data-quality-gate")
            else:
                features = build_features(bars)
                result = search_fn(symbol, features, cfg)
                if smoke:
                    result = _smoke_label(result)
        except Exception as exc:
            audits.setdefault(symbol, {})["runtime_error"] = f"{type(exc).__name__}: {exc}"
            result = _empty_result(symbol, "ERROR", f"runtime-error:{type(exc).__name__}")
            print(f"COIN_ERROR symbol={symbol} error={type(exc).__name__}:{exc}", flush=True)
        results.append(result)
        print("COIN_RESULT " + json.dumps(result.to_dict(), sort_keys=True), flush=True)

    manifest = build_manifest(source_sha=_source_sha(), start=start, end=end)
    manifest["requested_symbols"] = symbols
    manifest["smoke"] = smoke
    manifest["generation"] = generation
    write_report(cfg.results_dir, manifest, audits, results)
    summary = build_final_summary([{"symbol": r.symbol, "status": r.status} for r in results])
    summary["source_sha"] = manifest["source_sha"]
    summary["symbols"] = symbols
    summary["generation"] = generation
    summary["results_dir"] = str(cfg.results_dir)
    (cfg.results_dir / "final_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    print("FINAL_SUMMARY_JSON=" + json.dumps(summary, sort_keys=True), flush=True)
    return results, summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Isolated Binance USD-M ten-coin research backtest")
    p.add_argument("--symbols", default=",".join(SYMBOLS), help="comma-separated subset of locked 10-coin universe")
    p.add_argument("--start", default=DEFAULT_CONFIG.start)
    p.add_argument("--end", default=_default_end())
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--generation", choices=("g1", "g2", "g3", "g4", "g5", "g6"), default="g2")
    p.add_argument("--results-dir", default=str(DEFAULT_CONFIG.results_dir))
    return p


def main() -> int:
    args = build_parser().parse_args()
    symbols = parse_symbols(args.symbols)
    run_batch(symbols, args.start, args.end, smoke=args.smoke, results_dir=Path(args.results_dir), generation=args.generation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
