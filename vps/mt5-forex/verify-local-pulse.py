#!/usr/bin/env python3
import json
import os
import pathlib
import sys
import time


def fail(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main():
    if len(sys.argv) != 2:
        fail("usage: verify-local-pulse.py <pulse.json>", 2)

    expected_login = (os.environ.get("MT5_ACCOUNT_LOGIN") or "").strip()
    expected_server = (os.environ.get("MT5_ACCOUNT_SERVER") or "").strip()
    if not expected_login:
        fail("MT5_ACCOUNT_LOGIN missing", 3)

    path = pathlib.Path(sys.argv[1])
    if not path.is_file():
        fail("local pulse missing", 4)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid local pulse JSON: {type(exc).__name__}: {exc}", 5)

    terminal_id = str(data.get("terminalId") or "")
    expected_id = f"{expected_login}-{expected_server}" if expected_server else ""
    if not terminal_id.startswith(expected_login + "-"):
        fail("local pulse terminalId does not match configured account", 6)
    if expected_id and terminal_id != expected_id:
        fail("local pulse terminalId does not match configured server", 12)

    # EA 0.402 canonical schema nests terminal/account metrics.
    mt5 = data.get("mt5") or {}
    account = data.get("account") or {}
    if not isinstance(mt5, dict):
        fail("local pulse mt5 object missing", 13)
    if not isinstance(account, dict):
        fail("local pulse account object missing", 14)

    connected = mt5.get("connected")
    trade_allowed = mt5.get("tradeAllowed")
    if connected is not True:
        fail(f"local pulse connected={connected!r}", 7)

    try:
        balance = float(account.get("balance") or 0)
        equity = float(account.get("equity") or 0)
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
    print(f"MT5_LOCAL_TRADE_ALLOWED={str(trade_allowed).lower()}")
    print("MT5_LOCAL_CONNECTED=PASS")
    print("MT5_LOCAL_BALANCE_EQUITY=PASS")
    print("MT5_LOCAL_PULSE_VERIFY=PASS")


if __name__ == "__main__":
    main()
