#!/usr/bin/env python3
"""Runtime repair + legacy-learning layer for V11 four-month backtest.

This wrapper keeps the base research engine isolated from production runtime while
strengthening four areas:
- exact historical-data fanout for every V11 market class;
- safe legacy-prior ingestion from V73 / Symbol Knowledge / V76 research;
- exact-timestamp chronological walk-forward evaluation;
- hard dedupe/cap so no symbol can exceed its calibrated <=3 entries/day.

Historical priors remain priors only. Fresh walk-forward evidence always decides
PASS/FAIL. This module never deploys, trades, or unlocks Signal V11.
"""
from __future__ import annotations

import importlib.util
import json
import lzma
import math
import statistics
import struct
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "scripts/v11_backtest_legacy_ml_4m.py"
REGISTRY = ROOT / "data/symbol_knowledge_registry.json"
V76 = ROOT / "data/v76_entry_summary.json"

spec = importlib.util.spec_from_file_location("v11legacy", P)
b = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(b)

# Canonical research gate. Environment variables may not weaken the >=80 threshold.
b.VERSION = "V11-LEGACY-ML-WF-4M-R2"
b.REQUIRED_WR = 80.0


def jget(url, timeout=35, retries=4):
    last = None
    for n in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "trading-api-v11-backtest/2.0",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(0.35 * (n + 1))
    raise RuntimeError(f"HTTP_FAIL {last}")


def rawget(url, timeout=40, retries=3):
    last = None
    for n in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "trading-api-v11-backtest/2.0",
                    "Accept": "application/octet-stream,*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except HTTPError as e:
            if e.code == 404:
                return b""
            last = e
        except Exception as e:
            last = e
        time.sleep(0.45 * (n + 1))
    raise RuntimeError(f"HTTP_FAIL {last}")


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


REGISTRY_DATA = _load_json(REGISTRY)
V76_DATA = _load_json(V76)
V76_PAIRS = {
    str(x.get("symbol", "")).upper(): x
    for x in (V76_DATA.get("pairs") or [])
    if isinstance(x, dict) and x.get("symbol")
}


def base_asset(symbol):
    s = b.norm(symbol)
    if not s.endswith("USDT"):
        raise ValueError(s)
    return s[:-4]


def kucoin_4h(symbol, start_ts, end_ts):
    inst = base_asset(symbol) + "-USDT"
    out = []
    cur = start_ts
    span = 1450 * 14400
    while cur <= end_ts:
        z = min(end_ts, cur + span)
        q = urllib.parse.urlencode(
            {"type": "4hour", "symbol": inst, "startAt": cur, "endAt": z}
        )
        j = jget("https://api.kucoin.com/api/v1/market/candles?" + q)
        if str(j.get("code")) != "200000":
            raise RuntimeError(j.get("msg") or j)
        arr = j.get("data") or []
        if not arr and not out:
            raise RuntimeError("KUCOIN_EMPTY")
        for x in arr:
            if len(x) < 6:
                continue
            t = int(x[0])
            # KuCoin: time, open, close, high, low, volume, turnover
            out.append(
                [t, float(x[1]), float(x[3]), float(x[4]), float(x[2]), float(x[5])]
            )
        cur = z + 1
        time.sleep(0.02)
    d = {r[0]: r for r in out if start_ts <= r[0] <= end_ts}
    if not d:
        raise RuntimeError("KUCOIN_EMPTY")
    return [d[k] for k in sorted(d)], "KuCoin Spot 4H", True


def gate_4h(symbol, start_ts, end_ts):
    pair = base_asset(symbol) + "_USDT"
    out = []
    cur = start_ts
    span = 950 * 14400
    while cur <= end_ts:
        z = min(end_ts, cur + span)
        q = urllib.parse.urlencode(
            {
                "currency_pair": pair,
                "interval": "4h",
                "from": cur,
                "to": z,
                "limit": "1000",
            }
        )
        arr = jget("https://api.gateio.ws/api/v4/spot/candlesticks?" + q)
        if isinstance(arr, dict):
            raise RuntimeError(arr.get("message") or arr)
        if not arr and not out:
            raise RuntimeError("GATE_EMPTY")
        for x in arr:
            if len(x) < 6:
                continue
            t = int(float(x[0]))
            vol = float(x[6]) if len(x) > 6 else float(x[1] or 0)
            # Gate: timestamp, quote volume, close, high, low, open, base volume
            out.append([t, float(x[5]), float(x[3]), float(x[4]), float(x[2]), vol])
        cur = z + 1
        time.sleep(0.02)
    d = {r[0]: r for r in out if start_ts <= r[0] <= end_ts}
    if not d:
        raise RuntimeError("GATE_EMPTY")
    return [d[k] for k in sorted(d)], "Gate.io Spot 4H", True


