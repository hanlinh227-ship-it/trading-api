from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config import DEFAULT_CONFIG, SYMBOLS


def build_manifest(source_sha: str, start: str, end: str) -> dict:
    return {
        "venue": "Binance",
        "instrument": "USD-M perpetual",
        "symbols": list(SYMBOLS),
        "source_sha": source_sha,
        "start": start,
        "end": end,
        "target_rr": DEFAULT_CONFIG.rr_primary,
        "secondary_rr": DEFAULT_CONFIG.rr_secondary,
        "min_completed_trades": DEFAULT_CONFIG.min_completed_trades,
        "target_wr": DEFAULT_CONFIG.target_wr,
        "fee_bps_per_side": DEFAULT_CONFIG.costs.fee_bps_per_side,
        "slippage_bps_per_side": DEFAULT_CONFIG.costs.slippage_bps_per_side,
        "research_only": True,
    }


def write_report(results_dir: Path, manifest: dict, audits: dict, results: list) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "trades").mkdir(exist_ok=True)
    (results_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    (results_dir / "data_audit.json").write_text(json.dumps(audits, indent=2, sort_keys=True))
    profiles = {}
    rows = []
    md = ["# Cloud 10-Coin Backtest Report", "", f"Source SHA: `{manifest['source_sha']}`", "", "| Symbol | Status | Eval trades | RR2 WR | Expectancy R | Bottleneck |", "|---|---:|---:|---:|---:|---|"]
    for result in results:
        d = result.to_dict()
        profiles[result.symbol] = d.get("locked_profile")
        e = d["evaluation"]
        rows.append({"symbol": result.symbol, "status": result.status, **e, "bottlenecks": ",".join(result.bottlenecks)})
        md.append(f"| {result.symbol} | {result.status} | {e['completed_trades']} | {e['rr2_wr']:.2%} | {e['expectancy_r']:.3f} | {', '.join(result.bottlenecks)} |")
        if result.evaluation_trades:
            pd.DataFrame(result.evaluation_trades).to_csv(results_dir / "trades" / f"{result.symbol}.csv", index=False)
    (results_dir / "profiles.json").write_text(json.dumps(profiles, indent=2, sort_keys=True))
    pd.DataFrame(rows).to_csv(results_dir / "coin_summary.csv", index=False)
    (results_dir / "report.md").write_text("\n".join(md) + "\n")
