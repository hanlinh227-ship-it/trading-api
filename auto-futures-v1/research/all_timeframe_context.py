import json
import math
import statistics
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://fapi.binance.com"
ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"
SNAPSHOT = STATE / "market_snapshot.json"

ALL_TIMEFRAMES = (
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
)

MISSING_TIMEFRAMES = ("2h", "6h", "8h", "12h", "3d", "1w", "1M")

LAYER_MAP = {
    "execution": ("1m", "3m", "5m"),
    "setup": ("15m", "30m"),
    "intraday": ("1h", "2h", "4h"),
    "macro": ("6h", "8h", "12h", "1d"),
    "structural": ("3d", "1w", "1M"),
}

LAYER_WEIGHTS = {
    "execution": 1.00,
    "setup": 1.20,
    "intraday": 1.10,
    "macro": 0.75,
    "structural": 0.35,
}


def get_json(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "AUTO-FUTURES-V5-ALL-TF/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def ema(values, length):
    if not values:
        return 0.0
    alpha = 2.0 / (length + 1.0)
    out = values[0]
    for v in values[1:]:
        out = alpha * v + (1.0 - alpha) * out
    return out


def rsi(values, length=14):
    if len(values) < length + 1:
        return 50.0
    gains, losses = [], []
    for a, b in zip(values[-length-1:-1], values[-length:]):
        d = b - a
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains) / length
    al = sum(losses) / length
    if al == 0:
        return 100.0
    rs = ag / al
    return 100.0 - 100.0 / (1.0 + rs)


def atr(highs, lows, closes, length=14):
    trs = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])))
    if not trs:
        return 0.0
    x = trs[-length:]
    return sum(x) / len(x)


def pct(a, b):
    return ((a - b) / b * 100.0) if b else 0.0


def analyze_tf(symbol, interval):
    rows = get_json("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": 180})[:-1]
    if len(rows) < 60:
        raise RuntimeError(f"insufficient {interval} candles")
    closes = [float(r[4]) for r in rows]
    highs = [float(r[2]) for r in rows]
    lows = [float(r[3]) for r in rows]
    vols = [float(r[5]) for r in rows]
    price = closes[-1]
    e9 = ema(closes[-100:], 9)
    e21 = ema(closes[-120:], 21)
    e50 = ema(closes[-160:], 50)
    a14 = atr(highs, lows, closes, 14)
    avg_vol = statistics.mean(vols[-21:-1]) if len(vols) > 21 else statistics.mean(vols)
    vr = vols[-1] / avg_vol if avg_vol else 0.0
    trend = "NEUTRAL"
    direction = 0.0
    if price > e9 > e21 > e50:
        trend, direction = "BULL", 1.0
    elif price < e9 < e21 < e50:
        trend, direction = "BEAR", -1.0
    elif price > e21 and e9 > e21:
        trend, direction = "BULL_WEAK", 0.5
    elif price < e21 and e9 < e21:
        trend, direction = "BEAR_WEAK", -0.5
    return {
        "interval": interval,
        "price": price,
        "ema9": e9,
        "ema21": e21,
        "ema50": e50,
        "rsi14": rsi(closes),
        "atr14": a14,
        "atr_pct": a14 / price * 100.0 if price else 0.0,
        "volume_ratio": vr,
        "momentum_3": pct(closes[-1], closes[-4]),
        "momentum_10": pct(closes[-1], closes[-11]),
        "recent_high": max(highs[-20:]),
        "recent_low": min(lows[-20:]),
        "trend": trend,
        "direction": direction,
        "distance_ema21_atr": (price - e21) / max(a14, price * 0.00005),
    }


def layer_score(timeframes, names):
    values = [float(timeframes[x].get("direction", 0.0)) for x in names if x in timeframes]
    if not values:
        return 0.0
    return sum(values) / len(values)


def direction_label(value):
    if value >= 0.25:
        return "BULL"
    if value <= -0.25:
        return "BEAR"
    return "NEUTRAL"


def build_hierarchy(setup):
    tf = setup.get("timeframes", {})
    scores = {name: layer_score(tf, frames) for name, frames in LAYER_MAP.items()}
    weighted_num = sum(scores[k] * LAYER_WEIGHTS[k] for k in scores)
    weighted_den = sum(LAYER_WEIGHTS.values())
    weighted = weighted_num / weighted_den if weighted_den else 0.0
    hierarchy = {
        name: {
            "timeframes": list(frames),
            "score": round(scores[name], 4),
            "direction": direction_label(scores[name]),
        }
        for name, frames in LAYER_MAP.items()
    }
    hierarchy["composite"] = round(weighted, 4)
    hierarchy["composite_direction"] = direction_label(weighted)
    return hierarchy


