import json
import tempfile
from copy import deepcopy

def pnl(side, entry, exit_price, qty):
    if side == "LONG":
        return (exit_price - entry) * qty
    return (entry - exit_price) * qty


position = {
    "symbol": "TESTUSDT",
    "side": "LONG",
    "entry": 100.0,
    "stop_loss": 98.0,
    "initial_stop": 98.0,
    "tp1": 103.0,
    "tp2": 105.0,
    "tp3": 108.0,
    "quantity": 10.0,
    "remaining_qty": 10.0,
    "tp1_done": False,
    "tp2_done": False,
    "break_even": False,
    "trailing_active": False,
    "trail_price": None,
    "realized_pnl": 0.0,
    "status": "OPEN",
}

events = []

def close_partial(pos, price, fraction, name):
    qty = min(pos["quantity"] * fraction, pos["remaining_qty"])
    gain = pnl(pos["side"], pos["entry"], price, qty)
    pos["remaining_qty"] -= qty
    pos["realized_pnl"] += gain
    events.append((name, price, qty, gain))


def close_all(pos, price, reason):
    qty = pos["remaining_qty"]
    gain = pnl(pos["side"], pos["entry"], price, qty)
    pos["remaining_qty"] = 0
    pos["realized_pnl"] += gain
    pos["status"] = "CLOSED"
    events.append((reason, price, qty, gain))


def update(pos, price):
    if pos["status"] != "OPEN":
        return

    if price <= pos["stop_loss"]:
        close_all(pos, price, "STOP")
        return

    if not pos["tp1_done"] and price >= pos["tp1"]:
        close_partial(pos, price, 0.30, "TP1")
        pos["tp1_done"] = True
        pos["break_even"] = True
        pos["stop_loss"] = pos["entry"]

    if not pos["tp2_done"] and price >= pos["tp2"]:
        close_partial(pos, price, 0.30, "TP2")
        pos["tp2_done"] = True
        pos["trailing_active"] = True
        pos["trail_price"] = pos["tp1"]

    if pos["trailing_active"]:
        distance = pos["entry"] - pos["initial_stop"]
        candidate = price - distance
        if pos["trail_price"] is None or candidate > pos["trail_price"]:
            pos["trail_price"] = candidate
            pos["stop_loss"] = max(pos["stop_loss"], candidate)

    if price >= pos["tp3"]:
        close_all(pos, price, "TP3")


path = [
    100.0,
    103.1,
    105.2,
    106.0,
    107.0,
    108.1,
]

print("=== PAPER POSITION CYCLE VALIDATION ===")

for price in path:
    update(position, price)
    print(
        "PRICE", price,
        "| STATUS", position["status"],
        "| SL", round(position["stop_loss"], 4),
        "| REM", round(position["remaining_qty"], 4),
        "| PNL", round(position["realized_pnl"], 4),
    )

print()
print("EVENTS:")
for e in events:
    print(e)

checks = {
    "TP1_DONE": position["tp1_done"],
    "BREAK_EVEN": position["break_even"],
    "TP2_DONE": position["tp2_done"],
    "TRAIL_ACTIVE": position["trailing_active"],
    "CLOSED": position["status"] == "CLOSED",
    "REMAINING_ZERO": abs(position["remaining_qty"]) < 1e-9,
    "PNL_POSITIVE": position["realized_pnl"] > 0,
}

print()
for name, ok in checks.items():
    print(name, "PASS" if ok else "FAIL")

passed = all(checks.values())

print()
print("VALIDATION:", "PASS" if passed else "FAIL")

raise SystemExit(0 if passed else 1)