def okx_4h(symbol, start_ts, end_ts):
    inst = base_asset(symbol) + "-USDT"
    out = []
    after = None
    guard = 0
    while guard < 36:
        guard += 1
        params = {"instId": inst, "bar": "4H", "limit": "100"}
        if after is not None:
            params["after"] = str(after)
        q = urllib.parse.urlencode(params)
        j = jget("https://www.okx.com/api/v5/market/history-candles?" + q)
        if str(j.get("code")) != "0":
            raise RuntimeError(j.get("msg") or j)
        arr = j.get("data") or []
        if not arr:
            break
        ts = []
        for x in arr:
            if len(x) < 6:
                continue
            t = int(x[0]) // 1000
            ts.append(t)
            out.append(
                [t, float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])]
            )
        oldest = min(ts)
        if oldest <= start_ts:
            break
        nxt = oldest * 1000
        if after == nxt:
            break
        after = nxt
        time.sleep(0.04)
    d = {r[0]: r for r in out if start_ts <= r[0] <= end_ts}
    if not d:
        raise RuntimeError("OKX_EMPTY")
    return [d[k] for k in sorted(d)], "OKX Spot 4H", True


def mexc_4h(symbol, start_ts, end_ts):
    """Exact public MEXC USDT spot 4H candles, used mainly for listing gaps."""
    inst = b.norm(symbol)
    out = []
    cur = start_ts * 1000
    end = end_ts * 1000
    span = 950 * 4 * 3600 * 1000
    guard = 0
    while cur <= end and guard < 24:
        guard += 1
        z = min(end, cur + span)
        q = urllib.parse.urlencode(
            {
                "symbol": inst,
                "interval": "4h",
                "startTime": cur,
                "endTime": z,
                "limit": 1000,
            }
        )
        arr = jget("https://api.mexc.com/api/v3/klines?" + q, timeout=30, retries=3)
        if isinstance(arr, dict):
            raise RuntimeError(arr.get("msg") or arr)
        if not arr:
            break
        for x in arr:
            if len(x) < 6:
                continue
            t = int(x[0]) // 1000
            out.append(
                [t, float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])]
            )
        last_ms = int(arr[-1][0])
        nxt = last_ms + 4 * 3600 * 1000
        if nxt <= cur:
            break
        cur = nxt
        if len(arr) < 1000 and cur > z:
            # Continue because the requested span may end before global end.
            pass
        time.sleep(0.03)
    d = {r[0]: r for r in out if start_ts <= r[0] <= end_ts}
    if not d:
        raise RuntimeError("MEXC_EMPTY")
    return [d[k] for k in sorted(d)], "MEXC Spot 4H", True


DUKAS_INSTRUMENT = {
    "XAUUSD": "XAUUSD",
    "XAGUSD": "XAGUSD",
    "NAS100": "USATECHIDXUSD",
    "US30": "USA30IDXUSD",
    "US500": "USA500IDXUSD",
    "DEX": "DEUIDXEUR",
    "JP225": "JPNIDXJPY",
}

DUKAS_BOUNDS = {
    "XAUUSD": (10.0, 100000.0),
    "XAGUSD": (0.1, 10000.0),
    "NAS100": (100.0, 1000000.0),
    "US30": (100.0, 1000000.0),
    "US500": (100.0, 1000000.0),
    "DEX": (100.0, 1000000.0),
    "JP225": (100.0, 1000000.0),
}


def _month_floor(dt):
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)


def _next_month(dt):
    return (dt.replace(day=28) + timedelta(days=4)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )


