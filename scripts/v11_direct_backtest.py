#!/usr/bin/env python3
"""Owner-authorized direct V11 backtest wrapper.

Keeps the R5 engine isolated while correcting the mandatory daily execution gate:
eligible days come from exact cached market-data days, not from threshold-passing
candidate days, and the 1..3 cap is applied to actual next-bar execution date.
"""
from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import v11_backtest_mtf as engine
import v11_backtest_mtf_run as runner


def _day(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), timezone.utc).date().isoformat()


def _market_day(ts: int, market: str) -> bool:
    dt = datetime.fromtimestamp(int(ts), timezone.utc)
    return market == "crypto" or dt.weekday() < 5


def evaluate_candidates_direct(candidates, base_frame, rr, threshold, max_trades, market, start_ts, end_ts):
    # Eligible days are defined from the exact cached feed itself, independently
    # of the strategy threshold. This prevents zero-candidate days disappearing.
    eligible_days = {
        _day(r["ts"])
        for r in base_frame.rows
        if start_ts <= int(r["ts"]) < end_ts and _market_day(int(r["ts"]), market)
    }

    by_execution_day = defaultdict(list)
    for c in candidates:
        if c.get("score", -1) < threshold:
            continue
        i = int(c.get("i", -1))
        if i < 0 or i + 1 >= len(base_frame.rows):
            continue
        exec_ts = int(base_frame.rows[i + 1]["ts"])
        if not (start_ts <= exec_ts < end_ts):
            continue
        if not _market_day(exec_ts, market):
            continue
        item = dict(c)
        item["executionTs"] = exec_ts
        item["executionDay"] = _day(exec_ts)
        by_execution_day[item["executionDay"]].append(item)

    trades = []
    day_counts = defaultdict(int)
    signal_day_counts = defaultdict(int)
    traded_days = set()

    for day in sorted(eligible_days):
        ranked = sorted(by_execution_day.get(day, []), key=lambda x: x.get("score", 0), reverse=True)
        for c in ranked:
            if day_counts[day] >= max_trades:
                break
            res = engine.simulate_trade(base_frame, c, rr, market)
            if not res:
                continue
            signal_day = c.get("day") or _day(c.get("ts", c["executionTs"]))
            # Preserve <=3 on signal date too; execution-date cap is the primary user contract.
            if signal_day_counts[signal_day] >= 3:
                continue
            trade = {**c, **res, "signalDay": signal_day}
            trades.append(trade)
            day_counts[day] += 1
            signal_day_counts[signal_day] += 1
            traded_days.add(day)

    n = len(trades)
    tp = sum(1 for t in trades if t.get("outcome") == "TP")
    sl = sum(1 for t in trades if t.get("outcome") == "SL")
    timeout = sum(1 for t in trades if t.get("outcome") == "TIMEOUT")
    wr = 100.0 * tp / n if n else 0.0
    mean_r = statistics.mean([float(t.get("r", 0.0)) for t in trades]) if n else -9.0
    zero_days = sorted(eligible_days - traded_days)

    return {
        "trades": n,
        "daysTraded": len(traded_days),
        "eligibleDays": len(eligible_days),
        "coveragePct": round(100.0 * len(traded_days) / len(eligible_days), 2) if eligible_days else 0.0,
        "zeroExecutionDays": len(zero_days),
        "zeroExecutionDayExamples": zero_days[:12],
        "tp": tp,
        "sl": sl,
        "timeout": timeout,
        "winRate": round(wr, 2),
        "meanR": round(mean_r, 4),
        "maxTradesInDay": max(day_counts.values(), default=0),
        "maxSignalsInDay": max(signal_day_counts.values(), default=0),
        "dailyExecutionIntegrity": bool(eligible_days) and len(zero_days) == 0 and max(day_counts.values(), default=0) <= 3,
    }


def stats_ok_direct(s):
    return bool(s) and (
        s.get("trades", 0) > 0
        and s.get("dailyExecutionIntegrity") is True
        and s.get("coveragePct", 0) == 100.0
        and s.get("zeroExecutionDays", 1) == 0
        and 1 <= s.get("maxTradesInDay", 99) <= 3
        and s.get("maxSignalsInDay", 99) <= 3
        and s.get("winRate", 0) >= engine.REQUIRED_WR
        and s.get("meanR", -9) > 0
    )


# Patch only the research scoring surface used by select_profile/run_final.
engine.evaluate_candidates = evaluate_candidates_direct
engine.stats_ok = stats_ok_direct

if __name__ == "__main__":
    print("DIRECT_INTEGRITY_PATCH active eligible=data-days cap=actual-execution-day min=1 max=3", flush=True)
    raise SystemExit(runner.main())
