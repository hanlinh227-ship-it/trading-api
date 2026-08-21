import json
from pathlib import Path

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
SNAPSHOT = ROOT / "state" / "market_snapshot.json"


def load_snapshot():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def candidate_setups(snapshot):
    items = snapshot.get("ai_candidates") or snapshot.get("setups") or []
    return items[:12]


def compact_setup(s):
    return {
        "symbol": s["symbol"],
        "candidate_action": s.get("candidate_action", "WAIT"),
        "strategy": s.get("strategy", "NO_EDGE"),
        "setup_score": s.get("setup_score", 0),
        "setup_quality": s.get("setup_quality", 0),
        "entry": s.get("entry"),
        "stop_loss": s.get("stop_loss"),
        "tp1": s.get("tp1"),
        "tp2": s.get("tp2"),
        "tp3": s.get("tp3"),
        "funding_rate": s.get("funding_rate"),
        "open_interest": s.get("open_interest"),
        "timeframes": s.get("timeframes"),
        "reasons": s.get("reasons", []),
        "warnings": s.get("warnings", []),
        "blockers": s.get("blockers", []),
        "management": s.get("management", {}),
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
