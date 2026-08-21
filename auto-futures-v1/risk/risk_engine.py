import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"
SNAPSHOT_FILE = STATE / "market_snapshot.json"
CONSENSUS_FILE = STATE / "ai_consensus.json"
POSITIONS_FILE = STATE / "paper_positions.json"
OUTPUT_FILE = STATE / "risk_decisions.json"

REQUIRE_AI_COUNT = 3
MIN_AI_CONFIDENCE = 62
MAX_LEVERAGE = 3
MAX_CONCURRENT_POSITIONS = 5
REQUIRED_DEEP_TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"}


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def risk_pct_for_equity(equity):
    if equity < 100:
        return 1.00
    if equity < 250:
        return 0.75
    if equity < 1000:
        return 0.60
    if equity < 5000:
        return 0.50
    return 0.35


def main():
    snapshot = load(SNAPSHOT_FILE, {"setups":[]})
    consensus = load(CONSENSUS_FILE, {"symbols":{}})
    state = load(POSITIONS_FILE, {"starting_equity":50.0,"equity":50.0,"positions":[]})
    setups = {x.get("symbol"):x for x in snapshot.get("setups",[]) if x.get("symbol")}
    positions = state.get("positions", [])
    open_positions = [p for p in positions if p.get("status") == "OPEN"]
    open_symbols = {p.get("symbol") for p in open_positions}
    open_count = len(open_positions)
    equity = float(state.get("equity", state.get("starting_equity", 50.0)) or 50.0)
    risk_pct = risk_pct_for_equity(max(equity, 0.01))
    decisions = {}

    # Slots are dynamic. A closed/done position immediately frees one slot on the next scan.
    slots_left = max(0, MAX_CONCURRENT_POSITIONS - open_count)
    approvals_used = 0

    # Evaluate strongest consensus first so a full book never fills with lower-quality setups.
    ranked = sorted(
        consensus.get("symbols", {}).items(),
        key=lambda kv: float((kv[1] or {}).get("average_confidence", 0) or 0),
        reverse=True,
    )

    for symbol, ai in ranked:
        action = str(ai.get("final_action", "WAIT")).upper()
        setup = setups.get(symbol, {})
        approved, reason = False, "NO_TRADE"
        tf_keys = set((setup.get("timeframes") or {}).keys())
        mtf = setup.get("mtf_alignment") or {}

        if action not in {"LONG","SHORT"}:
            reason = "NO_EDGE"
        elif int(ai.get("available_reviewers",0)) != REQUIRE_AI_COUNT:
            reason = "REQUIRE_3_AI"
        elif float(ai.get("average_confidence",0) or 0) < MIN_AI_CONFIDENCE:
            reason = "AI_CONFIDENCE_TOO_LOW"
        elif symbol in open_symbols:
            reason = "POSITION_ALREADY_OPEN"
        elif open_count + approvals_used >= MAX_CONCURRENT_POSITIONS:
            reason = "MAX_5_CONCURRENT_POSITIONS"
        elif not REQUIRED_DEEP_TIMEFRAMES.issubset(tf_keys):
            reason = "DEEP_MTF_INCOMPLETE"
        elif not mtf or setup.get("regime") in {None, "UNASSESSED_DEEP_MTF"}:
            reason = "MTF_ALIGNMENT_MISSING"
        elif setup.get("candidate_action") != action:
            reason = "SCANNER_AI_CONFLICT"
        elif setup.get("blockers"):
            reason = "SCANNER_BLOCKER"
        elif setup.get("entry") is None or setup.get("stop_loss") is None:
            reason = "ENTRY_OR_STOP_MISSING"
        elif action == "LONG" and float(setup["stop_loss"]) >= float(setup["entry"]):
            reason = "INVALID_LONG_STOP"
        elif action == "SHORT" and float(setup["stop_loss"]) <= float(setup["entry"]):
            reason = "INVALID_SHORT_STOP"
        else:
            approved, reason = True, "PASS"
            approvals_used += 1

        decisions[symbol] = {
            "action":action,"approved":approved,"reason":reason,
            "strategy":setup.get("strategy","NO_EDGE"),
            "regime":setup.get("regime","UNKNOWN"),
            "mtf_alignment":setup.get("mtf_alignment",{}),
            "learning_multiplier":setup.get("learning_multiplier",1.0),
            "spread_bps":setup.get("spread_bps"),
            "entry":setup.get("entry"),"stop_loss":setup.get("stop_loss"),
            "tp1":setup.get("tp1"),"tp2":setup.get("tp2"),"tp3":setup.get("tp3"),
            "management":setup.get("management",{}),
            "risk_pct":risk_pct,"max_leverage":MAX_LEVERAGE,
            "margin_mode":"ISOLATED",
            "ai_confidence":ai.get("average_confidence",0),
        }

    out = {
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "mode":"PAPER",
        "engine":"V6_MTF_ADAPTIVE_SCALP_RISK",
        "policy":{
            "style":"SCALP_ONLY_24_7",
            "daily_trade_limit":None,
            "daily_loss_limit":None,
            "max_loss_limit":None,
            "max_concurrent_positions":MAX_CONCURRENT_POSITIONS,
            "margin_mode":"ISOLATED_ONLY",
            "refill_slot_after_position_done":True,
            "stop_required_per_trade":True,
            "deep_mtf_required":sorted(REQUIRED_DEEP_TIMEFRAMES),
        },
        "paper_equity":equity,
        "adaptive_risk_pct":risk_pct,
        "open_positions":open_count,
        "slots_left":slots_left,
        "decisions":decisions,
    }
    OUTPUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("="*56)
    print("V6 MULTI-TIMEFRAME ADAPTIVE SCALP RISK ENGINE")
    print("="*56)
    print("PAPER EQUITY:", equity, "| RISK/TRADE:", risk_pct, "%")
    print("CONCURRENT POSITIONS:", open_count, "/", MAX_CONCURRENT_POSITIONS, "| SLOTS LEFT:", slots_left)
    print("MARGIN MODE: ISOLATED ONLY | CLOSED POSITION FREES SLOT NEXT SCAN")
    print("DEEP MTF REQUIRED:", ",".join(sorted(REQUIRED_DEEP_TIMEFRAMES)))
    for s,d in decisions.items():
        print(s, "|", d["regime"], "|", d["strategy"], "|", d["action"], "| APPROVED", d["approved"], "|", d["reason"])
    print("PER-TRADE STRUCTURAL/VOLATILITY STOP REMAINS MANDATORY")
    print("NO REAL BINANCE ORDER AUTHORITY")


if __name__ == "__main__":
    main()
