import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"
LOGS = ROOT / "logs"

risk = json.loads(
    (STATE / "risk_decisions.json").read_text()
)

orders = []

for symbol, d in risk["decisions"].items():
    if not d["approved"]:
        continue

    orders.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "side": d["action"],
        "entry": d["entry"],
        "stop_loss": d["stop_loss"],
        "tp1": d["tp1"],
        "tp2": d["tp2"],
        "tp3": d["tp3"],
        "risk_pct": d["risk_pct"],
        "max_leverage": d["max_leverage"],
        "status": "PAPER_OPEN"
    })

out = {
    "mode":"PAPER",
    "orders":orders
}

(STATE / "paper_orders.json").write_text(
    json.dumps(out, indent=2),
    encoding="utf-8"
)

with (LOGS / "paper_orders.jsonl").open("a") as f:
    for x in orders:
        f.write(json.dumps(x) + "\n")

print(json.dumps(out, indent=2))
print("NO BINANCE ORDER WAS SENT")
