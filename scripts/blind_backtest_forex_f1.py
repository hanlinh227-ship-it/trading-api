#!/usr/bin/env python3
import json
import math
import os
import statistics
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

PAIRS = [
    "EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
    "EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY",
    "GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD",
    "AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY",
]
CURRENCIES = ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]

# Locked before any outcome inspection. First 5 = development for RR only;
# final 5 = holdout validation and must not influence RR selection.
DEV_CUTOFFS = [
    "2026-06-22T08:00:00Z",
    "2026-06-23T08:00:00Z",
    "2026-06-25T08:00:00Z",
    "2026-07-03T08:00:00Z",
    "2026-07-14T08:00:00Z",
]
VAL_CUTOFFS = [
    "2026-07-15T08:00:00Z",
    "2026-07-16T08:00:00Z",
    "2026-07-23T08:00:00Z",
    "2026-07-29T08:00:00Z",
    "2026-07-30T08:00:00Z",
]
ALL_CUTOFFS = DEV_CUTOFFS + VAL_CUTOFFS
RR_GRID = [1.30, 1.50, 1.80, 2.00, 2.20]
END_DATE = "2026-08-03 08:00:00"
OUTPUTSIZE = 4000
LIMIT_PULLBACK_R = 0.30
LIMIT_EXPIRY_HOURS = 4
TRADE_EXPIRY_HOURS = 24


def iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def ema(values, period):
    if not values:
        return None
    a = 2.0 / (period + 1.0)
    x = values[0]
    for v in values[1:]:
        x = a * v + (1.0 - a) * x
    return x


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for a, b in zip(closes[-period-1:-1], closes[-period:]):
        d = b - a
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains) / period
    al = sum(losses) / period
    if al == 0:
        return 100.0
    rs = ag / al
    return 100.0 - 100.0 / (1.0 + rs)


def atr(rows, period=14):
    if len(rows) < period + 1:
        return None
    rs = rows[-period-1:]
    tr = []
    for i in range(1, len(rs)):
        prev = rs[i-1]["close"]
        r = rs[i]
        tr.append(max(r["high"]-r["low"], abs(r["high"]-prev), abs(r["low"]-prev)))
    return sum(tr) / len(tr) if tr else None


def floor_bucket(dt, hours):
    h = (dt.hour // hours) * hours
    return dt.replace(hour=h, minute=0, second=0, microsecond=0)


def aggregate(rows, hours):
    buckets = defaultdict(list)
    for r in rows:
        buckets[floor_bucket(r["dt"], hours)].append(r)
    out = []
    expected = hours * 4
    for dt in sorted(buckets):
        g = buckets[dt]
        # Avoid partial higher-timeframe bars. Weekend/session gaps are naturally absent.
        if len(g) < max(1, expected - 1):
            continue
        out.append({
            "dt": dt,
            "open": g[0]["open"],
            "high": max(x["high"] for x in g),
            "low": min(x["low"] for x in g),
            "close": g[-1]["close"],
        })
    return out


def nearest_close(rows, target):
    best = None
    for r in rows:
        if r["dt"] <= target:
            best = r["close"]
        else:
            break
    return best


def zmap(values):
    xs = list(values.values())
    if len(xs) < 2:
        return {k: 0.0 for k in values}
    mu = statistics.mean(xs)
    sd = statistics.pstdev(xs)
    if sd < 1e-12:
        return {k: 0.0 for k in values}
    return {k: (v-mu)/sd for k, v in values.items()}


def parse_batch_payload(payload):
    out = {}
    # Batch /time_series normally maps requested symbols to individual responses.
    if isinstance(payload, dict) and "values" not in payload:
        for key, val in payload.items():
            if not isinstance(val, dict):
                continue
            inner = val.get("data") if isinstance(val.get("data"), dict) else val
            if isinstance(inner, dict) and inner.get("values"):
                symbol = (inner.get("meta") or {}).get("symbol") or key
                out[symbol.replace("/", "").upper()] = inner
    elif isinstance(payload, dict) and payload.get("values"):
        symbol = (payload.get("meta") or {}).get("symbol")
        if symbol:
            out[symbol.replace("/", "").upper()] = payload
    return out


def fetch_all():
    api_key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TWELVEDATA_API_KEY missing")
    raw = {}
    groups = [PAIRS[i:i+7] for i in range(0, len(PAIRS), 7)]
    for gi, group in enumerate(groups):
        td_symbols = [f"{p[:3]}/{p[3:]}" for p in group]
        params = {
            "symbol": ",".join(td_symbols),
            "interval": "15min",
            "outputsize": str(OUTPUTSIZE),
            "end_date": END_DATE,
            "timezone": "UTC",
            "order": "asc",
            "apikey": api_key,
        }
        url = "https://api.twelvedata.com/time_series?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "trading-api-forex-blind/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"Twelve Data batch {gi+1} failed: {e}")
        parsed = parse_batch_payload(payload)
        missing = [p for p in group if p not in parsed]
        if missing:
            detail = payload if len(str(payload)) < 3000 else str(payload)[:3000]
            raise RuntimeError(f"Batch {gi+1} missing {missing}; response={detail}")
        raw.update(parsed)
        print(f"Fetched batch {gi+1}/{len(groups)}: {', '.join(group)}")
        if gi != len(groups)-1:
            time.sleep(66)
    return raw