def _decode_dukas_record(symbol, base_ts, rec):
    """Decode one native Dukascopy H1 24-byte candle conservatively.

    Native record is big-endian: seconds-offset + four integer prices + float volume.
    The common BID_candles_hour_1 layout is O,C,L,H. Some third-party descriptions
    name the middle fields differently, so we accept only a layout whose OHLC
    invariants are internally valid and fail closed otherwise.
    """
    off, p1, p2, p3, p4, vol = rec
    scale = 1000.0
    o = p1 / scale

    candidates = [
        (o, p4 / scale, p3 / scale, p2 / scale),  # O,H,L,C description
        (o, p4 / scale, p3 / scale, p2 / scale),
    ]
    # Preferred documented native layout: O,C,L,H.
    preferred = (o, p4 / scale, p3 / scale, p2 / scale)
    # Convert preferred tuple above to O,H,L,C using p4 high / p3 low / p2 close.
    candidates = [preferred]
    # Defensive alternate O,H,L,C raw field order => O=p1,H=p2,L=p3,C=p4.
    candidates.append((o, p2 / scale, p3 / scale, p4 / scale))

    lo_bound, hi_bound = DUKAS_BOUNDS[symbol]
    valid = []
    for oo, hh, ll, cc in candidates:
        vals = (oo, hh, ll, cc)
        if not all(math.isfinite(v) and lo_bound <= v <= hi_bound for v in vals):
            continue
        if ll <= min(oo, cc) <= max(oo, cc) <= hh and hh >= ll:
            valid.append((oo, hh, ll, cc))
    if not valid:
        return None
    # Prefer native O,C,L,H interpretation when both are mathematically possible.
    oo, hh, ll, cc = valid[0]
    t = int(base_ts + int(off))
    return [t, oo, hh, ll, cc, float(vol) if math.isfinite(float(vol)) else 0.0]


def dukascopy_h1(symbol, start_ts, end_ts):
    s = b.norm(symbol)
    inst = DUKAS_INSTRUMENT.get(s)
    if not inst:
        raise RuntimeError(f"DUKAS_NO_MAPPING {s}")
    cur = _month_floor(datetime.fromtimestamp(start_ts, timezone.utc))
    end_dt = datetime.fromtimestamp(end_ts, timezone.utc)
    out = []
    while cur <= end_dt:
        month0 = cur.month - 1
        url = (
            f"https://datafeed.dukascopy.com/datafeed/{inst}/"
            f"{cur.year}/{month0:02d}/BID_candles_hour_1.bi5"
        )
        blob = rawget(url)
        if blob:
            try:
                raw = lzma.decompress(blob)
            except Exception as e:
                raise RuntimeError(f"DUKAS_LZMA {inst} {cur.date()} {e}")
            usable = len(raw) - (len(raw) % 24)
            if usable <= 0:
                raise RuntimeError(f"DUKAS_BAD_RECORD_SIZE {inst} {cur.date()}")
            base_ts = int(cur.timestamp())
            for rec in struct.iter_unpack(">IIIIIf", raw[:usable]):
                row = _decode_dukas_record(s, base_ts, rec)
                if row and start_ts <= row[0] <= end_ts:
                    out.append(row)
        cur = _next_month(cur)
    d = {r[0]: r for r in out}
    rows = [d[k] for k in sorted(d)]
    if not rows:
        raise RuntimeError("DUKAS_EMPTY")
    # Exact H1 backtest needs enough context, not a tiny accidental fragment.
    if len(rows) < 2500:
        raise RuntimeError(f"DUKAS_INSUFFICIENT_H1={len(rows)}")
    return rows, f"Dukascopy {inst} BID Spot/Index H1", True


_original_fetch = b.fetch_one


