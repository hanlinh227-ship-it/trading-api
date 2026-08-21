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
BROAD_DEEP_CANDIDATES = 18
AI_CANDIDATES = 12
BROAD_TIMEFRAMES = ("1m", "5m")
DEEP_TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d")
EXCLUDED_BASES = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "TRY", "BRL"}
EST_ROUNDTRIP_COST_BPS = 12.0
MAX_SPREAD_BPS = 12.0
POLICY_FILE = STATE_DIR / "adaptive_policy.json"

TF_WEIGHTS = {
    "1m": 0.55,
    "3m": 0.75,
    "5m": 1.00,
    "15m": 1.20,
    "30m": 1.25,
    "1h": 1.45,
    "4h": 1.20,
    "1d": 0.60,
}


def get_json(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "AUTO-FUTURES-V5-MTF-SCALP/1.0"})
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


def load_policy():
    try:
        if POLICY_FILE.exists():
            data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"strategy_multipliers": {}, "symbol_multipliers": {}, "regime_multipliers": {}, "status": "DEFAULT"}


def policy_multiplier(policy, symbol, strategy, regime):
    sm = float(policy.get("strategy_multipliers", {}).get(strategy, 1.0))
    xm = float(policy.get("symbol_multipliers", {}).get(symbol, 1.0))
    rm = float(policy.get("regime_multipliers", {}).get(regime, 1.0))
    return max(0.80, min(1.20, sm * xm * rm))


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


def book_spreads():
    out = {}
    try:
        rows = get_json("/fapi/v1/ticker/bookTicker")
        for x in rows:
            bid, ask = float(x.get("bidPrice", 0)), float(x.get("askPrice", 0))
            if bid > 0 and ask > bid:
                mid = (bid + ask) / 2.0
                out[x["symbol"]] = (ask - bid) / mid * 10000.0
    except Exception:
        pass
    return out


def analyze_tf(symbol, interval, limit=180):
    rows = get_json("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})[:-1]
    if len(rows) < 60:
        raise RuntimeError(f"insufficient {interval} candles")
    closes = [float(r[4]) for r in rows]
    highs = [float(r[2]) for r in rows]
    lows = [float(r[3]) for r in rows]
    vols = [float(r[5]) for r in rows]
    price = closes[-1]
    e9, e21, e50 = ema(closes[-100:], 9), ema(closes[-120:], 21), ema(closes[-160:], 50)
    a14 = atr(highs, lows, closes, 14)
    returns = [pct(closes[i], closes[i-1]) for i in range(max(1, len(closes)-30), len(closes))]
    rv = statistics.pstdev(returns) if len(returns) > 1 else 0.0
    avg_vol = statistics.mean(vols[-21:-1]) if len(vols) > 21 else statistics.mean(vols)
    vol_ratio = vols[-1] / avg_vol if avg_vol else 0.0
    recent_hi = max(highs[-20:])
    recent_lo = min(lows[-20:])
    long_range = max(highs[-50:]) - min(lows[-50:])
    short_range = max(highs[-10:]) - min(lows[-10:])
    compression = short_range / long_range if long_range > 0 else 1.0
    trend = "NEUTRAL"
    direction = 0
    if price > e9 > e21 > e50:
        trend, direction = "BULL", 1
    elif price < e9 < e21 < e50:
        trend, direction = "BEAR", -1
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
        "atr_pct": a14 / price * 100 if price else 0,
        "vwap": weighted_vwap(highs, lows, closes, vols),
        "volume_ratio": vol_ratio,
        "momentum_3": pct(closes[-1], closes[-4]),
        "momentum_10": pct(closes[-1], closes[-11]),
        "recent_high": recent_hi,
        "recent_low": recent_lo,
        "compression": compression,
        "realized_vol": rv,
        "trend": trend,
        "direction": direction,
        "distance_ema21_atr": (price - e21) / max(a14, price * 0.00005),
        "distance_vwap_atr": (price - weighted_vwap(highs, lows, closes, vols)) / max(a14, price * 0.00005),
    }


def broad_score(symbol):
    tf = {x: analyze_tf(symbol, x, 100) for x in BROAD_TIMEFRAMES}
    t1, t5 = tf["1m"], tf["5m"]
    participation = min(3.0, max(0.0, t1["volume_ratio"]))
    momentum = abs(t1["momentum_3"]) + abs(t5["momentum_3"]) * 0.7
    volatility = min(3.0, t5["atr_pct"] * 3.0)
    alignment = 1.0 if t1["direction"] * t5["direction"] > 0 else 0.0
    score = participation * 18.0 + momentum * 25.0 + volatility * 8.0 + alignment * 15.0
    return {"symbol": symbol, "broad_score": round(score, 3), "broad_timeframes": tf}


