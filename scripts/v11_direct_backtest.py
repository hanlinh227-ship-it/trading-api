#!/usr/bin/env python3
"""Owner-authorized direct V11 research wrapper.

Research-only guarantees added here without changing production authority:
- eligible days come from exact cached market-data days after a fixed warm-up;
- every eligible execution day must contain 1..3 real executions;
- DEV, VALIDATION and untouched FINAL are chronologically disjoint;
- profile selection uses DEV/VALIDATION only;
- FINAL is replayed only with an already-frozen profile;
- Twelve Data paging is rate-limited for the serial research runner.
"""
from __future__ import annotations

import statistics
import sys
import time
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
        if not (start_ts <= exec_ts < end_ts) or not _market_day(exec_ts, market):
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
            if signal_day_counts[signal_day] >= 3:
                continue
            trades.append({**c, **res, "signalDay": signal_day})
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
        "dailyExecutionIntegrity": bool(eligible_days) and len(zero_days) == 0 and 1 <= max(day_counts.values(), default=0) <= 3,
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


def _boundaries(base_rows):
    # Fixed warm-up is eligibility logic, not strategy-dependent candidate filtering.
    warm = 61
    if len(base_rows) <= warm + 30:
        return None
    usable = len(base_rows) - warm
    dev_end_i = warm + max(1, int(usable * 0.60))
    val_end_i = warm + max(2, int(usable * 0.82))
    dev_end_i = min(dev_end_i, len(base_rows) - 2)
    val_end_i = min(max(val_end_i, dev_end_i + 1), len(base_rows) - 1)
    return {
        "devStart": int(base_rows[warm]["ts"]),
        "devEnd": int(base_rows[dev_end_i]["ts"]),
        "validationStart": int(base_rows[dev_end_i]["ts"]),
        "validationEnd": int(base_rows[val_end_i]["ts"]),
        "finalStart": int(base_rows[val_end_i]["ts"]),
        "finalEnd": int(base_rows[-1]["ts"]) + 1,
    }


def select_profile_direct(symbol, market, rows, cache_dir=None):
    if len(rows) < engine.MIN_BARS[engine.BASE_TF[market]]:
        return None, {"reason": "INSUFFICIENT_BARS", "bars": len(rows)}
    frames, btf, _ = engine.build_frames(market, rows)
    base = frames[btf]
    bounds = _boundaries(base.rows)
    if not bounds:
        return None, {"reason": "INSUFFICIENT_PARTITION_BARS", "bars": len(base.rows)}
    candidates = engine.build_or_load_candidates(symbol, market, rows, cache_dir)
    best = None
    for rr in engine.ALLOWED_RR:
        for threshold in engine.THRESHOLDS:
            for max_trades in engine.MAX_TRADES_OPTIONS:
                dev = evaluate_candidates_direct(candidates, base, rr, threshold, max_trades, market, bounds["devStart"], bounds["devEnd"])
                val = evaluate_candidates_direct(candidates, base, rr, threshold, max_trades, market, bounds["validationStart"], bounds["validationEnd"])
                rank = (
                    1 if stats_ok_direct(val) else 0,
                    float(val.get("coveragePct", 0)),
                    -int(val.get("zeroExecutionDays", 10**9)),
                    float(val.get("winRate", 0)),
                    float(val.get("meanR", -9)),
                    float(dev.get("coveragePct", 0)),
                    float(dev.get("winRate", 0)),
                    float(dev.get("meanR", -9)),
                )
                profile = {
                    "rr": float(rr),
                    "threshold": float(threshold),
                    "maxTrades": int(max_trades),
                    **bounds,
                    "partitionPolicy": "DEV_60_VALIDATION_22_FINAL_18_AFTER_FIXED_WARMUP",
                }
                if best is None or rank > best[0]:
                    best = (rank, profile, dev, val)
    if not best:
        return None, {"reason": "NO_CANDIDATE"}
    return best[1], {"dev": best[2], "validation": best[3]}


def run_fast_direct(symbol, market, rows, cache_dir=None):
    profile, ev = select_profile_direct(symbol, market, rows, cache_dir)
    val = ev.get("validation") or {}
    ok = bool(profile) and stats_ok_direct(val)
    return {
        "symbol": symbol,
        "market": market,
        "mode": "fast",
        "pass": ok,
        "reasons": [] if ok else ["NO_DEV_PROFILE" if not profile else "VALIDATION_FAIL"],
        "profile": profile,
        "dev": ev.get("dev"),
        "validation": val,
    }


def run_final_direct(symbol, market, rows, cache_dir, profile):
    required = ("rr", "threshold", "maxTrades", "finalStart", "finalEnd", "validationEnd")
    if not profile or any(k not in profile for k in required):
        return {"symbol": symbol, "market": market, "mode": "final", "pass": False, "reasons": ["UNSEALED_PROFILE"], "profile": profile, "oos": {}}
    if int(profile["finalStart"]) != int(profile["validationEnd"]):
        return {"symbol": symbol, "market": market, "mode": "final", "pass": False, "reasons": ["FINAL_BOUNDARY_MISMATCH"], "profile": profile, "oos": {}}
    frames, btf, _ = engine.build_frames(market, rows)
    base = frames[btf]
    candidates = engine.build_or_load_candidates(symbol, market, rows, cache_dir)
    oos = evaluate_candidates_direct(
        candidates,
        base,
        float(profile["rr"]),
        float(profile["threshold"]),
        int(profile["maxTrades"]),
        market,
        int(profile["finalStart"]),
        int(profile["finalEnd"]),
    )
    ok = stats_ok_direct(oos)
    return {"symbol": symbol, "market": market, "mode": "final", "pass": ok, "reasons": [] if ok else ["OOS_FAIL"], "profile": profile, "oos": oos}


# Twelve Data Grow-plan-safe serial paging. The workflow intentionally uses one shard
# while cache is being populated, so this limiter is process-global and deterministic.
_original_get_json = runner.dcache.get_json
_last_td_call = 0.0


def _research_get_json(url, timeout=45, retries=4, headers=None):
    global _last_td_call
    if "api.twelvedata.com" not in str(url):
        return _original_get_json(url, timeout, retries, headers)
    for attempt in range(4):
        elapsed = time.monotonic() - _last_td_call
        if elapsed < 1.35:
            time.sleep(1.35 - elapsed)
        _last_td_call = time.monotonic()
        try:
            return _original_get_json(url, timeout, retries, headers)
        except Exception as e:
            if "429" not in str(e) or attempt == 3:
                raise
            time.sleep(15.0 * (attempt + 1))
    raise RuntimeError("TWELVEDATA_RATE_LIMIT_EXHAUSTED")


runner.dcache.get_json = _research_get_json
engine.dcache.get_json = _research_get_json
engine.evaluate_candidates = evaluate_candidates_direct
engine.stats_ok = stats_ok_direct
engine.select_profile = select_profile_direct
engine.run_fast = run_fast_direct
engine.run_final = run_final_direct

if __name__ == "__main__":
    print("DIRECT_RESEARCH_R2 integrity=1..3_per_eligible_day partitions=DEV/VALIDATION/UNTOUCHED_FINAL td_serial_rate_limit=on", flush=True)
    raise SystemExit(runner.main())