def standardize_entry(setup):
    action = str(setup.get("candidate_action", "WAIT")).upper()
    hierarchy = setup["timeframe_hierarchy"]
    if action not in {"LONG", "SHORT"}:
        return {
            "status": "WAIT",
            "direction": action,
            "execution_confirmed": False,
            "setup_confirmed": False,
            "strong_opposition": False,
            "context_score": 0.0,
            "reasons": ["scanner has no directional entry candidate"],
        }
    sign = 1.0 if action == "LONG" else -1.0
    execution = hierarchy["execution"]["score"] * sign
    setup_layer = hierarchy["setup"]["score"] * sign
    intraday = hierarchy["intraday"]["score"] * sign
    macro = hierarchy["macro"]["score"] * sign
    structural = hierarchy["structural"]["score"] * sign
    execution_ok = execution >= 0.25
    setup_ok = setup_layer >= -0.05
    strong_opposition = intraday <= -0.55 or macro <= -0.65
    structural_warning = structural <= -0.70
    context = (
        execution * 0.36 +
        setup_layer * 0.28 +
        intraday * 0.18 +
        macro * 0.12 +
        structural * 0.06
    )
    reasons = []
    if not execution_ok:
        reasons.append("execution layer 1m/3m/5m is not synchronized")
    if not setup_ok:
        reasons.append("15m/30m setup layer materially opposes entry")
    if strong_opposition:
        reasons.append("higher-timeframe intraday/macro opposition is too strong")
    if structural_warning:
        reasons.append("3d/1w/1M structural context strongly opposes; confidence must be reduced")
    status = "CONFIRMED"
    if strong_opposition or not execution_ok:
        status = "BLOCKED"
    elif not setup_ok or structural_warning or context < 0.15:
        status = "MIXED"
    return {
        "status": status,
        "direction": action,
        "execution_confirmed": execution_ok,
        "setup_confirmed": setup_ok,
        "strong_opposition": strong_opposition,
        "structural_warning": structural_warning,
        "context_score": round(context, 4),
        "layer_signed_scores": {
            "execution": round(execution, 4),
            "setup": round(setup_layer, 4),
            "intraday": round(intraday, 4),
            "macro": round(macro, 4),
            "structural": round(structural, 4),
        },
        "reasons": reasons,
        "principle": "short frames time entry; long frames shape context/veto, they do not need unanimous alignment",
    }


def enrich_one(setup):
    symbol = setup["symbol"]
    tf = dict(setup.get("timeframes", {}))
    missing = [x for x in MISSING_TIMEFRAMES if x not in tf]
    if missing:
        with ThreadPoolExecutor(max_workers=min(7, len(missing))) as pool:
            futs = {pool.submit(analyze_tf, symbol, x): x for x in missing}
            for fut in as_completed(futs):
                interval = futs[fut]
                try:
                    tf[interval] = fut.result()
                except Exception as exc:
                    setup.setdefault("warnings", []).append(f"{interval} context unavailable: {type(exc).__name__}")
    setup["timeframes"] = tf
    setup["all_timeframes_present"] = [x for x in ALL_TIMEFRAMES if x in tf]
    setup["timeframe_hierarchy"] = build_hierarchy(setup)
    setup["entry_standardization"] = standardize_entry(setup)
    if setup["entry_standardization"]["status"] == "BLOCKED" and setup.get("candidate_action") in {"LONG", "SHORT"}:
        setup.setdefault("blockers", []).append("ALL_TF_ENTRY_STANDARDIZATION_BLOCK")
    return setup


def main():
    if not SNAPSHOT.exists():
        raise SystemExit("market_snapshot.json missing")
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    candidates = data.get("ai_candidates") or []
    with ThreadPoolExecutor(max_workers=4) as pool:
        enriched = list(pool.map(enrich_one, candidates))
    by_symbol = {x["symbol"]: x for x in enriched}
    data["ai_candidates"] = enriched
    data["setups"] = [by_symbol.get(x.get("symbol"), x) for x in data.get("setups", [])]
    data["all_timeframe_context"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_binance_timeframes": list(ALL_TIMEFRAMES),
        "layers": {k: list(v) for k, v in LAYER_MAP.items()},
        "entry_principle": "execution 1m/3m/5m times the scalp; 15m/30m defines setup; 1h-1d shapes context; 3d-1M is structural context only",
    }
    SNAPSHOT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ALL-TIMEFRAME CONTEXT:", len(enriched), "AI candidates enriched")
    for x in enriched:
        e = x.get("entry_standardization", {})
        print(x["symbol"], "|", x.get("candidate_action"), "|", e.get("status"), "| ctx", e.get("context_score"))


if __name__ == "__main__":
    main()