def mtf_structure(tf):
    def weighted(names):
        den = sum(TF_WEIGHTS[x] for x in names)
        return sum(float(tf[x]["direction"]) * TF_WEIGHTS[x] for x in names) / den if den else 0.0
    macro = weighted(("1h", "4h", "1d"))
    setup = weighted(("15m", "30m"))
    trigger = weighted(("1m", "3m", "5m"))
    total = weighted(DEEP_TIMEFRAMES)
    regime = "MIXED"
    if abs(macro) >= 0.45 and abs(setup) >= 0.35 and macro * setup > 0:
        regime = "TREND"
    elif tf["15m"]["compression"] < 0.32 or tf["30m"]["compression"] < 0.32:
        regime = "SQUEEZE"
    elif abs(macro) < 0.25 and abs(setup) < 0.25:
        regime = "RANGE"
    elif abs(trigger) > 0.55 and macro * trigger < 0:
        regime = "COUNTERTREND"
    return {
        "macro": round(macro, 4),
        "setup": round(setup, 4),
        "trigger": round(trigger, 4),
        "total": round(total, 4),
        "regime": regime,
        "macro_direction": "BULL" if macro > 0.2 else "BEAR" if macro < -0.2 else "NEUTRAL",
        "setup_direction": "BULL" if setup > 0.2 else "BEAR" if setup < -0.2 else "NEUTRAL",
        "trigger_direction": "BULL" if trigger > 0.2 else "BEAR" if trigger < -0.2 else "NEUTRAL",
    }


def standardized_entry_gate(action, strategy, tf, mtf, spread_bps):
    blockers = []
    warnings = []
    sign = 1 if action == "LONG" else -1
    trigger_votes = [1 if tf[x]["direction"] * sign > 0 else 0 for x in ("1m", "3m", "5m")]
    setup_conflict = mtf["setup"] * sign < -0.30
    macro_conflict = mtf["macro"] * sign < -0.50
    if sum(trigger_votes) < 2:
        blockers.append("ENTRY_GATE: fewer than 2/3 execution timeframes confirm")
    if setup_conflict:
        blockers.append("ENTRY_GATE: 15m/30m setup layer opposes entry")
    if macro_conflict:
        blockers.append("ENTRY_GATE: 1h/4h/1d macro layer strongly opposes entry")
    if spread_bps is not None and spread_bps > MAX_SPREAD_BPS:
        blockers.append(f"ENTRY_GATE: spread too wide ({spread_bps:.2f} bps)")
    if strategy != "MEAN_REVERSION" and tf["5m"]["distance_ema21_atr"] * sign > 2.3:
        blockers.append("ENTRY_GATE: 5m extension too large")
    if tf["1m"]["volume_ratio"] < 0.40:
        warnings.append("low 1m participation")
    if tf["5m"]["atr_pct"] <= 0.01:
        blockers.append("ENTRY_GATE: volatility too low for scalp")
    return blockers, warnings