def normalize_rows(item):
    rows = []
    for x in item.get("values", []):
        dt = datetime.fromisoformat(x["datetime"]).replace(tzinfo=timezone.utc)
        rows.append({
            "dt": dt,
            "open": float(x["open"]),
            "high": float(x["high"]),
            "low": float(x["low"]),
            "close": float(x["close"]),
        })
    rows.sort(key=lambda x: x["dt"])
    return rows


def currency_strength(frames, cutoff):
    r24, r72 = {}, {}
    for p, rows in frames.items():
        pre = [r for r in rows if r["dt"] + timedelta(minutes=15) <= cutoff]
        if not pre:
            continue
        now = pre[-1]["close"]
        c24 = nearest_close(pre, cutoff - timedelta(hours=24))
        c72 = nearest_close(pre, cutoff - timedelta(hours=72))
        if c24 and c72 and now > 0 and c24 > 0 and c72 > 0:
            r24[p] = math.log(now/c24)
            r72[p] = math.log(now/c72)
    z24, z72 = zmap(r24), zmap(r72)
    strength = {c: [] for c in CURRENCIES}
    for p in PAIRS:
        if p not in z24 or p not in z72:
            continue
        val = 0.65*z24[p] + 0.35*z72[p]
        b, q = p[:3], p[3:]
        strength[b].append(val)
        strength[q].append(-val)
    return {c: (statistics.mean(v) if v else 0.0) for c, v in strength.items()}


