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

ENV_FILE = Path("/opt/trading/.env.binance")

RISK_FILE = STATE / "risk_decisions.json"
GUARD_FILE = STATE / "execution_guard.json"

BASE = "https://fapi.binance.com"


def now():
    return datetime.now(timezone.utc).isoformat()


def load_env():
    data = {}

    for line in ENV_FILE.read_text(
        encoding="utf-8"
    ).splitlines():

        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        k, v = line.split("=", 1)

        data[k.strip()] = (
            v.strip()
            .strip('"')
            .strip("'")
        )

    return data


ENV = load_env()

API_KEY = ENV.get(
    "BINANCE_API_KEY",
    ""
)

API_SECRET = ENV.get(
    "BINANCE_API_SECRET",
    ""
)

LIVE_TRADING = (
    ENV.get(
        "BINANCE_LIVE_TRADING",
        "false"
    ).lower()
    == "true"
)

LIVE_ARMED = (
    ENV.get(
        "BINANCE_LIVE_ARMED",
        "false"
    ).lower()
    == "true"
)


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
    ) as r:

        return json.loads(
            r.read().decode()
        )


def signed_request(
    method,
    path,
    params
):
    server = public_get(
        "/fapi/v1/time"
    )

    params = dict(params)

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

    query = (
        query
        + "&signature="
        + signature
    )

    url = BASE + path

    if method == "GET":
        url += "?" + query
        data = None

    else:
        data = query.encode()

    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-MBX-APIKEY":
                API_KEY,

            "Content-Type":
                "application/x-www-form-urlencoded",
        }
    )

    try:

        with urllib.request.urlopen(
            req,
            timeout=20
        ) as r:

            return json.loads(
                r.read().decode()
            )

    except urllib.error.HTTPError as e:

        body = e.read().decode(
            errors="replace"
        )

        raise RuntimeError(
            f"BINANCE_HTTP_{e.code}: {body}"
        )


def get_account():
    return signed_request(
        "GET",
        "/fapi/v2/account",
        {}
    )


def get_exchange_info():
    return public_get(
        "/fapi/v1/exchangeInfo"
    )


def symbol_info(
    exchange_info,
    symbol
):
    for item in exchange_info[
        "symbols"
    ]:

        if item["symbol"] == symbol:
            return item

    return None


def get_filter(
    info,
    filter_type
):
    for f in info.get(
        "filters",
        []
    ):

        if f.get(
            "filterType"
        ) == filter_type:

            return f

    return None


def floor_step(
    value,
    step
):
    value = Decimal(str(value))
    step = Decimal(str(step))

    if step == 0:
        return float(value)

    units = (
        value / step
    ).to_integral_value(
        rounding=ROUND_DOWN
    )

    return float(
        units * step
    )


def build_plan(
    symbol,
    decision,
    account,
    exchange_info
):
    info = symbol_info(
        exchange_info,
        symbol
    )

    if not info:

        return {
            "symbol": symbol,
            "status": "BLOCKED",
            "reason": "SYMBOL_NOT_FOUND",
        }

    entry = float(
        decision["entry"]
    )

    stop = float(
        decision["stop_loss"]
    )

    action = decision[
        "action"
    ]

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

    available = float(
        account.get(
            "availableBalance",
            0
        )
    )

    if available <= 0:

        return {
            "symbol": symbol,
            "status": "BLOCKED",
            "reason": "NO_AVAILABLE_BALANCE",
        }

    stop_distance = abs(
        entry - stop
    )

    if stop_distance <= 0:

        return {
            "symbol": symbol,
            "status": "BLOCKED",
            "reason": "INVALID_STOP_DISTANCE",
        }

    risk_usd = (
        available
        * risk_pct
        / 100
    )

    qty_by_risk = (
        risk_usd
        / stop_distance
    )

    max_notional = (
        available
        * leverage
    )

    qty_by_leverage = (
        max_notional
        / entry
    )

    qty = min(
        qty_by_risk,
        qty_by_leverage
    )

    lot = (
        get_filter(
            info,
            "MARKET_LOT_SIZE"
        )
        or
        get_filter(
            info,
            "LOT_SIZE"
        )
    )

    step_size = float(
        lot["stepSize"]
    )

    min_qty = float(
        lot["minQty"]
    )

    qty = floor_step(
        qty,
        step_size
    )

    if qty < min_qty:

        return {
            "symbol": symbol,
            "status": "BLOCKED",
            "reason":
                f"QTY_BELOW_MIN_{qty}",
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
        "symbol":
            symbol,

        "status":
            "READY",

        "action":
            action,

        "side":
            side,

        "close_side":
            close_side,

        "quantity":
            qty,

        "leverage":
            leverage,

        "entry_reference":
            entry,

        "stop_loss":
            stop,

        "tp1":
            decision.get("tp1"),

        "tp2":
            decision.get("tp2"),

        "tp3":
            decision.get("tp3"),

        "risk_pct":
            risk_pct,

        "available_balance":
            available,
    }