def build_deep_setup(symbol, broad, spread_bps, policy):
    tf = {}
    for x in DEEP_TIMEFRAMES:
        tf[x] = broad["broad_timeframes"].get(x) or analyze_tf(symbol, x)
    mtf = mtf_structure(tf)
    t1, t3, t5, t15, t30 = tf["1m"], tf["3m"], tf["5m"], tf["15m"], tf["30m"]
    price = t1["price"]
    a1 = max(t1["atr14"], price * 0.00015)
    a5 = max(t5["atr14"], price * 0.00035)
    strategy, action, base_score = "NO_EDGE", "WAIT", 0.0
    reasons, warnings, blockers = [], [], []

    aligned_bull = mtf["macro"] > 0.25 and mtf["setup"] > 0.25
    aligned_bear = mtf["macro"] < -0.25 and mtf["setup"] < -0.25
    near_ema = abs(price - t1["ema21"]) <= max(a1 * 0.85, price * 0.00035)
    near_vwap = abs(price - t1["vwap"]) <= max(a1 * 0.90, price * 0.00035)
    squeeze = t15["compression"] < 0.32 or t30["compression"] < 0.30
    breakout_up = price >= t5["recent_high"] - 0.20 * a5
    breakout_dn = price <= t5["recent_low"] + 0.20 * a5

    if aligned_bull and (near_ema or near_vwap) and mtf["trigger"] >= 0.15 and 38 <= t1["rsi14"] <= 68:
        strategy, action, base_score = "TREND_PULLBACK", "LONG", 72
        reasons.append("macro+setup bullish; execution layer confirms controlled pullback")
    elif aligned_bear and (near_ema or near_vwap) and mtf["trigger"] <= -0.15 and 32 <= t1["rsi14"] <= 62:
        strategy, action, base_score = "TREND_PULLBACK", "SHORT", 72
        reasons.append("macro+setup bearish; execution layer confirms controlled pullback")
    elif squeeze and breakout_up and t1["volume_ratio"] >= 1.30 and t3["momentum_3"] > 0 and mtf["setup"] >= -0.10:
        strategy, action, base_score = "BREAKOUT", "LONG", 69
        reasons.append("15m/30m compression breaks upward with 1m/3m participation")
    elif squeeze and breakout_dn and t1["volume_ratio"] >= 1.30 and t3["momentum_3"] < 0 and mtf["setup"] <= 0.10:
        strategy, action, base_score = "BREAKOUT", "SHORT", 69
        reasons.append("15m/30m compression breaks downward with 1m/3m participation")
    elif aligned_bull and mtf["trigger"] > 0.35 and t1["volume_ratio"] >= 1.15 and t5["momentum_3"] > 0:
        strategy, action, base_score = "MOMENTUM", "LONG", 66
        reasons.append("multi-layer bullish momentum with active participation")
    elif aligned_bear and mtf["trigger"] < -0.35 and t1["volume_ratio"] >= 1.15 and t5["momentum_3"] < 0:
        strategy, action, base_score = "MOMENTUM", "SHORT", 66
        reasons.append("multi-layer bearish momentum with active participation")
    elif mtf["regime"] == "RANGE":
        dev = t1["distance_vwap_atr"]
        if dev <= -1.5 and t1["rsi14"] < 30 and mtf["trigger"] > -0.50:
            strategy, action, base_score = "MEAN_REVERSION", "LONG", 62
            reasons.append("range regime downside VWAP deviation with exhaustion")
        elif dev >= 1.5 and t1["rsi14"] > 70 and mtf["trigger"] < 0.50:
            strategy, action, base_score = "MEAN_REVERSION", "SHORT", 62
            reasons.append("range regime upside VWAP deviation with exhaustion")

    if action in {"LONG", "SHORT"}:
        b, w = standardized_entry_gate(action, strategy, tf, mtf, spread_bps)
        blockers.extend(b)
        warnings.extend(w)
        sign = 1 if action == "LONG" else -1
        alignment_bonus = max(-8.0, min(10.0, mtf["total"] * sign * 10.0))
        base_score += alignment_bonus
        if t1["volume_ratio"] >= 1.5:
            base_score += 4
        if abs(t1["distance_vwap_atr"]) > 2.5 and strategy != "MEAN_REVERSION":
            base_score -= 8
            warnings.append("execution price far from 1m VWAP")
        if (action == "LONG" and t1["rsi14"] > 80) or (action == "SHORT" and t1["rsi14"] < 20):
            base_score -= 10
            warnings.append("1m exhaustion/chase risk")

    multiplier = policy_multiplier(policy, symbol, strategy, mtf["regime"])
    learned_score = base_score * multiplier
    score = max(0, min(100, round(learned_score, 2)))
    if blockers or score < 58:
        action = "WAIT"

    entry = stop = tp1 = tp2 = tp3 = None
    management = {"tp1_close_pct": 30, "tp2_close_pct": 30, "runner_pct": 40,
                  "breakeven_after_tp1": True, "trail_after_tp2": True, "trail_atr_mult": 0.85}
    if action in {"LONG", "SHORT"}:
        if strategy == "BREAKOUT":
            sl_atr, rrs, trail = 1.15, (1.0, 1.8, 3.0), 1.05
        elif strategy == "MEAN_REVERSION":
            sl_atr, rrs, trail = 0.90, (0.8, 1.35, 2.0), 0.75
        elif strategy == "MOMENTUM":
            sl_atr, rrs, trail = 1.00, (1.0, 1.7, 2.6), 0.90
        else:
            sl_atr, rrs, trail = 0.95, (1.0, 1.8, 2.8), 0.85
        entry = price
        noise_floor = max(a1 * 0.85, price * 0.0007)
        if action == "LONG":
            structural = min(t1["recent_low"], t3["recent_low"]) - 0.10 * a5
            stop = min(structural, entry - sl_atr * a5)
            if entry - stop < noise_floor:
                stop = entry - noise_floor
            risk = entry - stop
            tp1, tp2, tp3 = (entry + risk * r for r in rrs)
        else:
            structural = max(t1["recent_high"], t3["recent_high"]) + 0.10 * a5
            stop = max(structural, entry + sl_atr * a5)
            if stop - entry < noise_floor:
                stop = entry + noise_floor
            risk = stop - entry
            tp1, tp2, tp3 = (entry - risk * r for r in rrs)
        management["trail_atr_mult"] = trail
        tp1_bps = abs(tp1 - entry) / entry * 10000.0 if entry else 0.0
        if tp1_bps < EST_ROUNDTRIP_COST_BPS * 1.8:
            blockers.append("ENTRY_GATE: TP1 edge too small versus estimated fees/slippage")
            action = "WAIT"
            entry = stop = tp1 = tp2 = tp3 = None

    return {
        "symbol": symbol,
        "candidate_action": action,
        "strategy": strategy,
        "regime": mtf["regime"],
        "setup_score": score,
        "setup_quality": score,
        "base_score": round(base_score, 2),
        "learning_multiplier": round(multiplier, 4),
        "entry": entry,
        "stop_loss": stop,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "timeframes": tf,
        "mtf_alignment": mtf,
        "spread_bps": spread_bps,
        "estimated_roundtrip_cost_bps": EST_ROUNDTRIP_COST_BPS,
        "reasons": reasons,
        "warnings": warnings,
        "blockers": blockers,
        "management": management,
        "entry_standard": {
            "deep_timeframes_required": list(DEEP_TIMEFRAMES),
            "trigger_layer": ["1m", "3m", "5m"],
            "setup_layer": ["15m", "30m"],
            "macro_layer": ["1h", "4h", "1d"],
            "requires_2_of_3_trigger_confirmation": True,
            "macro_strong_opposition_blocks": True,
            "setup_opposition_blocks": True,
            "spread_gate_bps": MAX_SPREAD_BPS,
            "cost_edge_gate": True,
        },
        "broad_score": broad["broad_score"],
    }


