#!/usr/bin/env python3
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone


def fail(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main():
    if len(sys.argv) != 2:
        fail("usage: verify-local-pulse.py <pulse.json>", 2)

    expected = (os.environ.get("MT5_ACCOUNT_LOGIN") or "").strip()
    if not expected:
        fail("MT5_ACCOUNT_LOGIN missing", 3)

    path = pathlib.Path(sys.argv[1])
    if not path.is_file():
        fail("local pulse missing", 4)

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as exc:
        fail(f"invalid local pulse JSON: {type(exc).__name__}: {exc}", 5)

    terminal_id = str(data.get("terminalId") or "")
    if not terminal_id.startswith(expected + "-"):
        fail("local pulse terminalId does not match configured account", 6)

    if data.get("connected") is not True:
        fail("local pulse connected=false", 7)

    try:
        balance = float(data.get("balance") or 0)
        equity = float(data.get("equity") or 0)
    except Exception as exc:
        fail(f"invalid balance/equity: {exc}", 8)

    if balance <= 0:
        fail("local pulse balance is not positive", 9)
    if equity <= 0:
        fail("local pulse equity is not positive", 10)

    max_age = float(os.environ.get("MT5_LOCAL_PULSE_MAX_AGE_SECONDS") or "180")
    age = time.time() - path.stat().st_mtime
    if age < -30 or age > max_age:
        fail(f"local pulse stale age_seconds={age:.1f}", 11)

    print(f"MT5_LOCAL_PULSE_AGE_SECONDS={age:.1f}")
    print(f"MT5_LOCAL_TERMINAL_ID={terminal_id}")
    print("MT5_LOCAL_CONNECTED=PASS")
    print("MT5_LOCAL_BALANCE_EQUITY=PASS")
    print("MT5_LOCAL_PULSE_VERIFY=PASS")


if __name__ == "__main__":
    main()
