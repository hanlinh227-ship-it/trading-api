import json
import os
import time
import hmac
import hashlib
import urllib.parse
import urllib.request
import urllib.error

from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"
LOGS = ROOT / "logs"

RISK_FILE = STATE / "risk_decisions.json"

BASE = "https://fapi.binance.com"

ENV_FILE = "/opt/trading/.env.binance"


def now():
    return datetime.now(timezone.utc).isoformat()


def load_env():
    data = {}

    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            data[key.strip()] = (
                value.strip()
                .strip('"')
                .strip("'")
            )

    return data


ENV = load_env()

API_KEY = ENV.get("BINANCE_API_KEY", "")
API_SECRET = ENV.get("BINANCE_API_SECRET", "")

LIVE_TRADING = (
    ENV.get(
        "BINANCE_LIVE_TRADING",
        "false"
    ).lower()
    == "true"
)


# ============================================================
# SAFETY
# ============================================================

if LIVE_TRADING:
    raise SystemExit(
        "SAFETY BLOCK: BINANCE_LIVE_TRADING=true. "
        "This executor is DRY-RUN only."
    )


# ============================================================
# HTTP
# ============================================================

def public_get(path):
    req = urllib.request.Request(
        BASE + path,
        headers={
            "User-Agent": "AUTO-FUTURES-V1"
        }
    )

    with urllib.request.urlopen(
        req,
        timeout=15
    ) as response:
        return json.loads(
            response.read().decode()
        )


def signed_get(path, params=None):
    params = dict(params or {})

    server = public_get(
        "/fapi/v1/time"
    )

    params["timestamp"] = int(
        server["serverTime"]
    )

    params["recvWindow"] = 10000

    query = urllib.parse.urlencode(
        params
    )

    signature = hmac.new(
        API_SECRET.encode(),
        query.encode(),
        hashlib.sha256
    ).hexdigest()

    url = (
        BASE
        + path
        + "?"
        + query
        + "&signature="
        + signature
    )

    req = urllib.request.Request(
        url,
        headers={
            "X-MBX-APIKEY": API_KEY
        }
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=15
        ) as response:
            return json.loads(
                response.read().decode()
            )

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            errors="replace"
        )

        raise RuntimeError(
            f"BINANCE HTTP {exc.code}: {body}"
        )


# ============================================================
# BINANCE FILTERS
# ============================================================

def get_symbol_info(symbol):
    data = public_get(
        "/fapi/v1/exchangeInfo"
    )

    for item in data["symbols"]:
        if item["symbol"] == symbol:
            return item

    raise ValueError(
        f"Symbol not found: {symbol}"
    )


def get_filter(symbol_info, name):
    for f in symbol_info["filters"]:
        if f["filterType"] == name:
            return f

    return None


def floor_step(value, step):
    value = Decimal(str(value))
    step = Decimal(str(step))

    if step == 0:
        return float(value)

    return float(
        (
            value / step
        ).to_integral_value(
            rounding=ROUND_DOWN
        )
        * step
    )


# ============================================================
# ACCOUNT
# ============================================================

def get_account():
    return signed_get(
        "/fapi/v2/account"
    )


def get_available_balance(account):
    try:
        return float(
            account[
                "availableBalance"
            ]
        )
    except Exception:
        return 0.0


# ============================================================
# POSITION SIZE
# ============================================================

def calculate_quantity(
    symbol,
    entry,
    stop,
    risk_pct,
    max_leverage,
    available_balance
):
    if entry <= 0:
        return None, "INVALID_ENTRY"

    stop_distance = abs(
        entry - stop
    )

    if stop_distance <= 0:
        return None, "INVALID_STOP_DISTANCE"

    risk_usd = (
        available_balance
        * risk_pct
        / 100.0
    )

    raw_qty = (
        risk_usd
        / stop_distance
    )

    max_notional = (
        available_balance
        * max_leverage
    )

    max_qty = (
        max_notional
        / entry
    )

    raw_qty = min(
        raw_qty,
        max_qty
    )

    info = get_symbol_info(
        symbol
    )

    lot = get_filter(
        info,
        "LOT_SIZE"
    )

    market_lot = get_filter(
        info,
        "MARKET_LOT_SIZE"
    )

    qty_filter = (
        market_lot
        if market_lot
        else lot
    )

    step = float(
        qty_filter[
            "stepSize"
        ]
    )

    min_qty = float(
        qty_filter[
            "minQty"
        ]
    )

    qty = floor_step(
        raw_qty,
        step
    )

    if qty < min_qty:
        return None, (
            f"QTY_BELOW_MIN "
            f"{qty} < {min_qty}"
        )

    return qty, None


