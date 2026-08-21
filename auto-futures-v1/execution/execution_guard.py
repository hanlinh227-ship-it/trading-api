import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"
SNAPSHOT_FILE = STATE / "market_snapshot.json"
CONSENSUS_FILE = STATE / "ai_consensus.json"
RISK_FILE = STATE / "risk_decisions.json"
EXEC_STATE_FILE = STATE / "execution_state.json"
OUTPUT_FILE = STATE / "execution_guard.json"
MAX_SIGNAL_AGE_SECONDS = 420


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def fingerprint(symbol, decision, consensus):
    raw = json.dumps({"symbol":symbol,"action":decision.get("action"),"strategy":decision.get("strategy"),"entry":decision.get("entry"),"stop":decision.get("stop_loss"),"consensus":consensus.get("generated_at")}, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def main():
    snapshot = load(SNAPSHOT_FILE, {})
    consensus = load(CONSENSUS_FILE, {})
    risk = load(RISK_FILE, {"decisions":{}})
    state = load(EXEC_STATE_FILE, {"processed":{},"emergency_stop":False})
    now = datetime.now(timezone.utc)
    global_blocks = []
    if state.get("emergency_stop"):
        global_blocks.append("MANUAL_EMERGENCY_STOP")
    for label, value in (("SNAPSHOT", snapshot.get("generated_at")), ("CONSENSUS", consensus.get("generated_at")), ("RISK", risk.get("generated_at"))):
        t = parse_time(value)
        if t is None:
            global_blocks.append(f"{label}_TIME_INVALID")
        else:
            age = (now - t).total_seconds()
            if age > MAX_SIGNAL_AGE_SECONDS:
                global_blocks.append(f"{label}_STALE_{int(age)}S")

    decisions = {}
    for symbol, d in risk.get("decisions", {}).items():
        reasons = list(global_blocks)
        if not d.get("approved"):
            reasons.append("RISK_ENGINE_NOT_APPROVED")
        if d.get("action") not in {"LONG","SHORT"}:
            reasons.append("NOT_ENTRY_ACTION")
        if d.get("entry") is None or d.get("stop_loss") is None:
            reasons.append("MISSING_ENTRY_OR_STOP")
        fp = fingerprint(symbol, d, consensus)
        if state.get("processed", {}).get(symbol) == fp:
            reasons.append("DUPLICATE_DECISION")
        decisions[symbol] = {"executable":not reasons,"fingerprint":fp,"blocks":reasons,"action":d.get("action"),"strategy":d.get("strategy"),"entry":d.get("entry"),"stop_loss":d.get("stop_loss"),"tp1":d.get("tp1"),"tp2":d.get("tp2"),"tp3":d.get("tp3")}

    out = {"generated_at":now.isoformat(),"mode":"DRY_RUN","policy":{"daily_loss_kill":False,"daily_trade_limit":None,"manual_emergency_stop":True,"freshness_guard":True,"duplicate_guard":True},"global_blocks":global_blocks,"decisions":decisions}
    OUTPUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("="*48); print("V4 SCALP EXECUTION GUARD"); print("="*48)
    print("EMERGENCY STOP:", state.get("emergency_stop",False), "| DAILY LOSS KILL: DISABLED")
    for s,d in decisions.items():
        print(s, "| EXECUTABLE", d["executable"], "|", ",".join(d["blocks"]) if d["blocks"] else "PASS")
    print("NO BINANCE ORDER AUTHORITY")


if __name__ == "__main__":
    main()
