import json
from pathlib import Path

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
SNAPSHOT = ROOT / "state" / "market_snapshot.json"
LEARNING = ROOT / "state" / "learning_stats.json"
POLICY = ROOT / "state" / "adaptive_policy.json"


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
    return items[:12]


def compact_setup(s):
    return {
        "symbol": s["symbol"],
        "candidate_action": s.get("candidate_action", "WAIT"),
        "strategy": s.get("strategy", "NO_EDGE"),
        "regime": s.get("regime", "UNKNOWN"),
        "setup_score": s.get("setup_score", 0),
        "setup_quality": s.get("setup_quality", 0),
        "base_score": s.get("base_score"),
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
        "timeframe_hierarchy": s.get("timeframe_hierarchy", {}),
        "entry_standardization": s.get("entry_standardization", {}),
        "all_timeframes_present": s.get("all_timeframes_present", []),
        "reasons": s.get("reasons", []),
        "warnings": s.get("warnings", []),
        "blockers": s.get("blockers", []),
        "management": s.get("management", {}),
    }


def reviewer_context(snapshot):
    return {
        "engine": snapshot.get("engine"),
        "policy": snapshot.get("policy", {}),
        "all_timeframe_context": snapshot.get("all_timeframe_context", {}),
        "learning_stats": load_optional(LEARNING),
        "adaptive_policy": load_optional(POLICY),
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