def send_entry(plan):
    leverage_result = signed_request(
        "POST",
        "/fapi/v1/leverage",
        {
            "symbol":
                plan["symbol"],

            "leverage":
                plan["leverage"],
        }
    )

    order = signed_request(
        "POST",
        "/fapi/v1/order",
        {
            "symbol":
                plan["symbol"],

            "side":
                plan["side"],

            "type":
                "MARKET",

            "quantity":
                plan["quantity"],

            "newOrderRespType":
                "RESULT",
        }
    )

    return {
        "leverage":
            leverage_result,

        "entry_order":
            order,
    }


def main():
    risk = json.loads(
        RISK_FILE.read_text(
            encoding="utf-8"
        )
    )

    guard = json.loads(
        GUARD_FILE.read_text(
            encoding="utf-8"
        )
    )

    account = get_account()
    exchange_info = get_exchange_info()

    plans = []

    for symbol, decision in risk.get(
        "decisions",
        {}
    ).items():

        guard_decision = (
            guard.get(
                "decisions",
                {}
            ).get(
                symbol,
                {}
            )
        )

        if not decision.get(
            "approved"
        ):
            continue

        if not guard_decision.get(
            "executable"
        ):
            continue

        if decision.get(
            "action"
        ) not in (
            "LONG",
            "SHORT"
        ):
            continue

        plan = build_plan(
            symbol,
            decision,
            account,
            exchange_info
        )

        plans.append(
            plan
        )

    output = {
        "generated_at":
            now(),

        "live_trading":
            LIVE_TRADING,

        "live_armed":
            LIVE_ARMED,

        "plans":
            plans,

        "executed":
            [],
    }

    #
    # DOUBLE ARMING:
    #
    # BOTH flags must be true.
    #
    # This prevents accidental live activation.
    #

    if (
        LIVE_TRADING
        and LIVE_ARMED
    ):

        for plan in plans:

            if plan[
                "status"
            ] != "READY":
                continue

            result = send_entry(
                plan
            )

            output[
                "executed"
            ].append({
                "symbol":
                    plan[
                        "symbol"
                    ],

                "result":
                    result,
            })

    path = (
        STATE
        / "live_executor_state.json"
    )

    path.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 55)
    print("BINANCE FUTURES LIVE EXECUTOR")
    print("=" * 55)

    print(
        "API AUTH       : PASS"
    )

    print(
        "LIVE TRADING   :",
        LIVE_TRADING
    )

    print(
        "LIVE ARMED     :",
        LIVE_ARMED
    )

    print(
        "PLANS          :",
        len(plans)
    )

    print(
        "EXECUTED       :",
        len(
            output[
                "executed"
            ]
        )
    )

    for plan in plans:

        print()

        print(
            plan[
                "symbol"
            ],
            "|",
            plan[
                "status"
            ]
        )

        if plan[
            "status"
        ] == "READY":

            print(
                "SIDE     :",
                plan[
                    "side"
                ]
            )

            print(
                "QTY      :",
                plan[
                    "quantity"
                ]
            )

            print(
                "LEV      :",
                plan[
                    "leverage"
                ]
            )

            print(
                "SL       :",
                plan[
                    "stop_loss"
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

    if not (
        LIVE_TRADING
        and LIVE_ARMED
    ):

        print()
        print(
            "LIVE EXECUTION LOCKED"
        )

        print(
            "NO REAL ORDER WAS SENT"
        )


if __name__ == "__main__":
    main()
