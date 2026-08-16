#!/usr/bin/env python3
import json, math, statistics, time, urllib.parse, urllib.request
from datetime import datetime, timezone

OKX_BASE = "https://www.okx.com"
COINS = "BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TON TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS IP LIT PUMP VIRTUAL XPL ZEC".split()
MEMES = set("SHIB BONK DOGE FLOKI MOODENG PENGU PEPE PNUT POPCAT TRUMP WIF AIXBT FARTCOIN PUMP".split())
MAJORS = set("BTC ETH SOL XRP ADA".split())
TF = {"D1":"1Dutc","H4":"4H","H1":"1H","M15":"15m","M5":"5m"}
TF_MS = {"D1":86400000,"H4":14400000,"H1":3600000,"M15":900000,"M5":300000}
CUTOFF = "2026-08-13T12:00:00Z"
RR_TARGET = 1.5
MAX_FORWARD_HOURS = 72


def iso_ms(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def ms_iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def http(url):
    req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"breakout-blind-v5"})
    for n in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception:
            if n == 3:
                raise
            time.sleep(0.8 * (n + 1))


def fv(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def rows(rs):
    out = []
    for r in rs:
        ts = int(r[0])
        out.append({
            "ts": ts,
            "datetime": ms_iso(ts),
            "open": fv(r[1]),
            "high": fv(r[2]),
            "low": fv(r[3]),
            "close": fv(r[4]),
            "volume": fv(r[5]),
        })
    return sorted([x for x in out if x["close"] is not None], key=lambda x: x["ts"])


def hist(inst, bar, cut, limit=300):
    u = f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar={bar}&after={cut}&limit={limit}"
    return rows(http(u).get("data") or [])


def future_page(inst, before, after):
    u = f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar=5m&before={before}&after={after}&limit=300"
    return rows(http(u).get("data") or [])


def ema(v, p):
    if len(v) < p:
        return None
    x = sum(v[:p]) / p
    k = 2 / (p + 1)
    for z in v[p:]:
        x = z * k + x * (1 - k)
    return x


def rsi(v, p=14):
    if len(v) <= p:
        return None
    g = l = 0.0
    for i in range(1, p + 1):
        d = v[i] - v[i - 1]
        g += max(d, 0)
        l += max(-d, 0)
    g /= p
    l /= p
    for i in range(p + 1, len(v)):
        d = v[i] - v[i - 1]
        g = (g * (p - 1) + max(d, 0)) / p
        l = (l * (p - 1) + max(-d, 0)) / p
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def atr(c, p=14):
    if len(c) <= p:
        return None
    tr = []
    for i in range(1, len(c)):
        cur, prev = c[i], c[i - 1]
        tr.append(max(cur["high"] - cur["low"], abs(cur["high"] - prev["close"]), abs(cur["low"] - prev["close"])))
    x = sum(tr[:p]) / p
    for z in tr[p:]:
        x = (x * (p - 1) + z) / p
    return x


def adx(c, p=14):
    if len(c) < p * 2 + 2:
        return None
    trs, plus, minus = [], [], []
    for i in range(1, len(c)):
        up = c[i]["high"] - c[i - 1]["high"]
        dn = c[i - 1]["low"] - c[i]["low"]
        plus.append(up if up > dn and up > 0 else 0.0)
        minus.append(dn if dn > up and dn > 0 else 0.0)
        trs.append(max(c[i]["high"] - c[i]["low"], abs(c[i]["high"] - c[i - 1]["close"]), abs(c[i]["low"] - c[i - 1]["close"])))
    atrs = sum(trs[:p]); ps = sum(plus[:p]); ms = sum(minus[:p]); dx = []
    for i in range(p, len(trs)):
        if i > p:
            atrs = atrs - atrs / p + trs[i]
            ps = ps - ps / p + plus[i]
            ms = ms - ms / p + minus[i]
        pdi = 100 * ps / atrs if atrs else 0
        mdi = 100 * ms / atrs if atrs else 0
        dx.append(100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0)
    if len(dx) < p:
        return None
    a = sum(dx[:p]) / p
    for z in dx[p:]:
        a = (a * (p - 1) + z) / p
    return a


def ret(c, n):
    if len(c) <= n or c[-n - 1]["close"] == 0:
        return 0.0
    return c[-1]["close"] / c[-n - 1]["close"] - 1


def structure(c, n=20):
    x = c[-n:]
    m = max(2, n // 2)
    a, b = x[:m], x[m:]
    hh = max(z["high"] for z in b) > max(z["high"] for z in a)
    hl = min(z["low"] for z in b) > min(z["low"] for z in a)
    lh = max(z["high"] for z in b) < max(z["high"] for z in a)
    ll = min(z["low"] for z in b) < min(z["low"] for z in a)
    return 1 if hh and hl else -1 if lh and ll else 0


def breakout(c, n=20):
    if len(c) < n + 1:
        return 0
    prev = c[-n - 1:-1]
    last = c[-1]
    if last["close"] > max(x["high"] for x in prev):
        return 1
    if last["close"] < min(x["low"] for x in prev):
        return -1
    return 0


def summ(c):
    v = [x["close"] for x in c]
    cl = v[-1]
    e20, e50, e200 = ema(v, 20), ema(v, 50), ema(v, 200)
    rr, aa, ax = rsi(v), atr(c), adx(c)
    trend = "neutral"
    if e20 is not None and e50 is not None:
        if cl > e20 > e50:
            trend = "bullish"
        elif cl < e20 < e50:
            trend = "bearish"
    vv = [x["volume"] or 0 for x in c[-21:]]
    base = sum(vv[:-1]) / max(1, len(vv) - 1)
    vr = vv[-1] / base if base else 1
    dist = (cl - e20) / aa if e20 is not None and aa else 0
    return {
        "close": cl, "ema20": e20, "ema50": e50, "ema200": e200,
        "rsi14": rr, "atr14": aa, "adx14": ax, "trend": trend,
        "dist20ATR": dist, "volumeRatio": vr,
    }


def load_frames(sym, cut):
    inst = f"{sym}-USDT"
    frames, sums = {}, {}
    for k, b in TF.items():
        c = [x for x in hist(inst, b, cut) if x["ts"] + TF_MS[k] <= cut]
        if len(c) < 60:
            raise RuntimeError(f"{k} insufficient:{len(c)}")
        frames[k] = c
        sums[k] = summ(c)
    return frames, sums


def regime(sums):
    h4, h1 = sums["H4"], sums["H1"]
    aligned = h4["trend"] == h1["trend"] and h4["trend"] != "neutral"
    if aligned and (h4["adx14"] or 0) >= 20 and (h1["adx14"] or 0) >= 18:
        return "trend"
    if (h4["adx14"] or 99) < 18 and (h1["adx14"] or 99) < 18:
        return "range"
    return "transition"


def directional_score(sym, sums, frames, btc_frames, btc_sums):
    rg = regime(sums)
    d1, h4, h1, m15, m5 = [sums[k] for k in ("D1","H4","H1","M15","M5")]

    # 1) HTF core: price structure + EMA50/200 + RSI, intentionally simple.
    htf = 0.0
    for k, wt in (("D1", 2.2), ("H4", 3.0), ("H1", 2.4)):
        s = sums[k]
        q = 0.0
        q += 1.0 if s["trend"] == "bullish" else -1.0 if s["trend"] == "bearish" else 0.0
        q += 0.45 * structure(frames[k])
        if s["ema200"] is not None:
            q += 0.25 if s["close"] > s["ema200"] else -0.25
        if s["rsi14"] is not None:
            q += 0.18 if s["rsi14"] >= 55 else -0.18 if s["rsi14"] <= 45 else 0.0
        htf += wt * q

    # 2) Setup quality: M15 then M5 trigger. Volume confirms but cannot create a trade alone.
    ltf = 0.0
    for k, wt in (("M15", 1.7), ("M5", 1.0)):
        s = sums[k]
        q = 0.0
        q += 1.0 if s["trend"] == "bullish" else -1.0 if s["trend"] == "bearish" else 0.0
        q += 0.35 * structure(frames[k])
        q += 0.30 * breakout(frames[k], 16 if k == "M15" else 20)
        direction = 1 if s["close"] >= s["ema20"] else -1
        q += 0.20 * direction * min(1.8, max(0.5, s["volumeRatio"]))
        ltf += wt * q

    # 3) Pullback/chase logic. In trend, prefer continuation but penalize entries already >1.5 ATR from EMA20.
    chase = 0.0
    for s, wt in ((h1, 1.0), (m15, 0.8), (m5, 0.4)):
        if s["dist20ATR"] > 1.5:
            chase -= wt
        elif s["dist20ATR"] < -1.5:
            chase += wt
    # Exhaustion is softer than prior V4.
    if (m15["rsi14"] or 50) > 74:
        chase -= 0.8
    elif (m15["rsi14"] or 50) < 26:
        chase += 0.8

    # 4) Range mode: mean reversion is only meaningful when HTF is actually range-like.
    meanrev = 0.0
    if rg == "range":
        for s, wt in ((h1, 0.8), (m15, 1.3), (m5, 0.7)):
            if s["dist20ATR"] > 1.2:
                meanrev -= wt
            elif s["dist20ATR"] < -1.2:
                meanrev += wt
            if (s["rsi14"] or 50) > 70:
                meanrev -= 0.45 * wt
            elif (s["rsi14"] or 50) < 30:
                meanrev += 0.45 * wt

    # 5) Relative strength: soft tiebreaker only, never dominant.
    rs = 0.0
    if sym != "BTC":
        rs1 = ret(frames["H1"], 12) - ret(btc_frames["H1"], 12)
        rs4 = ret(frames["H4"], 6) - ret(btc_frames["H4"], 6)
        rs = 1.2 * max(-1, min(1, rs1 / 0.03)) + 0.8 * max(-1, min(1, rs4 / 0.06))

    # 6) BTC market regime: low-weight macro beta filter for alts.
    btc_bias = 0.0
    if sym != "BTC":
        b = btc_sums
        btc_bias += 1 if b["H4"]["trend"] == "bullish" else -1 if b["H4"]["trend"] == "bearish" else 0
        btc_bias += 0.7 if b["H1"]["trend"] == "bullish" else -0.7 if b["H1"]["trend"] == "bearish" else 0

    if rg == "trend":
        final = 0.63 * htf + 0.27 * ltf + 0.07 * rs + 0.03 * btc_bias + chase
    elif rg == "range":
        final = 0.30 * htf + 0.20 * ltf + 0.40 * meanrev + 0.07 * rs + 0.03 * btc_bias + 0.5 * chase
    else:
        final = 0.50 * htf + 0.32 * ltf + 0.10 * rs + 0.08 * btc_bias + 0.75 * chase

    return final, {
        "regime": rg,
        "htfScore": htf,
        "ltfScore": ltf,
        "meanReversionScore": meanrev,
        "relativeStrengthScore": rs,
        "btcBias": btc_bias,
        "chaseAdjustment": chase,
    }


def choose(sym, sums, frames, btc_frames, btc_sums):
    sc, model = directional_score(sym, sums, frames, btc_frames, btc_sums)
    side = "BUY" if sc >= 0 else "SELL"
    entry = frames["M5"][-1]["close"]
    a = sums["M15"]["atr14"] or entry * 0.01
    recent = frames["M15"][-12:]
    mult = 1.55 if sym in MEMES else 1.35 if sym not in MAJORS else 1.20
    if side == "BUY":
        sl = min(min(x["low"] for x in recent), entry - mult * a)
        tp = entry + RR_TARGET * (entry - sl)
    else:
        sl = max(max(x["high"] for x in recent), entry + mult * a)
        tp = entry - RR_TARGET * (sl - entry)
    return side, sc, entry, sl, tp, model


def evaluate(inst, side, entry, sl, tp, cut):
    end = cut + MAX_FORWARD_HOURS * 3600000
    cursor = cut
    mfe = mae = 0.0
    seen = 0
    while cursor < end:
        nxt = min(end, cursor + 24 * 3600000)
        cs = [x for x in future_page(inst, cursor, nxt) if cursor <= x["ts"] < nxt]
        seen += len(cs)
        for x in cs:
            if side == "BUY":
                mfe = max(mfe, x["high"] - entry)
                mae = max(mae, entry - x["low"])
                hit_sl = x["low"] <= sl
                hit_tp = x["high"] >= tp
            else:
                mfe = max(mfe, entry - x["low"])
                mae = max(mae, x["high"] - entry)
                hit_sl = x["high"] >= sl
                hit_tp = x["low"] <= tp
            if hit_sl and hit_tp:
                return {"result":"AMBIGUOUS","mfe":mfe,"mae":mae,"candles":seen}
            if hit_sl:
                return {"result":"SL","mfe":mfe,"mae":mae,"candles":seen}
            if hit_tp:
                return {"result":"TP","mfe":mfe,"mae":mae,"candles":seen}
        cursor = nxt
    return {"result":"UNRESOLVED_72H","mfe":mfe,"mae":mae,"candles":seen}


def main():
    cut = iso_ms(CUTOFF)
    btc_frames, btc_sums = load_frames("BTC", cut)
    results = []
    for sym in COINS:
        try:
            frames, sums = (btc_frames, btc_sums) if sym == "BTC" else load_frames(sym, cut)
            side, sc, entry, sl, tp, model = choose(sym, sums, frames, btc_frames, btc_sums)
            out = evaluate(f"{sym}-USDT", side, entry, sl, tp, cut)
            results.append({
                "symbol": sym + "USDT",
                "cutoff": CUTOFF,
                "source": "OKX historical REST",
                "blind": True,
                "decision": side,
                "score": round(sc, 3),
                "entry": entry,
                "sl": sl,
                "tp1_5R": tp,
                "model": model,
                "snapshot": sums,
                "outcome": out,
            })
        except Exception as e:
            results.append({"symbol": sym + "USDT", "cutoff": CUTOFF, "error": str(e)})

    usable = [r for r in results if r.get("decision") in ("BUY", "SELL")]
    resolved = [r for r in usable if r.get("outcome", {}).get("result") in ("TP", "SL")]
    wins = sum(r["outcome"]["result"] == "TP" for r in resolved)
    losses = sum(r["outcome"]["result"] == "SL" for r in resolved)
    summary = {
        "requested": len(COINS),
        "marketTrades": len(usable),
        "dataErrors": len(results) - len(usable),
        "resolved": len(resolved),
        "wins": wins,
        "losses": losses,
        "unresolved": len(usable) - len(resolved),
        "winRateResolved": round(100 * wins / len(resolved), 2) if resolved else None,
        "expectancyR": round((wins * RR_TARGET - losses) / len(resolved), 3) if resolved else None,
    }
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": "V5 forced-market strict blind: simplified regime-first crypto model; D1/H4/H1 structure+EMA50/200+RSI, M15/M5 setup+volume, range-only mean reversion, soft BTC/relative-strength filter, anti-chase; structure+ATR SL; TP=1.5R; hidden future up to 72h",
        "universeRequested": len(COINS),
        "tests": results,
        "summary": summary,
    }
    with open("data/blind_backtest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