def enrich_derivatives(setup):
    symbol = setup["symbol"]
    try:
        p = get_json("/fapi/v1/premiumIndex", {"symbol": symbol})
        oi = get_json("/fapi/v1/openInterest", {"symbol": symbol})
        setup["funding_rate"] = float(p.get("lastFundingRate", 0.0))
        setup["open_interest"] = float(oi.get("openInterest", 0.0))
        try:
            hist = get_json("/futures/data/openInterestHist", {"symbol": symbol, "period": "5m", "limit": 3})
            if len(hist) >= 2:
                a = float(hist[-2].get("sumOpenInterest", 0))
                b = float(hist[-1].get("sumOpenInterest", 0))
                setup["open_interest_change_pct"] = pct(b, a)
            else:
                setup["open_interest_change_pct"] = 0.0
        except Exception:
            setup["open_interest_change_pct"] = 0.0
        try:
            taker = get_json("/futures/data/takerlongshortRatio", {"symbol": symbol, "period": "5m", "limit": 3})
            setup["taker_buy_sell_ratio"] = float(taker[-1].get("buySellRatio", 1.0)) if taker else 1.0
        except Exception:
            setup["taker_buy_sell_ratio"] = 1.0
    except Exception as exc:
        setup["funding_rate"], setup["open_interest"] = 0.0, 0.0
        setup["open_interest_change_pct"], setup["taker_buy_sell_ratio"] = 0.0, 1.0
        setup["warnings"].append(f"derivatives enrichment unavailable: {type(exc).__name__}")
    return setup


