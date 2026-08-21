import json
from pathlib import Path

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
SNAPSHOT = ROOT / "state" / "market_snapshot.json"
LEARNING = ROOT / "state" / "learning_stats.json"
POLICY = ROOT / "state" / "adaptive_policy.json"
MARKET_CONTEXT = ROOT / "state" / "market_context.json"
POSITIONS = ROOT / "state" / "paper_positions.json"


def load_snapshot():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def load_optional(path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def candidate_setups(snapshot):
    items = snapshot.get("ai_candidates") or snapshot.get("setups") or []
    positions = load_optional(POSITIONS).get("positions", [])
    open_symbols = {p.get("symbol") for p in positions if p.get("status") == "OPEN"}
    # Token policy: always preserve open positions, then only the strongest new candidates.
    open_rows = [x for x in items if x.get("symbol") in open_symbols]
    new_rows = [x for x in items if x.get("symbol") not in open_symbols]
    new_rows = sorted(new_rows, key=lambda x: float(x.get("setup_quality", x.get("setup_score", 0)) or 0), reverse=True)
    merged = []
    seen = set()
    for x in open_rows + new_rows[:7]:
        symbol = x.get("symbol")
        if symbol and symbol not in seen:
            merged.append(x); seen.add(symbol)
    return merged[:12]


def compact_setup(s):
    return {
        "symbol": s["symbol"],
        "candidate_action": s.get("candidate_action", "WAIT"),
        "strategy": s.get("strategy", "NO_EDGE"),
        "regime": s.get("regime", "UNKNOWN"),
        "setup_score": s.get("setup_score", 0),
        "setup_quality": s.get("setup_quality", 0),
        "learning_multiplier": s.get("learning_multiplier", 1.0),
        "entry": s.get("entry"),
        "stop_loss": s.get("stop_loss"),
        "tp1": s.get("tp1"),
        "tp2": s.get("tp2"),
        "tp3": s.get("tp3"),
        "funding_rate": s.get("funding_rate"),
        "open_interest": s.get("open_interest"),
        "open_interest_change_pct": s.get("open_interest_change_pct"),
        "taker_buy_sell_ratio": s.get("taker_buy_sell_ratio"),
        "spread_bps": s.get("spread_bps"),
        "estimated_roundtrip_cost_bps": s.get("estimated_roundtrip_cost_bps"),
        "timeframes": s.get("timeframes"),
        "mtf_alignment": s.get("mtf_alignment", {}),
        "entry_standard": s.get("entry_standard", {}),
        "reasons": s.get("reasons", [])[:6],
        "warnings": s.get("warnings", [])[:6],
        "blockers": s.get("blockers", [])[:6],
        "management": s.get("management", {}),
    }


def reviewer_context(snapshot):
    market = load_optional(MARKET_CONTEXT)
    # Do not send a giant market dump to every AI. Only cached compact context is included.
    return {
        "engine": snapshot.get("engine"),
        "policy": snapshot.get("policy", {}),
        "all_timeframe_context": snapshot.get("all_timeframe_context", {}),
        "adaptive_policy": load_optional(POLICY),
        "market_context": {
            "generated_at": market.get("generated_at"),
            "source": market.get("source"),
            "symbols": market.get("symbols", {}),
        },
    }


def normalize_confidence(value):
    try:
        value = float(value)
    except Exception:
        return 0.0
    if 0 <= value <= 1:
        value *= 100
    return round(max(0.0, min(100.0, value)), 2)


def validate_review(x):
    if not isinstance(x, dict):
        return False
    if str(x.get("action", "")).upper() not in {"LONG", "SHORT", "WAIT", "EXIT", "HOLD"}:
        return False
    if not x.get("symbol"):
        return False
    return True