def fetch_one(symbol, market, start_ts, end_ts):
    errors = []
    if market == "crypto":
        providers = (kucoin_4h, gate_4h, okx_4h, mexc_4h)
        for fn in providers:
            try:
                rows, src, exact = fn(symbol, start_ts, end_ts)
                # 330d context target ~=1980 4H bars; 900 preserves enough training
                # for newer listings without silently accepting a tiny fragment.
                if len(rows) < 900:
                    raise RuntimeError(f"{src} insufficient4h={len(rows)}")
                return symbol, rows, src, exact, None
            except Exception as e:
                errors.append(f"{fn.__name__}:{e}")
        # Last-resort exact exchange APIs already present in the base engine.
        for name, fn in (("bybit_h1", b.bybit_history), ("binance_h1", b.binance_history)):
            try:
                rows, src, exact = fn(symbol, start_ts, end_ts)
                if len(rows) < 3600:
                    raise RuntimeError(f"{src} insufficient1h={len(rows)}")
                return symbol, rows, src, exact, None
            except Exception as e:
                errors.append(f"{name}:{e}")
        return symbol, [], None, False, " | ".join(errors)[:1600]

    if market == "metal":
        try:
            rows, src, exact = dukascopy_h1(symbol, start_ts, end_ts)
            return symbol, rows, src, exact, None
        except Exception as e:
            errors.append(f"dukascopy_h1:{e}")
        # Base Yahoo may return an exact spot ticker when available; its futures
        # fallback is already marked exact=False and therefore cannot pass.
        ss, rows, src, exact, err = _original_fetch(symbol, market, start_ts, end_ts)
        if rows:
            return ss, rows, src, exact, err
        errors.append(f"yahoo:{err}")
        return symbol, [], None, False, " | ".join(errors)[:1200]

    if market == "index":
        # Canonical exact cash-index Yahoo feed is preferred because baseline proved it.
        ss, rows, src, exact, err = _original_fetch(symbol, market, start_ts, end_ts)
        if rows and exact:
            return ss, rows, src, exact, err
        if err:
            errors.append(f"yahoo:{err}")
        try:
            rows, src, exact = dukascopy_h1(symbol, start_ts, end_ts)
            return symbol, rows, src, exact, None
        except Exception as e:
            errors.append(f"dukascopy_h1:{e}")
        if rows:
            return ss, rows, src, exact, err
        return symbol, [], None, False, " | ".join(errors)[:1200]

    # Forex exact Yahoo H1 proved complete for all 28 catalog pairs in the baseline.
    return _original_fetch(symbol, market, start_ts, end_ts)


def forex_maps(data):
    maps = {s: {r["dt"]: (i, r) for i, r in enumerate(rows)} for s, rows in data.items()}
    if not maps:
        return {}, []
    common = set.intersection(*(set(x) for x in maps.values()))
    return maps, sorted(t for t in common if t.hour in (0, 4, 8, 12, 16, 20))


def crypto_regime(symbols, maps, t):
    eligible = {}
    for s in symbols:
        q = maps.get(s, {}).get(t)
        if q and q[1].get("ret24") is not None and q[1].get("adx") is not None:
            eligible[s] = q
    if len(eligible) < max(15, int(len(symbols) * 0.5)):
        return None
    rets = [q[1]["ret24"] for q in eligible.values()]
    breadth = sum(x > 0 for x in rets) / len(rets)
    med = statistics.median(rets)
    disp = statistics.pstdev(rets) or 1e-9
    btc = eligible.get("BTCUSDT")
    btc24 = btc[1]["ret24"] if btc else med
    btc72 = btc[1].get("ret72", 0) if btc else 0
    return eligible, {
        "breadth": breadth,
        "median24": med,
        "dispersion24": disp,
        "btc24": btc24,
        "btc72": btc72,
        "eligible": len(eligible),
    }


def build_crypto_raw(symbols, data):
    maps = {s: {r["dt"]: (i, r) for i, r in enumerate(rows)} for s, rows in data.items()}
    times = sorted(set().union(*(set(x) for x in maps.values()))) if maps else []
    raw = {s: [] for s in symbols}
    baseline = (1.0, 1.0, 5)
    for t in times:
        regpack = crypto_regime(symbols, maps, t)
        if not regpack:
            continue
        eligible, reg = regpack
        for s, q in eligible.items():
            i, row = q
            for side in (1, -1):
                o = b.exec_intraday(data[s], i, side, baseline, "crypto")
                if o:
                    raw[s].append(
                        {
                            "i": i,
                            "time": t,
                            "day": b.daystr(t),
                            "side": side,
                            "x": b.crypto_feature(s, row, reg, side),
                            "label": 1 if o[0] == "TP" else 0,
                        }
                    )
    return raw


def build_generic_raw(symbols, data, market):
    maps = {s: {r["dt"]: (i, r) for i, r in enumerate(rows)} for s, rows in data.items()}
    raw = {s: [] for s in symbols}
    baseline = (1.0, 1.0, 8)
    times = sorted(set().union(*(set(x) for x in maps.values()))) if maps else []
    for t in times:
        avail = []
        for s in symbols:
            q = maps.get(s, {}).get(t)
            if q and q[1].get("ret24") is not None:
                avail.append((s, q))
        vals = [q[1]["ret24"] for _, q in avail]
        med = statistics.median(vals) if vals else 0
        disp = statistics.pstdev(vals) if len(vals) > 1 else 0
        for s, q in avail:
            i, row = q
            if row.get("adx") is None or row.get("rsi") is None:
                continue
            rel = (row.get("ret24", 0) - med) / (disp or 1)
            for side in (1, -1):
                o = b.exec_intraday(data[s], i, side, baseline, market)
                if o:
                    raw[s].append(
                        {
                            "i": i,
                            "time": t,
                            "day": b.daystr(t),
                            "side": side,
                            "x": b.generic_feature(
                                data[s],
                                i,
                                side,
                                (side * rel, abs(med) * 20, disp * 20),
                            ),
                            "label": 1 if o[0] == "TP" else 0,
                        }
                    )
    return raw


