#!/usr/bin/env python3
"""V76 Forex evaluator R2.

Uses frozen objective setup detection from research_v76_entry_forex.py, but applies
research-protocol corrections that do not tune setup thresholds:
- DST-aware London / New York / overlap labels;
- H1/M15 liquidity-room context bins;
- conservative LIMIT_FVG fill-bar scoring to avoid intrabar order look-ahead;
- stronger minimum-sample gates;
- DEV selects, VALIDATION gates, untouched OOS only promotes/rejects.
"""
from __future__ import annotations

import bisect
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import research_v76_entry_forex as base

VERSION = "V76-ENTRY-EVALUATOR-R2"
DEV_MIN_N = 60
VAL_MIN_N = 20
OOS_MIN_N = 20
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")


def session_label(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    lo = dt.astimezone(LONDON)
    ny = dt.astimezone(NEW_YORK)
    london_open = lo.weekday() < 5 and 7 <= lo.hour < 16
    new_york_open = ny.weekday() < 5 and 8 <= ny.hour < 13
    if london_open and new_york_open:
        return "OVERLAP"
    if london_open:
        return "LONDON"
    if new_york_open:
        return "NEW_YORK"
    return "OFF_SESSION"


def _tf_idx(tf, ts):
    return bisect.bisect_right(tf.end_ts, ts) - 1


def _room_bin(room_atr):
    if room_atr is None:
        return "UNKNOWN"
    if room_atr <= 0:
        return "NO_ROOM"
    if room_atr < 1:
        return "LT_1_ATR"
    if room_atr < 2:
        return "1_TO_2_ATR"
    if room_atr < 4:
        return "2_TO_4_ATR"
    return "GE_4_ATR"


def add_liquidity_context(signals, rows):
    m15 = base.enrich(base.resample(rows, 900), 900)
    h1 = base.enrich(base.resample(rows, 3600), 3600)
    for sig in signals:
        ts = sig["ts"]
        side = sig["side"]
        j15 = _tf_idx(m15, ts)
        j1 = _tf_idx(h1, ts)
        price = rows[sig["i"]][4]
        m15_atr = m15.atr14[j15] if j15 >= 0 else None
        h1_atr = h1.atr14[j1] if j1 >= 0 else None
        m15_room = h1_room = None
        if j15 >= 20 and m15_atr:
            prior = m15.rows[j15-20:j15]
            target = max(x[2] for x in prior) if side == "LONG" else min(x[3] for x in prior)
            m15_room = (target-price)/m15_atr if side == "LONG" else (price-target)/m15_atr
        if j1 >= 20 and h1_atr:
            prior = h1.rows[j1-20:j1]
            target = max(x[2] for x in prior) if side == "LONG" else min(x[3] for x in prior)
            h1_room = (target-price)/h1_atr if side == "LONG" else (price-target)/h1_atr
        sig["context"]["session"] = session_label(ts)
        sig["context"]["m15LiquidityRoom"] = _room_bin(m15_room)
        sig["context"]["h1LiquidityRoom"] = _room_bin(h1_room)
        sig["context"]["m15RoomATR"] = m15_room
        sig["context"]["h1RoomATR"] = h1_room
    return signals


def _entry(sig, m5, mode):
    i = sig["i"]
    side = sig["side"]
    atr = m5.atr14[i]
    if atr is None or atr <= 0:
        return None
    if mode == "CLOSE":
        return {"firstBar": i+1, "fillBar": None, "price": m5.rows[i][4]}
    if mode == "RETEST":
        level = sig["level"]
        for k in range(i+1, min(len(m5.rows), i+1+base.RETEST_BARS)):
            row = m5.rows[k]
            touched = row[3] <= level + .15*atr and row[2] >= level - .15*atr
            confirmed = row[4] >= level if side == "LONG" else row[4] <= level
            if touched and confirmed:
                return {"firstBar": k+1, "fillBar": None, "price": row[4]}
        return None
    zone = sig.get("fvg")
    if not zone:
        return None
    mid = sum(zone)/2
    for k in range(i+1, min(len(m5.rows), i+1+base.RETEST_BARS)):
        if m5.rows[k][3] <= mid <= m5.rows[k][2]:
            return {"firstBar": k, "fillBar": k, "price": mid}
    return None


def simulate(sig, m5, entry_mode, stop_mode, rr):
    fill = _entry(sig, m5, entry_mode)
    if not fill:
        return None
    px = fill["price"]
    first = fill["firstBar"]
    if first >= len(m5.rows)-1:
        return None
    side = sig["side"]
    atr = m5.atr14[sig["i"]]
    structure = float(sig["structure"])
    raw_stop = structure - .05*atr if side == "LONG" else structure + .05*atr
    risk = px-raw_stop if side == "LONG" else raw_stop-px
    if risk <= 0:
        return None
    if stop_mode == "STRUCTURE_ATR" and risk < .8*atr:
        risk = .8*atr
    sl = px-risk if side == "LONG" else px+risk
    tp = px+rr*risk if side == "LONG" else px-rr*risk
    mfe = mae = 0.0
    outcome = "TIMEOUT"
    result = None
    exit_i = min(len(m5.rows)-1, first+base.MAX_HOLD_BARS-1)

    # LIMIT_FVG: the fill candle's path is unknown. Be conservative:
    # any stop touch = SL. A TP on the fill candle counts only when the candle
    # closes through TP, which guarantees a post-fill recross before close.
    if fill["fillBar"] is not None:
        k = fill["fillBar"]
        row = m5.rows[k]
        fav = (row[2]-px)/risk if side == "LONG" else (px-row[3])/risk
        adv = (px-row[3])/risk if side == "LONG" else (row[2]-px)/risk
        mfe = max(mfe, fav)
        mae = max(mae, adv)
        hit_sl = row[3] <= sl if side == "LONG" else row[2] >= sl
        close_tp = row[4] >= tp if side == "LONG" else row[4] <= tp
        if hit_sl:
            result, outcome, exit_i = -1-base.COST_R, "SL", k
        elif close_tp:
            result, outcome, exit_i = rr-base.COST_R, "TP", k
        first = k+1

    if result is None:
        for k in range(first, min(len(m5.rows), first+base.MAX_HOLD_BARS)):
            row = m5.rows[k]
            fav = (row[2]-px)/risk if side == "LONG" else (px-row[3])/risk
            adv = (px-row[3])/risk if side == "LONG" else (row[2]-px)/risk
            mfe = max(mfe, fav)
            mae = max(mae, adv)
            hit_sl = row[3] <= sl if side == "LONG" else row[2] >= sl
            hit_tp = row[2] >= tp if side == "LONG" else row[3] <= tp
            if hit_sl:  # same-bar TP+SL is deliberately SL
                result, outcome, exit_i = -1-base.COST_R, "SL", k
                break
            if hit_tp:
                result, outcome, exit_i = rr-base.COST_R, "TP", k
                break
    if result is None:
        close = m5.rows[exit_i][4]
        mark = (close-px)/risk if side == "LONG" else (px-close)/risk
        result = max(-1, min(rr, mark))-base.COST_R

    c = sig["context"]
    return {
        "r": result, "outcome": outcome, "mfe": mfe, "mae": mae,
        "entryI": fill["fillBar"] if fill["fillBar"] is not None else fill["firstBar"],
        "exitI": exit_i, "side": side,
        "session": c["session"], "htfAlignment": c["htfAlignment"],
        "volRegime": c["volRegime"],
        "m15LiquidityRoom": c.get("m15LiquidityRoom", "UNKNOWN"),
        "h1LiquidityRoom": c.get("h1LiquidityRoom", "UNKNOWN"),
    }


def _grouped(trades, key):
    g = defaultdict(list)
    for t in trades:
        g[t[key]].append(t)
    return {k: base.metrics(v) for k,v in sorted(g.items())}


def score_dev(m):
    if m["n"] < DEV_MIN_N:
        return -999
    return (
        3.0*m["expectancyR"]
        + .25*min(m["profitFactor"], 3)
        + .002*m["wr"]
        - .03*m["maxDrawdownR"]
        - .01*m["maxLosingStreak"]
        - .001*m["timeoutRate"]
    )


def research_pair(symbol, rows, daily):
    # Patch only the session label used as context; objective setup thresholds stay frozen.
    original_session = base.session_label
    base.session_label = session_label
    try:
        signals, m5 = base.generate_signals(symbol, rows, daily)
    finally:
        base.session_label = original_session
    add_liquidity_context(signals, rows)
    n = len(rows)
    cut1, cut2 = int(n*.60), int(n*.80)
    variants = {}
    for arch in base.SETUP_DEFS:
        for entry_mode in base.ENTRY_MODES:
            for stop_mode in base.STOP_MODES:
                for rr in base.RR_VALUES:
                    trades=[]; last_exit=-1
                    for sig in signals:
                        if sig["arch"] != arch or sig["i"] < last_exit:
                            continue
                        t = simulate(sig, m5, entry_mode, stop_mode, rr)
                        if t:
                            trades.append(t); last_exit=t["exitI"]
                    dev=[t for t in trades if t["entryI"] < cut1]
                    val=[t for t in trades if cut1 <= t["entryI"] < cut2]
                    oos=[t for t in trades if t["entryI"] >= cut2]
                    key=base.vkey(arch, entry_mode, stop_mode, rr)
                    variants[key]={
                        "arch":arch,"entry":entry_mode,"stop":stop_mode,"rr":rr,
                        "dev":base.metrics(dev),"validation":base.metrics(val),"oos":base.metrics(oos),
                        "validationBySession":_grouped(val,"session"),
                        "validationByAlignment":_grouped(val,"htfAlignment"),
                        "validationByVolatility":_grouped(val,"volRegime"),
                        "validationByM15LiquidityRoom":_grouped(val,"m15LiquidityRoom"),
                        "validationByH1LiquidityRoom":_grouped(val,"h1LiquidityRoom"),
                        "validationBySide":_grouped(val,"side"),
                    }
    ordered=sorted(variants.values(),key=lambda x:score_dev(x["dev"]),reverse=True)
    top=[{k:x[k] for k in ("arch","entry","stop","rr","dev","validation","oos")} for x in ordered[:5]]
    return {
        "symbol":symbol,"bars":n,
        "from":base.iso(datetime.fromtimestamp(rows[0][0],tz=timezone.utc)),
        "to":base.iso(datetime.fromtimestamp(rows[-1][0]+300,tz=timezone.utc)),
        "signalCount":len(signals),"variants":variants,"top5Dev":top,
    }


def global_archetypes(results):
    stats={}
    for arch in base.SETUP_DEFS:
        validations=[]; devs=[]
        for result in results.values():
            choices=sorted([x for x in result["variants"].values() if x["arch"]==arch],key=lambda x:score_dev(x["dev"]),reverse=True)
            if not choices:
                continue
            x=choices[0];devs.append(x["dev"])
            if x["validation"]["n"] >= 10:
                validations.append(x["validation"])
        positive=sum(m["expectancyR"]>0 and m["profitFactor"]>1 for m in validations)
        vals=[m["expectancyR"] for m in validations]
        stats[arch]={
            "symbolsWithValidation":len(validations),
            "validationPositive":positive,
            "positiveShare":round(positive/len(validations),3) if validations else 0,
            "medianValidationExpectancyR":round(statistics.median(vals),4) if vals else 0,
            "medianDevExpectancyR":round(statistics.median([m["expectancyR"] for m in devs]),4) if devs else 0,
        }
    ranked=sorted(stats,key=lambda a:(stats[a]["positiveShare"],stats[a]["medianValidationExpectancyR"],stats[a]["symbolsWithValidation"]),reverse=True)
    retained=[a for a in ranked if stats[a]["symbolsWithValidation"]>=12 and stats[a]["positiveShare"]>=.55 and stats[a]["medianValidationExpectancyR"]>0][:4]
    # No OOS information is used to choose global archetypes. If nothing meets
    # the validation gate, keep the two validation-best archetypes as RESEARCH_ONLY candidates.
    return stats, retained, ranked[:2]


def lock_methods(results, retained, fallback_arches):
    allowed=retained or fallback_arches
    methods={}; counts=defaultdict(int)
    for symbol in base.PAIRS:
        choices=sorted([x for x in results[symbol]["variants"].values() if x["arch"] in allowed],key=lambda x:score_dev(x["dev"]),reverse=True)
        passing=[]
        for x in choices:
            d=x["dev"];v=x["validation"]
            if (
                d["n"]>=DEV_MIN_N and d["expectancyR"]>0 and d["profitFactor"]>=1.10
                and v["n"]>=VAL_MIN_N and v["expectancyR"]>0 and v["profitFactor"]>=1.05
            ):
                passing.append(x)
        chosen=passing[0] if passing else choices[0]
        d,v,o=chosen["dev"],chosen["validation"],chosen["oos"]
        promoted=bool(
            retained
            and d["n"]>=DEV_MIN_N and d["expectancyR"]>0 and d["profitFactor"]>=1.10
            and v["n"]>=VAL_MIN_N and v["expectancyR"]>0 and v["profitFactor"]>=1.05
            and o["n"]>=OOS_MIN_N and o["expectancyR"]>.05 and o["profitFactor"]>=1.15
            and o["maxDrawdownR"]<=10 and o["maxLosingStreak"]<=10
        )
        status="OOS_PROMOTED" if promoted else "RESEARCH_ONLY"
        counts[status]+=1;counts[chosen["arch"]]+=1
        methods[symbol]={
            "status":status,"liveEligible":promoted,
            "archetype":chosen["arch"],"entryMode":chosen["entry"],"stopMode":chosen["stop"],"rr":chosen["rr"],
            "selectedBy":"DEV_RANK_THEN_VALIDATION_GATE",
            "oosRole":"ONE_TIME_PROMOTION_CHECK_ONLY_NO_RETUNE",
            "dev":d,"validation":v,"oos":o,
            "validationBySession":chosen["validationBySession"],
            "validationByAlignment":chosen["validationByAlignment"],
            "validationByVolatility":chosen["validationByVolatility"],
            "validationByM15LiquidityRoom":chosen["validationByM15LiquidityRoom"],
            "validationByH1LiquidityRoom":chosen["validationByH1LiquidityRoom"],
            "validationBySide":chosen["validationBySide"],
        }
    return methods,dict(counts)


def protocol_summary():
    return {
        "evaluatorVersion":VERSION,
        "split":"chronological 60/20/20",
        "selection":"DEV ranks; VALIDATION gates; untouched OOS only promotes/rejects",
        "devMinN":DEV_MIN_N,"validationMinN":VAL_MIN_N,"oosMinN":OOS_MIN_N,
        "costModelR":base.COST_R,"sameBarTpSl":"SL",
        "limitFillBar":"conservative: any stop touch=SL; TP counts on fill bar only if close crosses TP",
        "newsHistoricalFilter":"NOT_TESTED_NO_CANONICAL_TIMESTAMPED_EVENT_FEED",
        "liveNewsGateStillRequired":True,
    }
