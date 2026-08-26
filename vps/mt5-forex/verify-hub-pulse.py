#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone


def fail(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def as_positive_number(value, name: str, code: int) -> float:
    try:
        parsed = float(value or 0)
    except Exception as exc:
        fail(f"invalid {name}: {exc}", code)
    if parsed <= 0:
        fail(f"MT5 {name} is not positive", code)
    return parsed


def main():
    if len(sys.argv) != 2:
        fail("usage: verify-hub-pulse.py <forex-health.json>", 2)

    expected_login = (os.environ.get("MT5_ACCOUNT_LOGIN") or "").strip()
    expected_server = (os.environ.get("MT5_ACCOUNT_SERVER") or "").strip()
    if not expected_login:
        fail("MT5_ACCOUNT_LOGIN missing", 3)

    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        fail(f"invalid forex health JSON: {type(exc).__name__}: {exc}", 4)

    last = data.get("lastTerminal") or {}
    if not isinstance(last, dict) or not last:
        fail("lastTerminal missing", 5)

    received = last.get("receivedAt")
    if not received:
        fail("lastTerminal.receivedAt missing", 6)
    try:
        ts = datetime.fromisoformat(str(received).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
    except Exception as exc:
        fail(f"invalid receivedAt: {exc}", 7)

    max_age = float(os.environ.get("MT5_HUB_PULSE_MAX_AGE_SECONDS") or "300")
    if age < -30 or age > max_age:
        fail(f"pulse stale age_seconds={age:.1f}", 8)
    if last.get("connected") is not True:
        fail("MT5 connected=false", 9)

    as_positive_number(last.get("balance"), "balance", 10)
    as_positive_number(last.get("equity"), "equity", 11)

    terminal_id = str(last.get("terminalId") or "")
    expected_prefix = expected_login + "-"
    if not terminal_id.startswith(expected_prefix):
        fail("terminalId does not match configured account", 12)
    if expected_server and terminal_id != f"{expected_login}-{expected_server}":
        fail("terminalId does not match configured server", 13)

    print(f"MT5_PULSE_AGE_SECONDS={age:.1f}")
    print(f"MT5_HUB_TERMINAL_ID={terminal_id}")
    print("MT5_HUB_CONNECTED=PASS")
    print("MT5_HUB_BALANCE_EQUITY=PASS")
    print("MT5_PULSE_VERIFY=PASS")


if __name__ == "__main__":
    main()
