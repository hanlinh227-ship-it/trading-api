#!/usr/bin/env python3
import json, os, statistics, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core
import blind_backtest_crypto_v22 as v22
import blind_backtest_crypto_v24 as v24

# Locked before outcomes are inspected. Repository search found no prior 2026-04-16 cutoff.
CUTOFF = "2026-04-16T12:00:00Z"
OBSERVE_MS = 15 * 60_000
LIMIT_PULLBACK_R = 0.35
LIMIT_EXPIRY_MS = 6 * 3600_000


def ms_iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def summarize_market(rows):
    ok = [r for r in rows if r.get("market")]
    clear = [r for r in ok if r["market"]["outcome"]["result"] in ("TP", "SL")]
    wins = [r for r in clear if r["market"]["outcome"]["result"] == "TP"]
    losses = [r for r in clear if r["market"]["outcome"]["result"] == "SL"]
    amb = [r for r in ok if r["market"]["outcome"]["result"] == "AMBIGUOUS"]
    unr = [r for r in ok if r["market"]["outcome"]["result"] == "UNRESOLVED"]
    exp = sum(r["market"]["rr"] if r["market"]["outcome"]["result"] == "TP" else -1 for r in clear)
    d6 = [r for r in ok if r["market"].get("direction6hCorrect") is not None]
    d24 = [r for r in ok if r["market"].get("direction24hCorrect") is not None]
    fav = [r for r in ok if r["market"].get("firstHalfR") == "FAVORABLE"]
    adv = [r for r in ok if r["market"].get("firstHalfR") == "ADVERSE"]
    return {
        "trades": len(ok),
        "resolved": len(clear),
        "tp": len(wins),
        "sl": len(losses),
        "ambiguous": len(amb),
        "unresolved": len(unr),
        "winRateResolved": round(100 * len(wins) / len(clear), 2) if clear else None,
        "expectancyR": round(exp / len(clear), 3) if clear else None,
        "direction6hAccuracy": round(100 * sum(bool(r["market"]["direction6hCorrect"]) for r in d6) / len(d6), 2) if d6 else None,
        "direction24hAccuracy": round(100 * sum(bool(r["market"]["direction24hCorrect"]) for r in d24) / len(d24), 2) if d24 else None,
        "firstHalfRFavorable": len(fav),
        "firstHalfRAdverse": len(adv),
    }


def summarize_limit(rows):
    ok = [r for r in rows if r.get("limit")]
    filled = [r for r in ok if r["limit"].get("filled")]
    clear = [r for r in filled if r["limit"]["outcome"]["result"] in ("TP", "SL")]
    wins = [r for r in clear if r["limit"]["outcome"]["result"] == "TP"]
    losses = [r for r in clear if r["limit"]["outcome"]["result"] == "SL"]
    amb = [r for r in filled if r["limit"]["outcome"]["result"] == "AMBIGUOUS"]
    unr = [r for r in filled if r["limit"]["outcome"]["result"] == "UNRESOLVED"]
    missed = [r for r in ok if r["limit"].get("status") == "TARGET_BEFORE_FILL"]
    expired = [r for r in ok if r["limit"].get("status") == "NOT_FILLED_6H"]
    exp = sum(r["limit"]["effectiveRR"] if r["limit"]["outcome"]["result"] == "TP" else -1 for r in clear)
    return {
        "orders": len(ok),
        "filled": len(filled),
        "fillRate": round(100 * len(filled) / len(ok), 2) if ok else None,
        "targetBeforeFill": len(missed),
        "notFilled6h": len(expired),
        "resolvedFilled": len(clear),
        "tp": len(wins),
        "sl": len(losses),
        "ambiguous": len(amb),
        "unresolved": len(unr),
        "winRateResolvedFilled": round(100 * len(wins) / len(clear), 2) if clear else None,
        "avgEffectiveRR": round(statistics.mean(r["limit"]["effectiveRR"] for r in filled), 3) if filled else None,
        "expectancyRResolvedFilled": round(exp / len(clear), 3) if clear else None,
    }


def close_at(rows, target_ms):
    xs = [x for x in rows if x["ts"] < target_ms]
    return xs[-1]["close"] if xs else None