def pair_features(pair, rows, cutoff, cstrength):
    pre = [r for r in rows if r["dt"] + timedelta(minutes=15) <= cutoff]
    if len(pre) < 300:
        return None
    h1 = aggregate(pre, 1)
    h4 = aggregate(pre, 4)
    if len(h1) < 60 or len(h4) < 55:
        return None
    m15 = pre
    px = m15[-1]["close"]
    a15 = atr(m15, 14)
    a1 = atr(h1, 14)
    if not a15 or not a1:
        return None

    h4c = [x["close"] for x in h4]
    h1c = [x["close"] for x in h1]
    m15c = [x["close"] for x in m15]
    h4e20 = ema(h4c[-80:], 20); h4e50 = ema(h4c[-120:], 50)
    h4e20_prev = ema(h4c[-83:-3], 20) if len(h4c) >= 83 else h4e20
    h1e20 = ema(h1c[-80:], 20); h1e50 = ema(h1c[-120:], 50)
    m15e20 = ema(m15c[-80:], 20)
    h1rsi = rsi(h1c, 14)
    if None in (h4e20,h4e50,h1e20,h1e50,m15e20,h1rsi):
        return None

    base, quote = pair[:3], pair[3:]
    curr_diff = cstrength.get(base,0.0) - cstrength.get(quote,0.0)

    h4score = 0.0
    if px > h4e20 > h4e50: h4score += 1.5
    elif px < h4e20 < h4e50: h4score -= 1.5
    h4score += 0.5 if h4e20 > h4e20_prev else -0.5

    h1score = 0.0
    if px > h1e20 > h1e50: h1score += 1.1
    elif px < h1e20 < h1e50: h1score -= 1.1
    if h1rsi >= 55: h1score += 0.4
    elif h1rsi <= 45: h1score -= 0.4

    m15score = 0.4 if px > m15e20 else -0.4
    mom4 = math.log(m15c[-1]/m15c[-5]) if len(m15c) >= 5 else 0.0
    m15score += 0.35 if mom4 >= 0 else -0.35

    score = 1.50*curr_diff + h4score + h1score + m15score
    side = "BUY" if score >= 0 else "SELL"
    sgn = 1 if side == "BUY" else -1

    chase_atr = abs(px - m15e20) / a15
    h4align = (h4score*sgn) > 0
    h1align = (h1score*sgn) > 0
    m15align = (m15score*sgn) > 0
    stretched_reversal = (
        (side == "BUY" and h1rsi >= 72 and mom4 < 0) or
        (side == "SELL" and h1rsi <= 28 and mom4 > 0)
    )

    recent = m15[-8:]
    if side == "BUY":
        structure = min(x["low"] for x in recent)
        raw_risk = px - structure + 0.15*a15
    else:
        structure = max(x["high"] for x in recent)
        raw_risk = structure - px + 0.15*a15
    risk = max(raw_risk, 1.00*a15)
    risk_atr = risk/a15
    sl = px - risk if side == "BUY" else px + risk

    quality = abs(score)
    if h4align: quality += 0.55
    if h1align: quality += 0.45
    if m15align: quality += 0.20
    if chase_atr > 1.25: quality -= 1.20
    if risk_atr > 2.20: quality -= 0.80
    if stretched_reversal: quality -= 1.50

    selective_ok = (
        abs(score) >= 2.20 and h4align and h1align and
        chase_atr <= 1.35 and risk_atr <= 2.60 and not stretched_reversal
    )
    return {
        "symbol": pair, "side": side, "entry": px, "sl": sl, "risk": risk,
        "score": round(score,4), "quality": round(quality,4),
        "currencyDiff": round(curr_diff,4), "h4Score": round(h4score,3),
        "h1Score": round(h1score,3), "m15Score": round(m15score,3),
        "h1Rsi": round(h1rsi,2), "chaseATR": round(chase_atr,3),
        "riskATR": round(risk_atr,3), "stretchedReversal": stretched_reversal,
        "selectiveOK": selective_ok,
    }


def evaluate_market(feature, rows, cutoff, rr):
    side=feature["side"]; en=feature["entry"]; sl=feature["sl"]; risk=feature["risk"]
    tp = en + risk*rr if side == "BUY" else en - risk*rr
    end = cutoff + timedelta(hours=TRADE_EXPIRY_HOURS)
    future = [r for r in rows if cutoff <= r["dt"] < end]
    for i,r in enumerate(future,1):
        hit_sl = r["low"] <= sl if side=="BUY" else r["high"] >= sl
        hit_tp = r["high"] >= tp if side=="BUY" else r["low"] <= tp
        if hit_sl and hit_tp:
            return {"result":"AMBIGUOUS","bars":i,"tp":tp,"rr":rr}
        if hit_sl:
            return {"result":"SL","bars":i,"tp":tp,"rr":rr}
        if hit_tp:
            return {"result":"TP","bars":i,"tp":tp,"rr":rr}
    return {"result":"TIMEOUT","bars":len(future),"tp":tp,"rr":rr}