_original_legacy_prior = b.legacy_prior


def legacy_prior(symbol, market):
    """Merge old knowledge conservatively; never reinterpret it as OOS proof."""
    s = b.norm(symbol)
    v73 = _original_legacy_prior(s, market) or {}
    reg = ((REGISTRY_DATA.get("symbols") or {}).get(s) or {})
    v76 = V76_PAIRS.get(s) if market == "forex" else None

    prior = {}
    sources = []

    # Registry is the most explicit normalized prior, but its own classification
    # states that it is exposed development / prior-only.
    if reg:
        sources.append(str(REGISTRY_DATA.get("version") or "SYMBOL_KNOWLEDGE"))
        for key in (
            "source",
            "timeframe",
            "priorClassification",
            "priorStatus",
            "families",
            "allowedModes",
            "entryMode",
            "signalHourUTC",
            "riskATR",
            "priorRR",
        ):
            if key in reg:
                prior[key] = reg[key]
        cal = reg.get("calibration") or {}
        prior["calibrationStatus"] = cal.get("status")
        prior["developmentSampleSize"] = cal.get("sampleSize")
        prior["developmentWinRatePct"] = cal.get("developmentWinRatePct")
        prior["developmentMeanR"] = cal.get("developmentMeanR")

    # V73 style can fill missing geometry only; it is never current evidence.
    if isinstance(v73, dict) and v73:
        sources.append("V73_EXPOSED_STYLE_FALLBACK")
        for key in ("signalHourUTC", "riskATR", "priorRR", "rr", "entryMode"):
            if key in v73 and key not in prior:
                prior[key] = v73[key]

    # V76 is explicitly RESEARCH_ONLY; retain a compact diagnostic prior so V11
    # can use its geometry as a final tie-break and improvement hint.
    if isinstance(v76, dict):
        sources.append(str(V76_DATA.get("version") or "V76_ENTRY_SUMMARY"))
        oos = v76.get("oos") or {}
        prior["v76Research"] = {
            "status": v76.get("status"),
            "liveEligible": bool(v76.get("liveEligible")),
            "archetype": v76.get("archetype"),
            "entryMode": v76.get("entryMode"),
            "stopMode": v76.get("stopMode"),
            "rr": v76.get("rr"),
            "oos": {
                "n": oos.get("n"),
                "wr": oos.get("wr"),
                "expectancyR": oos.get("expectancyR"),
                "profitFactor": oos.get("profitFactor"),
            },
        }
        if "priorRR" not in prior and v76.get("rr") in (1, 2, 1.0, 2.0):
            prior["priorRR"] = float(v76["rr"])

    prior["priorSources"] = sources
    prior["legacyEvidenceClass"] = "PRIOR_ONLY_NOT_CURRENT_OOS_PROOF"
    prior["legacyUsePolicy"] = (
        "candidate ordering/tie-break/context only; fresh chronological "
        "walk-forward evidence dominates"
    )
    return prior


def score_exact(base, train_before, start_dt, end_dt, model_spec, seed):
    """Fit on t < train_before and score only start_dt <= t < end_dt."""
    tr = [x for x in base if x["time"] < train_before]
    te = [x for x in base if start_dt <= x["time"] < end_dt]
    model = b.fit_model(tr, model_spec, seed)
    if model is None or not te:
        return []
    import numpy as np

    p = model.predict_proba(np.asarray([x["x"] for x in te], float))[:, 1]
    return [dict(x, prob=float(v)) for x, v in zip(te, p)]


def _prior_distance(cfg, prior):
    rr, risk_floor, _ = cfg
    score = 0.0
    prr = prior.get("priorRR")
    if prr is None:
        prr = prior.get("rr")
    try:
        if float(prr) in (1.0, 2.0):
            score += abs(rr - float(prr)) * 2.0
    except Exception:
        pass
    try:
        patr = float(prior.get("riskATR"))
        if math.isfinite(patr) and patr > 0:
            score += abs(risk_floor - patr)
    except Exception:
        pass
    return score


