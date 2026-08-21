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
STATE_DIR = ROOT / "state"
LOG_DIR = ROOT / "logs"
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

UNIVERSE_SIZE = 50
AI_CANDIDATES = 12
TIMEFRAMES = ("1m", "5m", "15m")
EXCLUDED_BASES = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "TRY", "BRL"}


def get_json(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "AUTO-FUTURES-V4-SCALP/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def ema(values, length):
    if not values:
        return 0.0
    a = 2.0 / (length + 1)
    out = values[0]
    for v in values[1:]:
        out = a * v + (1 - a) * out
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


def weighted_vwap(highs, lows, closes, volumes, lookback=60):
    hs, ls, cs, vs = highs[-lookback:], lows[-lookback:], closes[-lookback:], volumes[-lookback:]
    den = sum(vs)
    if den <= 0:
        return cs[-1]
    return sum(((h+l+c)/3.0) * v for h, l, c, v in zip(hs, ls, cs, vs)) / den


def select_universe():
    info = get_json("/fapi/v1/exchangeInfo")
    valid = {}
    for s in info.get("symbols", []):
        if s.get("contractType") != "PERPETUAL" or s.get("quoteAsset") != "USDT" or s.get("status") != "TRADING":
            continue
        if s.get("baseAsset") in EXCLUDED_BASES:
            continue
        valid[s["symbol"]] = s
    tickers = get_json("/fapi/v1/ticker/24hr")
    ranked = []
    for t in tickers:
        sym = t.get("symbol")
        if sym not in valid:
            continue
        try:
            quote_volume = float(t.get("quoteVolume", 0))
            trades = int(t.get("count", 0))
            last = float(t.get("lastPrice", 0))
        except Exception:
            continue
        if quote_volume <= 0 or trades < 1000 or last <= 0:
            continue
        ranked.append((quote_volume, sym))
    ranked.sort(reverse=True)
    return [s for _, s in ranked[:UNIVERSE_SIZE]]


def analyze_tf(symbol, interval):
    rows = get_json("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": 180})[:-1]
    closes = [float(r[4]) for r in rows]
    highs = [float(r[2]) for r in rows]
    lows = [float(r[3]) for r in rows]
    vols = [float(r[5]) for r in rows]
    price = closes[-1]
    e9, e21, e50 = ema(closes[-100:], 9), ema(closes[-120:], 21), ema(closes[-160:], 50)
    a14 = atr(highs, lows, closes, 14)
    rv = statistics.pstdev([pct(closes[i], closes[i-1]) for i in range(max(1, len(closes)-30), len(closes))])
    avg_vol = statistics.mean(vols[-21:-1]) if len(vols) > 21 else statistics.mean(vols)
    vol_ratio = vols[-1] / avg_vol if avg_vol else 0.0
    recent_hi = max(highs[-20:])
    recent_lo = min(lows[-20:])
    long_range = max(highs[-50:]) - min(lows[-50:])
    short_range = max(highs[-10:]) - min(lows[-10:])
    compression = short_range / long_range if long_range > 0 else 1.0
    trend = "NEUTRAL"
    if price > e9 > e21 > e50:
        trend = "BULL"
    elif price < e9 < e21 < e50:
        trend = "BEAR"
    return {
        "price": price, "ema9": e9, "ema21": e21, "ema50": e50,
        "rsi14": rsi(closes), "atr14": a14, "atr_pct": a14 / price * 100 if price else 0,
        "vwap": weighted_vwap(highs, lows, closes, vols), "volume_ratio": vol_ratio,
        "momentum_3": pct(closes[-1], closes[-4]), "momentum_10": pct(closes[-1], closes[-11]),
        "recent_high": recent_hi, "recent_low": recent_lo, "compression": compression,
        "realized_vol": rv, "trend": trend,
    }


