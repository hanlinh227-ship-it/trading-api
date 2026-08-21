import json
import sys
from pathlib import Path
from datetime import datetime, timezone

STATE = Path(
    "/opt/trading/trading-api/auto-futures-v1/state"
)

FILE = STATE / "execution_state.json"

state = {
    "processed": {},
    "emergency_stop": False,
}

if FILE.exists():
    try:
        state.update(
            json.loads(
                FILE.read_text()
            )
        )
    except Exception:
        pass

command = (
    sys.argv[1].lower()
    if len(sys.argv) > 1
    else "status"
)

if command == "on":
    state["emergency_stop"] = True

elif command == "off":
    state["emergency_stop"] = False

elif command != "status":
    raise SystemExit(
        "Usage: emergency_stop.py on|off|status"
    )

state["updated_at"] = (
    datetime.now(
        timezone.utc
    ).isoformat()
)

FILE.write_text(
    json.dumps(
        state,
        indent=2
    )
)

print(
    "EMERGENCY STOP:",
    state["emergency_stop"]
)
