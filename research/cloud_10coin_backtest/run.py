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
from optimize.search import CoinResearchResult, search_coin
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
    return {
        "pass_count": pass_count,
        "total": total,
        "all_pass": total > 0 and pass_count == total,
    }


def _default_end() -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()


def _source_sha() -> str:
    return (
        os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("DEPLOYMENT_SOURCE_SHA")
        or os.getenv("SOURCE_SHA")
        or "unknown"
    )


def _empty_result(symbol: str, status: str, bottleneck: str) -> CoinResearchResult:
    zero = summarize_outcomes([])
    return CoinResearchResult(
        symbol=symbol,
        status=status,
        locked_profile=None,
        development=zero,
        validation=zero,
        holdout=zero,
        evaluation=zero,
        bottlenecks=[bottleneck],
        rejected_candidates=[],
        evaluation_trades=[],
    )


def _smoke_label(result: CoinResearchResult) -> CoinResearchResult:
    if result.evaluation.completed_trades >= DEFAULT_CONFIG.min_completed_trades:
        return result
    result.status = "NOT_EVALUATED"
    if "smoke-sample-below-hard-gate" not in result.bottlenecks:
        result.bottlenecks.insert(0, "smoke-sample-below-hard-gate")
    return result


def run_batch(symbols: list[str], start: str, end: str, smoke: bool = False, results_dir: Path | None = None) -> tuple[list[CoinResearchResult], dict]:
    cfg = replace(
        DEFAULT_CONFIG,
        start=start,
        end=end,
        results_dir=results_dir or DEFAULT_CONFIG.results_dir,
    )
    audits: dict[str, dict] = {}
    results: list[CoinResearchResult] = []

    for symbol in symbols:
        print(f"COIN_START symbol={symbol} start={start} end={end}", flush=True)
        try:
            bars, audit_meta = load_history(symbol, "5m", start, end, cfg.cache_dir)
            audits[symbol] = audit_meta
            audit = audit_meta.get("audit", {})
            if not audit.get("ok", False):
                result = _empty_result(symbol, "DATA_FAIL", "data-quality-gate")
            else:
                features = build_features(bars)
                result = search_coin(symbol, features, cfg)
                if smoke:
                    result = _smoke_label(result)
        except Exception as exc:
            audits.setdefault(symbol, {})["runtime_error"] = f"{type(exc).__name__}: {exc}"
            result = _empty_result(symbol, "ERROR", f"runtime-error:{type(exc).__name__}")
            print(f"COIN_ERROR symbol={symbol} error={type(exc).__name__}:{exc}", flush=True)
        results.append(result)
        payload = result.to_dict()
        print("COIN_RESULT " + json.dumps(payload, sort_keys=True), flush=True)

    manifest = build_manifest(source_sha=_source_sha(), start=start, end=end)
    manifest["requested_symbols"] = symbols
    manifest["smoke"] = smoke
    write_report(cfg.results_dir, manifest, audits, results)
    summary_rows = [{"symbol": r.symbol, "status": r.status} for r in results]
    summary = build_final_summary(summary_rows)
    summary["source_sha"] = manifest["source_sha"]
    summary["symbols"] = symbols
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
    p.add_argument("--results-dir", default=str(DEFAULT_CONFIG.results_dir))
    return p


def main() -> int:
    args = build_parser().parse_args()
    symbols = parse_symbols(args.symbols)
    run_batch(symbols, args.start, args.end, smoke=args.smoke, results_dir=Path(args.results_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