def tune_symbol(symbol, market, base, rows, eval_start, prior, seed):
    # Entire style selection sits strictly before the four-month evaluation.
    tune_end = eval_start
    tune_start = eval_start - timedelta(days=31)
    cfgs = b.configs_for(market)
    tune_base = [x for x in base if tune_start <= x["time"] < tune_end]
    outcomes = b.precompute_outcomes(rows, tune_base, cfgs, market)
    best = None
    bp = None
    for mi, model_spec in enumerate(b.MODEL_SPECS):
        scored = score_exact(base, tune_start, tune_start, tune_end, model_spec, seed + mi)
        if not scored:
            continue
        for w, hours in b.windows_for(market, prior).items():
            for direction in b.DIRS:
                exp = b.expected_days(scored, hours, direction, market)
                if exp < b.MIN_TUNE_DAYS:
                    continue
                for threshold in b.THRESHOLDS:
                    for margin in b.MARGINS:
                        for maxtrades in b.MAXTRADES:
                            sel = b.choose_day(
                                scored,
                                hours,
                                direction,
                                threshold,
                                margin,
                                maxtrades,
                                market,
                            )
                            for cfg in cfgs:
                                stats = b.eval_sel(
                                    sel, rows, cfg, exp, market, outcomes
                                )
                                # Fresh performance dominates. Legacy geometry is
                                # only the final deterministic tie-break.
                                q = b.rank_tune(stats) + (-_prior_distance(cfg, prior),)
                                if best is None or q > best:
                                    best = q
                                    bp = (
                                        model_spec,
                                        w,
                                        hours,
                                        direction,
                                        threshold,
                                        margin,
                                        maxtrades,
                                        cfg,
                                        stats,
                                    )
    return bp


def month_chunks(start_dt, end_dt):
    cur = start_dt
    out = []
    while cur < end_dt:
        first_this = cur.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        nxt = _next_month(first_this)
        z = min(end_dt, nxt)
        out.append((cur, z))
        cur = z
    return out


def _execution_day(event, rows=None):
    if rows is not None:
        i = int(event.get("i", -1)) + 1
        if 0 <= i < len(rows):
            return rows[i]["dt"].date().isoformat()
    return event["day"]


def cap_dedupe(sel, maxtrades, rows=None):
    """Hard invariant: unique events, <=maxtrades on signal AND execution day."""
    limit = max(1, min(3, int(maxtrades)))
    unique = {}
    for e in sel:
        unique.setdefault(b.event_key(e), e)

    signal_counts = defaultdict(int)
    execution_counts = defaultdict(int)
    out = []
    ordered = sorted(
        unique.values(), key=lambda e: (e["time"], -float(e.get("prob", 0)))
    )
    for e in ordered:
        signal_day = e["day"]
        execution_day = _execution_day(e, rows)
        if signal_counts[signal_day] >= limit:
            continue
        if execution_counts[execution_day] >= limit:
            continue
        signal_counts[signal_day] += 1
        execution_counts[execution_day] += 1
        out.append(e)
    return out


def _eligible_day_set(scored, hours, direction, market):
    h = set(hours)
    days = set()
    for x in scored:
        if market != "crypto" and x["time"].weekday() >= 5:
            continue
        if x["time"].hour not in h:
            continue
        if direction == "BUY" and x["side"] != 1:
            continue
        if direction == "SELL" and x["side"] != -1:
            continue
        days.add(x["day"])
    return days


def walk_forward(symbol, market, base, rows, bp, eval_start, eval_end, seed):
    model_spec, w, hours, direction, threshold, margin, maxtrades, cfg, tune = bp
    monthly = []
    allsel = []
    expected_days = set()

    for j, (a_dt, z_dt) in enumerate(month_chunks(eval_start, eval_end)):
        # Expanding chronological fit: only observations strictly before chunk start.
        scored = score_exact(
            base, a_dt, a_dt, z_dt, model_spec, seed + 100 + j
        )
        exp_days = _eligible_day_set(scored, hours, direction, market)
        sel = b.choose_day(
            scored,
            hours,
            direction,
            threshold,
            margin,
            maxtrades,
            market,
        )
        sel = cap_dedupe(sel, maxtrades, rows)
        stats = b.eval_sel(sel, rows, cfg, len(exp_days), market)
        monthly.append(
            {
                "start": a_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "endExclusive": z_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                **stats,
            }
        )
        expected_days.update(exp_days)
        allsel.extend(sel)

    allsel = cap_dedupe(allsel, maxtrades, rows)
    full = b.eval_sel(allsel, rows, cfg, len(expected_days), market)
    # This should be impossible after cap_dedupe; keep it explicit and fail loud.
    if full.get("maxTradesInDay", 0) > min(3, int(maxtrades)):
        raise AssertionError(
            f"MAX3_REGRESSION {symbol} got={full.get('maxTradesInDay')} "
            f"profile={maxtrades}"
        )
    return monthly, full