# ============================================================
# BUILD DRY-RUN ORDER
# ============================================================

def build_order(
    symbol,
    decision,
    available_balance
):
    action = decision[
        "action"
    ]

    entry = float(
        decision["entry"]
    )

    stop = float(
        decision["stop_loss"]
    )

    risk_pct = float(
        decision.get(
            "risk_pct",
            0.5
        )
    )

    leverage = int(
        decision.get(
            "max_leverage",
            3
        )
    )

    qty, error = calculate_quantity(
        symbol,
        entry,
        stop,
        risk_pct,
        leverage,
        available_balance
    )

    if error:
        return {
            "symbol": symbol,
            "status": "BLOCKED",
            "reason": error,
        }

    side = (
        "BUY"
        if action == "LONG"
        else "SELL"
    )

    close_side = (
        "SELL"
        if action == "LONG"
        else "BUY"
    )

    return {
        "timestamp": now(),

        "mode": "DRY_RUN",

        "symbol": symbol,

        "signal":
            action,

        "entry_order": {
            "side":
                side,

            "type":
                "MARKET",

            "quantity":
                qty,
        },

        "protective_stop": {
            "side":
                close_side,

            "type":
                "STOP_MARKET",

            "stopPrice":
                stop,

            "reduceOnly":
                True,
        },

        "tp1":
            decision.get(
                "tp1"
            ),

        "tp2":
            decision.get(
                "tp2"
            ),

        "tp3":
            decision.get(
                "tp3"
            ),

        "risk_pct":
            risk_pct,

        "max_leverage":
            leverage,

        "status":
            "READY_DRY_RUN",
    }


# ============================================================
# MAIN
# ============================================================

def main():

    if not API_KEY:
        raise SystemExit(
            "BINANCE_API_KEY missing"
        )

    if not API_SECRET:
        raise SystemExit(
            "BINANCE_API_SECRET missing"
        )

    if not RISK_FILE.exists():
        raise SystemExit(
            "risk_decisions.json missing"
        )

    risk = json.loads(
        RISK_FILE.read_text(
            encoding="utf-8"
        )
    )

    account = get_account()

    available_balance = (
        get_available_balance(
            account
        )
    )

    plans = []

    for symbol, decision \
            in risk.get(
                "decisions",
                {}
            ).items():

        if not decision.get(
            "approved"
        ):
            continue

        if decision.get(
            "action"
        ) not in (
            "LONG",
            "SHORT"
        ):
            continue

        plan = build_order(
            symbol,
            decision,
            available_balance
        )

        plans.append(
            plan
        )

    output = {
        "generated_at":
            now(),

        "mode":
            "DRY_RUN",

        "live_trading":
            False,

        "available_balance":
            available_balance,

        "plans":
            plans,
    }

    path = (
        STATE
        / "live_executor_dry_run.json"
    )

    path.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    with (
        LOGS
        / "live_executor_dry_run.jsonl"
    ).open(
        "a",
        encoding="utf-8"
    ) as log:

        log.write(
            json.dumps(
                output,
                ensure_ascii=False
            )
            + "\n"
        )

    print()
    print(
        "========================================"
    )

    print(
        "BINANCE FUTURES EXECUTOR — DRY RUN"
    )

    print(
        "========================================"
    )

    print(
        "AUTHENTICATION     : PASS"
    )

    print(
        "LIVE TRADING       :",
        LIVE_TRADING
    )

    print(
        "AVAILABLE BALANCE  :",
        available_balance
    )

    print(
        "APPROVED PLANS     :",
        len(plans)
    )

    for plan in plans:

        print()

        print(
            plan[
                "symbol"
            ],
            plan[
                "signal"
            ],
            "|",
            plan[
                "status"
            ]
        )

        if plan[
            "status"
        ] == "READY_DRY_RUN":

            print(
                "QTY      :",
                plan[
                    "entry_order"
                ][
                    "quantity"
                ]
            )

            print(
                "SL       :",
                plan[
                    "protective_stop"
                ][
                    "stopPrice"
                ]
            )

            print(
                "TP1      :",
                plan[
                    "tp1"
                ]
            )

            print(
                "TP2      :",
                plan[
                    "tp2"
                ]
            )

            print(
                "TP3      :",
                plan[
                    "tp3"
                ]
            )

        else:

            print(
                "BLOCKED  :",
                plan.get(
                    "reason"
                )
            )

    print()
    print(
        "NO BINANCE ORDER WAS SENT"
    )

    print(
        "DRY RUN COMPLETE"
    )


if __name__ == "__main__":
    main()
