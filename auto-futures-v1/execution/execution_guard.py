import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"

SNAPSHOT_FILE = STATE / "market_snapshot.json"
CONSENSUS_FILE = STATE / "ai_consensus.json"
RISK_FILE = STATE / "risk_decisions.json"
DAILY_FILE = STATE / "daily_risk.json"
EXEC_STATE_FILE = STATE / "execution_state.json"

MAX_SIGNAL_AGE_SECONDS = 600


def utc_now():
    return datetime.now(timezone.utc)


def load(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def parse_time(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except Exception:
        return None


def fingerprint(symbol, decision, consensus):
    payload = {
        "symbol": symbol,
        "action": decision.get("action"),
        "entry": decision.get("entry"),
        "stop_loss": decision.get("stop_loss"),
        "tp1": decision.get("tp1"),
        "tp2": decision.get("tp2"),
        "tp3": decision.get("tp3"),
        "consensus_generated_at": consensus.get("generated_at"),
    }

    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    return hashlib.sha256(raw).hexdigest()


def main():
    snapshot = load(SNAPSHOT_FILE, {})
    consensus = load(CONSENSUS_FILE, {})
    risk = load(RISK_FILE, {"decisions": {}})
    daily = load(DAILY_FILE, {})
    exec_state = load(
        EXEC_STATE_FILE,
        {
            "processed": {},
            "emergency_stop": False,
        }
    )

    global_blocks = []

    if exec_state.get("emergency_stop"):
        global_blocks.append("MANUAL_EMERGENCY_STOP")

    if daily.get("kill_switch"):
        global_blocks.append("DAILY_LOSS_KILL_SWITCH")

    snapshot_time = parse_time(
        snapshot.get("generated_at")
    )

    consensus_time = parse_time(
        consensus.get("generated_at")
    )

    now = utc_now()

    if snapshot_time is None:
        global_blocks.append("SNAPSHOT_TIME_INVALID")
    else:
        age = (
            now - snapshot_time
        ).total_seconds()

        if age > MAX_SIGNAL_AGE_SECONDS:
            global_blocks.append(
                f"SNAPSHOT_STALE_{int(age)}S"
            )

    if consensus_time is None:
        global_blocks.append("CONSENSUS_TIME_INVALID")
    else:
        age = (
            now - consensus_time
        ).total_seconds()

        if age > MAX_SIGNAL_AGE_SECONDS:
            global_blocks.append(
                f"CONSENSUS_STALE_{int(age)}S"
            )

    decisions = {}

    for symbol, decision in risk.get(
        "decisions", {}
    ).items():

        approved = bool(
            decision.get("approved")
        )

        fp = fingerprint(
            symbol,
            decision,
            consensus,
        )

        reasons = list(global_blocks)

        if not approved:
            reasons.append(
                "RISK_ENGINE_NOT_APPROVED"
            )

        if decision.get("action") not in (
            "LONG",
            "SHORT",
        ):
            reasons.append(
                "NOT_ENTRY_ACTION"
            )

        previous = exec_state.get(
            "processed",
            {}
        ).get(symbol)

        if previous == fp:
            reasons.append(
                "DUPLICATE_DECISION"
            )

        executable = (
            len(reasons) == 0
        )

        decisions[symbol] = {
            "executable": executable,
            "fingerprint": fp,
            "blocks": reasons,
            "action": decision.get("action"),
            "entry": decision.get("entry"),
            "stop_loss": decision.get("stop_loss"),
            "tp1": decision.get("tp1"),
            "tp2": decision.get("tp2"),
            "tp3": decision.get("tp3"),
        }

    output = {
        "generated_at": now.isoformat(),
        "mode": "DRY_RUN",
        "global_blocks": global_blocks,
        "decisions": decisions,
    }

    (
        STATE / "execution_guard.json"
    ).write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 50)
    print("EXECUTION SAFETY GUARD")
    print("=" * 50)

    print(
        "EMERGENCY STOP :",
        exec_state.get(
            "emergency_stop",
            False
        )
    )

    print(
        "DAILY KILL      :",
        daily.get(
            "kill_switch",
            False
        )
    )

    print(
        "GLOBAL BLOCKS   :",
        global_blocks or "NONE"
    )

    print()

    for symbol, item in decisions.items():
        print(
            symbol,
            "| EXECUTABLE:",
            item["executable"],
            "|",
            ",".join(item["blocks"])
            if item["blocks"]
            else "PASS"
        )

    print()
    print("DRY RUN ONLY")
    print("NO BINANCE ORDER AUTHORITY")


if __name__ == "__main__":
    main()