_original_eval_sel = b.eval_sel


def eval_sel(sel, rows, cfg, expected, market, outcomes=None):
    """Base metrics plus real next-bar execution-day cadence."""
    stats = _original_eval_sel(sel, rows, cfg, expected, market, outcomes)
    execution_counts = defaultdict(int)
    valid = 0
    for e in sel:
        if outcomes is not None:
            o = outcomes.get(b.event_key(e), {}).get(cfg)
        else:
            o = b.exec_intraday(rows, e["i"], e["side"], cfg, market)
        if not o:
            continue
        valid += 1
        execution_counts[_execution_day(e, rows)] += 1
    stats["maxTradesExecutionDay"] = max(execution_counts.values(), default=0)
    stats["avgTradesPerTradedDay"] = (
        round(valid / stats["daysTraded"], 3) if stats.get("daysTraded") else 0.0
    )
    return stats


_original_optimize = b.optimize_symbol


def _improvement_proposal(result):
    reasons = set(result.get("reasons") or [])
    proposals = []
    if "DATA_UNAVAILABLE" in reasons:
        proposals.append(
            "Backfill exact historical bars from the next mapped provider; keep symbol fail-closed until sufficient chronological history exists."
        )
    if "NON_EXACT_DATA_FALLBACK" in reasons:
        proposals.append(
            "Require exact mapped instrument history (spot for metals); non-exact proxy/futures data cannot promote the symbol."
        )
    if "INSUFFICIENT_HISTORY_OR_CANDIDATES" in reasons or "MIN_EVAL_TRADES" in reasons:
        proposals.append(
            "Increase pre-evaluation history/listing coverage and research additional valid legacy-seeded candidate families outside the held-out window."
        )
    if "COVERAGE_BELOW_90" in reasons:
        proposals.append(
            "Widen only pre-evaluated valid session/candidate families; do not force low-quality trades to manufacture cadence."
        )
    if "WIN_RATE_BELOW_80" in reasons:
        proposals.append(
            "Keep fail-closed; improve separation with earlier-window regime/style research and re-test on untouched chronological chunks."
        )
    if "MEAN_R_NONPOSITIVE" in reasons:
        proposals.append(
            "Re-evaluate structural/ATR geometry and RR 1:1 versus 1:2 using earlier data only; require positive fresh expectancy."
        )
    if "MAX3_BREACH" in reasons:
        proposals.append(
            "Integrity failure: reject evidence and repair dedupe/day-cap before any performance interpretation."
        )
    if "RR_INVALID" in reasons:
        proposals.append("Reject profile; only RR 1:1 or 1:2 is permitted.")
    if not proposals and not result.get("pass"):
        proposals.append(
            "Remain research-only and gather more independent walk-forward evidence before promotion."
        )
    return proposals


def optimize_symbol(symbol, market, base, rows, source, exact, err, eval_start, eval_end, seed):
    result = _original_optimize(
        symbol, market, base, rows, source, exact, err, eval_start, eval_end, seed
    )
    # Rebuild prior with normalized V11 legacy knowledge even on early data failures.
    result["legacyPrior"] = legacy_prior(symbol, market)
    result["improvementProposal"] = _improvement_proposal(result)
    result["promotionStatus"] = (
        "ELIGIBLE_RESEARCH_PROFILE"
        if result.get("pass")
        else "FAIL_CLOSED_RESEARCH_ONLY"
    )
    return result