def main():
    generated = datetime.now(timezone.utc).isoformat()
    universe = select_universe()
    spreads = book_spreads()
    policy = load_policy()
    broad_results, broad_errors = [], []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(broad_score, s): s for s in universe}
        for f in as_completed(futs):
            s = futs[f]
            try:
                broad_results.append(f.result())
            except Exception as exc:
                broad_errors.append({"symbol": s, "stage": "broad", "error": repr(exc)})
    broad_results.sort(key=lambda x: x["broad_score"], reverse=True)
    deep_targets = broad_results[:BROAD_DEEP_CANDIDATES]

    deep_results, deep_errors = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(build_deep_setup, x["symbol"], x, spreads.get(x["symbol"]), policy): x["symbol"] for x in deep_targets}
        for f in as_completed(futs):
            s = futs[f]
            try:
                deep_results.append(f.result())
            except Exception as exc:
                deep_errors.append({"symbol": s, "stage": "deep", "error": repr(exc)})

    deep_results.sort(key=lambda x: (x["candidate_action"] != "WAIT", x["setup_score"]), reverse=True)
    shortlist = deep_results[:AI_CANDIDATES]
    with ThreadPoolExecutor(max_workers=6) as pool:
        shortlist = list(pool.map(enrich_derivatives, shortlist))
    short_map = {x["symbol"]: x for x in shortlist}
    deep_results = [short_map.get(x["symbol"], x) for x in deep_results]

    broad_only = []
    deep_symbols = {x["symbol"] for x in deep_results}
    for x in broad_results:
        if x["symbol"] not in deep_symbols:
            broad_only.append({
                "symbol": x["symbol"], "candidate_action": "WAIT", "strategy": "BROAD_FILTER_ONLY",
                "regime": "UNASSESSED_DEEP_MTF", "setup_score": 0, "setup_quality": 0,
                "entry": None, "stop_loss": None, "tp1": None, "tp2": None, "tp3": None,
                "timeframes": x["broad_timeframes"], "mtf_alignment": {}, "spread_bps": spreads.get(x["symbol"]),
                "reasons": ["not promoted to deep multi-timeframe candidate"], "warnings": [],
                "blockers": ["ENTRY_GATE: deep multi-timeframe assessment required before any trade"],
                "management": {}, "broad_score": x["broad_score"],
            })

    all_results = deep_results + broad_only
    snapshot = {
        "generated_at": generated,
        "mode": "PAPER",
        "live_trading": False,
        "engine": "AUTO_FUTURES_V5_MTF_ADAPTIVE_SCALP",
        "universe_size": len(universe),
        "universe": universe,
        "deep_assessed_symbols": [x["symbol"] for x in deep_results],
        "deep_timeframes": list(DEEP_TIMEFRAMES),
        "setups": all_results,
        "ai_candidates": shortlist,
        "errors": broad_errors + deep_errors,
        "policy": {
            "style": "SCALP_ONLY_24_7",
            "daily_trade_limit": None,
            "daily_loss_limit": None,
            "max_loss_limit": None,
            "per_trade_stop_required": True,
            "adaptive_strategy_per_symbol": True,
            "entry_requires_deep_mtf": True,
            "learning_policy_status": policy.get("status", "DEFAULT"),
            "learning_policy_generated_at": policy.get("generated_at"),
        },
    }
    (STATE_DIR / "market_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    with (LOG_DIR / "scanner.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"generated_at": generated, "engine": snapshot["engine"], "top": [{"symbol": x["symbol"], "action": x["candidate_action"], "strategy": x["strategy"], "regime": x.get("regime"), "score": x["setup_score"]} for x in deep_results[:12]]}) + "\n")
    print("=" * 84)
    print("AUTO FUTURES V5 — MULTI-TIMEFRAME ADAPTIVE SCALP 24/7 — PAPER")
    print(generated)
    print("Universe:", len(universe), "| deep MTF:", len(deep_results), "| AI candidates:", len(shortlist), "| errors:", len(snapshot["errors"]))
    print("Deep TF:", ",".join(DEEP_TIMEFRAMES))
    print("=" * 84)
    for x in deep_results[:12]:
        m = x.get("mtf_alignment", {})
        print(x["symbol"], "|", x["regime"], "|", x["strategy"], "|", x["candidate_action"], "| SCORE", x["setup_score"], "| MTF", m.get("macro"), m.get("setup"), m.get("trigger"))
        if x["candidate_action"] != "WAIT":
            print("  ENTRY", x["entry"], "SL", x["stop_loss"], "TP", x["tp1"], x["tp2"], x["tp3"], "spread_bps", x.get("spread_bps"))
        if x.get("blockers"):
            print("  BLOCK", "; ".join(x["blockers"]))
    print("SNAPSHOT:", STATE_DIR / "market_snapshot.json")
    print("PAPER MODE ONLY")
    print("NO BINANCE ORDER WAS SENT")


if __name__ == "__main__":
    main()