def excursion(side, entry, risk, rows, end_ms):
    xs = [x for x in rows if x["ts"] < end_ms]
    if not xs or risk <= 0:
        return {"mfeR6h": None, "maeR6h": None, "firstHalfR": None}
    if side == "BUY":
        mfe = (max(x["high"] for x in xs) - entry) / risk
        mae = (entry - min(x["low"] for x in xs)) / risk
        for x in xs:
            fav = x["high"] >= entry + 0.5 * risk
            adv = x["low"] <= entry - 0.5 * risk
            if fav and adv:
                first = "AMBIGUOUS"
                break
            if fav:
                first = "FAVORABLE"
                break
            if adv:
                first = "ADVERSE"
                break
        else:
            first = "NEITHER"
    else:
        mfe = (entry - min(x["low"] for x in xs)) / risk
        mae = (max(x["high"] for x in xs) - entry) / risk
        for x in xs:
            fav = x["low"] <= entry - 0.5 * risk
            adv = x["high"] >= entry + 0.5 * risk
            if fav and adv:
                first = "AMBIGUOUS"
                break
            if fav:
                first = "FAVORABLE"
                break
            if adv:
                first = "ADVERSE"
                break
        else:
            first = "NEITHER"
    return {"mfeR6h": round(mfe, 3), "maeR6h": round(mae, 3), "firstHalfR": first}


def evaluate_limit(side, limit_px, sl, tp, future_rows, signal_t):
    expiry = signal_t + LIMIT_EXPIRY_MS
    search = [x for x in future_rows if x["ts"] < expiry]
    for i, x in enumerate(search):
        if side == "BUY":
            fill = x["low"] <= limit_px
            target = x["high"] >= tp
            if fill and target:
                return {"filled": False, "status": "AMBIGUOUS_FILL_TARGET_SEQUENCE", "fillTimeMs": x["ts"], "outcome": {"result": "AMBIGUOUS", "candles": 1}}
            if target and not fill:
                return {"filled": False, "status": "TARGET_BEFORE_FILL", "fillTimeMs": None, "outcome": None}
            if fill:
                if x["low"] <= sl:
                    return {"filled": True, "status": "FILLED", "fillTimeMs": x["ts"], "outcome": {"result": "SL", "candles": 1}}
                rest = future_rows[future_rows.index(x) + 1:]
                out = v22.evaluate(side, limit_px, sl, tp, rest)
                return {"filled": True, "status": "FILLED", "fillTimeMs": x["ts"], "outcome": out}
        else:
            fill = x["high"] >= limit_px
            target = x["low"] <= tp
            if fill and target:
                return {"filled": False, "status": "AMBIGUOUS_FILL_TARGET_SEQUENCE", "fillTimeMs": x["ts"], "outcome": {"result": "AMBIGUOUS", "candles": 1}}
            if target and not fill:
                return {"filled": False, "status": "TARGET_BEFORE_FILL", "fillTimeMs": None, "outcome": None}
            if fill:
                if x["high"] >= sl:
                    return {"filled": True, "status": "FILLED", "fillTimeMs": x["ts"], "outcome": {"result": "SL", "candles": 1}}
                rest = future_rows[future_rows.index(x) + 1:]
                out = v22.evaluate(side, limit_px, sl, tp, rest)
                return {"filled": True, "status": "FILLED", "fillTimeMs": x["ts"], "outcome": out}
    return {"filled": False, "status": "NOT_FILLED_6H", "fillTimeMs": None, "outcome": None}


