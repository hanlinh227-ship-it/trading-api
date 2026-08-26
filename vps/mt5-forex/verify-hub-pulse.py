#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone


def fail(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main():
    if len(sys.argv) != 2:
        fail("usage: verify-hub-pulse.py <forex-health.json>", 2)
    expected = (os.environ.get("MT5_ACCOUNT_LOGIN") or "").strip()
    if not expected:
        fail("MT5_ACCOUNT_LOGIN missing", 3)
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        fail(f"invalid forex health JSON: {type(exc).__name__}: {exc}", 4)

    last = data.get("lastTerminal") or {}
    if not last:
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

    if age < -30 or age > 180:
        fail(f"pulse stale age_seconds={age:.1f}", 8)
    if last.get("connected") is not True:
        fail("MT5 connected=false", 9)
    if float(last.get("balance") or 0) <= 0:
        fail("MT5 balance is not positive", 10)
    if float(last.get("equity") or 0) <= 0:
        fail("MT5 equity is not positive", 11)

    terminal_id = str(last.get("terminalId") or "")
    if not terminal_id.startswith(expected + "-"):
        fail("terminalId does not match configured account", 12)

    print(f"MT5_PULSE_AGE_SECONDS={age:.1f}")
    print("MT5_PULSE_VERIFY=PASS")


if __name__ == "__main__":
    main()
