import json
from pathlib import Path

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
SNAPSHOT = ROOT / "state" / "market_snapshot.json"
LEARNING = ROOT / "state" / "learning_stats.json"
POLICY = ROOT / "state" / "adaptive_policy.json"
MARKET_CONTEXT = ROOT / "state" / "market_context.json"


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
    """Fast entry-review set.

    Position management is handled by the dedicated guardian, so PAPER positions
    are never injected into entry-review prompts. Only actionable LONG/SHORT
    scanner candidates are sent to the three reviewers, ranked by quality.
    """
    items = snapshot.get("ai_candidates") or snapshot.get("setups") or []
    actionable = [
        x for x in items
        if str(x.get("candidate_action", "WAIT")).upper() in {"LONG", "SHORT"}
        and not (x.get("blockers") or [])
    ]
    actionable.sort(
        key=lambda x: (
            float(x.get("setup_quality", x.get("setup_score", 0)) or 0),
            -float(x.get("spread_bps", 999999) or 999999),
        ),
        reverse=True,
    )
    return actionable[:3]


def compact_setup(s):
    tfs = s.get("timeframes") or {}
    # Keep only the fields needed for the decision. This materially reduces
    # Claude latency/token use while preserving all eight timeframe layers.
    compact_tfs = {}
    for tf in ("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"):
        d = tfs.get(tf)
        if not isinstance(d, dict):
            continue
        compact_tfs[tf] = {
            k: d.get(k) for k in (
                "trend", "rsi", "momentum", "mom3", "ema20_dist_pct",
                "volume_ratio", "atr_pct"
            ) if k in d
        }
    return {
        "symbol": s["symbol"],
        "candidate_action": s.get("candidate_action", "WAIT"),
        "strategy": s.get("strategy", "NO_EDGE"),
        "regime": s.get("regime", "UNKNOWN"),
        "setup_quality": s.get("setup_quality", s.get("setup_score", 0)),
        "learning_multiplier": s.get("learning_multiplier", 1.0),
        "entry": s.get("entry"),
        "stop_loss": s.get("stop_loss"),
        "tp1": s.get("tp1"),
        "tp2": s.get("tp2"),
        "tp3": s.get("tp3"),
        "funding_rate": s.get("funding_rate"),
        "open_interest_change_pct": s.get("open_interest_change_pct"),
        "taker_buy_sell_ratio": s.get("taker_buy_sell_ratio"),
        "spread_bps": s.get("spread_bps"),
        "estimated_roundtrip_cost_bps": s.get("estimated_roundtrip_cost_bps"),
        "timeframes": compact_tfs,
        "mtf_alignment": s.get("mtf_alignment", {}),
        "entry_standard": s.get("entry_standard", {}),
        "warnings": (s.get("warnings") or [])[:3],
        "management": s.get("management", {}),
    }


def reviewer_context(snapshot):
    market = load_optional(MARKET_CONTEXT)
    return {
        "engine": snapshot.get("engine"),
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