def main():
    cut = v6.iso_ms(CUTOFF)
    signal_t = cut + OBSERVE_MS

    # All scoring inputs are rebuilt at signal_t, so the just-completed M15 bar is observable.
    btc_source, btc_frames, btc_sums = v6.load_frames("BTC", signal_t)
    tmp = []
    errors = []
    for sym in v6.COINS:
        try:
            source, fr, su = (btc_source, btc_frames, btc_sums) if sym == "BTC" else v6.load_frames(sym, signal_t)
            _, _, _, _, _, _, model = v6.choose(sym, su, fr, btc_frames, btc_sums)
            feat = core.features(sym, fr, su, btc_frames)
            tmp.append({"sym": sym, "source": source, "fr": fr, "su": su, "model": model, "f": feat})
        except Exception as e:
            errors.append({"symbol": sym + "USDT", "error": str(e)})

    price_breadth = sum(x["f"]["r24"] > 0 for x in tmp) / len(tmp) if tmp else 0.5

    available_flows = []
    for r in tmp:
        try:
            flow = v22.tradeflow(r["sym"], signal_t - 5 * 60_000, signal_t)
        except Exception as e:
            flow = {"available": False, "n": 0, "ofi": 0.0, "lastPx": None, "error": str(e)}
        r["flow"] = flow
        if flow.get("available"):
            available_flows.append(flow)

    flow_breadth = sum(x["ofi"] > 0 for x in available_flows) / len(available_flows) if available_flows else 0.5
    flow_median = statistics.median([x["ofi"] for x in available_flows]) if available_flows else 0.0
    market_regime = v24.classify_market(price_breadth, flow_breadth, flow_median)

    rows = []
    for r in tmp:
        sym = r["sym"]
        macro = v22.macro_score(sym, r["f"], r["model"], price_breadth)
        flow = r["flow"]
        entry = flow.get("lastPx") if flow.get("lastPx") is not None else r["fr"]["M5"][-1]["close"]
        micro, move = v22.micro_score(flow, r["fr"]["M5"][-2]["close"] if len(r["fr"]["M5"]) >= 2 else entry, r["su"]["M15"].get("atr14"))
        side, score, rr = v24.decide(macro, micro, flow, move, r["model"], market_regime)
        sl, tp, risk = v22.levels(sym, side, entry, r["su"], r["fr"], rr)
        future_rows = v22.future(r["source"], sym, signal_t)
        market_out = v22.evaluate(side, entry, sl, tp, future_rows)

        c6 = close_at(future_rows, signal_t + 6 * 3600_000)
        c24 = close_at(future_rows, signal_t + 24 * 3600_000)
        d6 = None if c6 is None else ((c6 > entry) if side == "BUY" else (c6 < entry))
        d24 = None if c24 is None else ((c24 > entry) if side == "BUY" else (c24 < entry))
        ex = excursion(side, entry, risk, future_rows, signal_t + 6 * 3600_000)

        limit_px = entry - LIMIT_PULLBACK_R * risk if side == "BUY" else entry + LIMIT_PULLBACK_R * risk
        limit_eval = evaluate_limit(side, limit_px, sl, tp, future_rows, signal_t)
        limit_risk = abs(limit_px - sl)
        effective_rr = abs(tp - limit_px) / limit_risk if limit_risk > 0 else None
        limit_block = {
            "price": limit_px,
            "pullbackR": LIMIT_PULLBACK_R,
            "expiryHours": 6,
            "sameStructuralSL": sl,
            "sameAbsoluteTP": tp,
            "effectiveRR": round(effective_rr, 3) if effective_rr is not None else None,
            **limit_eval,
        }

        rows.append({
            "symbol": sym + "USDT",
            "side": side,
            "score": round(score, 3),
            "macroScore": round(macro, 3),
            "microScore": round(micro, 3),
            "modelRegime": r["model"].get("regime"),
            "source": r["source"],
            "market": {
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "risk": risk,
                "rr": rr,
                "outcome": market_out,
                "close6h": c6,
                "close24h": c24,
                "direction6hCorrect": d6,
                "direction24hCorrect": d24,
                **ex,
            },
            "limit": limit_block,
        })

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": "Final locked MARKET-vs-LIMIT execution comparison. Signal is evaluated only after one complete 15m observation window. Direction keeps the surviving V24/V22 architecture: 6h/24h/72h momentum, H4/H1 structure, H4 EMA context, BTC relative strength, market breadth and actual final-5m taker flow when historically available. MARKET enters at the observable +15m price. LIMIT is fixed ex ante at a 0.35R pullback toward the same structural SL, expires after 6h, and keeps the same absolute TP as MARKET; therefore a filled LIMIT earns a naturally higher effective RR. If the original TP is reached before LIMIT fills, the pending order is cancelled and counted TARGET_BEFORE_FILL. No outcomes were inspected before locking date/rules.",
        "cutoff": CUTOFF,
        "signalTime": ms_iso(signal_t),
        "universe": len(v6.COINS),
        "tested": len(rows),
        "priceBreadth": round(price_breadth, 3),
        "flowBreadth": round(flow_breadth, 3),
        "flowMedian": round(flow_median, 3),
        "flowCoverage": round(len(available_flows) / len(tmp), 3) if tmp else 0,
        "marketRegime": market_regime,
        "limitRule": {"pullbackR": LIMIT_PULLBACK_R, "expiryHours": 6, "sameStructuralSL": True, "sameAbsoluteTP": True},
        "dataErrors": errors,
        "marketSummary": summarize_market(rows),
        "limitSummary": summarize_limit(rows),
        "tests": rows,
    }
    with open("data/final_market_vs_limit_blind.json", "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps({
        "cutoff": CUTOFF,
        "signalTime": ms_iso(signal_t),
        "tested": len(rows),
        "errors": errors,
        "priceBreadth": round(price_breadth, 3),
        "marketRegime": market_regime,
        "market": payload["marketSummary"],
        "limit": payload["limitSummary"],
        "perCoin": [
            {
                "symbol": r["symbol"], "side": r["side"],
                "market": r["market"]["outcome"]["result"],
                "firstHalfR": r["market"]["firstHalfR"],
                "dir6h": r["market"]["direction6hCorrect"],
                "dir24h": r["market"]["direction24hCorrect"],
                "limitStatus": r["limit"]["status"],
                "limitOutcome": r["limit"]["outcome"]["result"] if r["limit"].get("outcome") else None,
                "limitRR": r["limit"]["effectiveRR"],
            } for r in rows
        ]
    }, indent=2))


if __name__ == "__main__":
    main()