def evaluate_limit(feature, rows, cutoff, rr):
    side=feature["side"]; en=feature["entry"]; sl=feature["sl"]; risk=feature["risk"]
    market_tp = en + risk*rr if side=="BUY" else en - risk*rr
    limit = en - LIMIT_PULLBACK_R*risk if side=="BUY" else en + LIMIT_PULLBACK_R*risk
    fill_deadline = cutoff + timedelta(hours=LIMIT_EXPIRY_HOURS)
    trade_deadline = cutoff + timedelta(hours=TRADE_EXPIRY_HOURS)
    future = [r for r in rows if cutoff <= r["dt"] < trade_deadline]
    fill_i = None
    for i,r in enumerate(future):
        if r["dt"] >= fill_deadline:
            break
        target_before = r["high"] >= market_tp if side=="BUY" else r["low"] <= market_tp
        fill = r["low"] <= limit if side=="BUY" else r["high"] >= limit
        if target_before and not fill:
            return {"result":"TARGET_BEFORE_FILL","filled":False,"limit":limit,"tp":market_tp}
        if fill:
            fill_i = i
            break
    if fill_i is None:
        return {"result":"NO_FILL","filled":False,"limit":limit,"tp":market_tp}
    lim_risk = abs(limit-sl)
    effective_rr = abs(market_tp-limit)/lim_risk if lim_risk>0 else None
    for j,r in enumerate(future[fill_i:],1):
        hit_sl = r["low"] <= sl if side=="BUY" else r["high"] >= sl
        hit_tp = r["high"] >= market_tp if side=="BUY" else r["low"] <= market_tp
        if hit_sl and hit_tp:
            return {"result":"AMBIGUOUS","filled":True,"bars":j,"limit":limit,"tp":market_tp,"effectiveRR":effective_rr}
        if hit_sl:
            return {"result":"SL","filled":True,"bars":j,"limit":limit,"tp":market_tp,"effectiveRR":effective_rr}
        if hit_tp:
            return {"result":"TP","filled":True,"bars":j,"limit":limit,"tp":market_tp,"effectiveRR":effective_rr}
    return {"result":"TIMEOUT","filled":True,"bars":len(future)-fill_i,"limit":limit,"tp":market_tp,"effectiveRR":effective_rr}


def summarize_market(rows, rr):
    resolved=[x for x in rows if x["outcome"]["result"] in ("TP","SL")]
    wins=sum(x["outcome"]["result"]=="TP" for x in resolved)
    losses=len(resolved)-wins
    exp=(wins*rr-losses)/len(resolved) if resolved else None
    return {"signals":len(rows),"resolved":len(resolved),"wins":wins,"losses":losses,
            "timeouts":sum(x["outcome"]["result"]=="TIMEOUT" for x in rows),
            "ambiguous":sum(x["outcome"]["result"]=="AMBIGUOUS" for x in rows),
            "winRateResolved":round(100*wins/len(resolved),2) if resolved else None,
            "rr":rr,"expectancyR":round(exp,3) if exp is not None else None}


def summarize_limit(rows):
    fills=[x for x in rows if x["outcome"].get("filled")]
    resolved=[x for x in fills if x["outcome"]["result"] in ("TP","SL")]
    wins=sum(x["outcome"]["result"]=="TP" for x in resolved)
    losses=len(resolved)-wins
    rrvals=[x["outcome"].get("effectiveRR") for x in resolved if x["outcome"].get("effectiveRR") is not None]
    total=0.0
    for x in resolved:
        total += x["outcome"].get("effectiveRR",0.0) if x["outcome"]["result"]=="TP" else -1.0
    return {"signals":len(rows),"fills":len(fills),"fillRate":round(100*len(fills)/len(rows),2) if rows else None,
            "resolved":len(resolved),"wins":wins,"losses":losses,
            "noFill":sum(x["outcome"]["result"]=="NO_FILL" for x in rows),
            "targetBeforeFill":sum(x["outcome"]["result"]=="TARGET_BEFORE_FILL" for x in rows),
            "timeoutsAfterFill":sum(x["outcome"]["result"]=="TIMEOUT" and x["outcome"].get("filled") for x in rows),
            "ambiguous":sum(x["outcome"]["result"]=="AMBIGUOUS" for x in rows),
            "winRateResolved":round(100*wins/len(resolved),2) if resolved else None,
            "avgEffectiveRR":round(statistics.mean(rrvals),3) if rrvals else None,
            "expectancyR":round(total/len(resolved),3) if resolved else None}


def select_top3(features):
    eligible=[x for x in features if x["selectiveOK"]]
    eligible.sort(key=lambda x:x["quality"], reverse=True)
    chosen=[]; exposure=defaultdict(int)
    for f in eligible:
        b,q=f["symbol"][:3],f["symbol"][3:]
        if exposure[b] >= 2 or exposure[q] >= 2:
            continue
        chosen.append(f); exposure[b]+=1; exposure[q]+=1
        if len(chosen)==3: break
    return chosen


