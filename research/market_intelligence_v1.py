"""Read-only market intelligence sidecar over existing V75 research snapshots.

No provider calls, trading operations or change to strategy/execution authority.
Missing or stale data cannot be promoted to a trade recommendation.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
FRESH_SECONDS = 300


def _parse_utc(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            return None
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _dir(value):
    value = str(value or "").upper()
    if value in ("BUY", "LONG", "BULLISH"):
        return 1
    if value in ("SELL", "SHORT", "BEARISH"):
        return -1
    return 0


def fx_strength(pairs):
    """Proxy technical breadth across listed FX pairs, not actual macro currency flows."""
    state = {c: [0, 0] for c in CURRENCIES}
    seen = set()
    for row in pairs:
        symbol = row.get("symbol", "")
        if not isinstance(symbol, str) or len(symbol) != 6 or symbol in seen:
            continue
        base, quote = symbol[:3], symbol[3:]
        side = _dir(row.get("technicalBias"))
        if base not in state or quote not in state or not side:
            continue
        seen.add(symbol)
        state[base][0] += side
        state[quote][0] -= side
        state[base][1] += 1
        state[quote][1] += 1
    return {"method": "CORRELATED_TOP3_TECHNICAL_BIAS_NOT_28_PAIR_CURRENCY_FLOW",
            "observedPairs": len(seen), "coverage": "PARTIAL" if len(seen) >= 20 else "LOW",
            "strength": {k: round(v[0] / v[1], 3) if v[1] >= 3 else None for k, v in state.items()}}


def _regime(row):
    frame = row.get("frameDirection", {})
    if not isinstance(frame, dict):
        frame = {}
    h = _dir(frame.get("H1"))
    m = _dir(frame.get("M5"))
    higher = _dir(frame.get("H4"))
    if not h or not m:
        return "UNKNOWN_OR_TRANSITION"
    if h != m:
        return "TIMEFRAME_CONFLICT"
    if higher and higher != h:
        return "HIGHER_TIMEFRAME_CONFLICT"
    return "TREND_ALIGNED"


def _data_quality(snapshot, now):
    stamp = _parse_utc(snapshot.get("updatedAt"))
    age = (now - stamp).total_seconds() if stamp else None
    if age is None or age < -10:
        return {"status": "UNAVAILABLE", "asOfUTC": snapshot.get("updatedAt"), "ageSeconds": age}
    return {"status": "VERIFIED" if age <= FRESH_SECONDS else "DELAYED",
            "verificationScope": "SNAPSHOT_TIMESTAMP_ONLY",
            "asOfUTC": stamp.isoformat(), "ageSeconds": round(age, 1)}


def build_research(forex_snapshot, crypto_snapshot, now=None):
    now = now or datetime.now(timezone.utc)
    fx_rows = forex_snapshot.get("top3", [])
    crypto_rows = crypto_snapshot.get("top", [])
    if not isinstance(fx_rows, list):
        fx_rows = []
    if not isinstance(crypto_rows, list):
        crypto_rows = []
    fxq, crq = _data_quality(forex_snapshot, now), _data_quality(crypto_snapshot, now)
    fx = []
    for row in fx_rows:
        if not isinstance(row, dict):
            continue
        fx.append({"symbol": row.get("symbol"), "technicalBias": row.get("technicalBias"),
                   "regime": _regime(row), "sourceStatus": fxq["status"],
                   "spreadVerified": row.get("spreadVerified") is True,
                   "freshQuoteVerified": row.get("strictV74PriceFresh") is True,
                   "decision": "HOLD", "reason": "RESEARCH_ONLY_FOREX_V76_NO_OOS_APPROVAL"})
    cr = []
    for row in crypto_rows:
        if not isinstance(row, dict):
            continue
        h = row.get("H1", {})
        h = h if isinstance(h, dict) else {}
        ema20, ema50 = h.get("ema20"), h.get("ema50")
        direction = _dir(row.get("side"))
        aligned = isinstance(ema20, (int, float)) and isinstance(ema50, (int, float)) and (ema20 - ema50) * direction > 0
        cr.append({"symbol": row.get("symbol"), "technicalBias": row.get("side"),
                   "h1TrendAligned": bool(aligned), "sourceStatus": crq["status"],
                   "spreadObserved": isinstance(row.get("spreadPct"), (int, float)),
                   "decision": "HOLD", "reason": "RESEARCH_SIDECAR_NO_EXECUTION_AUTHORITY"})
    n_aligned = sum(x["h1TrendAligned"] for x in cr)
    return {"schemaVersion": "market-intelligence-v1", "mode": "READ_ONLY_RESEARCH",
            "generatedAtUTC": now.isoformat(), "executionAuthorized": False,
            "strategyAuthority": "BYBIT-TOP100-STATEFLOW-3.0_UNMODIFIED",
            "forex": {"quality": fxq, "reportedPairsScanned": forex_snapshot.get("pairsScanned"),
                      "observedInSnapshot": len(fx_rows), "technicalStrength": fx_strength(fx_rows), "candidates": fx},
            "crypto": {"quality": crq, "reportedUniverseAnalyzed": crypto_snapshot.get("broadAnalyzed"),
                       "observedFinalists": len(cr), "finalistH1BiasAlignment": n_aligned,
                       "fullMarketBreadth": "UNAVAILABLE_TOP5_NOT_FULL_UNIVERSE", "candidates": cr},
            "unverified": ["FRESH_BROKER_EXECUTION_QUOTES", "AS_OF_MACRO_EVENT_DATA",
                           "INDEPENDENT_ORDER_FLOW", "FUNDING_AND_OPEN_INTEREST", "FULL_UNIVERSE_BREADTH"],
            "notes": ["Input snapshot as-of time is distinct from current time.",
                      "This report is contextual evidence only. No strategy promotion or order authority."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forex", default="data/forex-fast.json")
    parser.add_argument("--crypto", default="data/crypto-fast.json")
    parser.add_argument("--output", default="", help="optional research JSON sidecar output")
    args = parser.parse_args()
    out = build_research(json.loads(Path(args.forex).read_text(encoding="utf-8")),
                         json.loads(Path(args.crypto).read_text(encoding="utf-8")))
    text = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