def classify_and_score(symbol):
    tf = {x: analyze_tf(symbol, x) for x in TIMEFRAMES}
    t1, t5, t15 = tf["1m"], tf["5m"], tf["15m"]
    price, a5 = t1["price"], max(t5["atr14"], price * 0.0005)
    strategy, action, score = "NO_EDGE", "WAIT", 0
    reasons, warnings = [], []

    aligned_bull = t15["trend"] == "BULL" and t5["trend"] == "BULL"
    aligned_bear = t15["trend"] == "BEAR" and t5["trend"] == "BEAR"
    near_vwap = abs(price - t1["vwap"]) <= max(t1["atr14"] * 0.8, price * 0.0005)
    near_ema = abs(price - t1["ema21"]) <= max(t1["atr14"] * 0.7, price * 0.0004)
    breakout_up = price >= t5["recent_high"] - 0.25 * a5
    breakout_dn = price <= t5["recent_low"] + 0.25 * a5
    squeeze = t5["compression"] < 0.32

    if aligned_bull and (near_ema or near_vwap) and 42 <= t1["rsi14"] <= 66 and t1["momentum_3"] >= -0.08:
        strategy, action, score = "TREND_PULLBACK", "LONG", 70
        reasons.append("15m/5m uptrend with controlled 1m pullback")
    elif aligned_bear and (near_ema or near_vwap) and 34 <= t1["rsi14"] <= 58 and t1["momentum_3"] <= 0.08:
        strategy, action, score = "TREND_PULLBACK", "SHORT", 70
        reasons.append("15m/5m downtrend with controlled 1m pullback")
    elif squeeze and breakout_up and t1["volume_ratio"] >= 1.35 and t1["momentum_3"] > 0:
        strategy, action, score = "BREAKOUT", "LONG", 68
        reasons.append("compressed range breaks upward with volume expansion")
    elif squeeze and breakout_dn and t1["volume_ratio"] >= 1.35 and t1["momentum_3"] < 0:
        strategy, action, score = "BREAKOUT", "SHORT", 68
        reasons.append("compressed range breaks downward with volume expansion")
    elif aligned_bull and t1["volume_ratio"] >= 1.2 and t1["momentum_3"] > 0.10 and t5["momentum_3"] > 0:
        strategy, action, score = "MOMENTUM", "LONG", 64
        reasons.append("multi-timeframe bullish momentum with participation")
    elif aligned_bear and t1["volume_ratio"] >= 1.2 and t1["momentum_3"] < -0.10 and t5["momentum_3"] < 0:
        strategy, action, score = "MOMENTUM", "SHORT", 64
        reasons.append("multi-timeframe bearish momentum with participation")
    elif t15["trend"] == "NEUTRAL" and t5["trend"] == "NEUTRAL":
        dev = (price - t1["vwap"]) / max(t1["atr14"], price * 0.0005)
        if dev <= -1.5 and t1["rsi14"] < 30:
            strategy, action, score = "MEAN_REVERSION", "LONG", 60
            reasons.append("range regime: downside VWAP deviation with short-term exhaustion")
        elif dev >= 1.5 and t1["rsi14"] > 70:
            strategy, action, score = "MEAN_REVERSION", "SHORT", 60
            reasons.append("range regime: upside VWAP deviation with short-term exhaustion")

    if t1["volume_ratio"] < 0.45:
        score -= 12
        warnings.append("very low 1m relative volume")
    if t5["atr_pct"] > 2.5:
        score -= 10
        warnings.append("abnormally high 5m volatility")
    extension = abs(price - t5["ema21"]) / max(a5, 1e-12)
    if extension > 2.2 and strategy in {"TREND_PULLBACK", "MOMENTUM"}:
        score -= 18
        warnings.append("entry extended from 5m EMA21")
    if action == "LONG" and t1["rsi14"] > 78:
        score -= 12
        warnings.append("1m long chase risk")
    if action == "SHORT" and t1["rsi14"] < 22:
        score -= 12
        warnings.append("1m short chase risk")

    score = max(0, min(100, score))
    if score < 56:
        action = "WAIT"

    entry = stop = tp1 = tp2 = tp3 = None
    if action in {"LONG", "SHORT"}:
        if strategy == "BREAKOUT":
            sl_atr, rrs = 1.05, (1.0, 1.8, 3.0)
        elif strategy == "MEAN_REVERSION":
            sl_atr, rrs = 0.85, (0.8, 1.35, 2.0)
        elif strategy == "MOMENTUM":
            sl_atr, rrs = 0.95, (1.0, 1.7, 2.6)
        else:
            sl_atr, rrs = 0.90, (1.0, 1.8, 2.8)
        entry = price
        if action == "LONG":
            structural = t1["recent_low"] - 0.15 * a5
            stop = min(structural, entry - sl_atr * a5)
            risk = entry - stop
            tp1, tp2, tp3 = (entry + risk * r for r in rrs)
        else:
            structural = t1["recent_high"] + 0.15 * a5
            stop = max(structural, entry + sl_atr * a5)
            risk = stop - entry
            tp1, tp2, tp3 = (entry - risk * r for r in rrs)

    return {
        "symbol": symbol, "candidate_action": action, "strategy": strategy,
        "setup_score": score, "setup_quality": score,
        "entry": entry, "stop_loss": stop, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "timeframes": tf, "reasons": reasons, "warnings": warnings, "blockers": [],
        "management": {"tp1_close_pct": 30, "tp2_close_pct": 30, "runner_pct": 40,
                       "breakeven_after_tp1": True, "trail_after_tp2": True,
                       "trail_atr_mult": 0.85 if strategy != "BREAKOUT" else 1.05},
    }


