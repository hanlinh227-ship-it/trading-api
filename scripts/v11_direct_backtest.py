#!/usr/bin/env python3
"""Owner-authorized direct V11 research wrapper.

Research-only. Production Signal V11/TRADING_STATE are untouched.

Integrity guarantees:
- exact cached instrument/source metadata is required;
- OHLC/timestamp integrity is checked before research use;
- crypto 4H history must be continuous because crypto is 24/7;
- DEV / VALIDATION / untouched FINAL are disjoint and day-aligned;
- candidate outcome horizons are fully contained inside each partition;
- every eligible execution day must contain 1..3 real executions;
- both DEV and VALIDATION must independently pass before a profile can qualify;
- RR is only 1:1 or 1:2;
- FINAL verifies a deterministic profile seal, data hash, source and canonical boundaries.
"""
from __future__ import annotations

import hashlib
import json
import math
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

DIRECT_VERSION = "V11-DIRECT-RESEARCH-R3"
_DATA_META = {}


def _day(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), timezone.utc).date().isoformat()


def _day_start(ts: int) -> int:
    return (int(ts) // 86400) * 86400


def _market_day(ts: int, market: str) -> bool:
    dt = datetime.fromtimestamp(int(ts), timezone.utc)
    return market == "crypto" or dt.weekday() < 5


def _hold_bars(base_frame) -> int:
    return max(6, int(12 * 3600 / base_frame.seconds))


def _valid_execution_slots(base_frame, market, start_ts, end_ts):
    """Strategy-independent execution slots whose full outcome horizon is inside partition."""
    hold = _hold_bars(base_frame)
    slots = set()
    raw_days = set()
    for k, row in enumerate(base_frame.rows):
        ts = int(row["ts"])
        if not (start_ts <= ts < end_ts) or not _market_day(ts, market):
            continue
        raw_days.add(_day(ts))
        if k < 61:
            continue
        last = k + hold - 1
        if last >= len(base_frame.rows):
            continue
        last_close = int(base_frame.rows[last]["ts"]) + int(base_frame.seconds)
        if last_close <= end_ts:
            slots.add(k)
    eligible_days = {_day(base_frame.rows[k]["ts"]) for k in slots}
    return slots, eligible_days, sorted(raw_days - eligible_days)


def evaluate_candidates_direct(candidates, base_frame, rr, threshold, max_trades, market, start_ts, end_ts):
    slots, eligible_days, boundary_excluded = _valid_execution_slots(base_frame, market, start_ts, end_ts)
    by_execution_day = defaultdict(list)
    for c in candidates:
        if c.get("score", -1) < threshold:
            continue
        i = int(c.get("i", -1))
        k = i + 1
        if i < 0 or k not in slots:
            continue
        exec_ts = int(base_frame.rows[k]["ts"])
        item = dict(c)
        item["executionTs"] = exec_ts
        item["executionDay"] = _day(exec_ts)
        by_execution_day[item["executionDay"]].append(item)

    trades = []
    day_counts = defaultdict(int)
    traded_days = set()
    for day in sorted(eligible_days):
        ranked = sorted(by_execution_day.get(day, []), key=lambda x: x.get("score", 0), reverse=True)
        for c in ranked:
            if day_counts[day] >= int(max_trades):
                break
            res = engine.simulate_trade(base_frame, c, rr, market)
            if not res:
                continue
            trades.append({**c, **res, "signalDay": c.get("day"), "executionDay": day})
            day_counts[day] += 1
            traded_days.add(day)

    n = len(trades)
    tp = sum(1 for t in trades if t.get("outcome") == "TP")
    sl = sum(1 for t in trades if t.get("outcome") == "SL")
    timeout = sum(1 for t in trades if t.get("outcome") == "TIMEOUT")
    wr = 100.0 * tp / n if n else 0.0
    mean_r = statistics.mean([float(t.get("r", 0.0)) for t in trades]) if n else -9.0
    zero_days = sorted(eligible_days - traded_days)
    min_day = min(day_counts.values(), default=0)
    max_day = max(day_counts.values(), default=0)
    return {
        "trades": n,
        "daysTraded": len(traded_days),
        "eligibleDays": len(eligible_days),
        "coveragePct": round(100.0 * len(traded_days) / len(eligible_days), 2) if eligible_days else 0.0,
        "zeroExecutionDays": len(zero_days),
        "zeroExecutionDayExamples": zero_days[:12],
        "boundaryExcludedDays": len(boundary_excluded),
        "boundaryExcludedDayExamples": boundary_excluded[:6],
        "tp": tp,
        "sl": sl,
        "timeout": timeout,
        "winRate": round(wr, 2),
        "meanR": round(mean_r, 4),
        "minTradesInDay": min_day,
        "maxTradesInDay": max_day,
        "dailyExecutionIntegrity": bool(eligible_days) and len(zero_days) == 0 and 1 <= min_day <= max_day <= 3,
    }


def stats_ok_direct(s):
    return bool(s) and (
        s.get("trades", 0) > 0
        and s.get("dailyExecutionIntegrity") is True
        and s.get("coveragePct", 0) == 100.0
        and s.get("zeroExecutionDays", 1) == 0
        and 1 <= s.get("minTradesInDay", 0) <= s.get("maxTradesInDay", 99) <= 3
        and s.get("winRate", 0) >= engine.REQUIRED_WR
        and s.get("meanR", -9) > 0
    )


def _boundaries(base_rows, market):
    if len(base_rows) <= 100:
        return None
    observed = sorted({_day_start(r["ts"]) for r in base_rows[61:] if _market_day(r["ts"], market)})
    # Dataset endpoints are arbitrary UTC times; drop the two boundary dates so all
    # tuning/evaluation partitions start and end on explicit day boundaries.
    if len(observed) < 12:
        return None
    days = observed[1:-1]
    n = len(days)
    dev_n = max(1, int(n * 0.60))
    val_n = max(1, int(n * 0.22))
    if dev_n + val_n >= n:
        return None
    return {
        "devStart": int(days[0]),
        "devEnd": int(days[dev_n]),
        "validationStart": int(days[dev_n]),
        "validationEnd": int(days[dev_n + val_n]),
        "finalStart": int(days[dev_n + val_n]),
        "finalEnd": int(days[-1] + 86400),
        "partitionDays": {"total": n, "dev": dev_n, "validation": val_n, "final": n - dev_n - val_n},
    }


def _profile_seal(profile):
    body = {k: v for k, v in profile.items() if k != "seal"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _meta_for(symbol, market, rows):
    m = dict(_DATA_META.get(symbol) or {})
    m.setdefault("dataHash", runner.dcache.compute_data_hash(rows))
    m.setdefault("exact", False)
    m.setdefault("source", "UNKNOWN")
    m.setdefault("instrument", "UNKNOWN")
    m["market"] = market
    return m


def _make_profile(symbol, market, rows, rr, threshold, max_trades, bounds):
    meta = _meta_for(symbol, market, rows)
    p = {
        "symbol": symbol,
        "market": market,
        "rr": float(rr),
        "threshold": float(threshold),
        "maxTrades": int(max_trades),
        **bounds,
        "partitionPolicy": "DAY_ALIGNED_DEV60_VALIDATION22_FINAL18_AFTER_FIXED_WARMUP",
        "directVersion": DIRECT_VERSION,
        "engineVersion": str(engine.VERSION),
        "featureSchema": str(engine.FEATURE_SCHEMA),
        "dataHash": meta.get("dataHash"),
        "source": meta.get("source"),
        "instrument": meta.get("instrument"),
        "exact": bool(meta.get("exact")),
    }
    p["seal"] = _profile_seal(p)
    return p


def select_profile_direct(symbol, market, rows, cache_dir=None):
    if len(rows) < engine.MIN_BARS[engine.BASE_TF[market]]:
        return None, {"reason": "INSUFFICIENT_BARS", "bars": len(rows)}
    frames, btf, _ = engine.build_frames(market, rows)
    base = frames[btf]
    bounds = _boundaries(base.rows, market)
    if not bounds:
        return None, {"reason": "INSUFFICIENT_PARTITION_BARS", "bars": len(base.rows)}
    meta = _meta_for(symbol, market, rows)
    if not meta.get("exact"):
        return None, {"reason": "DATA_NOT_EXACT"}
    candidates = engine.build_or_load_candidates(symbol, market, rows, cache_dir)
    best = None
    for rr in engine.ALLOWED_RR:
        for threshold in engine.THRESHOLDS:
            for max_trades in engine.MAX_TRADES_OPTIONS:
                dev = evaluate_candidates_direct(candidates, base, rr, threshold, max_trades, market, bounds["devStart"], bounds["devEnd"])
                val = evaluate_candidates_direct(candidates, base, rr, threshold, max_trades, market, bounds["validationStart"], bounds["validationEnd"])
                dev_ok = stats_ok_direct(dev)
                val_ok = stats_ok_direct(val)
                rank = (
                    1 if dev_ok and val_ok else 0,
                    min(float(dev.get("coveragePct", 0)), float(val.get("coveragePct", 0))),
                    -int(dev.get("zeroExecutionDays", 10**9)) - int(val.get("zeroExecutionDays", 10**9)),
                    min(float(dev.get("winRate", 0)), float(val.get("winRate", 0))),
                    min(float(dev.get("meanR", -9)), float(val.get("meanR", -9))),
                    float(val.get("winRate", 0)),
                )
                profile = _make_profile(symbol, market, rows, rr, threshold, max_trades, bounds)
                if best is None or rank > best[0]:
                    best = (rank, profile, dev, val, dev_ok, val_ok)
    if not best:
        return None, {"reason": "NO_CANDIDATE"}
    return best[1], {"dev": best[2], "validation": best[3], "devPass": best[4], "validationPass": best[5]}


def run_fast_direct(symbol, market, rows, cache_dir=None):
    profile, ev = select_profile_direct(symbol, market, rows, cache_dir)
    dev = ev.get("dev") or {}
    val = ev.get("validation") or {}
    ok = bool(profile) and stats_ok_direct(dev) and stats_ok_direct(val)
    reasons = []
    if not profile:
        reasons.append(ev.get("reason") or "NO_DEV_PROFILE")
    else:
        if not stats_ok_direct(dev): reasons.append("DEV_FAIL")
        if not stats_ok_direct(val): reasons.append("VALIDATION_FAIL")
    return {"symbol": symbol, "market": market, "mode": "fast", "pass": ok, "reasons": reasons, "profile": profile, "dev": dev, "validation": val}


def run_final_direct(symbol, market, rows, cache_dir, profile):
    required = ("symbol", "market", "rr", "threshold", "maxTrades", "devStart", "devEnd", "validationStart", "validationEnd", "finalStart", "finalEnd", "dataHash", "source", "instrument", "exact", "seal")
    if not profile or any(k not in profile for k in required):
        return {"symbol": symbol, "market": market, "mode": "final", "pass": False, "reasons": ["UNSEALED_PROFILE"], "profile": profile, "oos": {}}
    problems = []
    if str(profile.get("seal")) != _profile_seal(profile): problems.append("PROFILE_SEAL_MISMATCH")
    if profile.get("symbol") != symbol or profile.get("market") != market: problems.append("PROFILE_IDENTITY_MISMATCH")
    if float(profile.get("rr", -1)) not in tuple(float(x) for x in engine.ALLOWED_RR): problems.append("RR_NOT_ALLOWED")
    if float(profile.get("threshold", -9)) not in tuple(float(x) for x in engine.THRESHOLDS): problems.append("THRESHOLD_NOT_ALLOWED")
    if int(profile.get("maxTrades", -1)) not in tuple(int(x) for x in engine.MAX_TRADES_OPTIONS): problems.append("MAX_TRADES_NOT_ALLOWED")
    frames, btf, _ = engine.build_frames(market, rows)
    base = frames[btf]
    canonical = _boundaries(base.rows, market)
    if not canonical:
        problems.append("CANONICAL_BOUNDARY_UNAVAILABLE")
    else:
        for k in ("devStart", "devEnd", "validationStart", "validationEnd", "finalStart", "finalEnd"):
            if int(profile.get(k, -1)) != int(canonical.get(k, -2)): problems.append("BOUNDARY_MISMATCH_" + k)
    meta = _meta_for(symbol, market, rows)
    if not meta.get("exact"): problems.append("DATA_NOT_EXACT")
    if profile.get("dataHash") != meta.get("dataHash"): problems.append("DATA_HASH_MISMATCH")
    if profile.get("source") != meta.get("source"): problems.append("DATA_SOURCE_MISMATCH")
    if profile.get("instrument") != meta.get("instrument"): problems.append("INSTRUMENT_MISMATCH")
    if problems:
        return {"symbol": symbol, "market": market, "mode": "final", "pass": False, "reasons": problems, "profile": profile, "oos": {}}
    candidates = engine.build_or_load_candidates(symbol, market, rows, cache_dir)
    oos = evaluate_candidates_direct(candidates, base, float(profile["rr"]), float(profile["threshold"]), int(profile["maxTrades"]), market, int(profile["finalStart"]), int(profile["finalEnd"]))
    ok = stats_ok_direct(oos)
    return {"symbol": symbol, "market": market, "mode": "final", "pass": ok, "reasons": [] if ok else ["OOS_FAIL"], "profile": profile, "oos": oos}


def _validate_rows(symbol, market, entry):
    if not entry or entry.get("exact") is not True:
        return False, "EXACT_FLAG_REQUIRED"
    rows = entry.get("rows") or []
    if not rows:
        return False, "ROWS_EMPTY"
    base_sec = int(engine.TF_SECONDS[engine.BASE_TF[market]])
    prev = None
    for n, r in enumerate(rows):
        if not isinstance(r, (list, tuple)) or len(r) < 6:
            return False, f"ROW_SHAPE_{n}"
        try:
            ts = int(r[0]); o,h,l,c = map(float, r[1:5]); v=float(r[5] or 0)
        except Exception:
            return False, f"ROW_PARSE_{n}"
        if prev is not None and ts <= prev:
            return False, f"TIMESTAMP_ORDER_{n}"
        if ts % base_sec != 0:
            return False, f"TIMESTAMP_ALIGNMENT_{n}"
        if not all(math.isfinite(x) for x in (o,h,l,c,v)) or min(o,h,l,c) <= 0 or v < 0:
            return False, f"NUMERIC_INVALID_{n}"
        if not (l <= min(o,c) <= max(o,c) <= h):
            return False, f"OHLC_INVALID_{n}"
        if market == "crypto" and prev is not None and ts - prev != base_sec:
            return False, f"CRYPTO_GAP_{prev}_{ts}"
        prev = ts
    return True, "OK"


_original_load_cache = runner.dcache.load_cache


def _research_load_cache(cache_dir, symbol, market, start_ts, end_ts):
    entry, spec, key = _original_load_cache(cache_dir, symbol, market, start_ts, end_ts)
    if not entry:
        return entry, spec, key
    ok, reason = _validate_rows(symbol, market, entry)
    if not ok:
        print("CACHE_INTEGRITY_FAIL", market, symbol, reason, flush=True)
        return None, spec, key
    _DATA_META[symbol] = {
        "exact": True,
        "source": str(entry.get("source") or "UNKNOWN"),
        "instrument": str(entry.get("instrument") or spec.get("instrument") or "UNKNOWN"),
        "dataHash": runner.dcache.compute_data_hash(entry.get("rows") or []),
    }
    return entry, spec, key


# Twelve Data Grow-plan-safe serial paging. The workflow populates cache with one
# process, avoiding cross-shard request bursts.
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
runner.dcache.load_cache = _research_load_cache
engine.dcache.load_cache = _research_load_cache
engine.evaluate_candidates = evaluate_candidates_direct
engine.stats_ok = stats_ok_direct
engine.select_profile = select_profile_direct
engine.run_fast = run_fast_direct
engine.run_final = run_final_direct

if __name__ == "__main__":
    print(DIRECT_VERSION, "integrity=partition_safe+sealed_profile+DEV_and_VALIDATION+1..3_daily", flush=True)
    raise SystemExit(runner.main())