def _selfcheck():
    if b.REQUIRED_WR < 80.0:
        raise AssertionError("REQUIRED_WR_WEAKENED")
    t0 = datetime(2026, 8, 1, 0, tzinfo=timezone.utc)
    fake = []
    for i in range(5):
        fake.append(
            {
                "i": i,
                "side": 1 if i % 2 == 0 else -1,
                "time": t0 + timedelta(hours=i),
                "day": "2026-08-01",
                "prob": 0.9 - i * 0.01,
            }
        )
    capped = cap_dedupe(fake + fake[:2], 3)
    if len(capped) != 3:
        raise AssertionError(f"MAX3_DEDUPE_SELFTEST {len(capped)}")
    chunks = month_chunks(
        datetime(2026, 4, 23, 14, tzinfo=timezone.utc),
        datetime(2026, 8, 23, 14, tzinfo=timezone.utc),
    )
    for i in range(1, len(chunks)):
        if chunks[i - 1][1] != chunks[i][0]:
            raise AssertionError("CHUNK_GAP_OR_OVERLAP")


def patch_outputs():
    try:
        report = json.loads(b.OUT.read_text(encoding="utf-8"))
        gate = json.loads(b.GATE.read_text(encoding="utf-8"))
    except Exception:
        return

    symbols = report.get("symbols") or {}
    provider_usage = Counter(
        str(x.get("source") or "UNAVAILABLE") for x in symbols.values()
    )
    prior_usage = Counter()
    for x in symbols.values():
        for src in ((x.get("legacyPrior") or {}).get("priorSources") or []):
            prior_usage[str(src)] += 1

    meta_patch = {
        "version": b.VERSION,
        "requiredWinRateInclusive": 80.0,
        "thresholdPolicy": "immutable canonical wrapper gate: PASS requires >=80.00%",
        "method": (
            "V11 R2: V62/V63/V73 normalized registry + V76 research priors used "
            "only for candidate context/tie-break; exact-timestamp pre-eval style "
            "selection + expanding monthly walk-forward; no final-window retuning"
        ),
        "sameBarRule": "SL conservative",
        "timeoutRule": "non-win",
        "dataSources": {
            "forex": "Yahoo Finance exact FX H1",
            "crypto": (
                "Exact USDT spot: KuCoin 4H -> Gate.io 4H -> OKX 4H -> "
                "MEXC 4H -> Bybit/Binance exact H1 fallback then resample 4H"
            ),
            "metal": (
                "Dukascopy exact BID spot H1 XAUUSD/XAGUSD -> Yahoo exact spot "
                "when available; futures fallback remains non-exact and cannot PASS"
            ),
            "index": (
                "Yahoo Finance exact cash index H1 -> mapped Dukascopy index H1 fallback"
            ),
        },
        "legacyLearning": {
            "sources": [
                "data/symbol_knowledge_registry.json (exposed development prior)",
                "data/v76_entry_summary.json (RESEARCH_ONLY prior)",
                "data/nocut_intraday_allpass_v73.json (fallback style prior)",
            ],
            "policy": "prior-only; fresh chronological walk-forward evidence dominates",
            "priorUsageCounts": dict(prior_usage),
        },
        "integrityRepair": {
            "baselineRun": "32644325780",
            "exactTimestampChunks": True,
            "dedupeByEventKey": True,
            "hardDailyCap": 3,
            "capBasis": "both signal day and actual next-bar execution day",
            "max3RegressionSelfcheck": "PASS",
        },
        "providerUsage": dict(provider_usage),
    }

    report.setdefault("meta", {}).update(meta_patch)
    gate.update(meta_patch)
    # Recalculate gate summaries from symbol truth, never from desired target.
    passed = [s for s, x in symbols.items() if bool(x.get("pass"))]
    failed = [s for s, x in symbols.items() if not bool(x.get("pass"))]
    report["meta"]["passCount"] = len(passed)
    report["meta"]["allPassed"] = len(passed) == len(symbols)
    gate["passCount"] = len(passed)
    gate["totalSymbols"] = len(symbols)
    gate["allPassed"] = len(passed) == len(symbols)
    gate["passingSymbols"] = passed
    gate["failingSymbols"] = failed

    b.OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    b.GATE.write_text(
        json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# Install research-only overrides.
b.fetch_one = fetch_one
b.forex_maps = forex_maps
b.crypto_regime = crypto_regime
b.build_crypto_raw = build_crypto_raw
b.build_generic_raw = build_generic_raw
b.legacy_prior = legacy_prior
b.tune_symbol = tune_symbol
b.walk_forward = walk_forward
b.eval_sel = eval_sel
b.optimize_symbol = optimize_symbol


if __name__ == "__main__":
    _selfcheck()
    rc = b.main()
    patch_outputs()
    raise SystemExit(rc)