def enrich_derivatives(setup):
    symbol = setup["symbol"]
    try:
        p = get_json("/fapi/v1/premiumIndex", {"symbol": symbol})
        oi = get_json("/fapi/v1/openInterest", {"symbol": symbol})
        setup["funding_rate"] = float(p.get("lastFundingRate", 0.0))
        setup["open_interest"] = float(oi.get("openInterest", 0.0))
    except Exception as exc:
        setup["funding_rate"], setup["open_interest"] = 0.0, 0.0
        setup["warnings"].append(f"derivatives enrichment unavailable: {type(exc).__name__}")
    return setup


def main():
    generated = datetime.now(timezone.utc).isoformat()
    universe = select_universe()
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(classify_and_score, s): s for s in universe}
        for f in as_completed(futs):
            s = futs[f]
            try:
                results.append(f.result())
            except Exception as exc:
                errors.append({"symbol": s, "error": repr(exc)})
    results.sort(key=lambda x: (x["candidate_action"] != "WAIT", x["setup_score"]), reverse=True)
    shortlist = results[:AI_CANDIDATES]
    with ThreadPoolExecutor(max_workers=6) as pool:
        shortlist = list(pool.map(enrich_derivatives, shortlist))
    by_symbol = {x["symbol"]: x for x in shortlist}
    results = [by_symbol.get(x["symbol"], x) for x in results]
    snapshot = {
        "generated_at": generated, "mode": "PAPER", "live_trading": False,
        "engine": "AUTO_FUTURES_V4_ADAPTIVE_SCALP", "universe_size": len(universe),
        "universe": universe, "setups": results, "ai_candidates": shortlist, "errors": errors,
        "policy": {"style": "SCALP_ONLY_24_7", "daily_trade_limit": None,
                   "daily_loss_limit": None, "max_loss_limit": None,
                   "per_trade_stop_required": True, "adaptive_strategy_per_symbol": True},
    }
    (STATE_DIR / "market_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    with (LOG_DIR / "scanner.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"generated_at": generated, "top": [{"symbol": x["symbol"], "action": x["candidate_action"], "strategy": x["strategy"], "score": x["setup_score"]} for x in results[:10]]}) + "\n")
    print("=" * 76)
    print("AUTO FUTURES V4 — ADAPTIVE SCALP 24/7 — PAPER")
    print(generated)
    print("Universe:", len(universe), "| AI candidates:", len(shortlist), "| errors:", len(errors))
    print("=" * 76)
    for x in results[:12]:
        print(x["symbol"], "|", x["strategy"], "|", x["candidate_action"], "| SCORE", x["setup_score"])
        if x["candidate_action"] != "WAIT":
            print("  ENTRY", x["entry"], "SL", x["stop_loss"], "TP", x["tp1"], x["tp2"], x["tp3"])
    print("SNAPSHOT:", STATE_DIR / "market_snapshot.json")
    print("PAPER MODE ONLY")
    print("NO BINANCE ORDER WAS SENT")


if __name__ == "__main__":
    main()