def build_cutoff(frames, cutoff, rr):
    cs=currency_strength(frames, cutoff)
    feats=[]
    for p in PAIRS:
        f=pair_features(p, frames[p], cutoff, cs)
        if f: feats.append(f)
    forced=[]
    for f in feats:
        forced.append({"feature":f,"outcome":evaluate_market(f,frames[f["symbol"]],cutoff,rr)})
    top=select_top3(feats)
    selective=[]; limits=[]
    for f in top:
        selective.append({"feature":f,"outcome":evaluate_market(f,frames[f["symbol"]],cutoff,rr)})
        limits.append({"feature":f,"outcome":evaluate_limit(f,frames[f["symbol"]],cutoff,rr)})
    return {"currencyStrength":{k:round(v,4) for k,v in cs.items()},"features":feats,
            "forced":forced,"selective":selective,"limits":limits}


def flatten(blocks, key):
    out=[]
    for b in blocks.values(): out.extend(b[key])
    return out


def main():
    raw=fetch_all()
    frames={p:normalize_rows(raw[p]) for p in PAIRS}

    # Development: compare RR only on the first five cutoffs, using selective MARKET.
    rr_dev={}
    dev_cache={}
    for rr in RR_GRID:
        blocks={c:build_cutoff(frames,iso(c),rr) for c in DEV_CUTOFFS}
        dev_cache[rr]=blocks
        rr_dev[str(rr)]=summarize_market(flatten(blocks,"selective"),rr)
    viable=[]
    for rr in RR_GRID:
        s=rr_dev[str(rr)]
        if s["resolved"] >= 8 and s["expectancyR"] is not None:
            viable.append((s["expectancyR"], s["winRateResolved"] or 0, -rr, rr))
    chosen_rr=max(viable)[-1] if viable else 1.5

    # Rebuild frozen chosen RR for dev and unseen validation.
    dev=dev_cache[chosen_rr]
    val={c:build_cutoff(frames,iso(c),chosen_rr) for c in VAL_CUTOFFS}

    def phase_summary(blocks):
        return {
            "forcedMarket":summarize_market(flatten(blocks,"forced"),chosen_rr),
            "selectiveTop3Market":summarize_market(flatten(blocks,"selective"),chosen_rr),
            "selectiveTop3Limit":summarize_limit(flatten(blocks,"limits")),
        }

    result={
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "method":"FOREX F1 blind research. One cached 15m Twelve Data series per pair; H1/H4 and 24h/72h currency strength are derived locally. Direction combines cross-currency relative strength, H4 structure, H1 trend/momentum and M15 setup/anti-chase. Structural M15 invalidation defines SL first. All-pair forced MARKET is diagnostic only. Live-style Top3 requires H4/H1 alignment, anti-chase/risk gates and currency-exposure control. LIMIT is fixed 0.30R pullback, 4h expiry, same structural SL and absolute MARKET TP. First 5 cutoffs select RR only; last 5 are untouched holdout validation.",
        "dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","pairs":28,"creditsExpected":28,"outputsizePerPair":OUTPUTSIZE,"rawCommitted":False},
        "cutoffs":{"development":DEV_CUTOFFS,"validation":VAL_CUTOFFS},
        "rrDevelopmentGrid":rr_dev,"chosenRR":chosen_rr,
        "developmentSummary":phase_summary(dev),
        "validationSummary":phase_summary(val),
        "validationByCutoff":{},
        "validationTrades":{},
    }
    for c,b in val.items():
        result["validationByCutoff"][c]={
            "forcedMarket":summarize_market(b["forced"],chosen_rr),
            "selectiveTop3Market":summarize_market(b["selective"],chosen_rr),
            "selectiveTop3Limit":summarize_limit(b["limits"]),
            "top3":[{"symbol":x["feature"]["symbol"],"side":x["feature"]["side"],"score":x["feature"]["score"],"quality":x["feature"]["quality"],"market":x["outcome"]["result"]} for x in b["selective"]],
        }
        result["validationTrades"][c]={
            "selectiveMarket":b["selective"],"selectiveLimit":b["limits"]
        }

    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f1.json","w",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2,default=str)
    print(json.dumps({
        "chosenRR":chosen_rr,
        "development":result["developmentSummary"],
        "validation":result["validationSummary"],
        "rrGrid":rr_dev,
    },indent=2))

if __name__=="__main__":
    main()
