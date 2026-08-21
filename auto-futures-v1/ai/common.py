import json
from pathlib import Path

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
SNAPSHOT = ROOT / "state" / "market_snapshot.json"

def load_snapshot():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))

def compact_setup(s):
    return {
        "symbol": s["symbol"],
        "candidate_action": s["candidate_action"],
        "setup_score": s["setup_score"],
        "setup_quality": s["setup_quality"],
        "entry": s.get("entry"),
        "stop_loss": s.get("stop_loss"),
        "tp1": s.get("tp1"),
        "tp2": s.get("tp2"),
        "tp3": s.get("tp3"),
        "funding_rate": s.get("funding_rate"),
        "open_interest": s.get("open_interest"),
        "timeframes": s.get("timeframes"),
        "reasons": s.get("reasons"),
        "warnings": s.get("warnings"),
        "blockers": s.get("blockers"),
    }

def validate_review(x):
    allowed = {"LONG","SHORT","WAIT","EXIT","HOLD"}
    if not isinstance(x, dict):
        return False
    if x.get("action") not in allowed:
        return False
    if not isinstance(x.get("confidence"), (int,float)):
        return False
    if not 0 <= float(x["confidence"]) <= 100:
        return False
    return True
